/* Sidebar groups open and close, and the sidebar remembers what you chose.
   The group holding the current page always stays open. Loaded straight after
   the sidebar markup so groups are set before the page first paints. */
(function () {
  "use strict";
  var KEY = "sidebar-groups";
  var saved = {};
  try { saved = JSON.parse(localStorage.getItem(KEY)) || {}; } catch (e) { saved = {}; }

  document.querySelectorAll(".nav-group").forEach(function (group) {
    var key = group.getAttribute("data-group");
    if (!group.classList.contains("has-active") && key in saved) group.open = saved[key];
    group.addEventListener("toggle", function () {
      saved[key] = group.open;
      try { localStorage.setItem(KEY, JSON.stringify(saved)); } catch (e) { /* private window: just don't remember */ }
    });
  });

  /* Screen readers announce the highlighted link as the current page. */
  document.querySelectorAll(".side-link.active").forEach(function (a) { a.setAttribute("aria-current", "page"); });
})();
