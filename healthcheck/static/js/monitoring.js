document.addEventListener('DOMContentLoaded', () => {
    if (!document.getElementById('monitoring-form')) return;

    const form = document.getElementById('monitoring-form');
    const newEmailInput = document.getElementById('new_email');
    const currentEmails = document.getElementById('current-emails');
    const addEmailBtn = document.getElementById('add-email-btn');
    const frequencySelect = document.getElementById('frequency');
    const isActiveSwitch = document.getElementById('is_active');

    // Initialize ZAF Client
    ZAFClientSingleton.init().then(client => {
        // Remove Email Handler
        currentEmails.addEventListener('click', async (e) => {
            if (e.target.classList.contains('btn-close')) {
                const emailBadge = e.target.parentElement;
                const email = e.target.dataset.email;
                
                try {
                    // Save settings without this email
                    await saveSettings(client, emailBadge);
                    emailBadge.remove();
                    showMessage('success', '✅ Email removed successfully');
                } catch (error) {
                    showMessage('danger', '❌ Failed to remove email');
                }
            }
        });

        // Frequency Change Handler
        frequencySelect.addEventListener('change', async () => {
            try {
                await saveSettings(client);
                showMessage('success', '✅ Frequency updated successfully');
            } catch (error) {
                showMessage('danger', '❌ Failed to update frequency');
                // Revert to previous value if save failed
                frequencySelect.value = frequencySelect.dataset.lastValue || 'daily';
            }
            // Store current value for potential rollback
            frequencySelect.dataset.lastValue = frequencySelect.value;
        });

        // Active Status Change Handler
        isActiveSwitch.addEventListener('change', async () => {
            try {
                await saveSettings(client);
                showMessage('success', '✅ Monitoring status updated successfully');
            } catch (error) {
                showMessage('danger', '❌ Failed to update monitoring status');
                // Revert to previous state if save failed
                isActiveSwitch.checked = !isActiveSwitch.checked;
            }
        });

        // Form Submit Handler (for adding new email)
        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            
            const spinner = addEmailBtn.querySelector('.spinner-border');
            const btnText = addEmailBtn.querySelector('.btn-text');
            const email = newEmailInput.value.trim();

            // Validate email
            if (!validateEmail(email)) {
                showMessage('danger', 'Please enter a valid email address');
                return;
            }

            // Check if email already exists
            if (currentEmails.innerHTML.includes(email)) {
                showMessage('warning', 'This email is already added');
                return;
            }

            try {
                // Show loading state
                spinner.classList.remove('d-none');
                btnText.textContent = 'Adding...';
                addEmailBtn.disabled = true;

                // Create new badge
                const badge = document.createElement('div');
                badge.className = 'badge bg-light text-dark border mb-2 me-2 p-2';
                badge.innerHTML = `
                    ${email}
                    <button type="button" class="btn-close ms-2" data-email="${email}" aria-label="Remove"></button>
                `;

                // Save settings with new email
                await saveSettings(client, null, email);
                
                // Add badge and clear input
                currentEmails.appendChild(badge);
                newEmailInput.value = '';
                showMessage('success', '✅ Email added successfully');

            } catch (error) {
                console.error('Error saving settings:', error);
                showMessage('danger', `❌ ${error.message || 'Failed to add email'}. Please try again.`);
            } finally {
                spinner.classList.add('d-none');
                btnText.textContent = 'Add Email';
                addEmailBtn.disabled = false;
            }
        });
    });
});

async function saveSettings(client, removedBadge = null, newEmail = null) {
    // Get current emails
    const currentEmailBadges = Array.from(document.getElementById('current-emails').children);
    let emails = currentEmailBadges
        .filter(badge => badge !== removedBadge) // Exclude removed badge if any
        .map(badge => badge.textContent.trim());
    
    // Add new email if provided
    if (newEmail) {
        emails.push(newEmail);
    }

    const form = document.getElementById('monitoring-form');
    const data = {
        installation_id: form.querySelector('[name="installation_id"]').value,
        user_id: ZAFClientSingleton.userInfo?.id,
        is_active: form.querySelector('#is_active').checked,
        frequency: form.querySelector('#frequency').value,
        notification_emails: emails,
        redirect_url: window.location.href
    };

    // Validate at least one email if monitoring is active
    if (data.is_active && emails.length === 0) {
        throw new Error('Please add at least one email address when monitoring is active');
    }

    const baseUrl = window.ENVIRONMENT === 'production' 
        ? 'https://gcx-healthcheck-zd-production.up.railway.app'
        : 'https://gcx-healthcheck-zd-development.up.railway.app';

    return client.request({
        url: `${baseUrl}/monitoring-settings/`,
        type: 'POST',
        contentType: 'application/json',
        data: JSON.stringify(data),
        secure: true
    });
}

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