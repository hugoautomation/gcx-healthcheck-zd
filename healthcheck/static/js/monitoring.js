// Use a monitoring-specific namespace to avoid conflicts
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
            
            await URLParamManager.initializeParamPreservation();
            await this.client.invoke('resize', { width: '100%', height: '800px' });
            
            this.initializeForm();

        } catch (error) {
            console.error('Error initializing monitoring:', error);
            this.initializeForm(); // Initialize form even if ZAF client fails
        }
    },

    initializeForm() {
        const form = document.getElementById('monitoring-form');
        if (!form) return;

        // Initialize email management
        this.initializeEmailManagement();
        
        // Handle form submission
        const saveButton = document.getElementById('save-settings-btn');
        if (saveButton) {
            form.addEventListener('submit', async (e) => {
                e.preventDefault();
                await this.handleFormSubmission(form, saveButton);
            });
        }
    },

    initializeEmailManagement() {
        // Add email button handler
        document.getElementById('add-email-btn').addEventListener('click', () => {
            const newEmailInput = document.getElementById('new_email');
            const email = newEmailInput.value.trim();
            
            if (email && this.validateEmail(email)) {
                this.addEmailBadge(email);
                newEmailInput.value = '';
            }
        });

        // Remove email badge handler
        document.getElementById('current-emails').addEventListener('click', (e) => {
            if (e.target.classList.contains('btn-close')) {
                e.target.closest('.badge').remove();
            }
        });
    },

    validateEmail(email) {
        return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
    },

    addEmailBadge(email) {
        const currentEmails = document.getElementById('current-emails');
        const badge = document.createElement('div');
        badge.className = 'badge bg-light text-dark border mb-2 me-2 p-2';
        badge.innerHTML = `
            ${email}
            <button type="button" class="btn-close ms-2" data-email="${email}" aria-label="Remove"></button>
        `;
        currentEmails.appendChild(badge);
    },

    async handleFormSubmission(form, saveButton) {
        const spinner = saveButton.querySelector('.spinner-border');
        const btnText = saveButton.querySelector('.btn-text');
        
        try {
            spinner.classList.remove('d-none');
            btnText.textContent = 'Saving...';
            saveButton.disabled = true;

            // Collect all emails from badges
            const emailBadges = document.querySelectorAll('#current-emails .badge');
            const emails = Array.from(emailBadges).map(badge => 
                badge.textContent.trim().replace('×', '').trim()
            );

            const formData = {
                installation_id: this.metadata?.installationId,
                user_id: ZAFClientSingleton.userInfo?.id,
                is_active: form.querySelector('#is_active').checked,
                frequency: form.querySelector('#frequency').value,
                notification_emails: emails
            };

            const baseUrl = getBaseUrl();
            // Use direct URL instead of URLParamManager
            const response = await this.client.request({
                url: `${baseUrl}/monitoring-settings/`,
                type: 'POST',
                contentType: 'application/json',
                data: JSON.stringify(formData),
                secure: true
            });

            this.showMessage('Settings saved successfully', 'success');

        } catch (error) {
            console.error('Error saving settings:', error);
            this.showMessage(error.responseJSON?.error || 'Failed to save settings', 'danger');
        } finally {
            spinner.classList.add('d-none');
            btnText.textContent = 'Save Settings';
            saveButton.disabled = false;
        }
    },

    showMessage(message, type) {
        const messagesDiv = document.querySelector('.messages');
        if (messagesDiv) {
            messagesDiv.innerHTML = `
                <div class="alert alert-${type} alert-dismissible fade show" role="alert">
                    ${message}
                    <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
                </div>`;
        }
    }
};

// Initialize on DOM load
document.addEventListener('DOMContentLoaded', () => MonitoringApp.initialize());