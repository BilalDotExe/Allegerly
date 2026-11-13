/* Expense form: add and remove lines (asking first when a line has something in it),
   keep the line numbers and the total up to date, and open the category suggestions. */
(function () {
  "use strict";
  var form = document.querySelector(".expense-form");
  if (!form) return;
  var body = form.querySelector("#expense-lines tbody"),
      totalForms = form.querySelector("[name$='-TOTAL_FORMS']"),
      template = document.getElementById("expense-line-template"),
      totalOut = document.getElementById("expense-total"),
      addButton = document.getElementById("add-line"),
      dialogEl = document.getElementById("remove-line-dialog"),
      dialog = dialogEl && window.bootstrap ? new window.bootstrap.Modal(dialogEl) : null,
      pendingRow = null,
      opener = null,
      removed = false;

  function rows() {
    return Array.prototype.filter.call(body.querySelectorAll("tr.line-row"), function (row) { return !row.hidden; });
  }
  function field(row, name) { return row.querySelector("[name$='-" + name + "']"); }
  function money(n) { return "$" + n.toFixed(2).replace(/\B(?=(\d{3})+(?!\d))/g, ","); }

  /* Number the visible lines 1, 2, 3... and keep each box's spoken label in step. */
  function refresh() {
    var sum = 0;
    rows().forEach(function (row, i) {
      var n = i + 1;
      row.querySelector(".line-no").textContent = n;
      row.querySelectorAll("[aria-label]").forEach(function (el) {
        if (el.classList.contains("line-del-btn")) return;
        el.setAttribute("aria-label", el.getAttribute("aria-label").replace(/(, line \d+)?$/, ", line " + n));
      });
      row.querySelector(".line-del-btn").setAttribute("aria-label", "Remove line " + n);
      sum += parseFloat(field(row, "amount").value) || 0;
    });
    totalOut.textContent = money(Math.round(sum * 100) / 100);
  }

  function addLine(focus) {
    var index = Number(totalForms.value);
    body.insertAdjacentHTML("beforeend", template.innerHTML.replace(/__prefix__/g, index));
    totalForms.value = index + 1;
    refresh();
    if (focus) field(body.lastElementChild, "category").focus();
  }

  function hasContent(row) {
    var saved = field(row, "id");
    return Boolean(saved && saved.value) || ["category", "description", "amount", "reference"].some(function (name) {
      return field(row, name).value.trim() !== "";
    });
  }

  /* A saved line is marked for deletion (it goes when you press Save); a new one is just dropped. */
  function removeLine(row) {
    var saved = field(row, "id");
    if (saved && saved.value) {
      field(row, "DELETE").checked = true;
      row.hidden = true;
    } else {
      row.remove();
    }
    refresh();
  }

  function describe(row) {
    var text = field(row, "description").value.trim() || field(row, "category").value.trim() || "This line";
    var amount = parseFloat(field(row, "amount").value);
    return amount ? text + ", " + money(amount) + "." : text + ".";
  }

  body.addEventListener("click", function (e) {
    var del = e.target.closest(".line-del-btn");
    if (del) {
      var row = del.closest("tr");
      if (!hasContent(row)) { removeLine(row); addButton.focus(); return; }   /* nothing typed: nothing to lose */
      if (!dialog) {
        if (window.confirm("Remove line " + row.querySelector(".line-no").textContent + "?")) { removeLine(row); addButton.focus(); }
        return;
      }
      pendingRow = row;
      opener = del;
      removed = false;
      dialogEl.querySelector("[data-line-no]").textContent = row.querySelector(".line-no").textContent;
      dialogEl.querySelector("[data-line-summary]").textContent = describe(row);
      dialog.show();
      return;
    }
    var chevron = e.target.closest(".category-open");
    if (chevron) {
      var input = chevron.parentNode.querySelector("input");
      input.focus();
      try { input.showPicker(); } catch (err) { /* older browsers: typing still shows suggestions */ }
    }
  });

  if (dialog) {
    document.getElementById("confirm-remove-line").addEventListener("click", function () {
      if (pendingRow) { removeLine(pendingRow); removed = true; }
      pendingRow = null;
      dialog.hide();
    });
    /* Once the dialog has closed: back to the delete button if the line was kept,
       or to "Add line" if it was removed (its own button is gone). */
    dialogEl.addEventListener("hidden.bs.modal", function () {
      pendingRow = null;
      (removed || !opener ? addButton : opener).focus();
    });
  }

  addButton.addEventListener("click", function () { addLine(true); });
  form.addEventListener("input", refresh);

  if (!rows().length) addLine(false);
  refresh();
})();
