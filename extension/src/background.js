/**
 * GTFB — Anti-Distraction Suite
 * Background Service Worker (Manifest V3)
 */

chrome.runtime.onInstalled.addListener((details) => {
  console.log("[GTFB Background] Extension installed/updated:", details.reason);
});
