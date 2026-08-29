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
