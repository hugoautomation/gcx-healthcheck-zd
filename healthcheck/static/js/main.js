document.addEventListener('DOMContentLoaded', function() {
    const client = window.ZAFClient ? window.ZAFClient.init() : null;
    
    if (!client) {
        console.error('ZAF Client could not be initialized');
        return;
    }

    client.invoke('resize', { width: '100%', height: '800px' });

    // Get the Zendesk domain
    client.context().then(function(context) {
        const domain = context.account.subdomain + '.zendesk.com';
        document.getElementById('domain').value = domain;
    });

    document.getElementById('healthcheck-form').addEventListener('submit', (e) => {
        e.preventDefault();
        
        const formData = new FormData();
        formData.append('url', document.getElementById('domain').value);
        formData.append('email', document.getElementById('email').value);
        formData.append('api_token', document.getElementById('token').value);

        // Show loading state
        document.getElementById('results').innerHTML = '<div class="text-center"><div class="spinner-border" role="status"><span class="sr-only">Loading...</span></div></div>';

        fetch('/check/', {
            method: 'POST',
            body: formData
        })
        .then(response => {
            console.log('Response status:', response.status); // Debug log
            return response.text();
        })
        .then(html => {
            console.log('Received HTML:', html); // Debug log
            document.getElementById('results').innerHTML = html;
            client.invoke('resize', { width: '100%', height: '800px' });
        })
        .catch(error => {
            console.error('Error:', error);
            document.getElementById('results').innerHTML = `
                <div class="alert alert-danger" role="alert">
                    An error occurred while running the health check. Please try again.
                </div>
            `;
        });
    });
});