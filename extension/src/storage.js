/**
 * GTFB — Anti-Distraction Suite
 * Storage Cache Wrapper Module
 */

import { extApi } from "./compat.js";

export const DEFAULT_CONFIG = {
  version: 1,
  profile_name: "Default",
  app_close_schedule: {
    target_hour: 22,
    target_minute: 0,
    enabled: true
  },
  block_rules: [
    {
      domains: ["reddit.com", "youtube.com", "x.com", "twitter.com", "instagram.com"],
      start_hour: 22,
      start_minute: 0,
      end_hour: 6,
      end_minute: 0,
      active: true
    }
  ]
};

export const DEFAULT_API_PORT = 8765;

/**
 * Retrieves the cached configuration from storage.
 * If storage is empty, saves and returns the default configuration.
 * @returns {Promise<object>} The cached configuration object
 */
export async function getCachedConfig() {
  const storage = extApi.storage?.local;
  if (!storage || typeof storage.get !== "function") {
    return DEFAULT_CONFIG;
  }
  const data = await storage.get("cachedConfig");
  if (!data || !data.cachedConfig) {
    await saveCachedConfig(DEFAULT_CONFIG);
    return DEFAULT_CONFIG;
  }
  return data.cachedConfig;
}

/**
 * Saves configuration to storage and updates lastSyncedAt.
 * @param {object} config - Configuration object to persist
 * @returns {Promise<void>}
 */
export async function saveCachedConfig(config) {
  const storage = extApi.storage?.local;
  if (!storage || typeof storage.set !== "function") {
    return;
  }
  await storage.set({
    cachedConfig: config,
    lastSyncedAt: Date.now()
  });
}

/**
 * Extracts and deduplicates domains from all active block rules in cachedConfig.
 * @returns {Promise<string[]>} Array of unique active domain strings
 */
export async function getActiveDomains() {
  const config = await getCachedConfig();
  const domains = [];
  if (config && config.block_rules && Array.isArray(config.block_rules)) {
    for (const rule of config.block_rules) {
      if (rule && (rule.active !== false) && Array.isArray(rule.domains)) {
        domains.push(...rule.domains);
      }
    }
  }
  return [...new Set(domains)];
}

/**
 * Retrieves the configured local API port from storage.
 * @returns {Promise<number>}
 */
export async function getApiPort() {
  const storage = extApi.storage?.local;
  if (!storage || typeof storage.get !== "function") {
    return DEFAULT_API_PORT;
  }
  const data = await storage.get("apiPort");
  return (data && typeof data.apiPort === "number") ? data.apiPort : DEFAULT_API_PORT;
}

/**
 * Sets the local API port in storage.
 * @param {number} port
 * @returns {Promise<void>}
 */
export async function setApiPort(port) {
  const storage = extApi.storage?.local;
  if (!storage || typeof storage.set !== "function") {
    return;
  }
  await storage.set({ apiPort: port });
}

/**
 * Retrieves the timestamp of the last successful config sync.
 * @returns {Promise<number|null>}
 */
export async function getLastSyncedAt() {
  const storage = extApi.storage?.local;
  if (!storage || typeof storage.get !== "function") {
    return null;
  }
  const data = await storage.get("lastSyncedAt");
  return data?.lastSyncedAt || null;
}

