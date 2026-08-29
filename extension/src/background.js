/**
 * GTFB — Anti-Distraction Suite
 * Background Service Worker (Manifest V3)
 */

import { applyBlockRules, clearBlockRules } from "./rules.js";

// Initialize block rules on extension install or update
chrome.runtime.onInstalled.addListener(async (details) => {
  console.log("[GTFB Background] Extension installed/updated:", details.reason);
  try {
    await applyBlockRules();
  } catch (err) {
    console.error("[GTFB Background] Failed to apply block rules on install:", err);
  }
});

// Re-apply block rules on browser startup
chrome.runtime.onStartup.addListener(async () => {
  console.log("[GTFB Background] Browser startup detected.");
  try {
    await applyBlockRules();
  } catch (err) {
    console.error("[GTFB Background] Failed to apply block rules on startup:", err);
  }
});

export { applyBlockRules, clearBlockRules };
