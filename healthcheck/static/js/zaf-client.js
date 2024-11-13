const ZAFClientSingleton = {
    client: null,
    metadata: null,
    context: null,
    userInfo: null,

    async init(retryCount = 3, delay = 100) {
        if (this.client) return this.client;

        try {
            await this.initializeClient(retryCount, delay);
            await this.loadData();
            await this.trackAnalytics(); // New separate method for analytics
            return this.client;
        } catch (error) {
            console.error('Failed to initialize:', error);
            throw error;
        }
    },

    async initializeClient(retryCount, delay) {
        const urlParams = new URLSearchParams(window.location.search);
        const origin = urlParams.get('origin');
        const appGuid = urlParams.get('app_guid');

        for (let i = 0; i < retryCount; i++) {
            try {
                await new Promise(resolve => setTimeout(resolve, delay));
                this.client = window.ZAFClient ?
                    (origin && appGuid ?
                        window.ZAFClient.init({ origin, appGuid }) :
                        window.ZAFClient.init())
                    : null;

                if (!this.client) throw new Error('ZAF Client could not be initialized');
                return;
            } catch (error) {
                console.warn(`ZAF initialization attempt ${i + 1} failed:`, error);
                if (i === retryCount - 1) throw error;
            }
        }
    },

    async loadData() {
        // Load all necessary data
        [this.context, this.metadata] = await Promise.all([
            this.client.context(),
            this.client.metadata(),
        ]);

        // Get user data separately to ensure it's fully loaded
        const userResponse = await this.client.get('currentUser');
        this.userInfo = userResponse.currentUser;
        
        console.log('Data loaded:', {
            context: this.context,
            metadata: this.metadata,
            userInfo: this.userInfo
        });
    },

    async trackAnalytics() {
        try {
            await new Promise(resolve => {
                if (window.analytics && window.analytics.initialized) {
                    resolve();
                } else {
                    analytics.ready(resolve);
                }
            });
    
            if (!this.userInfo || !this.metadata) {
                console.warn('Missing user info or metadata for analytics tracking');
                return;
            }
    
            const baseUrl = window.ENVIRONMENT === 'production'
                ? 'https://gcx-healthcheck-zd-production.up.railway.app'
                : 'https://gcx-healthcheck-zd-development.up.railway.app';
    
            try {
                const options = {
                    url: `${baseUrl}/api/users/create-or-update/`,
                    type: 'POST',
                    contentType: 'application/json',
                    headers: {
                        'X-Subsequent-Request': 'true'
                    },
                    data: JSON.stringify({
                        user_id: this.userInfo.id,
                        name: this.userInfo.name || '',
                        email: this.userInfo.email || '',
                        role: this.userInfo.role || '',
                        locale: this.userInfo.locale || '',
                        time_zone: this.userInfo.timeZone?.ianaName || null,
                        avatar_url: this.userInfo.avatarUrl || null,
                        subdomain: this.context?.account?.subdomain || '',
                        plan: this.metadata.plan?.name || 'Free'
                    }),
                    secure: true
                };
    
                console.log('Making request with options:', {
                    ...options
                });
    
                const response = await this.client.request(options);
                console.log('User created/updated:', response);
    
                // Track analytics with user ID
                analytics.identify(this.userInfo.id, {
                    name: this.userInfo.name,
                    email: this.userInfo.email,
                    subdomain: this.context.account.subdomain,
                    role: this.userInfo.role,
                    locale: this.userInfo.locale,
                    time_zone: this.userInfo.timeZone?.ianaName,
                    avatar: this.userInfo.avatarUrl,
                    plan: this.metadata.plan?.name || 'Free',
                });
    
                // Track group
                if (this.context?.account?.subdomain) {
                    analytics.group(this.context.account.subdomain, {
                        name: this.context.account.subdomain,
                        organization: this.context.account.subdomain,
                        plan: this.metadata.plan?.name || 'Free',
                    });
                }
    
            } catch (error) {
                console.error('Failed to create/update user:', error);
                // Don't throw the error to prevent app initialization from failing
            }
    
        } catch (error) {
            console.error('Analytics tracking error:', error);
            // Don't throw the error to prevent app initialization from failing
        }
    },

    async ensureUrlParams() {
        if (!this.metadata) return false;

        const currentUrl = new URL(window.location.href);
        const urlInstallationId = currentUrl.searchParams.get('installation_id');
        const urlPlan = currentUrl.searchParams.get('plan');
        const origin = currentUrl.searchParams.get('origin');
        const appGuid = currentUrl.searchParams.get('app_guid');
        const userId = currentUrl.searchParams.get('user_id');


        let needsRedirect = false;

        if (!urlInstallationId || !urlPlan) {
            currentUrl.searchParams.set('installation_id', this.metadata.installationId);
            currentUrl.searchParams.set('plan', this.metadata.plan?.name || 'Free');
            needsRedirect = true;
        }
            // Add user_id to URL params
        if (!userId && this.userInfo?.id) {
        currentUrl.searchParams.set('user_id', this.userInfo.id);
        needsRedirect = true;
    }

        // Preserve origin and app_guid when navigating
        if (!origin && this.context?.account?.subdomain) {
            currentUrl.searchParams.set('origin', `https://${this.context.account.subdomain}.zendesk.com`);
            needsRedirect = true;
        }

        if (!appGuid && this.metadata?.appGuid) {
            currentUrl.searchParams.set('app_guid', this.metadata.appGuid);
            needsRedirect = true;
        }

        if (needsRedirect) {
            window.location.href = currentUrl.toString();
            return false;
        }
        return true;
    },

    getUrlWithParams(baseUrl) {
        const url = new URL(baseUrl, window.location.origin);
        const currentParams = new URLSearchParams(window.location.search);

        // Preserve all necessary parameters
        ['installation_id', 'plan', 'origin', 'app_guid', 'user_id'].forEach(param => {
            const value = currentParams.get(param);
            if (value) url.searchParams.set(param, value);
        });

        return url.toString();
    }
};

