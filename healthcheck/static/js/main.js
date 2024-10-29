let client = null;
let metadata = null;
let context = null;

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


// Add these functions after your utility functions
function addEmailField(button) {
    const template = `
        <div class="input-group mb-2">
            <input type="email" class="form-control" name="notification_emails[]" 
                   ${button.closest('form').dataset.isFreePlan === 'true' ? 'disabled' : ''}>
            <button type="button" class="btn c-btn c-btn--danger rounded-end remove-email" onclick="removeEmailField(this)">-</button>
        </div>`;
    button.closest('.input-group').insertAdjacentHTML('beforebegin', template);
    adjustContentHeight();
}

function removeEmailField(button) {
    button.closest('.input-group').remove();
    adjustContentHeight();
}

// Add these functions after the utility functions and before initializeComponents()

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
    const unlockButtons = document.querySelectorAll('.unlock-report');
    if (!unlockButtons.length) return;

    unlockButtons.forEach(button => {
        button.addEventListener('click', async function(e) {
            e.preventDefault();
            const reportId = this.dataset.reportId;
            
            try {
                const response = await fetch(`check-unlock-status/?report_id=${reportId}`);
                if (!response.ok) throw new Error('Failed to check unlock status');
                
                const data = await response.json();
                if (data.is_unlocked) {
                    // If report is unlocked, update the content
                    document.getElementById('results').innerHTML = data.html;
                    initializeComponents();
                } else {
                    // If not unlocked, redirect to payment
                    window.location.href = `unlock-report/${reportId}/`;
                }
            } catch (error) {
                console.error('Error checking unlock status:', error);
                alert('Error checking unlock status. Please try again.');
            }
        });
    });
}

// Update initializeComponents to include error handling
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
        console.log('Run Health Check button clicked'); // Add this line
        const resultsDiv = document.getElementById('results');
        showLoadingState(resultsDiv);

        try {
            if (!client || !context || !metadata) {
                throw new Error('Client, context, or metadata not initialized');
            }

            const options = {
                url: 'https://gcx-healthcheck-zd-production.up.railway.app/check/',
                type: 'POST',
                contentType: 'application/json',
                data: JSON.stringify({
                    url: `${context.account.subdomain}.zendesk.com`,
                    email: '{{setting.admin_email}}',
                    api_token: '{{setting.api_token}}',
                    instance_guid: context.instanceGuid,
                    app_guid: metadata.appId,
                    installation_id: metadata.installationId,
                    subdomain: context.account.subdomain,
                    plan: metadata.plan?.name,
                    stripe_subscription_id: metadata.stripe_subscription_id,
                    version: metadata.version
                }),
                secure: true
            };

            const response = await client.request(options);
            console.log('Response:', response); // Add this line
            resultsDiv.innerHTML = response;
            initializeComponents();

        } catch (error) {
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
                const response = await fetch(`report/${this.dataset.reportId}/?installation_id=${metadata.installationId}`);
                if (response.ok) {
                    const data = await response.json();
                    resultsDiv.innerHTML = data.monitoring_html + data.results_html;
                    initializeComponents();
                } else {
                    throw new Error('Failed to load report');
                }
            } catch (error) {
                showError(resultsDiv, error, 'Error Loading Report');
            }
        });
    });
}

async function initializeApp() {
    try {
        client = window.ZAFClient ? window.ZAFClient.init() : null;
        if (!client) {
            console.error('ZAF Client could not be initialized');
            return;
        }

        console.log('ZAF Client initialized successfully');

        [context, metadata] = await Promise.all([
            client.context(),
            client.metadata()
        ]);

        console.log('Metadata:', metadata);

        const currentUrl = new URL(window.location.href);
        const urlInstallationId = currentUrl.searchParams.get('installation_id');
        const urlPlan = currentUrl.searchParams.get('plan');

        // If we don't have installation_id or plan in URL, add them and reload
        if (!urlInstallationId || !urlPlan) {
            currentUrl.searchParams.set('installation_id', metadata.installationId);
            currentUrl.searchParams.set('plan', metadata.plan?.name || 'Free');
            window.location.href = currentUrl.toString();
            return;
        }

        client.invoke('resize', { width: '100%', height: '800px' });
        
        initializeComponents();
        initializeRunCheck();
        initializeHistoricalReports();

    } catch (error) {
        console.error('Error initializing:', error);
    }
}

// Event Listeners
document.addEventListener('DOMContentLoaded', initializeApp);