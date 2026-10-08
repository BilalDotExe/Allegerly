/* Copy each column header onto its cells as data-label so phone layouts can render
   table rows as labelled cards (CSS only reads the attribute). */
(function () {
  "use strict";
  function label(table) {
    /* :scope keeps this on the table's own head and body. An unscoped query
       also walked the nested .expand-lines tables inside expandable rows and
       stamped the outer table's headers onto their cells. */
    var heads = Array.prototype.map.call(table.querySelectorAll(":scope > thead > tr > th"), function (th) {
      return th.textContent.trim();
    });
    table.querySelectorAll(":scope > tbody > tr").forEach(function (tr) {
      var i = 0;
      Array.prototype.forEach.call(tr.cells, function (td) {
        var span = parseInt(td.getAttribute("colspan") || "1", 10);
        if (span === 1 && heads[i] && !td.hasAttribute("data-label")) td.setAttribute("data-label", heads[i]);
        i += span;
      });
    });
  }
  function run() { document.querySelectorAll("table.data-table, table.app-table, table#invoice-lines, table#po-lines").forEach(label); }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", run); else run();
})();
