document.addEventListener('DOMContentLoaded', async () => {
    if (!document.getElementById('monitoring-form')) return;

    const form = document.getElementById('monitoring-form');
    const newEmailInput = document.getElementById('new_email');
    const currentEmails = document.getElementById('current-emails');
    const addEmailBtn = document.getElementById('add-email-btn');
    const frequencySelect = document.getElementById('frequency');
    const isActiveSwitch = document.getElementById('is_active');

    try {
        // Initialize ZAF client and wait for it to be ready
        await ZAFClientSingleton.init();
        const client = ZAFClientSingleton.client;

        if (!await ZAFClientSingleton.ensureUrlParams()) return;

        // Resize the app
        await client.invoke('resize', { width: '100%', height: '800px' });

        // Remove Email Handler
        currentEmails.addEventListener('click', async (e) => {
            if (e.target.classList.contains('btn-close')) {
                const emailBadge = e.target.parentElement;
                const email = e.target.dataset.email;
                
                try {
                    await saveSettings(client, emailBadge);
                    emailBadge.remove();
                    showMessage('success', '✅ Email removed successfully');
                } catch (error) {
                    showMessage('danger', '❌ Failed to remove email');
                }
            }
        });

        // Form Submit Handler (for adding new email)
        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            
            const email = newEmailInput.value.trim();
            if (!validateEmail(email)) {
                showMessage('danger', 'Please enter a valid email address');
                return;
            }

            if (currentEmails.innerHTML.includes(email)) {
                showMessage('warning', 'This email is already added');
                return;
            }

            const spinner = addEmailBtn.querySelector('.spinner-border');
            const btnText = addEmailBtn.querySelector('.btn-text');

            try {
                spinner.classList.remove('d-none');
                btnText.textContent = 'Adding...';
                addEmailBtn.disabled = true;

                await saveSettings(client, null, email);
                
                const badge = document.createElement('div');
                badge.className = 'badge bg-light text-dark border mb-2 me-2 p-2';
                badge.innerHTML = `
                    ${email}
                    <button type="button" class="btn-close ms-2" data-email="${email}" aria-label="Remove"></button>
                `;
                
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

        // Auto-save handlers for frequency and active status
        frequencySelect.addEventListener('change', async () => {
            try {
                await saveSettings(client);
                showMessage('success', '✅ Frequency updated successfully');
            } catch (error) {
                showMessage('danger', '❌ Failed to update frequency');
                frequencySelect.value = frequencySelect.dataset.lastValue || 'daily';
            }
            frequencySelect.dataset.lastValue = frequencySelect.value;
        });

        isActiveSwitch.addEventListener('change', async () => {
            try {
                await saveSettings(client);
                showMessage('success', '✅ Monitoring status updated successfully');
            } catch (error) {
                showMessage('danger', '❌ Failed to update monitoring status');
                isActiveSwitch.checked = !isActiveSwitch.checked;
            }
        });

    } catch (error) {
        console.error('Error initializing monitoring:', error);
        showMessage('danger', '❌ Failed to initialize monitoring settings');
    }
});

async function saveSettings(client, removedBadge = null, newEmail = null) {
    const form = document.getElementById('monitoring-form');
    const currentEmails = document.getElementById('current-emails');
    
    // Get current emails
    let emails = Array.from(currentEmails.children)
        .filter(badge => badge !== removedBadge)
        .map(badge => badge.textContent.trim());
    
    // Add new email if provided
    if (newEmail) {
        emails.push(newEmail);
    }

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

    messagesDiv.querySelectorAll('.alert').forEach(alert => alert.remove());

    const alert = document.createElement('div');
    alert.className = `alert alert-${type} alert-dismissible fade show`;
    alert.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
    `;
    
    messagesDiv.appendChild(alert);
    messagesDiv.scrollIntoView({ behavior: 'smooth', block: 'start' });

    setTimeout(() => {
        alert.classList.remove('show');
        setTimeout(() => alert.remove(), 150);
    }, 5000);
}