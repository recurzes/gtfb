/**
 * GTFB — Anti-Distraction Suite
 * Extension Action Popup Script
 */

import { getActiveDomains } from "./storage.js";

let countdownInterval = null;
let selectedDurationMinutes = 25;

/**
 * Formats total seconds into MM:SS display format.
 * @param {number} totalSeconds
 * @returns {string}
 */
export function formatTime(totalSeconds) {
  const mins = Math.floor(Math.max(0, totalSeconds) / 60);
  const secs = Math.floor(Math.max(0, totalSeconds) % 60);
  return `${mins.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`;
}

/**
 * Refreshes the domain count display in the popup footer from cachedConfig.
 */
export async function refreshDomainCount() {
  try {
    const domainCountElem = document.getElementById("domainCount");
    if (domainCountElem) {
      const domains = await getActiveDomains();
      const count = Array.isArray(domains) ? domains.length : 0;
      domainCountElem.textContent = `${count} domain${count === 1 ? "" : "s"} configured`;
    }
  } catch (err) {
    console.error("[GTFB Popup] Failed to refresh domain count:", err);
  }
}

/**
 * Updates popup UI elements based on blocking status and lock state.
 * @param {object} status
 */
export function updateUI(status = {}) {
  const blockingToggle = document.getElementById("blockingToggle");
  const statusLabel = document.getElementById("statusLabel");
  const statusDetail = document.getElementById("statusDetail");
  const mainControlCard = document.getElementById("mainControlCard");
  const lockBanner = document.getElementById("lockBanner");
  const lockCountdown = document.getElementById("lockCountdown");
  const focusSection = document.getElementById("focusSection");

  const isLocked = Boolean(status.isLocked && status.lockedUntil && status.lockedUntil > Date.now());
  const isBlockingActive = isLocked || Boolean(status.isBlockingActive);

  if (isLocked) {
    if (mainControlCard) mainControlCard.className = "main-control locked";
    if (statusLabel) statusLabel.textContent = "Focus Locked";
    if (statusDetail) statusDetail.textContent = "Anti-distraction enforced";

    if (blockingToggle) {
      blockingToggle.checked = true;
      blockingToggle.disabled = true;
      if (blockingToggle.parentElement) {
        blockingToggle.parentElement.classList.add("disabled");
      }
    }

    if (lockBanner) lockBanner.classList.remove("hidden");
    if (focusSection) focusSection.classList.add("hidden");

    // Start or update countdown ticker
    if (countdownInterval) {
      clearInterval(countdownInterval);
    }

    const tick = () => {
      const remainingSecs = Math.max(0, Math.ceil((status.lockedUntil - Date.now()) / 1000));
      if (lockCountdown) {
        lockCountdown.textContent = formatTime(remainingSecs);
      }
      if (remainingSecs <= 0) {
        clearInterval(countdownInterval);
        countdownInterval = null;
        fetchAndRefreshStatus();
      }
    };

    tick();
    countdownInterval = setInterval(tick, 1000);
  } else {
    // Clear countdown interval
    if (countdownInterval) {
      clearInterval(countdownInterval);
      countdownInterval = null;
    }

    if (lockBanner) lockBanner.classList.add("hidden");
    if (focusSection) focusSection.classList.remove("hidden");

    if (blockingToggle) {
      blockingToggle.checked = isBlockingActive;
      blockingToggle.disabled = false;
      if (blockingToggle.parentElement) {
        blockingToggle.parentElement.classList.remove("disabled");
      }
    }

    if (isBlockingActive) {
      if (mainControlCard) mainControlCard.className = "main-control active";
      if (statusLabel) statusLabel.textContent = "Blocking Active";
      if (statusDetail) statusDetail.textContent = "Distracting sites blocked";
    } else {
      if (mainControlCard) mainControlCard.className = "main-control";
      if (statusLabel) statusLabel.textContent = "Blocking Inactive";
      if (statusDetail) statusDetail.textContent = "Sites accessible";
    }
  }
}

