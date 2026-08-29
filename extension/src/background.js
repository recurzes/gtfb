/**
 * GTFB — Anti-Distraction Suite
 * Background Service Worker (Manifest V3)
 */

import { applyBlockRules, clearBlockRules } from "./rules.js";

/**
 * Retrieves the current blocking status and focus lock timer state.
 * @returns {Promise<{ isBlockingActive: boolean, isLocked: boolean, lockedUntil: number | null, remainingSeconds: number }>}
 */
export async function getBlockingStatus() {
  if (typeof chrome === "undefined" || !chrome.storage || !chrome.storage.local) {
    return { isBlockingActive: true, isLocked: false, lockedUntil: null, remainingSeconds: 0 };
  }

  const data = await chrome.storage.local.get(["isBlockingActive", "lockedUntil"]);
  const now = Date.now();
  let lockedUntil = data.lockedUntil || null;
  let isLocked = false;
  let remainingSeconds = 0;

  if (lockedUntil && lockedUntil > now) {
    isLocked = true;
    remainingSeconds = Math.max(0, Math.ceil((lockedUntil - now) / 1000));
  } else if (lockedUntil && lockedUntil <= now) {
    // Expired lock: clear lockedUntil
    lockedUntil = null;
    await chrome.storage.local.set({ lockedUntil: null });
  }

  // Default isBlockingActive is true if undefined
  const isBlockingActive = isLocked ? true : (data.isBlockingActive !== undefined ? Boolean(data.isBlockingActive) : true);

  return {
    isBlockingActive,
    isLocked,
    lockedUntil,
    remainingSeconds
  };
}

/**
 * Handles toggling site blocking state with optional focus lock duration.
 * @param {boolean} enable - Whether to enable blocking
 * @param {object} [options] - Optional settings (e.g. { durationMinutes: number })
 * @returns {Promise<{ success: boolean, isBlockingActive: boolean, isLocked?: boolean, lockedUntil?: number | null, error?: string }>}
 */
export async function handleToggle(enable, options = {}) {
  const now = Date.now();
  const currentStatus = await getBlockingStatus();

  // If attempting to disable blocking while lock timer is active, reject
  if (!enable && currentStatus.isLocked) {
    console.warn("[GTFB Background] Cannot disable blocking: Focus Lock is active until", new Date(currentStatus.lockedUntil).toLocaleTimeString());
    return {
      success: false,
      error: "Focus lock timer is currently active. Site blocking cannot be disabled until the timer expires.",
      isBlockingActive: true,
      isLocked: true,
      lockedUntil: currentStatus.lockedUntil,
      remainingSeconds: currentStatus.remainingSeconds
    };
  }

  if (enable) {
    await applyBlockRules();

    let lockedUntil = null;
    const durationMinutes = options && typeof options.durationMinutes === "number" ? options.durationMinutes : 0;

    if (durationMinutes > 0) {
      lockedUntil = now + Math.round(durationMinutes * 60 * 1000);
      if (typeof chrome !== "undefined" && chrome.storage && chrome.storage.local) {
        await chrome.storage.local.set({ isBlockingActive: true, lockedUntil });
      }
      if (typeof chrome !== "undefined" && chrome.action) {
        await chrome.action.setBadgeText({ text: "LOCK" });
        await chrome.action.setBadgeBackgroundColor({ color: "#8B5CF6" }); // Violet badge for Focus Lock
      }
      console.log(`[GTFB Background] Focus Lock activated for ${durationMinutes} minutes.`);
    } else {
      if (typeof chrome !== "undefined" && chrome.storage && chrome.storage.local) {
        await chrome.storage.local.set({ isBlockingActive: true, lockedUntil: null });
      }
      if (typeof chrome !== "undefined" && chrome.action) {
        await chrome.action.setBadgeText({ text: "ON" });
        await chrome.action.setBadgeBackgroundColor({ color: "#22C55E" }); // Green badge for standard ON
      }
      console.log("[GTFB Background] Blocking manually enabled.");
    }

    return {
      success: true,
      isBlockingActive: true,
      isLocked: Boolean(lockedUntil),
      lockedUntil: lockedUntil
    };
  } else {
    await clearBlockRules();
    if (typeof chrome !== "undefined" && chrome.storage && chrome.storage.local) {
      await chrome.storage.local.set({ isBlockingActive: false, lockedUntil: null });
    }
    if (typeof chrome !== "undefined" && chrome.action) {
      await chrome.action.setBadgeText({ text: "" });
    }
    console.log("[GTFB Background] Blocking manually disabled.");

    return {
      success: true,
      isBlockingActive: false,
      isLocked: false,
      lockedUntil: null
    };
  }
}

/**
 * Starts a Focus Lock session for a specified duration in minutes.
 * @param {number} durationMinutes - Lock duration in minutes
 * @returns {Promise<object>}
 */
export async function startLockTimer(durationMinutes) {
  if (!durationMinutes || durationMinutes <= 0) {
    return { success: false, error: "Duration must be greater than 0 minutes." };
  }
  return handleToggle(true, { durationMinutes });
}

// Runtime message listener
if (typeof chrome !== "undefined" && chrome.runtime && chrome.runtime.onMessage) {
  chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    if (!message || !message.action) {
      return false;
    }

    if (message.action === "TOGGLE_BLOCKING") {
      handleToggle(message.enabled, message.options)
        .then((res) => sendResponse(res))
        .catch((err) => sendResponse({ success: false, error: err.message }));
      return true; // Keep channel open for async response
    }

    if (message.action === "GET_BLOCKING_STATUS") {
      getBlockingStatus()
        .then((res) => sendResponse(res))
        .catch((err) => sendResponse({ success: false, error: err.message }));
      return true;
    }

    if (message.action === "START_LOCK_TIMER") {
      startLockTimer(message.durationMinutes)
        .then((res) => sendResponse(res))
        .catch((err) => sendResponse({ success: false, error: err.message }));
      return true;
    }

    return false;
  });
}

// Initialize block rules and badge on extension install or update
if (typeof chrome !== "undefined" && chrome.runtime && chrome.runtime.onInstalled) {
  chrome.runtime.onInstalled.addListener(async (details) => {
    console.log("[GTFB Background] Extension installed/updated:", details.reason);
    try {
      const status = await getBlockingStatus();
      if (status.isLocked) {
        const remainingMinutes = Math.max(1, Math.round(status.remainingSeconds / 60));
        await handleToggle(true, { durationMinutes: remainingMinutes });
      } else if (status.isBlockingActive) {
        await handleToggle(true);
      } else {
        await handleToggle(false);
      }
    } catch (err) {
      console.error("[GTFB Background] Failed to apply block rules on install:", err);
    }
  });
}

// Re-apply block rules on browser startup
if (typeof chrome !== "undefined" && chrome.runtime && chrome.runtime.onStartup) {
  chrome.runtime.onStartup.addListener(async () => {
    console.log("[GTFB Background] Browser startup detected.");
    try {
      const status = await getBlockingStatus();
      if (status.isLocked) {
        const remainingMinutes = Math.max(1, Math.round(status.remainingSeconds / 60));
        await handleToggle(true, { durationMinutes: remainingMinutes });
      } else if (status.isBlockingActive) {
        await handleToggle(true);
      } else {
        await handleToggle(false);
      }
    } catch (err) {
      console.error("[GTFB Background] Failed to apply block rules on startup:", err);
    }
  });
}

export { applyBlockRules, clearBlockRules };
