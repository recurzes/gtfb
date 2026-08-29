/**
 * GTFB — Anti-Distraction Suite
 * Cross-Browser Compatibility Layer
 * Normalizes extension API access across Firefox (browser.*) and Chromium (chrome.*).
 */

/**
 * Returns the active underlying extension API root object.
 * Resolves `browser` first (W3C standard / Firefox / polyfilled), then `chrome` (Chromium).
 * @returns {object} The browser or chrome API object
 */
export function getExtApi() {
  if (typeof browser !== "undefined" && browser !== null) {
    return browser;
  }
  if (typeof chrome !== "undefined" && chrome !== null) {
    return chrome;
  }
  return {};
}

/**
 * Unified cross-browser namespace proxy.
 * Dynamically resolves namespaces (storage, alarms, action, declarativeNetRequest, runtime)
 * on the current global environment.
 */
export const extApi = new Proxy({}, {
  get(target, prop, receiver) {
    const api = getExtApi();
    const val = Reflect.get(api, prop);
    if (typeof val === "function") {
      return val.bind(api);
    }
    return val;
  },
  has(target, prop) {
    return prop in getExtApi();
  },
  set(target, prop, value, receiver) {
    return Reflect.set(getExtApi(), prop, value);
  },
  ownKeys(target) {
    return Reflect.ownKeys(getExtApi());
  },
  getOwnPropertyDescriptor(target, prop) {
    return Reflect.getOwnPropertyDescriptor(getExtApi(), prop);
  }
});
