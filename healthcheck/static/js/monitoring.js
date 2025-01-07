// Initialize ZAF client singleton for monitoring
const MonitoringApp = {
    client: null,
    metadata: null,
    context: null,

    async initialize() {
        try {
            await ZAFClientSingleton.init();
            this.client = ZAFClientSingleton.client;
            this.metadata = ZAFClientSingleton.metadata;
            this.context = ZAFClientSingleton.context;

            if (!await ZAFClientSingleton.ensureUrlParams()) return;

            await this.client.invoke('resize', { width: '100%', height: '800px' });
            
            this.initializeForm();

        } catch (error) {
            console.error('Error initializing monitoring:', error);
            this.initializeForm();
        }
    },

    initializeForm() {
        const form = document.getElementById('monitoring-form');
        if (!form) return;

        // Add email field handler
        document.querySelectorAll('.add-email').forEach(button => {
            button.removeEventListener('click', this.addEmailField);
            button.addEventListener('click', this.addEmailField);
        });

        // Remove email field handler - Use event delegation
        document.getElementById('email-inputs').addEventListener('click', (e) => {
            if (e.target.classList.contains('remove-email')) {
                this.removeEmailField(e);
            }
        });
        
        const saveButton = document.getElementById('save-settings-btn');
        if (saveButton) {
            form.addEventListener('submit', async (e) => {
                e.preventDefault();
                console.log('Form submission started');
                
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
                        .map(input => input.value.trim())
                        .filter(email => email !== '' && this.validateEmail(email));

                    // Validate at least one email if monitoring is active
                    const isActive = form.querySelector('#is_active').checked;
                    if (isActive && validEmails.length === 0) {
                        throw new Error('Please add at least one valid email address when monitoring is active');
                    }

                    // Get base URL based on environment
                    const baseUrl = window.ENVIRONMENT === 'production' 
                        ? 'https://gcx-healthcheck-zd-production.up.railway.app'
                        : 'https://gcx-healthcheck-zd-development.up.railway.app';

                    // Create data object from form
                    const formData = new FormData(form);
                    const data = {
                        installation_id: formData.get('installation_id'),
                        user_id: ZAFClientSingleton.userInfo?.id,
                        is_active: formData.get('is_active') === 'on',
                        frequency: formData.get('frequency'),
                        notification_emails: validEmails,
                        redirect_url: window.location.href
                    };

                    console.log('Sending data:', data);

                    // Submit form using client.request
                    const options = {
                        url: `${baseUrl}/monitoring-settings/`,
                        type: 'POST',
                        contentType: 'application/json',
                        data: JSON.stringify(data),
                        secure: true
                    };

                    const response = await this.client.request(options);
                    console.log('Response:', response);

                    // Show success message with emoji
                    this.showMessage('success', '✅ Settings saved successfully!');

                } catch (error) {
                    console.error('Error saving settings:', error);
                    
                    // Show error message
                    const errorMessage = error.responseJSON?.error || error.message || 'Failed to save settings';
                    this.showMessage('danger', `❌ ${errorMessage}. Please try again.`);
                } finally {
                    // Reset button state
                    spinner.classList.add('d-none');
                    btnText.textContent = 'Save Settings';
                    saveButton.disabled = false;
                }
            });
        }
    },

    addEmailField(e) {
        e.preventDefault();
        const emailInputs = document.getElementById('email-inputs');
        
        // Create new input group
        const newInputGroup = document.createElement('div');
        newInputGroup.className = 'input-group mb-2';
        newInputGroup.innerHTML = `
            <input type="email" class="form-control notification-email" name="notification_emails[]" required>
            <button type="button" class="btn c-btn c-btn--danger remove-email">-</button>
        `;
        
        // Insert before the last input group
        const lastInputGroup = emailInputs.lastElementChild;
        emailInputs.insertBefore(newInputGroup, lastInputGroup);

        // Focus the new input
        const newInput = newInputGroup.querySelector('input');
        newInput.focus();
    },

    removeEmailField(e) {
        e.preventDefault();
        const inputGroup = e.target.closest('.input-group');
        if (inputGroup) {
            inputGroup.style.transition = 'opacity 0.15s ease-out';
            inputGroup.style.opacity = '0';
            setTimeout(() => inputGroup.remove(), 150);
        }
    },

    validateEmail(email) {
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        return emailRegex.test(email.trim());
    },

    showMessage(type, message) {
        // Remove any existing messages
        const existingMessages = document.querySelectorAll('.alert');
        existingMessages.forEach(msg => msg.remove());

        // Create new message
        const alertHtml = `
            <div class="alert alert-${type} alert-dismissible fade show" role="alert">
                ${message}
                <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
            </div>`;
        
        const messagesDiv = document.querySelector('.messages');
        if (messagesDiv) {
            messagesDiv.innerHTML = alertHtml;
            
            // Scroll to message
            messagesDiv.scrollIntoView({ behavior: 'smooth', block: 'start' });
            
            // Auto-dismiss after 5 seconds
            setTimeout(() => {
                const alert = messagesDiv.querySelector('.alert');
                if (alert) {
                    alert.classList.remove('show');
                    setTimeout(() => alert.remove(), 150);
                }
            }, 5000);
        }
    }
};

// Initialize on DOM load
document.addEventListener('DOMContentLoaded', () => {
    // Only initialize if we're on the monitoring page
    if (document.getElementById('monitoring-form')) {
        MonitoringApp.initialize();
    }
});