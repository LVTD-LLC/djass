module.exports = {
  darkMode: 'class',
  content: [
    './frontend/templates/**/*.html',
    './frontend/src/js/**/*.js',
    './apps/**/*.py',
    './djass/**/*.py',
  ],
  theme: {
    extend: {},
  },
  plugins: [
    require('@tailwindcss/typography'),
    require('@tailwindcss/forms'),
  ],
};
