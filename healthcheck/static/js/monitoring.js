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

function addEmailField(e) {
    e.preventDefault(); // Prevent button default action
    const emailInputs = document.getElementById('email-inputs');
    const isFreePlan = document.querySelector('form').dataset.isFreePlan === 'true';
    
    const template = `
        <div class="input-group mb-2">
            <input type="email" class="form-control notification-email" name="notification_emails[]" 
                   ${isFreePlan ? 'disabled' : ''}>
            <button type="button" class="btn c-btn c-btn--danger remove-email">-</button>
        </div>`;
    
    // Insert before the last input group (the one with the + button)
    const lastInputGroup = emailInputs.lastElementChild;
    lastInputGroup.insertAdjacentHTML('beforebegin', template);
    
    // Add event listener to new remove button
    const newInputGroup = lastInputGroup.previousElementSibling;
    const removeButton = newInputGroup.querySelector('.remove-email');
    removeButton.addEventListener('click', removeEmailField);
}

function removeEmailField(e) {
    e.preventDefault(); // Prevent button default action
    const inputGroup = this.closest('.input-group');
    if (inputGroup) {
        inputGroup.remove();
    }
}

function initializeForm() {
    const form = document.getElementById('monitoring-form');
    const saveButton = document.getElementById('save-settings-btn');
    
    // Add email field handler
    const addButtons = document.querySelectorAll('.add-email');
    addButtons.forEach(button => {
        button.addEventListener('click', addEmailField);
    });

    // Remove email field handler
    const removeButtons = document.querySelectorAll('.remove-email');
    removeButtons.forEach(button => {
        button.addEventListener('click', removeEmailField);
    });
    
    if (form && saveButton) {
        form.addEventListener('submit', async function(e) {
            e.preventDefault();
            
            // Show loading state
            const spinner = saveButton.querySelector('.spinner-border');
            const btnText = saveButton.querySelector('.btn-text');
            
            try {
                // Enable loading state
                spinner.classList.remove('d-none');
                btnText.textContent = 'Saving...';
                saveButton.disabled = true;

                const emailInputs = form.querySelectorAll('.notification-email');
                const validEmails = Array.from(emailInputs)
                    .filter(input => input.value.trim() !== '')
                    .map(input => input.value.trim());

                const formData = new FormData(form);

                // Remove existing email fields
                for (const pair of formData.entries()) {
                    if (pair[0] === 'notification_emails[]') {
                        formData.delete(pair[0]);
                    }
                }

                // Add valid emails back
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

                // Redirect on success
                window.location.href = formData.get('redirect_url') || '/';

            } catch (error) {
                console.error('Error saving settings:', error);
                // Reset button state
                spinner.classList.add('d-none');
                btnText.textContent = 'Save Settings';
                saveButton.disabled = false;
                alert('Failed to save settings. Please try again.');
            }
        });
    }
}

document.addEventListener('DOMContentLoaded', initializeApp);