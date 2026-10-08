/* Receive-payment screen: typing an amount fills the invoice rows oldest first,
   and editing a row (or pressing Full) updates the amount received to match.
   Works in whole cents so totals never drift. The server re-checks everything. */
(function () {
  "use strict";

  var form = document.querySelector("form[data-receive-payment]");
  if (!form) return;

  var received = form.querySelector("#id_amount_received");
  var rows = Array.prototype.slice.call(form.querySelectorAll(".pay-input"));
  var appliedEl = document.querySelector("[data-applied]");
  var remainingEl = document.querySelector("[data-remaining]");
  var overEl = form.querySelector("[data-over]");
  var owed = toCents(remainingEl.getAttribute("data-owed"));

  function toCents(text) {
    var n = parseFloat(String(text || "").replace(/[$,\s]/g, ""));
    return isNaN(n) || n < 0 ? 0 : Math.round(n * 100);
  }
  function fromCents(c) { return (c / 100).toFixed(2); }
  function money(c) {
    return "$" + (c / 100).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }
  function balanceOf(input) { return toCents(input.getAttribute("data-balance")); }

  function rowTotal() {
    return rows.reduce(function (sum, input) { return sum + toCents(input.value); }, 0);
  }

  function refresh() {
    var applied = rowTotal();
    var typed = received ? toCents(received.value) : 0;
    appliedEl.textContent = money(applied);
    remainingEl.textContent = money(Math.max(owed - applied, 0));
    overEl.textContent = typed > owed
      ? "That is " + money(typed - owed) + " more than this customer owes."
      : "";
  }

  function distribute() {
    var left = toCents(received.value);
    rows.forEach(function (input) {
      var portion = Math.min(left, balanceOf(input));
      input.value = portion > 0 ? fromCents(portion) : "";
      left -= portion;
    });
    refresh();
  }

  if (received) received.addEventListener("input", distribute);

  form.addEventListener("input", function (e) {
    if (!e.target.classList.contains("pay-input")) return;
    var total = rowTotal();
    if (received) received.value = total > 0 ? fromCents(total) : "";
    refresh();
  });

  form.addEventListener("click", function (e) {
    var full = e.target.closest("[data-pay-full]");
    if (full) {
      var input = full.parentNode.querySelector(".pay-input");
      input.value = fromCents(balanceOf(input));
      input.dispatchEvent(new Event("input", { bubbles: true }));
      input.focus();
      return;
    }
    if (e.target.closest("[data-clear-payments]")) {
      rows.forEach(function (input) { input.value = ""; });
      if (received) received.value = "";
      refresh();
    }
  });

  refresh();
})();
