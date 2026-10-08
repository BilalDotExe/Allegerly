/* Three small guards shared by every page:
     1. forms marked data-confirm ask before submitting (irreversible actions),
     2. submit buttons go disabled with a "…" label so a slow LAN cannot produce
        a duplicate payment or goods receipt from a double click,
     3. leaving a half-filled form warns first.
   All delegated from the document, so formset rows added later are covered too. */
(function () {
  "use strict";

  var EDITABLE = "form.app-form, form.po-form, form.customer-form, form.settings-form, form.invoice-form";
  var dirty = false;
  var submitting = false;

  function lockButtons(form) {
    var label = form.getAttribute("data-busy-label") || "Saving";
    form.querySelectorAll('button[type="submit"], button:not([type]), input[type="submit"]').forEach(function (btn) {
      if (btn.disabled) return;
      btn.setAttribute("aria-busy", "true");
      /* Disabling straight away would drop the button's name/value from the
         POST, so let the browser serialise the form first. */
      window.setTimeout(function () {
        btn.disabled = true;
        btn.textContent = label + "…";
      }, 0);
    });
  }

  document.addEventListener("submit", function (e) {
    var form = e.target;
    if (!(form instanceof HTMLFormElement)) return;

    var question = form.getAttribute("data-confirm");
    if (question && !window.confirm(question)) {
      e.preventDefault();
      return;
    }

    /* Filter forms are GET and just reload the list — nothing to guard. */
    /* getAttribute, not form.method: a payment form has a field named "method",
       and a named control shadows the form's own property. */
    if ((form.getAttribute("method") || "get").toLowerCase() === "get") return;

    /* A form the browser rejects never reaches the server, so only lock once
       its own validation passes. */
    if (!form.noValidate && typeof form.checkValidity === "function" && !form.checkValidity()) return;

    dirty = false;
    submitting = true;
    lockButtons(form);
  });

  document.addEventListener("input", function (e) {
    if (e.target.closest(EDITABLE)) dirty = true;
  });

  /* Cancel / Back links are a deliberate exit, so they clear the flag instead
     of triggering the warning. Every other link still warns. */
  document.addEventListener("click", function (e) {
    if (e.target.closest("a.btn-outline-secondary, a.btn-secondary, a.page-back, a[data-discard]")) dirty = false;
  });

  window.addEventListener("beforeunload", function (e) {
    if (!dirty || submitting) return;
    e.preventDefault();
    e.returnValue = "";
  });
})();
