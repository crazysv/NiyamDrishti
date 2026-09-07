import { RulePackSummary, RulePackDetail } from "../types/rulePack";
import { API_BASE } from "../utils/apiConfig";

export async function fetchRulePacks(token?: string): Promise<RulePackSummary[]> {
  const headers: Record<string, string> = {};
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`${API_BASE}/rule-packs`, { headers });
  if (!res.ok) {
    const errorText = await res.text();
    throw new Error(`Failed to fetch rule packs: ${res.status} ${errorText}`);
  }
  return res.json();
}

export async function fetchActiveRulePack(token?: string): Promise<RulePackDetail> {
  const headers: Record<string, string> = {};
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`${API_BASE}/rule-packs/active`, { headers });
  if (!res.ok) {
    const errorText = await res.text();
    throw new Error(`Failed to fetch active rule pack: ${res.status} ${errorText}`);
  }
  return res.json();
}

export async function fetchRulePackByVersion(version: string, token?: string): Promise<RulePackDetail> {
  const headers: Record<string, string> = {};
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`${API_BASE}/rule-packs/${encodeURIComponent(version)}`, { headers });
  if (!res.ok) {
    const errorText = await res.text();
    throw new Error(`Failed to fetch rule pack ${version}: ${res.status} ${errorText}`);
  }
  return res.json();
}

export async function uploadRulePack(
  payload: {
    version: string;
    effective_from: string;
    effective_to?: string | null;
    source_citation: string;
    rules_json: Record<string, unknown>;
  },
  token?: string
): Promise<RulePackDetail> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`${API_BASE}/rule-packs`, {
    method: "POST",
    headers,
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    const errorText = await res.text();
    throw new Error(`Failed to upload rule pack: ${res.status} ${errorText}`);
  }
  return res.json();
}

export async function activateRulePack(version: string, token?: string): Promise<RulePackDetail> {
  const headers: Record<string, string> = {};
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`${API_BASE}/rule-packs/${encodeURIComponent(version)}/activate`, {
    method: "POST",
    headers,
  });

  if (!res.ok) {
    const errorText = await res.text();
    throw new Error(`Failed to activate rule pack ${version}: ${res.status} ${errorText}`);
  }
  return res.json();
}
