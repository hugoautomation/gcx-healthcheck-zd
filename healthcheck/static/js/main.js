document.addEventListener('DOMContentLoaded', function() {
    const client = window.ZAFClient ? window.ZAFClient.init() : null;
    const CACHE_KEY = 'healthcheck_results';
    const CACHE_TIMESTAMP_KEY = 'healthcheck_timestamp';
    
    if (!client) {
        console.error('ZAF Client could not be initialized');
        return;
    }

    console.log('ZAF Client initialized successfully');
    console.log('Client: ',client)

    // Initial resize with maximum height
    client.invoke('resize', { width: '100%', height: '800px' });

    // Handle scroll events
    const scrollContainer = document.querySelector('.scrollable-container');
    scrollContainer.addEventListener('scroll', (e) => {
        e.stopPropagation();
    });

    // Load cached results if they exist
    function loadCachedResults() {
        const cachedHtml = localStorage.getItem(CACHE_KEY);
        const timestamp = localStorage.getItem(CACHE_TIMESTAMP_KEY);
        
        if (cachedHtml) {
            const resultsDiv = document.getElementById('results');
            resultsDiv.innerHTML = cachedHtml;
            initializeFilters();
            
            // Add timestamp indicator
            const timeAgo = timestamp ? new Date(parseInt(timestamp)) : new Date();
            const timeDiff = Math.round((new Date() - timeAgo) / 1000 / 60); // minutes
            
            const timestampDiv = document.createElement('div');
            timestampDiv.className = 'text-muted small mb-3';
            timestampDiv.innerHTML = `Last checked: ${timeDiff} minutes ago`;
            resultsDiv.insertBefore(timestampDiv, resultsDiv.firstChild);
            
            return true;
        }
        return false;
    }

    // Try to load cached results on initial load
    loadCachedResults();

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

            console.log('Filtering:', { severity, category });

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

        // Store filter states
        const savedSeverity = localStorage.getItem('severity_filter');
        const savedCategory = localStorage.getItem('category_filter');
        
        if (savedSeverity) severityFilter.value = savedSeverity;
        if (savedCategory) categoryFilter.value = savedCategory;
        
        // Apply saved filters
        filterIssues();
    }

    document.getElementById('run-check').addEventListener('click', async () => {
        const resultsDiv = document.getElementById('results');
        
        // Clear existing cache when running new check
        localStorage.removeItem(CACHE_KEY);
        localStorage.removeItem(CACHE_TIMESTAMP_KEY);
        
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
            
                    // Fetch both context and metadata
        const [context, metadata] = await Promise.all([
            client.context(),
            client.metadata()
        ]);
            if (!loadCachedResults()) {
                // If no cache, fetch latest report from database
                try {
                    const options = {
                        url: 'https://gcx-healthcheck-zd-production.up.railway.app/latest_report/',
                        type: 'GET',
                        data: {
                            installation_id: metadata.installationId

                        }
                    };
                    
                    const response = await client.request(options);
                    if (response) {
                        const resultsDiv = document.getElementById('results');
                        resultsDiv.innerHTML = response;
                        initializeFilters();
                    }
                } catch (error) {
                    console.error('Error fetching latest report:', error);
                }
            }

               const options = {
            url: 'https://gcx-healthcheck-zd-production.up.railway.app/check/',
            type: 'POST',
            contentType: 'application/json',
            data: JSON.stringify({
                // Original auth data
                url: `${context.account.subdomain}.zendesk.com`,
                email: '{{setting.admin_email}}',
                api_token: '{{setting.api_token}}',
                
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

            // Cache the results
            localStorage.setItem(CACHE_KEY, response);
            localStorage.setItem(CACHE_TIMESTAMP_KEY, new Date().getTime().toString());

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

    // Save filter states when changed
    document.addEventListener('change', function(e) {
        if (e.target.id === 'severity-filter') {
            localStorage.setItem('severity_filter', e.target.value);
        } else if (e.target.id === 'category-filter') {
            localStorage.setItem('category_filter', e.target.value);
        }
    });
});