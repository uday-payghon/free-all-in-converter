/* Apply the saved theme before CSS paints. External file complies with script-src 'self'. */
(function () {
  'use strict';
  let selected = '';
  try { selected = localStorage.getItem('converter-theme') || ''; } catch (error) {}
  let systemDark = false;
  try { systemDark = window.matchMedia('(prefers-color-scheme: dark)').matches; } catch (error) {}
  document.documentElement.dataset.theme =
    selected === 'dark' || selected === 'light' ? selected : systemDark ? 'dark' : 'light';
})();
