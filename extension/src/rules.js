/**
 * GTFB — Anti-Distraction Suite
 * DeclarativeNetRequest Rule Compiler & Manager
 */

import { getActiveDomains } from "./storage.js";
import { extApi } from "./compat.js";

export const TEST_DOMAINS = [
  "reddit.com",
  "youtube.com",
  "x.com",
  "twitter.com",
  "instagram.com"
];

/**
 * Sanitizes a domain string by stripping protocol, path, port, and whitespace.
 * @param {string} domain - Raw domain string
 * @returns {string} Cleaned domain string
 */
export function sanitizeDomain(domain) {
  if (!domain || typeof domain !== "string") {
    return "";
  }
  let clean = domain.trim().toLowerCase();
  // Strip protocol if present
  clean = clean.replace(/^https?:\/\//i, "");
  // Strip trailing slashes, paths, queries
  clean = clean.split("/")[0].split("?")[0].split("#")[0];
  // Strip port
  clean = clean.split(":")[0];
  return clean;
}

/**
 * Compiles a list of domains into declarativeNetRequest Rule objects.
 * @param {string[]} domains - List of domain strings to block
 * @returns {Array<object>} Array of declarativeNetRequest rule objects
 */
export function compileBlockRules(domains = TEST_DOMAINS) {
  if (!Array.isArray(domains)) {
    return [];
  }

  const validDomains = domains
    .map(sanitizeDomain)
    .filter((d) => Boolean(d));

  // Deduplicate domains while preserving order
  const uniqueDomains = [...new Set(validDomains)];

  return uniqueDomains.map((domain, index) => ({
    id: index + 1,
    priority: 1,
    action: {
      type: "redirect",
      redirect: { extensionPath: `/src/blocked.html?domain=${encodeURIComponent(domain)}` }
    },
    condition: {
      urlFilter: `||${domain}`,
      resourceTypes: ["main_frame"]
    }
  }));
}

/**
 * Compiles and applies dynamic blocking rules directly from a configuration object.
 * @param {object} config - Configuration profile object
 * @returns {Promise<Array<object>>} The applied rules
 */
export async function syncAndApplyRules(config) {
  if (!config || !config.block_rules || !Array.isArray(config.block_rules)) {
    return [];
  }

  const domains = [];
  for (const rule of config.block_rules) {
    if (rule && (rule.active !== false) && Array.isArray(rule.domains)) {
      domains.push(...rule.domains);
    }
  }

  const dnr = extApi.declarativeNetRequest;
  const existingRules = (dnr && typeof dnr.getDynamicRules === "function")
    ? await dnr.getDynamicRules()
    : [];
  const removeRuleIds = existingRules.map((r) => r.id);
  const addRules = compileBlockRules(domains);

  if (dnr && typeof dnr.updateDynamicRules === "function") {
    await dnr.updateDynamicRules({
      removeRuleIds: removeRuleIds,
      addRules: addRules
    });
  }

  console.log(`[GTFB Rules] Synced and applied ${addRules.length} dynamic rules.`);
  return addRules;
}

/**
 * Applies dynamic blocking rules to declarativeNetRequest engine.
 * @param {string[]|null} [domains] - Optional custom domain list. If omitted or null, queries getActiveDomains() from storage.
 * @returns {Promise<Array<object>>} The applied rules
 */
export async function applyBlockRules(domains = null) {
  let targetDomains = domains;
  if (!targetDomains) {
    try {
      targetDomains = await getActiveDomains();
    } catch (e) {
      targetDomains = TEST_DOMAINS;
    }
  }

  const dnr = extApi.declarativeNetRequest;
  const existingRules = (dnr && typeof dnr.getDynamicRules === "function")
    ? await dnr.getDynamicRules()
    : [];
  const removeRuleIds = existingRules.map((r) => r.id);
  const addRules = compileBlockRules(targetDomains);

  if (dnr && typeof dnr.updateDynamicRules === "function") {
    await dnr.updateDynamicRules({
      removeRuleIds: removeRuleIds,
      addRules: addRules
    });
  }

  console.log(`[GTFB] Applied ${addRules.length} dynamic blocking rules.`);
  return addRules;
}

/**
 * Clears all active dynamic blocking rules.
 * @returns {Promise<void>}
 */
export async function clearBlockRules() {
  const dnr = extApi.declarativeNetRequest;
  const existingRules = (dnr && typeof dnr.getDynamicRules === "function")
    ? await dnr.getDynamicRules()
    : [];
  const removeRuleIds = existingRules.map((r) => r.id);

  if (dnr && typeof dnr.updateDynamicRules === "function") {
    await dnr.updateDynamicRules({
      removeRuleIds: removeRuleIds,
      addRules: []
    });
  }

  console.log("[GTFB] Cleared all blocking rules.");
}

