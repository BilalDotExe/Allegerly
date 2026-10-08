/* Expand/collapse the detail row under a table row (delegated, no dependencies). */
(function () {
  "use strict";
  document.addEventListener("click", function (e) {
    var btn = e.target.closest(".row-expand");
    if (!btn) return;
    var detail = document.getElementById(btn.getAttribute("aria-controls"));
    if (!detail) return;
    var open = btn.getAttribute("aria-expanded") !== "true";
    btn.setAttribute("aria-expanded", open ? "true" : "false");
    btn.closest("tr").classList.toggle("is-open", open);
    detail.hidden = !open;
  });
})();
