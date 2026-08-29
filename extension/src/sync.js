/**
 * GTFB — Anti-Distraction Suite
 * Localhost HTTP Configuration Sync Client
 */

import { saveCachedConfig } from "./storage.js";
import { extApi } from "./compat.js";

export const START_PORT = 8765;
export const MAX_PORT = 8775;
export const SYNC_ALARM_NAME = "gtfb-poll-sync";
export const DEFAULT_TIMEOUT_MS = 2000;

/**
 * Creates or updates the recurring configuration sync alarm.
 * @param {number} [periodInMinutes=1]
 */
export function setupSyncAlarm(periodInMinutes = 1) {
  if (extApi.alarms && typeof extApi.alarms.create === "function") {
    extApi.alarms.create(SYNC_ALARM_NAME, {
      periodInMinutes: periodInMinutes
    });
  }
}

let activeEventStreamController = null;
let isStreamActive = false;

/**
 * Handles incoming realtime configuration payload received via SSE /events or polling.
 * @param {object} configData
 * @param {number} activePort
 */
export async function handleIncomingConfigUpdate(configData, activePort) {
  if (!configData) return;
  await saveCachedConfig(configData);
  if (extApi.storage && extApi.storage.local) {
    await extApi.storage.local.set({
      isConnected: true,
      apiPort: activePort,
      lastSyncSuccess: Date.now()
    });
  }
  console.log(`[GTFB Sync] Realtime configuration synced from port ${activePort}`);

  try {
    const bg = await import("./background.js");
    if (bg && typeof bg.evaluateCurrentSchedule === "function") {
      await bg.evaluateCurrentSchedule();
    }
  } catch (e) {
    console.warn("[GTFB Sync] Error evaluating schedule after realtime sync:", e);
  }

  try {
    await reportStatusToApp(activePort);
  } catch (e) {
    console.warn("[GTFB Sync] Error reporting status to app:", e);
  }
}

/**
 * Establishes a persistent Server-Sent Events (SSE) stream with the desktop API server.
 * Listens for real-time config updates without waiting for polling alarms.
 * @param {number} port
 */
export async function startRealtimeEventStream(port) {
  // If running under Node.js test environment, skip persistent SSE stream so tests exit cleanly
  if (typeof process !== "undefined" && Boolean(process?.versions?.node)) {
    return;
  }
  if (isStreamActive) {
    return;
  }


  if (activeEventStreamController) {
    try {
      activeEventStreamController.abort();
    } catch (e) {}
    activeEventStreamController = null;
  }

  const controller = new AbortController();
  activeEventStreamController = controller;
  isStreamActive = true;

  try {
    const res = await fetch(`http://127.0.0.1:${port}/events`, {
      signal: controller.signal,
      headers: { Accept: "text/event-stream" }
    });

    if (!res.ok || !res.body) {
      isStreamActive = false;
      return;
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let buffer = "";

    while (isStreamActive) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";

      for (const line of lines) {
        const trimmed = line.trim();
        if (trimmed.startsWith("data:")) {
          const dataStr = trimmed.slice(5).trim();
          if (dataStr) {
            try {
              const payload = JSON.parse(dataStr);
              if (payload && (payload.type === "config_updated" || payload.type === "init") && payload.config) {
                await handleIncomingConfigUpdate(payload.config, port);
              }
            } catch (err) {
              console.debug("[GTFB Sync] Error parsing SSE event payload:", err);
            }
          }
        }
      }
    }
  } catch (err) {
    // Normal disconnection or network abort
    console.debug("[GTFB Sync] Realtime event stream disconnected:", err.message);
  } finally {
    isStreamActive = false;
    activeEventStreamController = null;
  }
}

/**
 * Fetches the latest configuration profile from the local GTFB desktop API.
 * Iterates through the supported port range (8765-8775) with timeout aborts.
 * Updates local storage cache, re-evaluates schedule/rules, and starts the realtime stream.
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
    await handleIncomingConfigUpdate(configData, activePort);

    // Launch realtime SSE background stream if not active
    startRealtimeEventStream(activePort).catch(() => {});

    return { success: true, config: configData, port: activePort };
  } else {
    if (extApi.storage && extApi.storage.local) {
      await extApi.storage.local.set({ isConnected: false });
    }
    console.warn("[GTFB Sync] Desktop app not reachable on localhost.");
    return { success: false };
  }
}


/**
 * Detect the browser vendor (brave, edge, firefox, opera, vivaldi, chrome).
 * @returns {Promise<string>}
 */
export async function detectBrowser() {
  if (typeof navigator === "undefined") {
    return "chrome";
  }

  // 1. Check Brave's official navigator.brave.isBrave() API
  try {
    if (navigator.brave && typeof navigator.brave.isBrave === "function") {
      const isBrave = await navigator.brave.isBrave();
      if (isBrave) {
        return "brave";
      }
    }
  } catch (err) {
    // Ignore error
  }

  const ua = navigator.userAgent || "";

  // 2. Check User-Agent strings
  if (ua.includes("Brave") || ua.includes("brave")) {
    return "brave";
  }
  if (ua.includes("Edg/")) {
    return "edge";
  }
  if (ua.includes("OPR/") || ua.includes("Opera")) {
    return "opera";
  }
  if (ua.includes("Vivaldi")) {
    return "vivaldi";
  }
  if (ua.includes("Firefox/")) {
    return "firefox";
  }

  // 3. Check User-Agent Data Brands
  try {
    if (navigator.userAgentData && Array.isArray(navigator.userAgentData.brands)) {
      const hasBraveBrand = navigator.userAgentData.brands.some(
        (b) => b && typeof b.brand === "string" && b.brand.toLowerCase().includes("brave")
      );
      if (hasBraveBrand) {
        return "brave";
      }
    }
  } catch (err) {
    // Ignore error
  }

  return "chrome";
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

    if (extApi.storage && extApi.storage.local) {
      const stored = await extApi.storage.local.get(["isBlockingActive", "apiPort", "lockedUntil"]);
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
      extApi.declarativeNetRequest &&
      typeof extApi.declarativeNetRequest.getDynamicRules === "function"
    ) {
      const dynamicRules = await extApi.declarativeNetRequest.getDynamicRules();
      rulesCount = Array.isArray(dynamicRules) ? dynamicRules.length : 0;
    }

    // Detect browser vendor
    const browserName = await detectBrowser();


    let version = "1.0.0";
    if (
      extApi.runtime &&
      typeof extApi.runtime.getManifest === "function"
    ) {
      const manifest = extApi.runtime.getManifest();
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
  if (!extApi.storage || !extApi.storage.local) {
    return { isConnected: false, apiPort: START_PORT, lastSyncSuccess: null };
  }
  const data = await extApi.storage.local.get(["isConnected", "apiPort", "lastSyncSuccess"]);
  return {
    isConnected: Boolean(data.isConnected),
    apiPort: (data && typeof data.apiPort === "number") ? data.apiPort : START_PORT,
    lastSyncSuccess: data?.lastSyncSuccess || null
  };
}

