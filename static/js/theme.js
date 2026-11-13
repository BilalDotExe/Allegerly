// Theme switch in the account menu: System / Light / Dark.
// The first paint is handled by partials/_theme_init.html; this file keeps it in sync afterwards.
(function () {
  var media = window.matchMedia('(prefers-color-scheme: dark)');

  function savedChoice() {
    try { return localStorage.getItem('theme') || 'system'; } catch (e) { return 'system'; }
  }

  function apply(choice) {
    var dark = choice === 'dark' || (choice === 'system' && media.matches);
    var theme = dark ? 'dark' : 'light';
    document.documentElement.setAttribute('data-theme', theme);
    document.documentElement.setAttribute('data-bs-theme', theme);

    var meta = document.querySelector('meta[name="theme-color"]');
    if (meta) meta.setAttribute('content', dark ? '#0e1513' : '#f2f5f3');

    document.querySelectorAll('[data-theme-choice]').forEach(function (button) {
      button.setAttribute('aria-pressed', button.getAttribute('data-theme-choice') === choice ? 'true' : 'false');
    });
    // Top bar switch: on = dark. Its knob position comes from CSS on <html data-theme>.
    document.querySelectorAll('[data-theme-toggle]').forEach(function (toggle) {
      toggle.setAttribute('aria-checked', dark ? 'true' : 'false');
    });
  }

  document.addEventListener('click', function (event) {
    var toggle = event.target.closest('[data-theme-toggle]');
    var button = event.target.closest('[data-theme-choice]');
    if (!toggle && !button) return;
    // The top bar switch always picks the opposite of what is showing now.
    var choice = toggle
      ? (document.documentElement.getAttribute('data-theme') === 'dark' ? 'light' : 'dark')
      : button.getAttribute('data-theme-choice');
    try {
      if (choice === 'system') localStorage.removeItem('theme');
      else localStorage.setItem('theme', choice);
    } catch (e) {}
    apply(choice);
  });

  // While on "System", follow the device when it switches between day and night.
  media.addEventListener('change', function () {
    if (savedChoice() === 'system') apply('system');
  });

  apply(savedChoice());
})();
