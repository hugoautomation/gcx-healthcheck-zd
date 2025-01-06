const ZAFClientSingleton = {
    client: null,
    metadata: null,
    context: null,
    userInfo: null,
    CACHE_DURATION: 5 * 60 * 1000, // 5 minutes in milliseconds

    // Add cache helper methods
    _getCachedData(key) {
        try {
            const item = localStorage.getItem(`zaf_${key}`);
            if (!item) return null;

            const data = JSON.parse(item);
            if (Date.now() > data.expiry) {
                localStorage.removeItem(`zaf_${key}`);
                return null;
            }
            return data.value;
        } catch (e) {
            console.warn('Cache read error:', e);
            return null;
        }
    },

    _setCachedData(key, value) {
        try {
            const item = {
                value: value,
                expiry: Date.now() + this.CACHE_DURATION
            };
            localStorage.setItem(`zaf_${key}`, JSON.stringify(item));
        } catch (e) {
            console.warn('Cache write error:', e);
        }
    },

    async loadData() {
        // Try to get cached data first
        this.metadata = this._getCachedData('metadata');
        this.context = this._getCachedData('context');
        this.userInfo = this._getCachedData('userInfo');

        // If any data is missing, load it all fresh
        if (!this.metadata || !this.context || !this.userInfo) {
            try {
                // Load fresh data
                [this.context, this.metadata] = await Promise.all([
                    this.client.context(),
                    this.client.metadata(),
                ]);

                const userResponse = await this.client.get('currentUser');
                this.userInfo = userResponse.currentUser;

                // Cache the fresh data
                this._setCachedData('metadata', this.metadata);
                this._setCachedData('context', this.context);
                this._setCachedData('userInfo', this.userInfo);

                // Also cache on server
                await this._cacheOnServer();

            } catch (error) {
                console.error('Error loading fresh data:', error);
                throw error;
            }
        }

        console.log('Data loaded:', {
            context: this.context,
            metadata: this.metadata,
            userInfo: this.userInfo
        });
    },

    async _cacheOnServer() {
        // Cache data on server
        const baseUrl = window.ENVIRONMENT === 'production'
            ? 'https://gcx-healthcheck-zd-production.up.railway.app'
            : 'https://gcx-healthcheck-zd-development.up.railway.app';

        try {
            await this.client.request({
                url: `${baseUrl}/api/cache/zaf-data/`,
                type: 'POST',
                contentType: 'application/json',
                headers: {
                    'X-Subsequent-Request': 'true'
                },
                data: JSON.stringify({
                    user_id: this.userInfo.id,
                    metadata: this.metadata,
                    context: this.context,
                    user_info: this.userInfo
                }),
                secure: true
            });
        } catch (error) {
            console.warn('Failed to cache data on server:', error);
            // Don't throw error as this is non-critical
        }
    },

    async init(retryCount = 3, delay = 100) {
        if (this.client) return this.client;

        try {
            await this.initializeClient(retryCount, delay);
            // Load data in parallel
            await Promise.all([
                this.loadData(),
                this.trackAnalytics()
            ]);
            return this.client;
        } catch (error) {
            console.error('Failed to initialize:', error);
            throw error;
        }
    },
        // Initialize client without waiting for data
        async quickInit() {
            if (this.client) return this.client;
            await this.initializeClient(3, 100);
            return this.client;
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
                // analytics.identify(this.userInfo.id, {
                //     name: this.userInfo.name,
                //     email: this.userInfo.email,
                //     subdomain: this.context.account.subdomain,
                //     role: this.userInfo.role,
                //     locale: this.userInfo.locale,
                //     time_zone: this.userInfo.timeZone?.ianaName,
                //     avatar: this.userInfo.avatarUrl,
                //     plan: this.metadata.plan?.name || 'Free',
                // });
    
            
    
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
    const cachedParams = this._getCachedUrlParams();
    let needsRedirect = false;

    // Check each parameter, using cached values first, then ZAF data
    const paramsToCheck = {
        'installation_id': {
            current: currentUrl.searchParams.get('installation_id'),
            cached: cachedParams?.installation_id,
            zaf: this.metadata.installationId
        },
        'plan': {
            current: currentUrl.searchParams.get('plan'),
            cached: cachedParams?.plan,
            zaf: this.metadata.plan?.name || 'Free'
        },
        'user_id': {
            current: currentUrl.searchParams.get('user_id'),
            cached: cachedParams?.user_id,
            zaf: this.userInfo?.id
        },
        'origin': {
            current: currentUrl.searchParams.get('origin'),
            cached: cachedParams?.origin,
            zaf: this.context?.account?.subdomain ? `https://${this.context.account.subdomain}.zendesk.com` : null
        },
        'app_guid': {
            current: currentUrl.searchParams.get('app_guid'),
            cached: cachedParams?.app_guid,
            zaf: this.metadata?.appGuid
        }
    };

    // Update missing parameters
    Object.entries(paramsToCheck).forEach(([param, values]) => {
        if (!values.current) {
            const newValue = values.cached || values.zaf;
            if (newValue) {
                currentUrl.searchParams.set(param, newValue);
                needsRedirect = true;
            }
        }
    });

    if (needsRedirect) {
        // Cache the new params before redirecting
        this._cacheUrlParams(Object.fromEntries(currentUrl.searchParams));
        window.location.href = currentUrl.toString();
        return false;
    }

    // Cache current params if we're not redirecting
    this._cacheUrlParams(Object.fromEntries(currentUrl.searchParams));
    return true;
},

getUrlWithParams(baseUrl) {
    const url = new URL(baseUrl, window.location.origin);
    const cachedParams = this._getCachedUrlParams() || {};
    const currentParams = Object.fromEntries(new URLSearchParams(window.location.search));
    
    // Combine current and cached params, with current taking precedence
    const params = { ...cachedParams, ...currentParams };

    // Add all available parameters
    ['installation_id', 'plan', 'origin', 'app_guid', 'user_id'].forEach(param => {
        if (params[param]) {
            url.searchParams.set(param, params[param]);
        }
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