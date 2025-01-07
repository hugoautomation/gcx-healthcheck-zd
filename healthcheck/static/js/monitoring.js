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
                e.preventDefault(); // Add this
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

        // Frequency Change Handler
        frequencySelect.addEventListener('change', async (e) => {
            e.preventDefault(); // Add this
            try {
                await saveSettings(client);
                showMessage('success', '✅ Frequency updated successfully');
            } catch (error) {
                showMessage('danger', '❌ Failed to update frequency');
                frequencySelect.value = frequencySelect.dataset.lastValue || 'daily';
            }
            frequencySelect.dataset.lastValue = frequencySelect.value;
        });

        // Active Status Change Handler
        isActiveSwitch.addEventListener('change', async (e) => {
            e.preventDefault(); // Add this
            try {
                await saveSettings(client);
                showMessage('success', '✅ Monitoring status updated successfully');
            } catch (error) {
                showMessage('danger', '❌ Failed to update monitoring status');
                isActiveSwitch.checked = !isActiveSwitch.checked;
            }
        });

        // Form Submit Handler
        form.addEventListener('submit', async (e) => {
            e.preventDefault(); // This was already here, good!
            
            const email = newEmailInput.value.trim();
            if (!validateEmail(email)) {
                showMessage('danger', 'Please enter a valid email address');
                return;
            }

            if (currentEmails.innerHTML.includes(email)) {
                showMessage('warning', 'This email is already added');
                return;
            }

            addEmailBtn.disabled = true;
            
            try {
                const badge = document.createElement('div');
                badge.className = 'badge bg-light text-dark border mb-2 me-2 p-2';
                badge.innerHTML = `
                    ${email}
                    <button type="button" class="btn-close ms-2" data-email="${email}" aria-label="Remove"></button>
                `;

                await saveSettings(client, null, email);
                
                currentEmails.appendChild(badge);
                newEmailInput.value = '';
                showMessage('success', '✅ Email added successfully');

            } catch (error) {
                console.error('Error saving settings:', error);
                showMessage('danger', '❌ Failed to add email. Please try again.');
            } finally {
                addEmailBtn.disabled = false;
            }
        });
    });
});

async function saveSettings(client, removedBadge = null, newEmail = null) {
    const form = document.getElementById('monitoring-form');
    const currentEmails = document.getElementById('current-emails');
    
    let emails = Array.from(currentEmails.children)
        .filter(badge => badge !== removedBadge)
        .map(badge => badge.textContent.trim());
    
    if (newEmail) {
        emails.push(newEmail);
    }

    const formData = {
        installation_id: form.querySelector('[name="installation_id"]').value,
        user_id: form.querySelector('[name="user_id"]').value,
        is_active: form.querySelector('#is_active').checked,
        frequency: form.querySelector('#frequency').value,
        notification_emails: emails,
        redirect_url: window.location.href
    };

    if (formData.is_active && emails.length === 0) {
        throw new Error('Please add at least one email address when monitoring is active');
    }

    const baseUrl = window.ENVIRONMENT === 'production' 
        ? 'https://gcx-healthcheck-zd-production.up.railway.app'
        : 'https://gcx-healthcheck-zd-development.up.railway.app';

    const response = await client.request({
        url: `${baseUrl}/monitoring-settings/`,
        type: 'POST',
        contentType: 'application/json',
        headers: {
            'X-Subsequent-Request': 'true'
        },
        data: JSON.stringify(formData),
        secure: true
    });

    return response;
}