!function () {
    var i = "analytics", analytics = window[i] = window[i] || []; if (!analytics.initialize) if (analytics.invoked) window.console && console.error && console.error("Segment snippet included twice."); else {
        analytics.invoked = !0; analytics.methods = ["trackSubmit", "trackClick", "trackLink", "trackForm", "pageview", "identify", "reset", "group", "track", "ready", "alias", "debug", "page", "screen", "once", "off", "on", "addSourceMiddleware", "addIntegrationMiddleware", "setAnonymousId", "addDestinationMiddleware", "register"]; analytics.factory = function (e) { return function () { if (window[i].initialized) return window[i][e].apply(window[i], arguments); var n = Array.prototype.slice.call(arguments); if (["track", "screen", "alias", "group", "page", "identify"].indexOf(e) > -1) { var c = document.querySelector("link[rel='canonical']"); n.push({ __t: "bpc", c: c && c.getAttribute("href") || void 0, p: location.pathname, u: location.href, s: location.search, t: document.title, r: document.referrer }) } n.unshift(e); analytics.push(n); return analytics } }; for (var n = 0; n < analytics.methods.length; n++) { var key = analytics.methods[n]; analytics[key] = analytics.factory(key) } analytics.load = function (key, n) { var t = document.createElement("script"); t.type = "text/javascript"; t.async = !0; t.setAttribute("data-global-segment-analytics-key", i); t.src = "https://cdn.segment.com/analytics.js/v1/" + key + "/analytics.min.js"; var r = document.getElementsByTagName("script")[0]; r.parentNode.insertBefore(t, r); analytics._loadOptions = n }; analytics._writeKey = "p06X1rcdcdqjGSvSUE0H1BCtcnDga52G";; analytics.SNIPPET_VERSION = "5.2.0";
        analytics.load("p06X1rcdcdqjGSvSUE0H1BCtcnDga52G");
        analytics.page();
    }
}();