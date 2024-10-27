/** @type {import('tailwindcss').Config} */
module.exports = {
    content: [
      './healthcheck/templates/**/*.html',
    ],
    theme: {
      extend: {
        colors: {
          // Using Garden's theme object color tokens
          primary: {
            600: 'var(--zd-color-primary-600)',
            700: 'var(--zd-color-primary-700)'
          },
          grey: {
            50: 'var(--zd-color-grey-50)',
            100: 'var(--zd-color-grey-100)',
            200: 'var(--zd-color-grey-200)',
            300: 'var(--zd-color-grey-300)',
            600: 'var(--zd-color-grey-600)',
            700: 'var(--zd-color-grey-700)'
          },
          red: {
            100: 'var(--zd-color-red-100)',
            700: 'var(--zd-color-red-700)'
          },
          yellow: {
            100: 'var(--zd-color-yellow-100)',
            700: 'var(--zd-color-yellow-700)'
          }
        }
      }
    },
    plugins: [
      require('@zendeskgarden/tailwindcss')
    ]
  }