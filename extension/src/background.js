/**
 * GTFB — Anti-Distraction Suite
 * Background Service Worker (Manifest V3)
 */

import { applyBlockRules, clearBlockRules, syncAndApplyRules } from "./rules.js";
import { isTimeInWindow } from "./scheduler_utils.js";
import { getCachedConfig, getActiveDomains } from "./storage.js";
import {
  fetchConfigFromApp,
  setupSyncAlarm,
  SYNC_ALARM_NAME,
  getSyncStatus,
  reportStatusToApp
} from "./sync.js";
import { extApi } from "./compat.js";

export const DEFAULT_SCHEDULE = {
  enabled: true,
  startHour: 22,
  startMinute: 0,
  endHour: 6,
  endMinute: 0
};

/**
 * Creates or updates the recurring schedule check alarm.
 */
export function setupScheduleAlarm() {
  if (extApi.alarms && typeof extApi.alarms.create === "function") {
    extApi.alarms.create("gtfb-schedule-check", {
      periodInMinutes: 1
    });
  }
}

/**
 * Evaluates current time against the scheduled window and applies or clears block rules accordingly.
 * Reads schedule configurations from cachedConfig in storage.
 * @param {Date|null} [nowOverride] - Optional override for current time (testing)
 * @param {object|null} [scheduleOverride] - Optional override for schedule config (testing)
 * @returns {Promise<void>}
 */
export async function evaluateCurrentSchedule(nowOverride = null, scheduleOverride = null) {
  const now = nowOverride || new Date();
  let shouldBlock = false;

  if (scheduleOverride) {
    const enabled = scheduleOverride.enabled !== undefined
      ? scheduleOverride.enabled
      : (scheduleOverride.active !== undefined ? scheduleOverride.active : true);
    if (enabled) {
      const startH = scheduleOverride.startHour ?? scheduleOverride.start_hour ?? 22;
      const startM = scheduleOverride.startMinute ?? scheduleOverride.start_minute ?? 0;
      const endH = scheduleOverride.endHour ?? scheduleOverride.end_hour ?? 6;
      const endM = scheduleOverride.endMinute ?? scheduleOverride.end_minute ?? 0;
      shouldBlock = isTimeInWindow(now, startH, startM, endH, endM);
    }
  } else {
    // Read from cachedConfig in storage
    const config = await getCachedConfig();
    if (config && Array.isArray(config.block_rules)) {
      for (const rule of config.block_rules) {
        if (rule && (rule.active !== false)) {
          const startH = rule.start_hour ?? rule.startHour ?? 22;
          const startM = rule.start_minute ?? rule.startMinute ?? 0;
          const endH = rule.end_hour ?? rule.endHour ?? 6;
          const endM = rule.end_minute ?? rule.endMinute ?? 0;
          if (isTimeInWindow(now, startH, startM, endH, endM)) {
            shouldBlock = true;
            break;
          }
        }
      }
    }
  }

  let isBlockingActive = false;
  let isLocked = false;

  if (extApi.storage && extApi.storage.local) {
    const status = await getBlockingStatus();
    isBlockingActive = status.isBlockingActive;
    isLocked = status.isLocked;
  }

  // If focus lock is currently active, do not disengage blocking but ensure rules are applied
  if (isLocked) {
    await applyBlockRules();
    try {
      await reportStatusToApp();
    } catch (e) {
      console.debug("[GTFB Background] Error reporting status after schedule check:", e);
    }
    return;
  }

  if (shouldBlock) {
    console.log("[GTFB Background] Scheduled bedtime window active. Enabling blocking.");
    await applyBlockRules();
    if (extApi.action && typeof extApi.action.setBadgeText === "function") {
      await extApi.action.setBadgeText({ text: "ON" });
      if (typeof extApi.action.setBadgeBackgroundColor === "function") {
        await extApi.action.setBadgeBackgroundColor({ color: "#22C55E" });
      }
    }
    if (extApi.storage && extApi.storage.local) {
      await extApi.storage.local.set({ isBlockingActive: true });
    }
    if (!isBlockingActive) {
      try {
        await reportStatusToApp();
      } catch (e) {
        console.debug("[GTFB Background] Error reporting status on schedule activation:", e);
      }
    }
  } else {
    if (isBlockingActive) {
      console.log("[GTFB Background] Scheduled bedtime window passed. Disabling blocking.");
    }
    await clearBlockRules();
    if (extApi.action && typeof extApi.action.setBadgeText === "function") {
      await extApi.action.setBadgeText({ text: "" });
    }
    if (extApi.storage && extApi.storage.local) {
      await extApi.storage.local.set({ isBlockingActive: false });
    }
    if (isBlockingActive) {
      try {
        await reportStatusToApp();
      } catch (e) {
        console.debug("[GTFB Background] Error reporting status on schedule deactivation:", e);
      }
    }
  }
}

// Alarm listener
if (extApi.alarms && extApi.alarms.onAlarm && typeof extApi.alarms.onAlarm.addListener === "function") {
  extApi.alarms.onAlarm.addListener(async (alarm) => {
    if (alarm && alarm.name === "gtfb-schedule-check") {
      await evaluateCurrentSchedule();
    } else if (alarm && alarm.name === SYNC_ALARM_NAME) {
      await fetchConfigFromApp();
    }
  });
}

// Top-level alarm setup
setupScheduleAlarm();
setupSyncAlarm();

