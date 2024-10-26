document.addEventListener('DOMContentLoaded', function() {
    const client = window.ZAFClient ? window.ZAFClient.init() : null;
    
    if (!client) {
        console.error('ZAF Client could not be initialized');
        return;
    }

    // Initial resize
    client.invoke('resize', { width: '100%', height: '600px' });

    // Get the Zendesk domain
    client.context().then(function(context) {
        const domain = context.account.subdomain + '.zendesk.com';
        document.getElementById('domain').value = domain;
    });

    document.getElementById('healthcheck-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const formData = new FormData();
        formData.append('url', document.getElementById('domain').value);
        formData.append('email', document.getElementById('email').value);
        formData.append('api_token', document.getElementById('token').value);

        // Show loading state
        const resultsDiv = document.getElementById('results');
        resultsDiv.innerHTML = `
            <div class="text-center my-5">
                <div class="spinner-border text-primary" role="status">
                    <span class="visually-hidden">Loading...</span>
                </div>
            </div>
        `;

        try {
            const response = await fetch('/check/', {
                method: 'POST',
                body: formData
            });

            console.log('Response status:', response.status);
            const html = await response.text();
            console.log('Response length:', html.length);

            // Update content
            resultsDiv.innerHTML = html;

            // Wait for content to be rendered
            setTimeout(() => {
                // Get the actual height of the content
                const contentHeight = Math.max(
                    resultsDiv.scrollHeight,
                    document.getElementById('health-check-content')?.scrollHeight || 0,
                    600 // minimum height
                );
                
                // Resize the app with some padding
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
            client.invoke('resize', { width: '100%', height: '100%' });
        }
    });
});