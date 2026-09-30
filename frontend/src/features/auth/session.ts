import { apiConfig } from "../../api/config";

const listeners = new Set<() => void>();
let memoryToken: string | null = null;
let storageAvailable = true;

export function getAccessToken(): string | null {
  if (storageAvailable) {
    try { memoryToken = localStorage.getItem(apiConfig.tokenStorageKey); }
    catch { storageAvailable = false; }
  }
  return memoryToken;
}

export function saveAccessToken(token: string | null) {
  memoryToken = token;
  if (storageAvailable) {
    try {
      if (token) localStorage.setItem(apiConfig.tokenStorageKey, token);
      else localStorage.removeItem(apiConfig.tokenStorageKey);
    } catch { storageAvailable = false; }
  }
  listeners.forEach(listener => listener());
}

// A late response from an older session must not sign out a newer session.
export function clearAccessToken(expectedToken?: string) {
  if (expectedToken && getAccessToken() !== expectedToken) return;
  saveAccessToken(null);
}

export function subscribeSession(listener: () => void) {
  listeners.add(listener);
  const onStorage = (event: StorageEvent) => {
    if (event.key === apiConfig.tokenStorageKey || event.key === null) listener();
  };
  window.addEventListener("storage", onStorage);
  return () => {
    listeners.delete(listener);
    window.removeEventListener("storage", onStorage);
  };
}
