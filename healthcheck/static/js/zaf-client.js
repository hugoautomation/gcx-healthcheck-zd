// Singleton pattern for ZAF client
const ZAFClientSingleton = {
    client: null,
    metadata: null,
    context: null,

    async init(retryCount = 3, delay = 100) {
        if (this.client) return this.client;

        for (let i = 0; i < retryCount; i++) {
            try {
                // Wait before trying to initialize
                await new Promise(resolve => setTimeout(resolve, delay));
                
                this.client = window.ZAFClient ? window.ZAFClient.init() : null;
                if (!this.client) {
                    throw new Error('ZAF Client could not be initialized');
                }

                // Get context and metadata
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

        if (!urlInstallationId || !urlPlan) {
            currentUrl.searchParams.set('installation_id', this.metadata.installationId);
            currentUrl.searchParams.set('plan', this.metadata.plan?.name || 'Free');
            window.location.href = currentUrl.toString();
            return false;
        }
        return true;
    }
};