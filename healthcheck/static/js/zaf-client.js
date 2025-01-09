
function getBaseUrl() {
    const bodyElement = document.body;
    return bodyElement.getAttribute('data-environment') || 'https://gcx-healthcheck-zd-development.up.railway.app';
}
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
        const baseUrl = getBaseUrl();

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
        if (this.client) {
            // If we already have data, just ensure URL params and return
            if (this.metadata && this.context && this.userInfo) {
                await this.ensureUrlParams();
                return this.client;
            }
        }

        try {
            await this.initializeClient(retryCount, delay);
            
            // Try to get cached data first
            const cachedData = this._getCachedData();
            if (cachedData) {
                this.context = cachedData.context;
                this.metadata = cachedData.metadata;
                this.userInfo = cachedData.userInfo;
                await this.ensureUrlParams();
                return this.client;
            }

            // Only load fresh data if cache miss
            await this.loadData();
            await this.trackAnalytics();
            await this._cacheOnServer();
            
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



   
async trackAnalytics() {
    try {
        console.log('Starting trackAnalytics...');
        console.log('Current userInfo:', this.userInfo);
        console.log('Current metadata:', this.metadata);

        // Check if window.analytics exists
        console.log('Analytics object available:', !!window.analytics);
        
        // Wait for analytics to be ready
        await new Promise(resolve => {
            if (!window.analytics) {
                console.warn('Analytics object not found');
                resolve(); // Resolve anyway to prevent hanging
                return;
            }

            if (window.analytics.initialized) {
                console.log('Analytics already initialized');
                resolve();
            } else {
                console.log('Waiting for analytics to initialize...');
                window.analytics.ready(resolve);
            }
        });

        if (!this.userInfo || !this.metadata) {
            console.warn('Missing required data:', {
                userInfo: !!this.userInfo,
                metadata: !!this.metadata
            });
            return;
        }

    
        const baseUrl = getBaseUrl();

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
    

    
            } catch (error) {
                console.error('Failed to create/update user:', error);
                // Don't throw the error to prevent app initialization from failing
            }
    
        } catch (error) {
            console.error('Analytics tracking error:', error);
            console.error('Error details:', {
                hasAnalytics: !!window.analytics,
                analyticsInitialized: window.analytics?.initialized,
                userInfo: this.userInfo,
                metadata: this.metadata
            });
            // Don't throw the error to prevent app initialization from failing
        }
    },
    async loadData() {
        // Try to get cached data first
        console.log('Starting loadData...');
        
        // Try to get cached data first
        const cachedData = this._getCachedData();
        console.log('Cached data:', cachedData);

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

    _getCacheKey(type) {
        // Create unique cache keys based on installation_id and subdomain
        const installationId = this.metadata?.installationId;
        const subdomain = this.context?.account?.subdomain;
        if (!installationId || !subdomain) return null;
        return `zaf_${type}_${installationId}_${subdomain}`;
    },
      _getCachedData() {
        try {
            const cacheKey = this._getCacheKey('client_data');
            if (!cacheKey) return null;

            const cached = localStorage.getItem(cacheKey);
            if (!cached) return null;

            const data = JSON.parse(cached);
            if (Date.now() > data.expiry) {
                localStorage.removeItem(cacheKey);
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
            const cacheKey = this._getCacheKey('client_data');
            if (!cacheKey) return;

            const data = {
                value: {
                    context: this.context,
                    metadata: this.metadata,
                    userInfo: this.userInfo
                },
                expiry: Date.now() + this.CACHE_DURATION.CLIENT_DATA
            };
            localStorage.setItem(cacheKey, JSON.stringify(data));
        } catch (e) {
            console.warn('Cache write error:', e);
        }
    },

    _getCachedUrlParams() {
        try {
            const cacheKey = this._getCacheKey('url_params');
            if (!cacheKey) return null;

            const cached = localStorage.getItem(cacheKey);
            if (!cached) return null;

            const data = JSON.parse(cached);
            if (Date.now() > data.expiry) {
                localStorage.removeItem(cacheKey);
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
            const cacheKey = this._getCacheKey('url_params');
            if (!cacheKey) return;

            const data = {
                value: params,
                expiry: Date.now() + this.CACHE_DURATION.URL_PARAMS
            };
            localStorage.setItem(cacheKey, JSON.stringify(data));
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