/**
 * Fetches latest blocking status from background service worker.
 */
export async function fetchAndRefreshStatus() {
  try {
    refreshDomainCount();
    if (typeof chrome !== "undefined" && chrome.runtime && chrome.runtime.sendMessage) {
      chrome.runtime.sendMessage({ action: "GET_BLOCKING_STATUS" }, (response) => {
        if (chrome.runtime.lastError || !response) {
          // Fallback to chrome.storage
          if (chrome.storage && chrome.storage.local) {
            chrome.storage.local.get(["isBlockingActive", "lockedUntil"]).then((data) => {
              const now = Date.now();
              const isLocked = Boolean(data.lockedUntil && data.lockedUntil > now);
              updateUI({
                isBlockingActive: isLocked || (data.isBlockingActive !== undefined ? Boolean(data.isBlockingActive) : true),
                isLocked,
                lockedUntil: data.lockedUntil
              });
            });
          }
          return;
        }
        updateUI(response);
      });
    }
  } catch (err) {
    console.error("[GTFB Popup] Failed to query status:", err);
  }
}

/**
 * Sets up event listeners for popup interactions.
 */
export function setupPopupListeners() {
  const blockingToggle = document.getElementById("blockingToggle");
  const presetChips = document.querySelectorAll(".chip");
  const startLockBtn = document.getElementById("startLockBtn");

  if (blockingToggle) {
    blockingToggle.addEventListener("change", (e) => {
      const isChecked = e.target.checked;
      if (typeof chrome !== "undefined" && chrome.runtime && chrome.runtime.sendMessage) {
        chrome.runtime.sendMessage(
          { action: "TOGGLE_BLOCKING", enabled: isChecked },
          (response) => {
            if (response && response.success !== false) {
              updateUI(response);
            } else if (response && response.error) {
              console.warn("[GTFB Popup] Toggle rejected:", response.error);
              updateUI(response);
            } else {
              fetchAndRefreshStatus();
            }
          }
        );
      } else {
        // Mock fallback for direct DOM testing
        updateUI({ isBlockingActive: isChecked, isLocked: false });
      }
    });
  }

  // Preset chips click handling
  presetChips.forEach((chip) => {
    chip.addEventListener("click", () => {
      presetChips.forEach((c) => c.classList.remove("active"));
      chip.classList.add("active");
      const mins = parseInt(chip.getAttribute("data-mins"), 10);
      if (!isNaN(mins)) {
        selectedDurationMinutes = mins;
        if (startLockBtn) {
          startLockBtn.innerHTML = `
            <svg class="btn-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <circle cx="12" cy="12" r="10"></circle>
              <polyline points="12 6 12 12 16 14"></polyline>
            </svg>
            Start ${selectedDurationMinutes}m Focus Lock
          `;
        }
      }
    });
  });

  // Start Focus Lock button handling
  if (startLockBtn) {
    startLockBtn.addEventListener("click", () => {
      if (typeof chrome !== "undefined" && chrome.runtime && chrome.runtime.sendMessage) {
        chrome.runtime.sendMessage(
          { action: "START_LOCK_TIMER", durationMinutes: selectedDurationMinutes },
          (response) => {
            if (response && response.success) {
              updateUI(response);
            } else {
              fetchAndRefreshStatus();
            }
          }
        );
      }
    });
  }

  // Listen for storage changes from background or other tabs
  if (typeof chrome !== "undefined" && chrome.storage && chrome.storage.onChanged) {
    chrome.storage.onChanged.addListener((changes, area) => {
      if (area === "local") {
        if (changes.isBlockingActive || changes.lockedUntil) {
          fetchAndRefreshStatus();
        }
        if (changes.cachedConfig) {
          refreshDomainCount();
        }
      }
    });
  }
}

// Initialize on DOM load
if (typeof document !== "undefined" && typeof document.addEventListener === "function") {
  document.addEventListener("DOMContentLoaded", () => {
    setupPopupListeners();
    fetchAndRefreshStatus();
    refreshDomainCount();
  });
}
