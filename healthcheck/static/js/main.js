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

function initializeComponents() {
    initializeFilters();
    initializeUnlockButtons();
    initializeMonitoringForm();
    adjustContentHeight();
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

// Component Initialization Functions
function initializeRunCheck() {
    const runCheckButton = document.getElementById('run-check');
    if (!runCheckButton) return;

    runCheckButton.addEventListener('click', async () => {
        const resultsDiv = document.getElementById('results');
        showLoadingState(resultsDiv);

        try {
            if (!client || !context || !metadata) {
                throw new Error('Client, context, or metadata not initialized');
            }

            const options = {
                url: 'check/',
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

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        const formData = new FormData(form);

        try {
            const response = await fetch('monitoring-settings/', {
                method: 'POST',
                body: formData
            });

            if (response.ok) {
                const html = await response.text();
                document.getElementById('monitoring-settings').outerHTML = html;
                initializeMonitoringForm();
            } else {
                throw new Error('Failed to save settings');
            }
        } catch (error) {
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