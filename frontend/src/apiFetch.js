import { getToken, authHeaders, clearAuth } from './auth';
import { API_URL } from './config';

/**
 * Safely parse a Response as JSON.
 * If the body is not valid JSON (e.g. nginx error HTML), throws with the
 * HTTP status and a short snippet of the body instead of a raw parse error.
 */
export async function safeJson(response) {
  const text = await response.text();
  try {
    return JSON.parse(text);
  } catch {
    const preview = text.slice(0, 120).replace(/\s+/g, ' ').trim();
    const status = response.status !== 200 ? ` (${response.status})` : '';
    throw new Error(`Server error${status} — unexpected response: ${preview || '(empty)'}`);
  }
}

/**
 * Authenticated fetch wrapper. Injects the Bearer token header automatically.
 * On 401, clears stored credentials and reloads to force re-login.
 */
export async function apiFetch(url, options = {}) {
  const response = await fetch(url, {
    ...options,
    headers: {
      ...(options.headers || {}),
      ...authHeaders(),
    },
  });

  if (response.status === 401) {
    clearAuth();
    window.location.reload();
    return response;
  }

  return response;
}

/**
 * Build an authenticated EventSource URL by appending ?token=... as a query param.
 * (EventSource cannot set custom headers, so the token is passed as a query param.)
 */
export function authEventSourceUrl(path) {
  const token = getToken();
  const sep = path.includes('?') ? '&' : '?';
  return `${API_URL}${path}${token ? `${sep}token=${encodeURIComponent(token)}` : ''}`;
}
