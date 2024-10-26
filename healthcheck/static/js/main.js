document.addEventListener('DOMContentLoaded', function() {
    const client = window.ZAFClient ? window.ZAFClient.init() : null;
    
    if (!client) {
        console.error('ZAF Client could not be initialized');
        return;
    }

    console.log('ZAF Client initialized successfully');

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

            console.log('Filtering:', { severity, category }); // Debug log

            rows.forEach(row => {
                const rowSeverity = row.dataset.severity;
                const rowCategory = row.dataset.category;
                
                const matchesSeverity = severity === 'all' || rowSeverity === severity;
                const matchesCategory = category === 'all' || rowCategory === category;
                
                row.style.display = matchesSeverity && matchesCategory ? '' : 'none';
                
                console.log('Row:', { 
                    rowSeverity, 
                    rowCategory, 
                    matches: matchesSeverity && matchesCategory 
                }); // Debug log
            });
        }

        // Event listeners
        severityFilter.addEventListener('change', filterIssues);
        categoryFilter.addEventListener('change', filterIssues);
    }

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

                console.log('Resizing to height:', contentHeight);
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
});