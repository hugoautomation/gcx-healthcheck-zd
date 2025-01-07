const URLParamManager = {
    CACHE_KEY: 'zaf_url_params',
    CACHE_DURATION: 30 * 60 * 1000, // 30 minutes

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

    _getCachedParams() {
        try {
            const cached = localStorage.getItem(this.CACHE_KEY);
            if (!cached) return null;

            const data = JSON.parse(cached);
            if (Date.now() > data.expiry) {
                localStorage.removeItem(this.CACHE_KEY);
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
            const data = {
                value: params,
                expiry: Date.now() + this.CACHE_DURATION
            };
            localStorage.setItem(this.CACHE_KEY, JSON.stringify(data));
        } catch (e) {
            console.warn('Cache write error:', e);
        }
    },

    getUrlWithParams(baseUrl) {
        const url = new URL(baseUrl, window.location.origin);
        const params = this.getParams();

        Object.entries(params).forEach(([key, value]) => {
            if (value) url.searchParams.set(key, value);
        });

        return url.toString();
    }
};