let client = null;
let metadata = null;
let context = null;

// Initialize the app
async function initializeApp() {
    try {
        // Initialize ZAF client
        await ZAFClientSingleton.init();
        client = ZAFClientSingleton.client;
        metadata = ZAFClientSingleton.metadata;
        context = ZAFClientSingleton.context;

        if (!await ZAFClientSingleton.ensureUrlParams()) return;

        // Initialize all components
        initializeRunCheck();
        initializeHistoricalReports();
        initializeComponents();

        // Adjust initial height
        await client.invoke('resize', { width: '100%', height: '600px' });

    } catch (error) {
        console.error('Error initializing app:', error);
        const resultsDiv = document.getElementById('results');
        if (resultsDiv) {
            showError(resultsDiv, error, 'Error Initializing App');
        }
    }
}

// Utility Functions
function adjustContentHeight() {
    if (!client) return;
    
    setTimeout(() => {
        const resultsDiv = document.getElementById('results');
        const healthCheckContent = document.getElementById('health-check-content');
        
        // Calculate total height including all visible elements
        const totalHeight = Math.min(
            Math.max(
                (resultsDiv?.scrollHeight || 0) +
                healthCheckContent?.scrollHeight || 0,
                600  // minimum height
            ),
            800  // maximum height
        );

        client.invoke('resize', { 
            width: '100%', 
            height: `${totalHeight}px`
        });
    }, 100);
}

function showLoadingState(element) {
    element.innerHTML = `
        <div class="text-center my-5">
            <div class="spinner-border text-primary" role="status">
                <span class="d-none">Loading...</span>
            </div>
        </div>
    `;
}

function showError(element, error, title = 'Error') {
    console.error(`${title}:`, error);
    element.innerHTML = `
        <div class="alert alert-danger" role="alert">
            <h5>${title}</h5>
            <p>${error.message || 'An unexpected error occurred. Please try again.'}</p>
        </div>
    `;
}

function initializeFilters() {
    const severityFilter = document.getElementById('severity-filter');
    const categoryFilter = document.getElementById('category-filter');
    
    if (!severityFilter || !categoryFilter) return;

    function filterIssues() {
        const selectedSeverity = severityFilter.value;
        const selectedCategory = categoryFilter.value;
        const issueRows = document.querySelectorAll('.issue-row');

        issueRows.forEach(row => {
            const severity = row.dataset.severity;
            const category = row.dataset.category;
            const showSeverity = selectedSeverity === 'all' || severity === selectedSeverity;
            const showCategory = selectedCategory === 'all' || category === selectedCategory;
            
            row.style.display = showSeverity && showCategory ? '' : 'none';
        });

        adjustContentHeight();
    }

    severityFilter.addEventListener('change', filterIssues);
    categoryFilter.addEventListener('change', filterIssues);
}

function initializeUnlockButtons() {
    document.querySelectorAll('.unlock-report').forEach(button => {
        button.replaceWith(button.cloneNode(true));
        const newButton = document.querySelector(`.unlock-report[data-report-id="${button.dataset.reportId}"]`);

        if (newButton) {
            newButton.addEventListener('click', function () {
                const reportId = this.dataset.reportId;
                const stripePaymentLink = `https://buy.stripe.com/dR68zbfDvboy7mweUU?client_reference_id=${reportId}`;
                const windowFeatures = 'width=800,height=600,menubar=no,toolbar=no,location=no,status=no';
                const paymentWindow = window.open(stripePaymentLink, 'StripePayment', windowFeatures);

                // Start polling for unlock status
                const pollInterval = setInterval(async () => {
                    try {
                        const baseUrl = window.ENVIRONMENT === 'production' 
                            ? 'https://gcx-healthcheck-zd-production.up.railway.app'
                            : 'https://gcx-healthcheck-zd-development.up.railway.app';

                        const options = {
                            url: `${baseUrl}/check-unlock-status/?report_id=${reportId}`,
                            type: 'GET',
                            secure: true
                        };
                        
                        const data = await client.request(options);

                        if (data.is_unlocked) {
                            document.getElementById('results').innerHTML = data.html;
                            initializeFilters();
                            initializeUnlockButtons();
                            adjustContentHeight();
                            clearInterval(pollInterval);
                        }
                    } catch (error) {
                        console.error('Error checking unlock status:', error);
                    }
                }, 2000);

                // Stop polling if payment window is closed
                const checkWindow = setInterval(() => {
                    if (paymentWindow.closed) {
                        clearInterval(pollInterval);
                        clearInterval(checkWindow);
                    }
                }, 1000);
            });
        }
    });
}

