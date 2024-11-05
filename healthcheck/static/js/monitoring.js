let client = null;
let metadata = null;
let context = null;

// Initialize ZAF client
async function initializeApp() {
    try {
        await ZAFClientSingleton.init();
        client = ZAFClientSingleton.client;
        metadata = ZAFClientSingleton.metadata;
        context = ZAFClientSingleton.context;

        if (!await ZAFClientSingleton.ensureUrlParams()) return;

        await client.invoke('resize', { width: '100%', height: '800px' });
        
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

                // Create data object from form
                const formData = new FormData(form);
                const data = {};
                
                // Convert FormData to object, excluding email fields
                for (const [key, value] of formData.entries()) {
                    if (key !== 'notification_emails[]') {
                        data[key] = value;
                    }
                }

                // Add valid emails array
                data.notification_emails = validEmails;

                // Submit form using client.request
                const options = {
                    url: 'https://gcx-healthcheck-zd-production.up.railway.app/monitoring-settings/',
                    type: 'POST',
                    contentType: 'application/json',
                    data: JSON.stringify(data),
                    secure: true
                };

                await client.request(options);

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

            } catch (error) {
                console.error('Error saving settings:', error);
                
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
            } finally {
                // Reset button state
                spinner.classList.add('d-none');
                btnText.textContent = 'Save Settings';
                saveButton.disabled = false;
            }
        });
    }
}

// Initialize on DOM load
document.addEventListener('DOMContentLoaded', initializeApp);