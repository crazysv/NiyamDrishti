import {
  SSOAuthResponse,
  SSOInitResponse,
  SSOSandboxProfile,
  SSOStatusResponse,
} from "../types/sso";
import { API_BASE } from "../utils/apiConfig";

/**
 * Checks the status and operating mode (live vs sandbox) of the Government SSO gateway.
 */
export async function getSSOStatus(): Promise<SSOStatusResponse> {
  const res = await fetch(`${API_BASE}/auth/sso/status`);
  if (!res.ok) {
    throw new Error(`Failed to check SSO status: ${res.status}`);
  }
  return res.json();
}

/**
 * Initiates the MeriPehchan / Jan Parichay OIDC login flow.
 */
export async function initiateSSO(redirectUri?: string): Promise<SSOInitResponse> {
  const url = `${API_BASE}/auth/sso/init${redirectUri ? `?redirect_uri=${encodeURIComponent(redirectUri)}` : ""}`;
  const res = await fetch(url);
  if (!res.ok) {
    throw new Error(`Failed to initiate SSO: ${res.status}`);
  }
  return res.json();
}

/**
 * Lists available officer personas for sandbox / testing mode.
 */
export async function listSandboxPersonas(): Promise<SSOSandboxProfile[]> {
  const res = await fetch(`${API_BASE}/auth/sso/sandbox`);
  if (!res.ok) {
    throw new Error(`Failed to load sandbox personas: ${res.status}`);
  }
  return res.json();
}

/**
 * Simulates authentication as a sandbox persona, issuing an authorization code.
 */
export async function authorizeSandboxPersona(
  personaId: string,
  state: string
): Promise<{ code: string; state: string; message: string }> {
  const res = await fetch(`${API_BASE}/auth/sso/sandbox/authorize`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ persona_id: personaId, state }),
  });
  if (!res.ok) {
    const err = await res.text();
    throw new Error(`Sandbox authorization failed: ${res.status} ${err}`);
  }
  return res.json();
}

/**
 * Completes the SSO login handoff, exchanging the authorization code for application JWT tokens.
 */
export async function handleSSOCallback(
  code: string,
  state: string,
  codeVerifier?: string
): Promise<SSOAuthResponse> {
  const res = await fetch(`${API_BASE}/auth/sso/callback`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ code, state, code_verifier: codeVerifier }),
  });
  if (!res.ok) {
    const err = await res.text();
    throw new Error(`SSO callback failed: ${res.status} ${err}`);
  }
  const data: SSOAuthResponse = await res.json();
  if (typeof window !== "undefined" && data.access_token) {
    localStorage.setItem("access_token", data.access_token);
    localStorage.setItem("refresh_token", data.refresh_token);
    localStorage.setItem("user", JSON.stringify(data.user));
  }
  return data;
}
