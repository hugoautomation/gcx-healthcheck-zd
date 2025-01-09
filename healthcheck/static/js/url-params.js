const URLParamManager = {
    CACHE_KEY: 'zaf_url_params',
    CACHE_DURATION: 30 * 60 * 1000, // 30 minutes
    
    preserveParams(element) {
        const currentParams = this._getCurrentParams();
        if (!element || !currentParams) return;

        if (element.tagName === 'A') {
            let url = new URL(element.href, window.location.origin);
            Object.entries(currentParams).forEach(([key, value]) => {
                if (value) url.searchParams.set(key, value);
            });
            element.href = url.toString();
        } else if (element.tagName === 'FORM') {
            Object.entries(currentParams).forEach(([key, value]) => {
                if (!element.querySelector(`[name="${key}"]`)) {
                    const input = document.createElement('input');
                    input.type = 'hidden';
                    input.name = key;
                    input.value = value;
                    element.appendChild(input);
                }
            });
        }
    },
    // Add this method to initialize all elements that need params
    initializeParamPreservation() {
        // Handle links with data-preserve-params
        document.querySelectorAll('[data-preserve-params]').forEach(element => {
            this.preserveParams(element);
        });

        // Handle forms with data-preserve-params
        document.querySelectorAll('form[data-preserve-params]').forEach(element => {
            this.preserveParams(element);
        });
    },
    getParams() {
        // Combine current and cached params
        const current = this._getCurrentParams();
        const cached = this._getCachedParams() || {};
        
        // Current params take precedence over cached
        const combined = { ...cached, ...current };
        
        // Only cache if we have new params
        if (Object.keys(current).length > 0) {
            this._cacheParams(combined);
        }
        
        return combined;
    },

    _getCurrentParams() {
        const urlParams = new URLSearchParams(window.location.search);
        const params = {};
        
        ['installation_id', 'origin', 'user_id', 'app_guid', 'plan'].forEach(key => {
            const value = urlParams.get(key);
            if (value) params[key] = value;
        });

        return params;
    },

    _getCacheKey() {
        const urlParams = new URLSearchParams(window.location.search);
        const installationId = urlParams.get('installation_id');
        const origin = urlParams.get('origin');
        if (!installationId || !origin) return null;
        
        // Extract subdomain from origin
        const subdomain = origin.split('.')[0].replace('https://', '');
        return `${this.CACHE_KEY}_${installationId}_${subdomain}`;
    },

    _getCachedParams() {
        try {
            const cacheKey = this._getCacheKey();
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

    _cacheParams(params) {
        try {
            const cacheKey = this._getCacheKey();
            if (!cacheKey) return;

            const data = {
                value: params,
                expiry: Date.now() + this.CACHE_DURATION
            };
            localStorage.setItem(cacheKey, JSON.stringify(data));
        } catch (e) {
            console.warn('Cache write error:', e);
        }
    }
};