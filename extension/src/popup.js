/**
 * GTFB — Anti-Distraction Suite
 * Extension Action Popup Script
 */

document.addEventListener("DOMContentLoaded", () => {
  console.log("[GTFB Popup] Initialized popup UI.");

  const statusLabel = document.getElementById("status-text");
  const statusDesc = document.getElementById("status-desc");

  if (statusLabel && statusDesc) {
    statusLabel.textContent = "Extension Active";
    statusDesc.textContent = "Manifest V3 service worker initialized and monitoring bedtime schedules.";
  }
});
