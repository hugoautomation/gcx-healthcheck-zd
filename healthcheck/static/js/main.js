document.addEventListener('DOMContentLoaded', function() {
    const client = window.ZAFClient ? window.ZAFClient.init() : null;
    
    if (!client) {
        console.error('ZAF Client could not be initialized');
        return;
    }

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
            // Get context and parameters
            const [context, metadata] = await Promise.all([
                client.context(),
                client.metadata()
            ]);

            const formData = new FormData();
            formData.append('url', context.account.subdomain + '.zendesk.com');
            formData.append('email', metadata.settings.admin_email);
            formData.append('api_token', metadata.settings.api_token);

            const response = await fetch('/check/', {
                method: 'POST',
                body: formData
            });

            const html = await response.text();
            resultsDiv.innerHTML = html;

            // Wait for content to be rendered
            setTimeout(() => {
                const contentHeight = Math.max(
                    resultsDiv.scrollHeight,
                    document.getElementById('health-check-content')?.scrollHeight || 0,
                    600
                );
                client.invoke('resize', { 
                    width: '100%', 
                    height: `${contentHeight + 50}px`
                });
            }, 100);

        } catch (error) {
            console.error('Error:', error);
            resultsDiv.innerHTML = `
                <div class="alert alert-danger" role="alert">
                    <h5>Error Running Health Check</h5>
                    <p>${error.message || 'An unexpected error occurred. Please try again.'}</p>
                </div>
            `;
        }
    });
});