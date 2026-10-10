document.addEventListener('click', function (e) {
  var toggle = e.target.closest('.nav-group-toggle');
  if (!toggle) return;
  var group = toggle.parentElement;
  var open = group.classList.toggle('is-open');
  toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
});
