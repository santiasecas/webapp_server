/**
 * Corporate Platform — minimal JS utilities
 * No framework dependencies.
 */

// ── Auto-dismiss alerts ────────────────────────────────────────────
(function () {
  const alerts = document.querySelectorAll('.alert');
  alerts.forEach(function (el) {
    setTimeout(function () {
      el.style.transition = 'opacity .5s ease';
      el.style.opacity = '0';
      setTimeout(function () { el.remove(); }, 500);
    }, 4000);
  });
})();

// ── Sidebar active state from query params ─────────────────────────
(function () {
  const params = new URLSearchParams(window.location.search);
  // Could be extended for dynamic highlighting
})();

// ── Confirm dialogs (fallback for non-JS) ─────────────────────────
// Already handled via inline onsubmit attributes in templates.
