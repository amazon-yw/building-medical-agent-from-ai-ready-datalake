/**
 * Cognito Hosted UI + PKCE flow (no SDK dependency)
 * Config is injected at build time via __COGNITO_CONFIG__ or read from window.
 */

export interface CognitoConfig {
  userPoolId: string;
  clientId: string;
  domain: string;       // e.g. https://medical-agent-123456789.auth.us-east-1.amazoncognito.com
  redirectUri: string;  // e.g. https://xxxx.cloudfront.net/app
}

declare const __COGNITO_CONFIG__: CognitoConfig;

export function getConfig(): CognitoConfig {
  return __COGNITO_CONFIG__;
}

// ── PKCE helpers ──────────────────────────────────────────────────────────────

function base64url(buf: ArrayBuffer): string {
  return btoa(String.fromCharCode(...new Uint8Array(buf)))
    .replace(/\+/g, "-").replace(/\//g, "_").replace(/=/g, "");
}

async function generatePKCE(): Promise<{ verifier: string; challenge: string }> {
  const verifier = base64url(crypto.getRandomValues(new Uint8Array(32)));
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(verifier));
  return { verifier, challenge: base64url(digest) };
}

// ── Login / Logout ────────────────────────────────────────────────────────────

export async function login(): Promise<void> {
  const cfg = getConfig();
  const { verifier, challenge } = await generatePKCE();
  const state = base64url(crypto.getRandomValues(new Uint8Array(16)));

  sessionStorage.setItem("pkce_verifier", verifier);
  sessionStorage.setItem("pkce_state", state);

  const params = new URLSearchParams({
    response_type: "code",
    client_id: cfg.clientId,
    redirect_uri: cfg.redirectUri,
    scope: "openid email profile",
    code_challenge_method: "S256",
    code_challenge: challenge,
    state,
  });
  window.location.href = `${cfg.domain}/oauth2/authorize?${params}`;
}

export function logout(): void {
  clearTokens();
  const cfg = getConfig();
  const params = new URLSearchParams({
    client_id: cfg.clientId,
    logout_uri: cfg.redirectUri,
  });
  window.location.href = `${cfg.domain}/logout?${params}`;
}

// ── Token exchange ────────────────────────────────────────────────────────────

export interface Tokens {
  idToken: string;
  accessToken: string;
  expiresAt: number; // epoch ms
}

export async function exchangeCode(code: string, state: string): Promise<Tokens> {
  const cfg = getConfig();
  const verifier = sessionStorage.getItem("pkce_verifier") ?? "";
  const savedState = sessionStorage.getItem("pkce_state") ?? "";

  if (state !== savedState) throw new Error("OAuth state mismatch");

  const body = new URLSearchParams({
    grant_type: "authorization_code",
    client_id: cfg.clientId,
    redirect_uri: cfg.redirectUri,
    code,
    code_verifier: verifier,
  });

  const res = await fetch(`${cfg.domain}/oauth2/token`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body,
  });
  if (!res.ok) throw new Error(`Token exchange failed: ${res.status}`);

  const data = await res.json();
  sessionStorage.removeItem("pkce_verifier");
  sessionStorage.removeItem("pkce_state");

  const tokens: Tokens = {
    idToken: data.id_token,
    accessToken: data.access_token,
    expiresAt: Date.now() + data.expires_in * 1000,
  };
  saveTokens(tokens);
  return tokens;
}

export async function refreshTokens(): Promise<Tokens | null> {
  const cfg = getConfig();
  const refresh = localStorage.getItem("refresh_token");
  if (!refresh) return null;

  const body = new URLSearchParams({
    grant_type: "refresh_token",
    client_id: cfg.clientId,
    refresh_token: refresh,
  });

  const res = await fetch(`${cfg.domain}/oauth2/token`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body,
  });
  if (!res.ok) { clearTokens(); return null; }

  const data = await res.json();
  const tokens: Tokens = {
    idToken: data.id_token,
    accessToken: data.access_token,
    expiresAt: Date.now() + data.expires_in * 1000,
  };
  saveTokens(tokens);
  return tokens;
}

// ── Token storage ─────────────────────────────────────────────────────────────

function saveTokens(t: Tokens): void {
  localStorage.setItem("id_token", t.idToken);
  localStorage.setItem("access_token", t.accessToken);
  localStorage.setItem("token_expires_at", String(t.expiresAt));
}

export function clearTokens(): void {
  ["id_token", "access_token", "token_expires_at", "refresh_token"].forEach(k =>
    localStorage.removeItem(k)
  );
}

export function loadTokens(): Tokens | null {
  const idToken = localStorage.getItem("id_token");
  const accessToken = localStorage.getItem("access_token");
  const expiresAt = Number(localStorage.getItem("token_expires_at") ?? 0);
  if (!idToken || !accessToken) return null;
  return { idToken, accessToken, expiresAt };
}

export function isTokenValid(t: Tokens): boolean {
  return Date.now() < t.expiresAt - 30_000; // 30s buffer
}

export function getEmail(idToken: string): string {
  try {
    const payload = JSON.parse(atob(idToken.split(".")[1]));
    return payload.email ?? payload["cognito:username"] ?? "user";
  } catch {
    return "user";
  }
}
