// The submit key lives in this browser only, never in the built bundle.
const STORAGE_KEY = "hermes-intake.api-key";

export function loadApiKey(): string {
  try {
    return window.localStorage.getItem(STORAGE_KEY) ?? "";
  } catch {
    return "";
  }
}

export function saveApiKey(key: string): void {
  try {
    if (key) window.localStorage.setItem(STORAGE_KEY, key);
    else window.localStorage.removeItem(STORAGE_KEY);
  } catch {
    // Storage blocked (private window): the key lasts for this page only.
  }
}
