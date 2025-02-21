let client = null;
let metadata = null;
let context = null;

// Initialize the app
function getBaseUrl() {
    const bodyElement = document.body;
    return bodyElement.getAttribute('data-environment') || 'https://gcx-healthcheck-zd-development.up.railway.app';
}

// Add this new function at the top with other utility functions
function showButtons(show = true) {
    const buttons = document.querySelectorAll('[data-preserve-params]');
    buttons.forEach(button => {
        if (show) {
            button.innerHTML = button.getAttribute('data-original-text');
            button.classList.remove('disabled');
            button.removeAttribute('disabled');
        } else {
            // Store original text if not already stored
            if (!button.getAttribute('data-original-text')) {
                button.setAttribute('data-original-text', button.innerHTML.trim());
            }
            button.innerHTML = `
                <span class="spinner-border spinner-border-sm" role="status"></span>
                <span class="ms-2">Loading...</span>
            `;
            button.classList.add('disabled');
            button.setAttribute('disabled', 'disabled');
        }
    });
}

// Add this function to handle chat widget injection
async function initializeChatWidget() {
    try {
        const baseUrl = getBaseUrl();
        const response = await fetch(`${baseUrl}/api/chat-widget/`);
        const data = await response.json();
        
        if (data.is_enabled && data.script) {
            // Create container if it doesn't exist
            let container = document.getElementById('chat-widget-container');
            if (!container) {
                container = document.createElement('div');
                container.id = 'chat-widget-container';
                document.body.appendChild(container);
            }
            
            // Create a new script element
            const scriptElement = document.createElement('script');
            
            // Preserve the type="module" attribute if present in the original script
            if (data.script.includes('type="module"')) {
                scriptElement.type = 'module';
            }
            
            // Set the script content
            scriptElement.textContent = data.script
                .replace(/<script[^>]*>|<\/script>/g, ''); // Remove script tags
            
            // Clear container and append new script
            container.innerHTML = '';
            container.appendChild(scriptElement);
        }
    } catch (error) {
        console.error('Error loading chat widget:', error);
    }
}

