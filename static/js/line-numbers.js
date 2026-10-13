/* Keep the "#" column of editable line tables in step with the rows.
   Rows ticked for deletion drop out of the count and are struck through, and
   rows added by the page's own "Add line" script are picked up automatically. */
(function () {
  "use strict";

  function renumber(table) {
    var n = 0;
    table.querySelectorAll(":scope > tbody > tr.line-row").forEach(function (row) {
      var cell = row.querySelector(".line-no");
      var del = row.querySelector('input[name$="-DELETE"]');
      var removed = !!(del && del.checked);
      row.classList.toggle("is-removed", removed);
      if (!cell) return;
      if (removed) { cell.textContent = "–"; return; }
      n += 1;
      cell.textContent = n;
    });
  }

  function init(table) {
    if (!table || table._lineNumbers) return;
    table._lineNumbers = true;
    renumber(table);
    var body = table.tBodies[0];
    if (body) new MutationObserver(function () { renumber(table); }).observe(body, { childList: true });
    table.addEventListener("change", function (e) {
      if (e.target.matches && e.target.matches('input[name$="-DELETE"]')) renumber(table);
    });
    table.addEventListener("click", function (e) {
      var btn = e.target.closest(".line-del-btn");
      if (!btn) return;
      var row = btn.closest("tr.line-row");
      var cb = row && row.querySelector('input[name$="-DELETE"]');
      if (!cb) return;
      cb.checked = !cb.checked;
      cb.dispatchEvent(new Event("change", { bubbles: true }));
    });
  }

  function run() { document.querySelectorAll("table.line-items[data-numbered]").forEach(init); }
  window.lineNumbers = { init: init };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", run); else run();
})();
