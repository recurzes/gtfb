/**
 * GTFB — Anti-Distraction Suite
 * Localhost HTTP Configuration Sync Client
 */

import { saveCachedConfig } from "./storage.js";

export const START_PORT = 8765;
export const MAX_PORT = 8775;
export const SYNC_ALARM_NAME = "gtfb-poll-sync";
export const DEFAULT_TIMEOUT_MS = 2000;

/**
 * Creates or updates the recurring configuration sync alarm.
 * @param {number} [periodInMinutes=1]
 */
export function setupSyncAlarm(periodInMinutes = 1) {
  if (typeof chrome !== "undefined" && chrome.alarms && chrome.alarms.create) {
    chrome.alarms.create(SYNC_ALARM_NAME, {
      periodInMinutes: periodInMinutes
    });
  }
}

/**
 * Fetches the latest configuration profile from the local GTFB desktop API.
 * Iterates through the supported port range (8765-8775) with timeout aborts.
 * Updates local storage cache, re-evaluates schedule/rules, and connection state upon success or failure.
 *
 * @param {number} [startPort=8765] - Starting port to scan
 * @param {number} [maxPort=8775] - Highest fallback port to scan
 * @param {number} [timeoutMs=2000] - Request timeout per port attempt
 * @returns {Promise<{ success: boolean, config?: object, port?: number, error?: string }>}
 */
export async function fetchConfigFromApp(
  startPort = START_PORT,
  maxPort = MAX_PORT,
  timeoutMs = DEFAULT_TIMEOUT_MS
) {
  let activePort = null;
  let configData = null;

  for (let port = startPort; port <= maxPort; port++) {
    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

      const res = await fetch(`http://127.0.0.1:${port}/config`, {
        signal: controller.signal
      });
      clearTimeout(timeoutId);

      if (res.ok) {
        configData = await res.json();
        activePort = port;
        break;
      }
    } catch (e) {
      // Server not listening on this port, refused, or timed out; try next fallback
    }
  }

  if (configData && activePort) {
    await saveCachedConfig(configData);
    if (typeof chrome !== "undefined" && chrome.storage && chrome.storage.local) {
      await chrome.storage.local.set({
        isConnected: true,
        apiPort: activePort,
        lastSyncSuccess: Date.now()
      });
    }
    console.log(`[GTFB Sync] Successfully synced config from port ${activePort}`);

    try {
      const bg = await import("./background.js");
      if (bg && typeof bg.evaluateCurrentSchedule === "function") {
        await bg.evaluateCurrentSchedule();
      }
    } catch (e) {
      console.warn("[GTFB Sync] Error evaluating schedule after sync:", e);
    }

    try {
      await reportStatusToApp(activePort);
    } catch (e) {
      console.warn("[GTFB Sync] Error reporting status to app:", e);
    }

    return { success: true, config: configData, port: activePort };
  } else {
    if (typeof chrome !== "undefined" && chrome.storage && chrome.storage.local) {
      await chrome.storage.local.set({ isConnected: false });
    }
    console.warn("[GTFB Sync] Desktop app not reachable on localhost.");
    return { success: false };
  }
}

/**
 * Reports current extension enforcement state, dynamic rule count, and browser metadata
 * to the GTFB desktop app's POST /status endpoint.
 *
 * @param {number|null} [apiPort=null] - Target desktop API port. If not supplied, reads from storage or defaults to 8765.
 * @returns {Promise<{ success: boolean, payload?: object, error?: string }>}
 */
export async function reportStatusToApp(apiPort = null) {
  try {
    let targetPort = apiPort;
    let isBlockingActive = false;

    if (typeof chrome !== "undefined" && chrome.storage && chrome.storage.local) {
      const stored = await chrome.storage.local.get(["isBlockingActive", "apiPort", "lockedUntil"]);
      if (stored) {
        if (!targetPort && typeof stored.apiPort === "number") {
          targetPort = stored.apiPort;
        }
        const now = Date.now();
        const isLocked = Boolean(stored.lockedUntil && stored.lockedUntil > now);
        isBlockingActive = isLocked || (stored.isBlockingActive !== undefined ? Boolean(stored.isBlockingActive) : true);
      }
    }

    if (!targetPort) {
      targetPort = START_PORT;
    }

    let rulesCount = 0;
    if (
      typeof chrome !== "undefined" &&
      chrome.declarativeNetRequest &&
      typeof chrome.declarativeNetRequest.getDynamicRules === "function"
    ) {
      const dynamicRules = await chrome.declarativeNetRequest.getDynamicRules();
      rulesCount = Array.isArray(dynamicRules) ? dynamicRules.length : 0;
    }

    // Detect browser vendor
    let browserName = "chrome";
    if (typeof navigator !== "undefined" && navigator.userAgent) {
      if (navigator.userAgent.includes("Edg/")) {
        browserName = "edge";
      } else if (navigator.userAgent.includes("Firefox/")) {
        browserName = "firefox";
      }
    }

    let version = "1.0.0";
    if (
      typeof chrome !== "undefined" &&
      chrome.runtime &&
      typeof chrome.runtime.getManifest === "function"
    ) {
      const manifest = chrome.runtime.getManifest();
      if (manifest && manifest.version) {
        version = manifest.version;
      }
    }

    const payload = {
      browser: browserName,
      version: version,
      blocking_active: Boolean(isBlockingActive),
      rules_count: rulesCount,
      timestamp: new Date().toISOString()
    };

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), DEFAULT_TIMEOUT_MS);

    const res = await fetch(`http://127.0.0.1:${targetPort}/status`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify(payload),
      signal: controller.signal
    });
    clearTimeout(timeoutId);

    if (res.ok) {
      console.log("[GTFB Status] Reported state to desktop app:", payload);
      return { success: true, payload };
    } else {
      console.debug("[GTFB Status] Server responded with status:", res.status);
      return { success: false, error: `HTTP ${res.status}` };
    }
  } catch (err) {
    // Desktop app may be closed or offline; ignore gracefully without throwing
    console.debug("[GTFB Status] Could not report status to desktop app:", err.message);
    return { success: false, error: err.message };
  }
}

/**
 * Retrieves the current synchronization and connection status from storage.
 * @returns {Promise<{ isConnected: boolean, apiPort: number, lastSyncSuccess: number|null }>}
 */
export async function getSyncStatus() {
  if (typeof chrome === "undefined" || !chrome.storage || !chrome.storage.local) {
    return { isConnected: false, apiPort: START_PORT, lastSyncSuccess: null };
  }
  const data = await chrome.storage.local.get(["isConnected", "apiPort", "lastSyncSuccess"]);
  return {
    isConnected: Boolean(data.isConnected),
    apiPort: (data && typeof data.apiPort === "number") ? data.apiPort : START_PORT,
    lastSyncSuccess: data?.lastSyncSuccess || null
  };
}
