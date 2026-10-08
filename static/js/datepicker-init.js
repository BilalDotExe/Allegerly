/* Initialise flatpickr on every <input type="date"> in the page.
   Runs after DOM ready; flatpickr.min.js must be loaded first. */
(function () {
  "use strict";

  var ICON = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3.5" y="5" width="17" height="15.5" rx="3"/><path d="M8 3v4M16 3v4M3.5 10h17"/></svg>';

  /* Flatpickr builds a brand-new visible input and turns the original into a
     hidden one, but it only copies class, placeholder, disabled, required and
     tabIndex across — never the id. That left every <label for="id_x"> pointing
     at a hidden field, so clicking the label did nothing and screen readers
     announced the visible box as unnamed. Move the id onto the visible input and
     park the original under a suffixed id (it still carries the submitted name). */
  function moveLabelToAltInput(fp) {
    var alt = fp.altInput;
    if (!alt || !fp.input.id) return;
    var id = fp.input.id;
    fp.input.id = id + "_value";
    alt.id = id;
    var describedBy = fp.input.getAttribute("aria-describedby");
    if (describedBy) alt.setAttribute("aria-describedby", describedBy);
  }

  function addIcon(fp) {
    var alt = fp.altInput;
    if (!alt || alt.parentNode.classList.contains("date-field")) return;
    var wrap = document.createElement("div");
    wrap.className = "date-field";
    alt.parentNode.insertBefore(wrap, alt);
    wrap.appendChild(alt);
    var btn = document.createElement("button");
    btn.type = "button";
    btn.className = "date-icon";
    btn.tabIndex = -1;
    btn.setAttribute("aria-label", "Open calendar");
    btn.innerHTML = ICON;
    btn.addEventListener("click", function () { fp.toggle(); });
    wrap.appendChild(btn);
  }

  function addFooter(fp) {
    var footer = document.createElement("div");
    footer.className = "fp-footer";
    var today = document.createElement("button");
    today.type = "button";
    today.className = "fp-today";
    today.textContent = "Today";
    today.addEventListener("click", function () { fp.setDate(new Date(), true); fp.close(); });
    var clear = document.createElement("button");
    clear.type = "button";
    clear.className = "fp-clear";
    clear.textContent = "Clear";
    clear.addEventListener("click", function () { fp.clear(); fp.close(); });
    footer.appendChild(today);
    footer.appendChild(clear);
    fp.calendarContainer.appendChild(footer);
  }

  var COARSE = !!(window.matchMedia && window.matchMedia("(pointer: coarse)").matches);

  var BASE_CONFIG = {
    dateFormat: "Y-m-d",      /* what gets POSTed / what the input value holds */
    altInput: true,           /* visible, human-readable input */
    altFormat: "M j, Y",      /* e.g. "Oct 6, 2026" */
    allowInput: !COARSE,      /* on touch screens keep the keyboard closed */
    disableMobile: true,      /* always use our calendar: the native picker adds a second icon */
    monthSelectorType: "dropdown",
    animate: false,           /* open animation is handled in CSS */
    onReady: function (_, __, fp) {
      if (fp.altInput && fp.input.className) {
        fp.altInput.className = fp.input.className + " flatpickr-alt";
      }
      moveLabelToAltInput(fp);
      addIcon(fp);
      addFooter(fp);
    },
  };

  function init() {
    document.querySelectorAll('input[type="date"]').forEach(function (el) {
      if (el._flatpickr) return;
      flatpickr(el, Object.assign({}, BASE_CONFIG));
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
  document.addEventListener("htmx:afterSwap", init);
})();