/**
 * Retrieves the current blocking status and focus lock timer state.
 * @returns {Promise<{ isBlockingActive: boolean, isLocked: boolean, lockedUntil: number | null, remainingSeconds: number }>}
 */
export async function getBlockingStatus() {
  if (!extApi.storage || !extApi.storage.local) {
    return { isBlockingActive: true, isLocked: false, lockedUntil: null, remainingSeconds: 0 };
  }

  const data = await extApi.storage.local.get(["isBlockingActive", "lockedUntil"]);
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
    await extApi.storage.local.set({ lockedUntil: null });
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
      if (extApi.storage && extApi.storage.local) {
        await extApi.storage.local.set({ isBlockingActive: true, lockedUntil });
      }
      if (extApi.action && typeof extApi.action.setBadgeText === "function") {
        await extApi.action.setBadgeText({ text: "LOCK" });
        if (typeof extApi.action.setBadgeBackgroundColor === "function") {
          await extApi.action.setBadgeBackgroundColor({ color: "#8B5CF6" }); // Violet badge for Focus Lock
        }
      }
      console.log(`[GTFB Background] Focus Lock activated for ${durationMinutes} minutes.`);
    } else {
      if (extApi.storage && extApi.storage.local) {
        await extApi.storage.local.set({ isBlockingActive: true, lockedUntil: null });
      }
      if (extApi.action && typeof extApi.action.setBadgeText === "function") {
        await extApi.action.setBadgeText({ text: "ON" });
        if (typeof extApi.action.setBadgeBackgroundColor === "function") {
          await extApi.action.setBadgeBackgroundColor({ color: "#22C55E" }); // Green badge for standard ON
        }
      }
      console.log("[GTFB Background] Blocking manually enabled.");
    }

    try {
      await reportStatusToApp();
    } catch (e) {
      console.debug("[GTFB Background] Error reporting status after toggle enable:", e);
    }

    return {
      success: true,
      isBlockingActive: true,
      isLocked: Boolean(lockedUntil),
      lockedUntil: lockedUntil
    };
  } else {
    await clearBlockRules();
    if (extApi.storage && extApi.storage.local) {
      await extApi.storage.local.set({ isBlockingActive: false, lockedUntil: null });
    }
    if (extApi.action && typeof extApi.action.setBadgeText === "function") {
      await extApi.action.setBadgeText({ text: "" });
    }
    console.log("[GTFB Background] Blocking manually disabled.");

    try {
      await reportStatusToApp();
    } catch (e) {
      console.debug("[GTFB Background] Error reporting status after toggle disable:", e);
    }

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

// Runtime message listener (extApi.runtime / chrome.runtime.onMessage)
if (extApi.runtime && extApi.runtime.onMessage && typeof extApi.runtime.onMessage.addListener === "function") {
  extApi.runtime.onMessage.addListener((message, sender, sendResponse) => {
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

    if (message.action === "SYNC_CONFIG" || message.action === "FETCH_CONFIG") {
      fetchConfigFromApp(message.startPort, message.maxPort, message.timeoutMs)
        .then((res) => sendResponse(res))
        .catch((err) => sendResponse({ success: false, error: err.message }));
      return true;
    }

    if (message.action === "GET_SYNC_STATUS") {
      getSyncStatus()
        .then((res) => sendResponse(res))
        .catch((err) => sendResponse({ success: false, error: err.message }));
      return true;
    }

    if (message.action === "REPORT_STATUS") {
      reportStatusToApp(message.apiPort)
        .then((res) => sendResponse(res))
        .catch((err) => sendResponse({ success: false, error: err.message }));
      return true;
    }

    return false;
  });
}

// Initialize sync, block rules, and badge on extension install or update (chrome.runtime.onInstalled.addListener)
if (extApi.runtime && extApi.runtime.onInstalled && typeof extApi.runtime.onInstalled.addListener === "function") {
  extApi.runtime.onInstalled.addListener(async (details) => {
    console.log("[GTFB Background] Extension installed/updated:", details?.reason);
    try {
      setupScheduleAlarm();
      setupSyncAlarm();
      await fetchConfigFromApp();
      const status = await getBlockingStatus();
      if (status.isLocked) {
        const remainingMinutes = Math.max(1, Math.round(status.remainingSeconds / 60));
        await handleToggle(true, { durationMinutes: remainingMinutes });
      } else {
        await evaluateCurrentSchedule();
      }
    } catch (err) {
      console.error("[GTFB Background] Failed to initialize on install:", err);
    }
  });
}

// Re-apply block rules and trigger sync on browser startup (chrome.runtime.onStartup.addListener)
if (extApi.runtime && extApi.runtime.onStartup && typeof extApi.runtime.onStartup.addListener === "function") {
  extApi.runtime.onStartup.addListener(async () => {
    console.log("[GTFB Background] Browser startup detected.");
    try {
      setupScheduleAlarm();
      setupSyncAlarm();
      await fetchConfigFromApp();
      const status = await getBlockingStatus();
      if (status.isLocked) {
        const remainingMinutes = Math.max(1, Math.round(status.remainingSeconds / 60));
        await handleToggle(true, { durationMinutes: remainingMinutes });
      } else {
        await evaluateCurrentSchedule();
      }
    } catch (err) {
      console.error("[GTFB Background] Failed to initialize on startup:", err);
    }
  });
}

export {
  applyBlockRules,
  clearBlockRules,
  syncAndApplyRules,
  fetchConfigFromApp,
  setupSyncAlarm,
  SYNC_ALARM_NAME,
  getSyncStatus,
  reportStatusToApp
};

