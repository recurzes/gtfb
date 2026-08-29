/**
 * GTFB — Anti-Distraction Suite
 * Blocked Landing Page Script
 */

document.addEventListener("DOMContentLoaded", () => {
  // Extract domain from query parameter if present
  const params = new URLSearchParams(window.location.search);
  const domain = params.get("domain");
  const badge = document.getElementById("domainBadge");

  if (badge && domain && domain.trim()) {
    badge.textContent = domain.trim();
  }

  // Close tab button action
  const closeBtn = document.getElementById("closeTabBtn");
  if (closeBtn) {
    closeBtn.addEventListener("click", () => {
      window.close();
    });
  }
});
