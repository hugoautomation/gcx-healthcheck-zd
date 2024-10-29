const ZAFClientSingleton = {
    client: null,
    metadata: null,
    context: null,

    async init(retryCount = 3, delay = 100) {
        if (this.client) return this.client;

        // Get origin and app_guid from URL parameters
        const urlParams = new URLSearchParams(window.location.search);
        const origin = urlParams.get('origin');
        const appGuid = urlParams.get('app_guid');

        for (let i = 0; i < retryCount; i++) {
            try {
                await new Promise(resolve => setTimeout(resolve, delay));
                
                // Initialize with origin and app_guid if available
                this.client = window.ZAFClient ? 
                    (origin && appGuid ? 
                        window.ZAFClient.init({origin, appGuid}) : 
                        window.ZAFClient.init()) 
                    : null;

                if (!this.client) {
                    throw new Error('ZAF Client could not be initialized');
                }

                [this.context, this.metadata] = await Promise.all([
                    this.client.context(),
                    this.client.metadata()
                ]);

                console.log('ZAF Client initialized successfully');
                return this.client;

            } catch (error) {
                console.warn(`ZAF initialization attempt ${i + 1} failed:`, error);
                if (i === retryCount - 1) throw error;
            }
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