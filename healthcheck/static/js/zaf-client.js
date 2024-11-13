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
        // Wait for analytics to be ready
        await new Promise(resolve => {
            if (window.analytics && window.analytics.initialized) {
                resolve();
            } else {
                analytics.ready(resolve);
            }
        });

        if (this.userInfo && this.metadata) {
            console.log('Tracking analytics with user:', this.userInfo);
            
            // Identify the user
            analytics.identify(this.userInfo.id, {
                test: 'test',
                name: this.userInfo.name,
                email: this.userInfo.email,
                role: this.userInfo.role,
                locale: this.userInfo.locale,
                time_zone: this.userInfo.timeZone?.ianaName,
                avatar_url: this.userInfo.avatarUrl,
            });

            // Track group
            if (this.context?.account?.subdomain) {
                analytics.group(this.context.account.subdomain, {
                    name: this.context.account.subdomain,
                    organization: this.context.account.subdomain,
                    plan: this.metadata.plan?.name || 'Free',
                });
            }
        } else {
            console.warn('Missing user info or metadata for analytics tracking');
        }
    },

    async ensureUrlParams() {
        if (!this.metadata) return false;

        const currentUrl = new URL(window.location.href);
        const urlInstallationId = currentUrl.searchParams.get('installation_id');
        const urlPlan = currentUrl.searchParams.get('plan');
        const origin = currentUrl.searchParams.get('origin');
        const appGuid = currentUrl.searchParams.get('app_guid');

        let needsRedirect = false;

        if (!urlInstallationId || !urlPlan) {
            currentUrl.searchParams.set('installation_id', this.metadata.installationId);
            currentUrl.searchParams.set('plan', this.metadata.plan?.name || 'Free');
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
        ['installation_id', 'plan', 'origin', 'app_guid'].forEach(param => {
            const value = currentParams.get(param);
            if (value) url.searchParams.set(param, value);
        });

        return url.toString();
    }
};

!function () {
    const environment = window.ENVIRONMENT || 'development';
    var i = "analytics", analytics = window[i] = window[i] || []; if (!analytics.initialize) if (analytics.invoked) window.console && console.error && console.error("Segment snippet included twice."); else {
        analytics.invoked = !0; analytics.methods = ["trackSubmit", "trackClick", "trackLink", "trackForm", "pageview", "identify", "reset", "group", "track", "ready", "alias", "debug", "page", "screen", "once", "off", "on", "addSourceMiddleware", "addIntegrationMiddleware", "setAnonymousId", "addDestinationMiddleware", "register"]; analytics.factory = function (e) { return function () { if (window[i].initialized) return window[i][e].apply(window[i], arguments); var n = Array.prototype.slice.call(arguments); if (["track", "screen", "alias", "group", "page", "identify"].indexOf(e) > -1) { var c = document.querySelector("link[rel='canonical']"); n.push({ __t: "bpc", c: c && c.getAttribute("href") || void 0, p: location.pathname, u: location.href, s: location.search, t: document.title, r: document.referrer }) } n.unshift(e); analytics.push(n); return analytics } }; for (var n = 0; n < analytics.methods.length; n++) { var key = analytics.methods[n]; analytics[key] = analytics.factory(key) } analytics.load = function (key, n) { var t = document.createElement("script"); t.type = "text/javascript"; t.async = !0; t.setAttribute("data-global-segment-analytics-key", i); t.src = "https://cdn.segment.com/analytics.js/v1/" + key + "/analytics.min.js"; var r = document.getElementsByTagName("script")[0]; r.parentNode.insertBefore(t, r); analytics._loadOptions = n }; analytics._writeKey = "p06X1rcdcdqjGSvSUE0H1BCtcnDga52G";; analytics.SNIPPET_VERSION = "5.2.0";
        if (environment === 'production') {
            analytics.load("p06X1rcdcdqjGSvSUE0H1BCtcnDga52G");
            analytics.page();
        } else {
            analytics.load("U6XH9kyxKENzjHCtzdfTLFe2m1BsNnKL");
            analytics.page();
            console.log('Test analytics loaded');
        }
    }
}();