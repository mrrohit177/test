// FarmConnect — vanilla JS (no build step, progressive enhancement)
(function () {
  "use strict";

  // Mobile nav toggle
  document.addEventListener("click", function (e) {
    const toggle = e.target.closest("[data-nav-toggle]");
    if (toggle) {
      const menu = document.getElementById("mobileMenu");
      if (menu) menu.classList.toggle("open");
    }
  });

  // Auto-dismiss flash messages after 6s
  document.querySelectorAll(".message").forEach(function (m) {
    setTimeout(function () {
      m.style.transition = "opacity .4s";
      m.style.opacity = "0";
      setTimeout(function () { m.remove(); }, 400);
    }, 6000);
  });

  // Confirm destructive actions
  document.addEventListener("submit", function (e) {
    const form = e.target;
    const confirmMsg = form.getAttribute("data-confirm");
    if (confirmMsg && !window.confirm(confirmMsg)) {
      e.preventDefault();
    }
  });

  // Image preview for file inputs
  document.querySelectorAll('input[type="file"][data-preview]').forEach(function (input) {
    input.addEventListener("change", function () {
      const target = document.getElementById(input.getAttribute("data-preview"));
      if (!target) return;
      target.innerHTML = "";
      Array.from(input.files).slice(0, 6).forEach(function (file) {
        if (!file.type.startsWith("image/")) return;
        const img = document.createElement("img");
        img.style.cssText = "width:70px;height:70px;object-fit:cover;border-radius:8px;border:1px solid #ddd";
        img.src = URL.createObjectURL(file);
        target.appendChild(img);
      });
    });
  });
})();
