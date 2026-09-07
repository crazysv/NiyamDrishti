export interface JanParichayClaims {
  parichay_id: string;
  user_id?: string | null;
  full_name: string;
  email: string;
  department: string;
  designation: string;
  state_code?: string | null;
  service_id?: string | null;
}

export interface SSOSandboxProfile {
  id: string;
  full_name: string;
  email: string;
  designation: string;
  department: string;
  state_code: string;
  mapped_app_role: 'officer' | 'supervisor' | 'admin';
  description: string;
}

export interface SSOInitResponse {
  authorization_url: string;
  state: string;
  code_verifier?: string | null;
  code_challenge?: string | null;
  is_sandbox: boolean;
}

export interface SSOStatusResponse {
  enabled: boolean;
  mode: 'live' | 'sandbox';
  provider_name: string;
  discovery_url: string;
  client_id_configured: boolean;
}

export interface SSOAuthResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  user: {
    id: string;
    email: string;
    full_name: string;
    role: string;
    region?: string | null;
    is_active: boolean;
  };
  claims?: JanParichayClaims | null;
}
