/* Powers two buttons on the employee create / reset-password pages:
     ".generate-password-btn" fills its data-target field with a random
     8-char password (upper+lower+digit guaranteed — mirrors
     core.utils.generate_temp_password so what's on screen before submit
     matches what the server would produce if the field were left blank).
     ".copy-btn" copies its data-copy value to the clipboard.
   Delegated from the document so it's harmless (does nothing) on every
   other page — no need to scope the <script> tag per template. */
(function () {
  "use strict";
  var UPPER = "ABCDEFGHIJKLMNOPQRSTUVWXYZ";
  var LOWER = "abcdefghijklmnopqrstuvwxyz";
  var DIGITS = "0123456789";
  var ALL = UPPER + LOWER + DIGITS;

  function randomIndex(max) {
    var arr = new Uint32Array(1);
    (window.crypto || window.msCrypto).getRandomValues(arr);
    return arr[0] % max;
  }

  function randomChar(pool) {
    return pool[randomIndex(pool.length)];
  }

  function shuffled(chars) {
    for (var i = chars.length - 1; i > 0; i--) {
      var j = randomIndex(i + 1);
      var tmp = chars[i]; chars[i] = chars[j]; chars[j] = tmp;
    }
    return chars;
  }

  function generatePassword(length) {
    var chars = [randomChar(UPPER), randomChar(LOWER), randomChar(DIGITS)];
    while (chars.length < length) chars.push(randomChar(ALL));
    return shuffled(chars).join("");
  }

  function copyText(text, onDone) {
    if (navigator.clipboard && window.isSecureContext) {
      navigator.clipboard.writeText(text).then(onDone, function () {});
      return;
    }
    var tmp = document.createElement("textarea");
    tmp.value = text;
    tmp.style.position = "fixed";
    tmp.style.opacity = "0";
    document.body.appendChild(tmp);
    tmp.focus();
    tmp.select();
    try { document.execCommand("copy"); onDone(); } catch (err) { /* ignore */ }
    document.body.removeChild(tmp);
  }

  document.addEventListener("click", function (e) {
    var genBtn = e.target.closest(".generate-password-btn");
    if (genBtn) {
      var targetId = genBtn.getAttribute("data-target");
      var field = targetId && document.getElementById(targetId);
      if (field) {
        field.value = generatePassword(8);
        field.focus();
        field.select();
      }
      return;
    }

    var copyBtn = e.target.closest(".copy-btn");
    if (copyBtn) {
      var text = copyBtn.getAttribute("data-copy") || "";
      copyText(text, function () {
        var original = copyBtn.textContent;
        copyBtn.textContent = "Copied";
        copyBtn.disabled = true;
        window.setTimeout(function () {
          copyBtn.textContent = original;
          copyBtn.disabled = false;
        }, 1600);
      });
    }
  });
})();
