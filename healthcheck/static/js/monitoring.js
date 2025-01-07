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
        // Remove Email Handler - Updated
        currentEmails.addEventListener('click', async (e) => {
            if (e.target.classList.contains('btn-close')) {
                e.preventDefault();
                e.stopPropagation();
                
                const emailBadge = e.target.closest('.badge');  // Use closest to find the badge
                if (!emailBadge) return;
                
                const emailText = emailBadge.childNodes[0].textContent.trim();  // Get just the email text
                
                try {
                    // First try to save the settings
                    await saveSettings(client, emailBadge);
                    // Only remove if save was successful
                    emailBadge.remove();
                    showMessage('success', '✅ Email removed successfully');
                } catch (error) {
                    console.error('Error removing email:', error);
                    showMessage('danger', '❌ Failed to remove email');
                }
            }
        });

        // Form Submit Handler for adding new email
        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            
            const email = newEmailInput.value.trim();
            if (!validateEmail(email)) {
                showMessage('danger', 'Please enter a valid email address');
                return;
            }

            // Check for duplicate email
            const existingEmails = Array.from(currentEmails.children)
                .map(badge => badge.childNodes[0].textContent.trim());
            if (existingEmails.includes(email)) {
                showMessage('warning', 'This email is already added');
                return;
            }

            addEmailBtn.disabled = true;
            
            try {
                // Create badge element
                const badge = document.createElement('div');
                badge.className = 'badge bg-light text-dark border mb-2 me-2 p-2';
                badge.innerHTML = `
                    ${email}
                    <button type="button" class="btn-close ms-2" aria-label="Remove"></button>
                `;

                // Try to save first
                await saveSettings(client, null, email);
                
                // Only add to DOM if save was successful
                currentEmails.appendChild(badge);
                newEmailInput.value = '';
                showMessage('success', '✅ Email added successfully');

            } catch (error) {
                console.error('Error adding email:', error);
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
    
    // Get current emails, excluding the one being removed
    let emails = Array.from(currentEmails.children)
        .filter(badge => badge !== removedBadge)
        .map(badge => badge.childNodes[0].textContent.trim());  // Get just the email text
    
    // Add new email if provided
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

    // Validate emails if monitoring is active
    if (formData.is_active && emails.length === 0) {
        throw new Error('Please add at least one email address when monitoring is active');
    }

    console.log('Saving settings with emails:', emails);  // Debug log

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