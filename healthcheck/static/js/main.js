document.addEventListener('DOMContentLoaded', function() {
    const client = window.ZAFClient ? window.ZAFClient.init() : null;
    
    if (!client) {
        console.error('ZAF Client could not be initialized');
        return;
    }

    console.log('ZAF Client initialized successfully');

    // Initial resize
    client.invoke('resize', { width: '100%', height: '600px' });

    document.getElementById('run-check').addEventListener('click', async () => {
        const resultsDiv = document.getElementById('results');
        
        // Show loading state
        resultsDiv.innerHTML = `
            <div class="text-center my-5">
                <div class="spinner-border text-primary" role="status">
                    <span class="visually-hidden">Loading...</span>
                </div>
            </div>
        `;

        try {
            console.log('Fetching context and metadata...');
            
            // Get context and parameters
            const context = await client.context();
            console.log('Context:', context);

            const options = {
                url: 'https://gcx-healthcheck-zd-production.up.railway.app/check/',
                type: 'POST',
                data: {
                    url: `${context.account.subdomain}.zendesk.com`,
                    email: '{{setting.admin_email}}',
                    api_token: '{{setting.api_token}}'
                },
                secure: true
            };

            console.log('Sending request to /check/...');
            const response = await client.request(options);
            
            console.log('Response:', response);
            resultsDiv.innerHTML = response;

            // Wait for content to be rendered
            setTimeout(() => {
                const contentHeight = Math.max(
                    resultsDiv.scrollHeight,
                    document.getElementById('health-check-content')?.scrollHeight || 0,
                    600
                );
                console.log('Resizing to height:', contentHeight + 50);
                client.invoke('resize', { 
                    width: '100%', 
                    height: `${contentHeight + 50}px`
                });
            }, 100);

        } catch (error) {
            console.error('Detailed error:', {
                message: error.message,
                stack: error.stack,
                error: error
            });
            resultsDiv.innerHTML = `
                <div class="alert alert-danger" role="alert">
                    <h5>Error Running Health Check</h5>
                    <p>${error.message || 'An unexpected error occurred. Please try again.'}</p>
                </div>
            `;
        }
    });
});