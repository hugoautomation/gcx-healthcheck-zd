let client = null;
let metadata = null;
let context = null;

// Initialize ZAF client
async function initializeApp() {
    try {
        // Wait a short moment before initializing ZAF client
        await new Promise(resolve => setTimeout(resolve, 100));
        
        client = window.ZAFClient ? window.ZAFClient.init() : null;
        if (!client) {
            console.warn('ZAF Client could not be initialized - running in standalone mode');
            initializeForm();
            return;
        }

        console.log('ZAF Client initialized successfully');

        [context, metadata] = await Promise.all([
            client.context(),
            client.metadata()
        ]);

        console.log('Metadata:', metadata);

        // Check URL parameters
        const currentUrl = new URL(window.location.href);
        const urlInstallationId = currentUrl.searchParams.get('installation_id');
        const urlPlan = currentUrl.searchParams.get('plan');

        if (!urlInstallationId || !urlPlan) {
            if (metadata) {
                currentUrl.searchParams.set('installation_id', metadata.installationId);
                currentUrl.searchParams.set('plan', metadata.plan?.name || 'Free');
                window.location.href = currentUrl.toString();
                return;
            }
        }

        // Resize the iframe
        await client.invoke('resize', { width: '100%', height: '800px' });
        
        // Initialize the form
        initializeForm();

    } catch (error) {
        console.error('Error initializing:', error);
        // Initialize form even if ZAF client fails
        initializeForm();
    }
}

function addEmailField(e) {
    e.preventDefault();
    const emailInputs = document.getElementById('email-inputs');
    const isFreePlan = document.getElementById('monitoring-form').dataset.isFreePlan === 'true';
    
    const template = `
        <div class="input-group mb-2">
            <input type="email" class="form-control notification-email" name="notification_emails[]" 
                   ${isFreePlan ? 'disabled' : ''}>
            <button type="button" class="btn c-btn c-btn--danger remove-email">-</button>
        </div>`;
    
    const lastInputGroup = emailInputs.lastElementChild;
    lastInputGroup.insertAdjacentHTML('beforebegin', template);
}

function removeEmailField(e) {
    e.preventDefault();
    e.target.closest('.input-group').remove();
}


function initializeForm() {
    const form = document.getElementById('monitoring-form');
    if (!form) return;

    // Add email field handler
    document.querySelectorAll('.add-email').forEach(button => {
        button.removeEventListener('click', addEmailField);
        button.addEventListener('click', addEmailField);
    });

    // Remove email field handler - Use event delegation
    document.getElementById('email-inputs').addEventListener('click', (e) => {
        if (e.target.classList.contains('remove-email')) {
            removeEmailField(e);
        }
    });
    
    const saveButton = document.getElementById('save-settings-btn');
    if (saveButton) {
        form.addEventListener('submit', async function(e) {
            e.preventDefault();
            
            const spinner = saveButton.querySelector('.spinner-border');
            const btnText = saveButton.querySelector('.btn-text');
            
            try {
                // Show loading state
                spinner.classList.remove('d-none');
                btnText.textContent = 'Saving...';
                saveButton.disabled = true;

                // Get all valid emails
                const emailInputs = form.querySelectorAll('.notification-email');
                const validEmails = Array.from(emailInputs)
                    .filter(input => input.value.trim() !== '')
                    .map(input => input.value.trim());

                // Create FormData
                const formData = new FormData(form);

                // Remove existing email fields and add valid ones back
                for (const pair of formData.entries()) {
                    if (pair[0] === 'notification_emails[]') {
                        formData.delete(pair[0]);
                    }
                }

                validEmails.forEach(email => {
                    formData.append('notification_emails[]', email);
                });

                // Submit form
                const response = await fetch(form.action, {
                    method: 'POST',
                    body: formData
                });

                if (!response.ok) {
                    throw new Error('Failed to save settings');
                }

                // Show success message
                const alertHtml = `
                    <div class="alert alert-success alert-dismissible fade show" role="alert">
                        Settings saved successfully
                        <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
                    </div>`;
                const messagesDiv = document.querySelector('.messages');
                if (messagesDiv) {
                    messagesDiv.innerHTML = alertHtml;
                }

                // Reset button state
                spinner.classList.add('d-none');
                btnText.textContent = 'Save Settings';
                saveButton.disabled = false;

            } catch (error) {
                console.error('Error saving settings:', error);
                // Reset button state
                spinner.classList.add('d-none');
                btnText.textContent = 'Save Settings';
                saveButton.disabled = false;

                // Show error message
                const alertHtml = `
                    <div class="alert alert-danger alert-dismissible fade show" role="alert">
                        Failed to save settings. Please try again.
                        <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
                    </div>`;
                const messagesDiv = document.querySelector('.messages');
                if (messagesDiv) {
                    messagesDiv.innerHTML = alertHtml;
                }
            }
        });
    }
}

// Initialize on DOM load
document.addEventListener('DOMContentLoaded', initializeApp);