(function() {
  const client = window.ZAFClient ? window.ZAFClient.init() : null;
  
  if (!client) {
      console.error('ZAF Client could not be initialized');
      return;
  }

  // Get CSRF token for Django
  const csrftoken = document.querySelector('[name=csrfmiddlewaretoken]').value;

  client.invoke('resize', { width: '100%', height: '800px' });

  // Rest of your initialization code...

  document.getElementById('healthcheck-form').addEventListener('submit', (e) => {
      e.preventDefault();
      
      const formData = new FormData();
      formData.append('url', document.getElementById('domain').value);
      formData.append('email', document.getElementById('email').value);
      formData.append('api_token', document.getElementById('token').value);

      fetch('/healthcheck/check/', {
          method: 'POST',
          headers: {
              'X-CSRFToken': csrftoken
          },
          body: formData
      })
      .then(response => response.json())
      .then(data => {
          // Your existing template rendering code...
      })
      .catch(error => {
          // Your existing error handling...
      });
  });
})();