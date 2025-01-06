const ZAFClientSingleton = {
    client: null,
    metadata: null,
    context: null,
    userInfo: null,

        // Cache durations in milliseconds
        CACHE_DURATION: {
            CLIENT_DATA: 5 * 60 * 1000,    // 5 minutes for ZAF client data
            URL_PARAMS: 30 * 60 * 1000,    // 30 minutes for URL parameters
            SERVER_DATA: 5 * 60 * 1000     // 5 minutes for server-side cache
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
        // Try to get cached data first
        const cachedData = this._getCachedData();
        if (cachedData) {
            this.context = cachedData.context;
            this.metadata = cachedData.metadata;
            this.userInfo = cachedData.userInfo;
            return;
        }

        // Load fresh data if no cache
        [this.context, this.metadata] = await Promise.all([
            this.client.context(),
            this.client.metadata(),
        ]);

        const userResponse = await this.client.get('currentUser');
        this.userInfo = userResponse.currentUser;

        // Cache the fresh data
        this._cacheData();
        
        console.log('Data loaded:', {
            context: this.context,
            metadata: this.metadata,
            userInfo: this.userInfo
        });
    },

    _getCachedData() {
        try {
            const cached = localStorage.getItem('zaf_client_data');
            if (!cached) return null;

            const data = JSON.parse(cached);
            if (Date.now() > data.expiry) {
                localStorage.removeItem('zaf_client_data');
                return null;
            }
            return data.value;
        } catch (e) {
            console.warn('Cache read error:', e);
            return null;
        }
    },

    _cacheData() {
        try {
            const data = {
                value: {
                    context: this.context,
                    metadata: this.metadata,
                    userInfo: this.userInfo
                },
                expiry: Date.now() + this.CACHE_DURATION.CLIENT_DATA
            };
            localStorage.setItem('zaf_client_data', JSON.stringify(data));
        } catch (e) {
            console.warn('Cache write error:', e);
        }
    },

    _getCachedUrlParams() {
        try {
            const cached = localStorage.getItem('zaf_url_params');
            if (!cached) return null;

            const data = JSON.parse(cached);
            if (Date.now() > data.expiry) {
                localStorage.removeItem('zaf_url_params');
                return null;
            }
            return data.value;
        } catch (e) {
            console.warn('URL params cache read error:', e);
            return null;
        }
    },

    _cacheUrlParams(params) {
        try {
            const data = {
                value: params,
                expiry: Date.now() + this.CACHE_DURATION.URL_PARAMS
            };
            localStorage.setItem('zaf_url_params', JSON.stringify(data));
        } catch (e) {
            console.warn('URL params cache write error:', e);
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