// Modify your existing initializeApp function
async function initializeApp() {
    try {
        showButtons(false);

        // Initialize ZAF client
        await ZAFClientSingleton.init();
        client = ZAFClientSingleton.client;
        metadata = ZAFClientSingleton.metadata;
        context = ZAFClientSingleton.context;

        if (!await ZAFClientSingleton.ensureUrlParams()) return;
        
        await URLParamManager.initializeParamPreservation();
        showButtons(true);

        // Initialize all components
        initializeRunCheck();
        initializeHistoricalReports();
        initializeComponents();
        
        // Initialize chat widget after everything else
        await initializeChatWidget();

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
    const statusFilter = document.getElementById('status-filter');
    
    if (!severityFilter || !categoryFilter) return;

    // Check if there are any active/inactive issues
    const issueRows = document.querySelectorAll('.issue-row');
    const hasStatusValues = Array.from(issueRows).some(row => row.dataset.status);

    // Hide status filter container if no status values exist
    if (statusFilter) {
        const statusFilterContainer = statusFilter.closest('.col-md-4');
        if (!hasStatusValues) {
            statusFilterContainer.style.display = 'none';
            // Adjust other columns to take full width
            const otherColumns = document.querySelectorAll('.filter-column');
            otherColumns.forEach(col => col.classList.remove('col-md-4'));
            otherColumns.forEach(col => col.classList.add('col-md-6'));
        }
    }

    function filterIssues() {
        const selectedSeverity = severityFilter.value;
        const selectedCategory = categoryFilter.value;
        const selectedStatus = statusFilter?.value || 'all';
        const issueRows = document.querySelectorAll('.issue-row');

        issueRows.forEach(row => {
            const severity = row.dataset.severity;
            const category = row.dataset.category;
            const status = row.dataset.status;
            const showSeverity = selectedSeverity === 'all' || severity === selectedSeverity;
            const showCategory = selectedCategory === 'all' || category === selectedCategory;
            const showStatus = selectedStatus === 'all' || status === selectedStatus;
            
            row.style.display = showSeverity && showCategory && showStatus ? '' : 'none';
        });

        adjustContentHeight();
    }

    severityFilter.addEventListener('change', filterIssues);
    categoryFilter.addEventListener('change', filterIssues);
    if (statusFilter && hasStatusValues) {
        statusFilter.addEventListener('change', filterIssues);
    }
}

function initializeUnlockButtons() {
    document.querySelectorAll('.unlock-report').forEach(button => {
        button.replaceWith(button.cloneNode(true));
        const newButton = document.querySelector(`.unlock-report[data-report-id="${button.dataset.reportId}"]`);

        if (newButton) {
            newButton.addEventListener('click', async function() {
                const reportId = this.dataset.reportId;
                
                try {
                    const baseUrl = getBaseUrl();

                    // Create a payment intent with report metadata
                    const response = await client.request({
                        url: `${baseUrl}/create-payment-intent/`,
                        type: 'POST',
                        data: JSON.stringify({
                            report_id: reportId,
                            installation_id: metadata.installationId,
                            user_id: ZAFClientSingleton.userInfo?.id
                        }),
                        secure: true
                    });

                    if (response.error) {
                        throw new Error(response.error);
                    }

                    // Open Stripe payment page
                    const windowFeatures = 'width=800,height=600,menubar=no,toolbar=no,location=no,status=no';
                    window.open(response.url, 'StripePayment', windowFeatures);

                    // Start polling for unlock status
                    const pollUnlockStatus = async () => {
                        try {
                            const statusResponse = await client.request({
                                url: `${baseUrl}/check-unlock-status/?report_id=${reportId}`,
                                type: 'GET',
                                secure: true
                            });

                            if (statusResponse.is_unlocked) {
                                // Refresh the report content
                                const reportResponse = await client.request({
                                    url: `${baseUrl}/report/${reportId}/?installation_id=${metadata.installationId}&user_id=${ZAFClientSingleton.userInfo?.id}`,
                                    type: 'GET',
                                    secure: true
                                });
                                
                                document.getElementById('results').innerHTML = reportResponse.results_html;
                                initializeComponents();
                                return true; // Stop polling
                            }
                            return false; // Continue polling
                        } catch (error) {
                            console.error('Error checking unlock status:', error);
                            return false;
                        }
                    };

                    // Poll every 2 seconds for up to 5 minutes
                    const maxAttempts = 150; // 5 minutes = 300 seconds / 2 seconds
                    let attempts = 0;
                    const pollInterval = setInterval(async () => {
                        attempts++;
                        const isUnlocked = await pollUnlockStatus();
                        if (isUnlocked || attempts >= maxAttempts) {
                            clearInterval(pollInterval);
                        }
                    }, 2000);

                } catch (error) {
                    console.error('Error creating payment:', error);
                    alert('Error creating payment. Please try again.');
                }
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

function updateLoadingProgress(progressBar, startTime, duration) {
    const elapsed = (Date.now() - startTime) / 1000; // Convert to seconds
    const progress = Math.min((elapsed / duration) * 100, 95); // Max at 95% until complete
    progressBar.style.width = `${progress}%`;
    progressBar.setAttribute('aria-valuenow', progress);
}

function initializeRunCheck() {
    const runCheckButton = document.getElementById('run-check');
    if (!runCheckButton) return;

    runCheckButton.addEventListener('click', async () => {
        const resultsDiv = document.getElementById('results');
        const startTime = Date.now();
        
        // Show loading state with progress bar
        resultsDiv.innerHTML = `
            <div class="results-container">
                <div class="text-center my-5">
                    <div class="spinner-border text-primary mb-3" role="status">
                        <span class="visually-hidden">Loading...</span>
                    </div>
                    <p class="text-muted mb-3">Running health check...</p>
                    <div class="progress" style="height: 20px;">
                        <div class="progress-bar progress-bar-striped progress-bar-animated" 
                             role="progressbar" 
                             aria-valuenow="0" 
                             aria-valuemin="0" 
                             aria-valuemax="100" 
                             style="width: 0%">
                        </div>
                    </div>
                </div>
            </div>
        `;

        const progressBar = resultsDiv.querySelector('.progress-bar');
        const progressInterval = setInterval(() => {
            updateLoadingProgress(progressBar, startTime, 90); // 90 seconds duration
        }, 100); // Update every 100ms for smooth animation


        try {
            if (!client || !context || !metadata) {
                throw new Error('Client, context, or metadata not initialized');
            }

            const baseUrl = getBaseUrl();
            const requestData = {
                url: context.account.subdomain,
                email: '{{setting.admin_email}}',
                api_token: '{{setting.api_token}}',
                instance_guid: context.instanceGuid,
                app_guid: metadata.appId,
                installation_id: metadata.installationId,
                user_id: ZAFClientSingleton.userInfo?.id,
                subdomain: context.account.subdomain,
                plan: metadata.plan?.name,
                stripe_subscription_id: metadata.stripe_subscription_id,
                version: metadata.version
            };

            const options = {
                url: `${baseUrl}/health_check/`,
                type: 'POST',
                contentType: 'application/json',
                data: JSON.stringify(requestData),
                secure: true,
                headers: {
                    'Accept': 'application/json',
                    'Content-Type': 'application/json',
                    'X-Subsequent-Request': 'true'
                }
            };

            // Make the initial request
           
            const response = await client.request(options);

            if (response.task_id) {
                let retryCount = 0;
                const maxRetries = 3;
                const maxPollingTime = 300000; // 5 minutes in milliseconds
                const startPollingTime = Date.now();

                const pollInterval = setInterval(async () => {
                    try {
                        // Check if we've exceeded maximum polling time
                        if (Date.now() - startPollingTime > maxPollingTime) {
                            clearInterval(pollInterval);
                            clearInterval(progressInterval);
                            showError(resultsDiv, new Error('Health check timed out. Please try again.'), 'Timeout Error');
                            return;
                        }

                        const statusResponse = await client.request({
                            url: `${baseUrl}/health_check/status/${response.task_id}/`,
                            type: 'GET',
                            secure: true
                        });
                        
                        if (statusResponse.status === 'complete') {
                            clearInterval(pollInterval);
                            clearInterval(progressInterval);
                            resultsDiv.innerHTML = statusResponse.results_html;
                            initializeComponents();
                        } else if (statusResponse.status === 'error') {
                            if (retryCount < maxRetries) {
                                retryCount++;
                                console.log(`Retrying... Attempt ${retryCount} of ${maxRetries}`);
                                // Continue polling on retriable errors
                                return;
                            }
                            clearInterval(pollInterval);
                            clearInterval(progressInterval);
                            showError(resultsDiv, new Error(statusResponse.error || 'Health check failed'), 'Health Check Error');
                        }
                        // Reset retry count on successful poll
                        retryCount = 0;
                    } catch (pollError) {
                        if (retryCount < maxRetries) {
                            retryCount++;
                            console.log(`Retrying after error... Attempt ${retryCount} of ${maxRetries}`);
                            return;
                        }
                        clearInterval(pollInterval);
                        clearInterval(progressInterval);
                        showError(resultsDiv, pollError, 'Polling Error');
                    }
                }, 3000); // Increased polling interval to 3 seconds
            } else {
                throw new Error(response.error || 'Unknown error occurred');
            }
        } catch (error) {
            clearInterval(progressInterval);
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
                const baseUrl = getBaseUrl();

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
document.addEventListener('DOMContentLoaded', () => {
    // Initialize chat widget regardless of page
    initializeChatWidget();
    
    // Only initialize if we're not on the monitoring page
    if (!document.getElementById('monitoring-form')) {
        initializeApp();
    }
});