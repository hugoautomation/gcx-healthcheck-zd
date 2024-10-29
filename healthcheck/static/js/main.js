let client = null;
let metadata = null;
let context = null;

// Utility Functions
function adjustContentHeight() {
    if (!client) return;
    
    setTimeout(() => {
        const contentHeight = Math.min(
            Math.max(
                document.getElementById('results').scrollHeight,
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
        initializeMonitoringForm();
        adjustContentHeight();
    } catch (error) {
        console.error('Error initializing components:', error);
    }
}

// Plan Change Handler
async function handlePlanChange(data) {
    try {
        const response = await fetch('/update-installation-plan/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                installation_id: metadata.installationId,
                plan: data.newPlan
            })
        });

        if (response.ok) {
            const monitoringSettings = document.getElementById('monitoring-settings');
            if (monitoringSettings) {
                const settingsResponse = await fetch(`/monitoring-settings/?installation_id=${metadata.installationId}`);
                if (settingsResponse.ok) {
                    const html = await settingsResponse.text();
                    monitoringSettings.outerHTML = html;
                    initializeMonitoringForm();
                }
            }
        }
    } catch (error) {
        console.error('Error updating plan:', error);
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

function initializeMonitoringForm() {
    const form = document.getElementById('monitoring-form');
    if (!form) return;

    // Handle email input buttons
    const emailInputs = document.getElementById('email-inputs');
    if (emailInputs) {
        emailInputs.addEventListener('click', (e) => {
            if (e.target.classList.contains('add-email')) {
                const template = `
                    <div class="input-group mb-2">
                        <input type="email" class="form-control" name="notification_emails[]" 
                               ${form.dataset.isFreePlan === 'true' ? 'disabled' : ''}>
                        <button type="button" class="btn c-btn c-btn--danger remove-email">-</button>
                    </div>`;
                e.target.closest('.input-group').insertAdjacentHTML('beforebegin', template);
            } else if (e.target.classList.contains('remove-email')) {
                e.target.closest('.input-group').remove();
            }
            adjustContentHeight();
        });
    }

    // Handle form submission
    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        try {
            const formData = new FormData(form);
            const response = await fetch('monitoring-settings/', {
                method: 'POST',
                body: formData
            });

            if (!response.ok) throw new Error('Failed to save settings');
            
            const html = await response.text();
            const tempDiv = document.createElement('div');
            tempDiv.innerHTML = html;
            
            // Replace the entire monitoring settings section
            const oldSettings = document.getElementById('monitoring-settings');
            oldSettings.replaceWith(tempDiv.firstElementChild);
            
            // Reinitialize the form
            initializeMonitoringForm();
            adjustContentHeight();
            
        } catch (error) {
            console.error('Error saving settings:', error);
            alert('Error saving settings: ' + error.message);
        }
    });
}

// Main Initialization
async function initializeApp() {
    try {
        client = window.ZAFClient ? window.ZAFClient.init() : null;
        if (!client) {
            console.error('ZAF Client could not be initialized');
            return;
        }

        client.on('plan.changed', handlePlanChange);
        console.log('ZAF Client initialized successfully');

        [context, metadata] = await Promise.all([
            client.context(),
            client.metadata()
        ]);

        console.log('Metadata:', metadata);

        const currentUrl = new URL(window.location.href);
        const urlInstallationId = currentUrl.searchParams.get('installation_id');

        if (!urlInstallationId) {
            currentUrl.searchParams.set('installation_id', metadata.installationId);
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