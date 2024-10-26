document.addEventListener('DOMContentLoaded', async function() {
    const client = window.ZAFClient ? window.ZAFClient.init() : null;
    const CACHE_KEY = 'healthcheck_results';
    const CACHE_TIMESTAMP_KEY = 'healthcheck_timestamp';
    
    if (!client) {
        console.error('ZAF Client could not be initialized');
        return;
    }

    console.log('ZAF Client initialized successfully');

    // Get metadata for installation_id and update URL
    const metadata = await client.metadata();
    const currentUrl = new URL(window.location.href);
    currentUrl.searchParams.set('installation_id', metadata.installationId);
    window.history.replaceState({}, '', currentUrl);

    // Initial resize with maximum height
    client.invoke('resize', { width: '100%', height: '800px' });

    // Handle scroll events
    const scrollContainer = document.querySelector('.scrollable-container');
    scrollContainer.addEventListener('scroll', (e) => {
        e.stopPropagation();
    });

    // Filtering function
    function initializeFilters() {
        const issuesTable = document.getElementById('issues-table-body');
        const severityFilter = document.getElementById('severity-filter');
        const categoryFilter = document.getElementById('category-filter');

        if (!issuesTable || !severityFilter || !categoryFilter) return;

        function filterIssues() {
            const rows = Array.from(issuesTable.getElementsByClassName('issue-row'));
            const severity = severityFilter.value;
            const category = categoryFilter.value;

            rows.forEach(row => {
                const rowSeverity = row.dataset.severity;
                const rowCategory = row.dataset.category;
                
                const matchesSeverity = severity === 'all' || rowSeverity === severity;
                const matchesCategory = category === 'all' || rowCategory === category;
                
                row.style.display = matchesSeverity && matchesCategory ? '' : 'none';
            });
        }

        // Event listeners
        severityFilter.addEventListener('change', filterIssues);
        categoryFilter.addEventListener('change', filterIssues);

        // Apply saved filters if they exist
        const savedSeverity = localStorage.getItem('severity_filter');
        const savedCategory = localStorage.getItem('category_filter');
        
        if (savedSeverity) severityFilter.value = savedSeverity;
        if (savedCategory) categoryFilter.value = savedCategory;
        
        filterIssues();
    }

    // Initialize filters for initial load
    initializeFilters();

    // Handle new health check requests
    document.getElementById('run-check').addEventListener('click', async () => {
        const resultsDiv = document.getElementById('results');
        
        // Show loading state
        resultsDiv.innerHTML = `
            <div class="text-center my-5">
                <div class="spinner-border text-primary" role="status">
                    <span class="d-none">Loading...</span>
                </div>
            </div>
        `;

        try {
            const [context, metadata] = await Promise.all([
                client.context(),
                client.metadata()
            ]);

            const options = {
                url: 'https://gcx-healthcheck-zd-production.up.railway.app/check/',
                type: 'POST',
                contentType: 'application/json',
                data: JSON.stringify({
                    // Original auth data
                    url: `${context.account.subdomain}.zendesk.com`,
                    email: metadata.settings.admin_email,
                    api_token: metadata.settings.api_token,
                    
                    // Additional instance data
                    instance_guid: context.instanceGuid,
                    app_guid: metadata.appId,
                    installation_id: metadata.installationId,
                    subdomain: context.account.subdomain,
                    
                    // App metadata
                    plan: metadata.plan?.name,
                    stripe_subscription_id: metadata.stripe_subscription_id,
                    version: metadata.version
                }),
                secure: true
            };

            console.log('Sending request to /check/...');
            const response = await client.request(options);
            
            console.log('Response:', response);
            resultsDiv.innerHTML = response;

            // Initialize filters after content is loaded
            initializeFilters();

            // Reset scroll position
            scrollContainer.scrollTop = 0;

            // Adjust height after content is rendered
            setTimeout(() => {
                const contentHeight = Math.min(
                    Math.max(
                        resultsDiv.scrollHeight,
                        document.getElementById('health-check-content')?.scrollHeight || 0,
                        600  // minimum height
                    ),
                    800  // maximum height
                );

                client.invoke('resize', { 
                    width: '100%', 
                    height: `${contentHeight}px`
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

    // Save filter states when changed
    document.addEventListener('change', function(e) {
        if (e.target.id === 'severity-filter') {
            localStorage.setItem('severity_filter', e.target.value);
        } else if (e.target.id === 'category-filter') {
            localStorage.setItem('category_filter', e.target.value);
        }
    });
});