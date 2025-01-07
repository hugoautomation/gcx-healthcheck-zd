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
            console.log('Form submission started');
            
            const spinner = saveButton.querySelector('.spinner-border');
            const btnText = saveButton.querySelector('.btn-text');
            
            try {
                spinner.classList.remove('d-none');
                btnText.textContent = 'Saving...';
                saveButton.disabled = true;

                // Get all valid emails
                const emailInputs = form.querySelectorAll('.notification-email');
                const validEmails = Array.from(emailInputs)
                    .filter(input => input.value.trim() !== '')
                    .map(input => input.value.trim());

                // Get base URL based on environment
                const baseUrl = window.ENVIRONMENT === 'production' 
                    ? 'https://gcx-healthcheck-zd-production.up.railway.app'
                    : 'https://gcx-healthcheck-zd-production.up.railway.app';

                // Create data object from form
                const formData = new FormData(form);
                const data = {
                    installation_id: formData.get('installation_id'),
                    user_id: ZAFClientSingleton.userInfo?.id,  // Add user_id
                    is_active: formData.get('is_active') === 'on',
                    frequency: formData.get('frequency'),
                    notification_emails: validEmails,
                    redirect_url: window.location.href
                };

                console.log('Sending data:', data);

                // Submit form using client.request with environment-aware URL
                const options = {
                    url: `${baseUrl}/monitoring-settings/`,
                    type: 'POST',
                    contentType: 'application/json',
                    data: JSON.stringify(data),
                    secure: true
                };

                const response = await client.request(options);
                console.log('Response:', response);

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
                
                // Show detailed error message
                const errorMessage = error.responseJSON?.error || error.message || 'Failed to save settings';
                const alertHtml = `
                    <div class="alert alert-danger alert-dismissible fade show" role="alert">
                        ${errorMessage}. Please try again.
                        <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
                    </div>`;
                const messagesDiv = document.querySelector('.messages');
                if (messagesDiv) {
                    messagesDiv.innerHTML = alertHtml;
                }
            } finally {
                spinner.classList.add('d-none');
                btnText.textContent = 'Save Settings';
                saveButton.disabled = false;
            }
        });
    }
}

// Initialize on DOM load
document.addEventListener('DOMContentLoaded', initializeApp);