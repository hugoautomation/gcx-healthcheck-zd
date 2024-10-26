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
            const [context, metadata] = await Promise.all([
                client.context(),
                client.metadata()
            ]);
            client.metadata().then(function(metadata) {
                console.log(metadata.settings);
              });

            console.log('Context:', context);
            console.log('Metadata:', metadata);

            const formData = new FormData();
            const subdomain = context.account.subdomain;
            const email = metadata.settings.admin_email;
            const token = metadata.settings.api_token;

            console.log('Subdomain:', subdomain);
            console.log('Admin Email:', email);
            console.log('API Token length:', token ? token.length : 0);

            formData.append('url', `${subdomain}.zendesk.com`);
            formData.append('email', email);
            formData.append('api_token', token);

            console.log('Sending request to /check/...');

            const response = await fetch('/check/', {
                method: 'POST',
                body: formData
            });

            console.log('Response status:', response.status);
            const html = await response.text();
            console.log('Response length:', html.length);
            console.log('Response preview:', html.substring(0, 200));

            resultsDiv.innerHTML = html;

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