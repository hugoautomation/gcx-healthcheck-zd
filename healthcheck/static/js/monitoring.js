let client = null;

// Initialize ZAF client
async function initializeApp() {
    try {
        client = window.ZAFClient ? window.ZAFClient.init() : null;
        if (!client) {
            console.error('ZAF Client could not be initialized');
            return;
        }

        client.invoke('resize', { width: '100%', height: '800px' });
        initializeForm();
    } catch (error) {
        console.error('Error initializing:', error);
    }
}

function initializeForm() {
    const form = document.getElementById('monitoring-form');
    const saveButton = document.getElementById('save-settings-btn');
    
    // Add email field handler
    document.querySelectorAll('.add-email').forEach(button => {
        button.addEventListener('click', addEmailField);
    });

    // Remove email field handler
    document.querySelectorAll('.remove-email').forEach(button => {
        button.addEventListener('click', removeEmailField);
    });
    
    if (form && saveButton) {
        form.addEventListener('submit', async function(e) {
            e.preventDefault();
            
            const spinner = saveButton.querySelector('.spinner-border');
            const btnText = saveButton.querySelector('.btn-text');
            
            spinner.classList.remove('d-none');
            btnText.textContent = 'Saving...';
            saveButton.disabled = true;

            try {
                const emailInputs = form.querySelectorAll('.notification-email');
                const validEmails = Array.from(emailInputs)
                    .filter(input => input.value.trim() !== '')
                    .map(input => input.value.trim());

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

                const response = await fetch(form.action, {
                    method: 'POST',
                    body: formData
                });

                if (!response.ok) {
                    throw new Error('Failed to save settings');
                }

                window.location.href = formData.get('redirect_url') || '/';

            } catch (error) {
                console.error('Error saving settings:', error);
                spinner.classList.add('d-none');
                btnText.textContent = 'Save Settings';
                saveButton.disabled = false;
                alert('Failed to save settings. Please try again.');
            }
        });
    }
}

function addEmailField() {
    const template = `
        <div class="input-group mb-2">
            <input type="email" class="form-control notification-email" name="notification_emails[]">
            <button type="button" class="btn c-btn c-btn--danger remove-email">-</button>
        </div>`;
    this.closest('.input-group').insertAdjacentHTML('beforebegin', template);
    
    // Add event listener to new remove button
    const newRemoveButton = this.closest('.input-group').previousElementSibling.querySelector('.remove-email');
    newRemoveButton.addEventListener('click', removeEmailField);
}

function removeEmailField() {
    this.closest('.input-group').remove();
}

document.addEventListener('DOMContentLoaded', initializeApp);