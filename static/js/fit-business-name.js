// Phones: shrink the business name in the top bar until the whole name fits on one line.
// Starts from the CSS size each time, so it grows back on a wider screen.
// Stops at 12px; a name that still doesn't fit ends in "…" (full name stays in the tooltip and account menu).
(function () {
  var name = document.querySelector('.topbar-business');
  if (!name) return;
  var MIN = 12;

  function fit() {
    name.style.fontSize = '';
    var size = parseFloat(getComputedStyle(name).fontSize);
    while (name.scrollWidth > name.clientWidth && size > MIN) {
      size -= 0.5;
      name.style.fontSize = size + 'px';
    }
  }

  var pending = false;
  window.addEventListener('resize', function () {
    if (pending) return;
    pending = true;
    requestAnimationFrame(function () { pending = false; fit(); });
  });
  // Groote loads after first paint and is wider than the fallback, so fit again once it is ready.
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(fit);
  fit();
})();
