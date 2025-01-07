document.addEventListener('DOMContentLoaded', () => {
    if (!document.getElementById('monitoring-form')) return;

    const form = document.getElementById('monitoring-form');
    const addEmailBtn = document.getElementById('add-email-btn');
    const newEmailInput = document.getElementById('new_email');
    const currentEmails = document.getElementById('current-emails');
    const saveButton = document.getElementById('save-settings-btn');

    // Initialize ZAF Client
    ZAFClientSingleton.init().then(client => {
        // Add Email Handler
        addEmailBtn.addEventListener('click', () => {
            const email = newEmailInput.value.trim();
            if (!validateEmail(email)) {
                showMessage('danger', 'Please enter a valid email address');
                return;
            }

            // Check if email already exists
            if (currentEmails.innerHTML.includes(email)) {
                showMessage('warning', 'This email is already added');
                return;
            }

            // Add new email badge
            const badge = document.createElement('div');
            badge.className = 'badge bg-light text-dark border mb-2 me-2 p-2';
            badge.innerHTML = `
                ${email}
                <button type="button" class="btn-close ms-2" data-email="${email}" aria-label="Remove"></button>
            `;
            currentEmails.appendChild(badge);
            newEmailInput.value = '';
        });

        // Remove Email Handler
        currentEmails.addEventListener('click', (e) => {
            if (e.target.classList.contains('btn-close')) {
                e.target.parentElement.remove();
            }
        });

        // Form Submit Handler
        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            
            const spinner = saveButton.querySelector('.spinner-border');
            const btnText = saveButton.querySelector('.btn-text');
            
            try {
                // Show loading state
                spinner.classList.remove('d-none');
                btnText.textContent = 'Saving...';
                saveButton.disabled = true;
        
                // Get all current emails
                const emails = Array.from(currentEmails.children).map(badge => 
                    badge.textContent.trim()
                );
                // Validate at least one email if monitoring is active
                const isActive = form.querySelector('#is_active').checked;
                if (isActive && emails.length === 0) {
                    throw new Error('Please add at least one email address when monitoring is active');
                }

                // Create data object
                const data = {
                    installation_id: form.querySelector('[name="installation_id"]').value,
                    user_id: ZAFClientSingleton.userInfo?.id,
                    is_active: isActive,
                    frequency: form.querySelector('#frequency').value,
                    notification_emails: emails,
                    redirect_url: window.location.href
                };

                // Submit form
                const baseUrl = window.ENVIRONMENT === 'production' 
                    ? 'https://gcx-healthcheck-zd-production.up.railway.app'
                    : 'https://gcx-healthcheck-zd-development.up.railway.app';

                    const response = await client.request({
                        url: `${baseUrl}/monitoring-settings/`,
                        type: 'POST',
                        contentType: 'application/json',
                        data: JSON.stringify(data),
                        secure: true
                    });
            
                    // Instead of showing message, reload the page
                    window.location.reload();
            
                } catch (error) {
                    console.error('Error saving settings:', error);
                    showMessage('danger', `❌ ${error.message || 'Failed to save settings'}. Please try again.`);
                    
                    // Reset button state on error
                    spinner.classList.add('d-none');
                    btnText.textContent = 'Save Settings';
                    saveButton.disabled = false;
                }
            });
    });
});

function validateEmail(email) {
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
}

function showMessage(type, message) {
    const messagesDiv = document.querySelector('.messages');
    if (!messagesDiv) return;

    // Remove existing messages
    messagesDiv.querySelectorAll('.alert').forEach(alert => alert.remove());

    // Add new message
    const alert = document.createElement('div');
    alert.className = `alert alert-${type} alert-dismissible fade show`;
    alert.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
    `;
    
    messagesDiv.appendChild(alert);
    messagesDiv.scrollIntoView({ behavior: 'smooth', block: 'start' });

    // Auto-dismiss after 5 seconds
    setTimeout(() => {
        alert.classList.remove('show');
        setTimeout(() => alert.remove(), 150);
    }, 5000);
}