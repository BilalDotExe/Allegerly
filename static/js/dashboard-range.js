/* Swap dashboard charts in place when the range toggle is clicked (no page reload).
   Without JS the toggle links still work as normal navigation. */
(function () {
  "use strict";
  var toggle = document.querySelector(".range-toggle");
  var grid = document.querySelector(".chart-grid");
  if (!toggle || !grid || !window.fetch || !window.DOMParser) return;

  var busy = false;

  function swap(doc, range) {
    var newCards = doc.querySelectorAll(".kpi-card");
    document.querySelectorAll(".kpi-card").forEach(function (el, i) {
      if (newCards[i]) el.innerHTML = newCards[i].innerHTML;
    });
    var newPanels = doc.querySelectorAll(".chart-grid .dashboard-panel");
    grid.querySelectorAll(".dashboard-panel").forEach(function (el, i) {
      var src = newPanels[i];
      if (!src) return;
      var p = el.querySelector(".panel-heading p"), sp = src.querySelector(".panel-heading p");
      if (p && sp) p.textContent = sp.textContent;
      var body = el.querySelector(".chart-body"), sb = src.querySelector(".chart-body");
      if (body && sb) body.innerHTML = sb.innerHTML;
    });
    toggle.querySelectorAll("a").forEach(function (a) {
      a.classList.toggle("active", a.getAttribute("href") === "?range=" + range);
    });
    /* The charts redraw silently, so say what changed for screen readers. */
    var status = document.getElementById("chart-range-status");
    if (status) status.textContent = "Charts updated to the last " + range + " months.";
  }

  toggle.addEventListener("click", function (e) {
    var link = e.target.closest("a");
    if (!link || e.metaKey || e.ctrlKey || e.shiftKey || busy) return;
    e.preventDefault();
    if (link.classList.contains("active")) return;
    var href = link.getAttribute("href"), range = href.split("=")[1];
    busy = true;
    grid.setAttribute("aria-busy", "true");
    fetch(href, { headers: { "X-Requested-With": "fetch" }, credentials: "same-origin" })
      .then(function (r) { if (!r.ok) throw new Error(r.status); return r.text(); })
      .then(function (html) {
        swap(new DOMParser().parseFromString(html, "text/html"), range);
        /* pushState, not replaceState, so Back returns to the previous range. */
        history.pushState({ range: range }, "", href);
      })
      .catch(function () { window.location.href = href; })  /* fall back to a normal load */
      .finally(function () { busy = false; grid.removeAttribute("aria-busy"); });
  });

  /* Back/forward moved us to another range: reload rather than try to rebuild. */
  window.addEventListener("popstate", function () { window.location.reload(); });
})();
