export function getStoredAuth() {
  try {
    return JSON.parse(window.localStorage.getItem("sistema_ads_auth") || "null");
  } catch {
    return null;
  }
}

export function setStoredAuth(auth) {
  window.localStorage.setItem("sistema_ads_auth", JSON.stringify(auth));
}

export function clearStoredAuth() {
  window.localStorage.removeItem("sistema_ads_auth");
}

export function getAccessToken() {
  return getStoredAuth()?.access_token || null;
}

export function authHeaders(extraHeaders = {}) {
  const token = getAccessToken();
  return {
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...extraHeaders,
  };
}

export async function authFetch(url, options = {}) {
  const headers = authHeaders(options.headers || {});
  return fetch(url, { ...options, headers });
}