function initializeComponents() {
    try {
        initializeFilters();
        initializeUnlockButtons();
        adjustContentHeight();
    } catch (error) {
        console.error('Error initializing components:', error);
    }
}

function initializeRunCheck() {
    const runCheckButton = document.getElementById('run-check');
    if (!runCheckButton) return;

    runCheckButton.addEventListener('click', async () => {
        console.log('Run Health Check button clicked');
        const resultsDiv = document.getElementById('results');
        showLoadingState(resultsDiv);

        try {
            if (!client || !context || !metadata) {
                throw new Error('Client, context, or metadata not initialized');
            }

            // Determine base URL based on environment
            const baseUrl = window.ENVIRONMENT === 'production'
                ? 'https://gcx-healthcheck-zd-production.up.railway.app'
                : 'https://gcx-healthcheck-zd-development.up.railway.app';

                const options = {
                    url: `${baseUrl}/health_check/`,
                    type: 'POST',
                    contentType: 'application/json',
                    headers: {
                        'Accept': 'application/json',
                        'Content-Type': 'application/json',
                        'X-Subsequent-Request': 'true',
                        'X-Admin-Email': '{{setting.admin_email}}',
                        'X-API-Token': '{{setting.api_token}}'
                    },
                    data: JSON.stringify({
                        url: context.account.subdomain + '.zendesk.com',
                        email: '{{setting.admin_email}}',    // Keep in payload
                        api_token: '{{setting.api_token}}',  // Keep in payload
                        instance_guid: context.instanceGuid,
                        app_guid: metadata.appId,
                        installation_id: metadata.installationId,
                        user_id: ZAFClientSingleton.userInfo?.id,
                        subdomain: context.account.subdomain,
                        plan: metadata.plan?.name,
                        stripe_subscription_id: metadata.stripe_subscription_id,
                        version: metadata.version
                    }),
                    secure: true
                };

            console.log('Request options:', { 
                ...options, 
                data: JSON.stringify(requestData) 
            });

            // Make the request
            const response = await client.request(options);
            console.log('Response received:', response);

            // Check if we have results_html, regardless of error status
            if (response.results_html) {
                resultsDiv.innerHTML = response.results_html;
                initializeComponents();
            } else {
                // Only throw if we don't have results to display
                throw new Error(response.error || 'Unknown error occurred');
            }

        } catch (error) {
            console.error('Full error details:', error);
            showError(resultsDiv, error, 'Error Running Health Check');
        }
    });
}

function initializeHistoricalReports() {
    document.querySelectorAll('.historical-report').forEach(link => {
        link.addEventListener('click', async function(e) {
            e.preventDefault();
            const resultsDiv = document.getElementById('results');
            showLoadingState(resultsDiv);

            try {
                const baseUrl = window.ENVIRONMENT === 'production' 
                    ? 'https://gcx-healthcheck-zd-production.up.railway.app'
                    : 'https://gcx-healthcheck-zd-development.up.railway.app';

                const options = {
                    url: `${baseUrl}/report/${this.dataset.reportId}/?installation_id=${metadata.installationId}&user_id=${ZAFClientSingleton.userInfo?.id}`,
                    type: 'GET',
                    secure: true
                };
                
                const data = await client.request(options);
                resultsDiv.innerHTML = data.results_html;
                initializeComponents();
            } catch (error) {
                showError(resultsDiv, error, 'Error Loading Report');
            }
        });
    });
}

// Event Listeners
document.addEventListener('DOMContentLoaded', initializeApp);