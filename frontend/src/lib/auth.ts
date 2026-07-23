// Token storage + session helpers (§9.2 lib/auth).
//
// The access token lives in localStorage for this local-dev build. The
// blueprint (§8) puts refresh tokens in httpOnly Secure SameSite cookies —
// which JS deliberately cannot read — so a production build must move token
// custody to the cookie and drop this module's storage half.

const KEY = "taxify.access_token";

let token: string | null = localStorage.getItem(KEY);
const listeners = new Set<(t: string | null) => void>();

export function getToken(): string | null {
  return token;
}

export function setToken(next: string | null): void {
  token = next;
  if (next) localStorage.setItem(KEY, next);
  else localStorage.removeItem(KEY);
  listeners.forEach((fn) => fn(next));
}

export function onTokenChange(fn: (t: string | null) => void): () => void {
  listeners.add(fn);
  return () => listeners.delete(fn);
}
