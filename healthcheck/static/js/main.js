let client = null;
let metadata = null;
let context = null;

document.addEventListener('DOMContentLoaded', async function() {
    try {
        // Initialize ZAF client
        client = window.ZAFClient ? window.ZAFClient.init() : null;
        
        if (!client) {
            console.error('ZAF Client could not be initialized');
            return;
        }

        console.log('ZAF Client initialized successfully');

        // Get metadata and context at startup
        [context, metadata] = await Promise.all([
            client.context(),
            client.metadata()
        ]);
        
        console.log('Metadata:', metadata);
        
        // Check if installation_id is already in URL
        const currentUrl = new URL(window.location.href);
        const urlInstallationId = currentUrl.searchParams.get('installation_id');
        
        if (!urlInstallationId) {
            // If not in URL, add it and reload
            currentUrl.searchParams.set('installation_id', metadata.installationId);
            window.location.href = currentUrl.toString();
            return;
        }

        // Initial resize
        client.invoke('resize', { width: '100%', height: '800px' });

        // Initialize components
        initializeFilters();
        initializeUnlockButtons();
        initializeRunCheck();

    } catch (error) {
        console.error('Error initializing:', error);
    }
});

function initializeRunCheck() {
    const runCheckButton = document.getElementById('run-check');
    if (!runCheckButton) return;

    runCheckButton.addEventListener('click', async () => {
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

            console.log('Sending request to /check/...');
            const response = await client.request(options);
            
            console.log('Response:', response);
            resultsDiv.innerHTML = response;

            // Initialize filters and unlock buttons after content is loaded
            initializeFilters();
            initializeUnlockButtons();

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
            console.error('Health check error:', error);
            resultsDiv.innerHTML = `
                <div class="alert alert-danger" role="alert">
                    <h5>Error Running Health Check</h5>
                    <p>${error.message || 'An unexpected error occurred. Please try again.'}</p>
                </div>
            `;
        }
    });
}

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

    // Save filter states when changed
    document.addEventListener('change', function(e) {
        if (e.target.id === 'severity-filter') {
            localStorage.setItem('severity_filter', e.target.value);
        } else if (e.target.id === 'category-filter') {
            localStorage.setItem('category_filter', e.target.value);
        }
    });
}

// Initialize unlock buttons
function initializeUnlockButtons() {
    document.querySelectorAll('.unlock-report').forEach(button => {
        // Remove existing event listeners to prevent duplicates
        button.replaceWith(button.cloneNode(true));
        
        // Get the fresh button reference after replacement
        const newButton = document.querySelector(`.unlock-report[data-report-id="${button.dataset.reportId}"]`);
        
        if (newButton) {
            newButton.addEventListener('click', function() {
                const reportId = this.dataset.reportId;
                const stripePaymentLink = `https://buy.stripe.com/dR68zbfDvboy7mweUU?client_reference_id=${reportId}`;
                
                // Define window features
                const windowFeatures = 'width=800,height=600,menubar=no,toolbar=no,location=no,status=no';
                
                // Open the payment window
                const paymentWindow = window.open(stripePaymentLink, 'StripePayment', windowFeatures);
                
                // Start polling for unlock status
                const pollInterval = setInterval(async () => {
                    try {
                        const response = await fetch(`/check-unlock-status/?report_id=${reportId}`);
                        const data = await response.json();
                        
                        if (response.ok && data.is_unlocked) {
                            // Report is unlocked, update the content
                            document.getElementById('results').innerHTML = data.html;
                            // Reinitialize filters and unlock buttons after content update
                            initializeFilters();
                            initializeUnlockButtons();
                            clearInterval(pollInterval);
                        }
                    } catch (error) {
                        console.error('Error checking unlock status:', error);
                    }
                }, 2000);

                // Stop polling if the payment window is closed
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





// Remove email input field
document.addEventListener('click', function(e) {
    if (e.target.classList.contains('remove-email')) {
        e.target.closest('.input-group').remove();
    }
});

// Handle form submission
document.getElementById('monitoring-form')?.addEventListener('submit', async function(e) {
    e.preventDefault();
    
    const formData = {
        is_active: document.getElementById('is_active').checked,
        frequency: document.getElementById('frequency').value,
        notification_emails: Array.from(document.getElementsByName('notification_emails[]'))
            .map(input => input.value)
            .filter(email => email.trim() !== '')
    };

    try {
        const response = await fetch('/monitoring-settings/?installation_id=' + installationId, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(formData)
        });

        if (response.ok) {
            alert('Settings saved successfully!');
        } else {
            throw new Error('Failed to save settings');
        }
    } catch (error) {
        alert('Error saving settings: ' + error.message);
    }
});

// Load existing settings
async function loadMonitoringSettings() {
    try {
        const response = await fetch('/monitoring-settings/?installation_id=' + installationId);
        if (response.ok) {
            const settings = await response.json();
            document.getElementById('is_active').checked = settings.is_active;
            document.getElementById('frequency').value = settings.frequency;
            
            // Clear existing email inputs
            const emailInputs = document.getElementById('email-inputs');
            emailInputs.innerHTML = '';
            
            // Add email inputs for existing emails
            settings.notification_emails.forEach(email => {
                const input = document.createElement('div');
                input.className = 'input-group mb-2';
                input.innerHTML = `
                    <input type="email" class="form-control" name="notification_emails[]" value="${email}">
                    <div class="input-group-append">
                        <button type="button" class="btn btn-danger remove-email">-</button>
                    </div>
                `;
                emailInputs.appendChild(input);
            });
        }
    } catch (error) {
        console.error('Error loading monitoring settings:', error);
    }
}

// Load settings when form exists
if (document.getElementById('monitoring-form')) {
    loadMonitoringSettings();
}