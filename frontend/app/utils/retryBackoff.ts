export interface RetryConfig {
  maxRetries?: number;
  baseDelayMs?: number;
  maxDelayMs?: number;
  retryOnStatusCodes?: number[];
  onRetry?: (attempt: number, delayMs: number, reason: string) => void;
}

export class SyncConflictError extends Error {
  code: string;
  serverStatus?: string;
  suggestedResolution?: string;
  inspectionId?: string;

  constructor(
    message: string,
    details: { code: string; serverStatus?: string; suggestedResolution?: string; inspectionId?: string }
  ) {
    super(message);
    this.name = 'SyncConflictError';
    this.code = details.code;
    this.serverStatus = details.serverStatus;
    this.suggestedResolution = details.suggestedResolution;
    this.inspectionId = details.inspectionId;
  }
}

export class SyncPermanentError extends Error {
  statusCode: number;

  constructor(message: string, statusCode: number) {
    super(message);
    this.name = 'SyncPermanentError';
    this.statusCode = statusCode;
  }
}

export class SyncTransientError extends Error {
  statusCode?: number;

  constructor(message: string, statusCode?: number) {
    super(message);
    this.name = 'SyncTransientError';
    this.statusCode = statusCode;
  }
}

export function isTransientNetworkError(err: unknown): boolean {
  if (!err) return false;
  if (typeof navigator !== 'undefined' && !navigator.onLine) return true;
  if (err instanceof TypeError && err.message.toLowerCase().includes('fetch')) return true;
  if (
    err instanceof Error &&
    (err.message.toLowerCase().includes('network') ||
      err.message.toLowerCase().includes('abort') ||
      err.message.toLowerCase().includes('timeout'))
  ) {
    return true;
  }
  return false;
}

export function calculateBackoffWithJitter(
  attempt: number,
  baseDelayMs: number = 800,
  maxDelayMs: number = 10000
): number {
  const exponential = Math.min(maxDelayMs, baseDelayMs * Math.pow(2, attempt));
  const jitterFactor = 0.5 + Math.random() * 0.5;
  return Math.floor(exponential * jitterFactor);
}

export async function fetchWithRetry(
  url: string,
  options: RequestInit = {},
  config: RetryConfig = {}
): Promise<Response> {
  const maxRetries = config.maxRetries ?? 3;
  const baseDelayMs = config.baseDelayMs ?? 800;
  const maxDelayMs = config.maxDelayMs ?? 10000;
  const retryCodes = config.retryOnStatusCodes ?? [408, 429, 500, 502, 503, 504];

  let lastError: unknown = null;

  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    try {
      if (typeof navigator !== 'undefined' && !navigator.onLine) {
        throw new SyncTransientError('Device is currently offline');
      }

      const response = await fetch(url, options);

      if (response.status === 409) {
        interface ConflictPayload {
          message?: string;
          code?: string;
          server_status?: string;
          suggested_resolution?: string;
          inspection_id?: string;
        }
        let conflictData: ConflictPayload = {};
        try {
          const json = (await response.json()) as { detail?: ConflictPayload } & ConflictPayload;
          conflictData = json.detail || json;
        } catch {
          // ignore parse error
        }
        throw new SyncConflictError(
          conflictData.message || 'Conflict occurred while synchronizing inspection',
          {
            code: conflictData.code || 'CONCURRENT_MODIFICATION',
            serverStatus: conflictData.server_status,
            suggestedResolution: conflictData.suggested_resolution || 'server_authoritative',
            inspectionId: conflictData.inspection_id,
          }
        );
      }

      if (retryCodes.includes(response.status)) {
        const retryAfterHeader = response.headers.get('Retry-After');
        const retryAfterSeconds = retryAfterHeader ? parseInt(retryAfterHeader, 10) : null;

        if (attempt < maxRetries) {
          const delay =
            retryAfterSeconds && !isNaN(retryAfterSeconds)
              ? retryAfterSeconds * 1000
              : calculateBackoffWithJitter(attempt, baseDelayMs, maxDelayMs);

          if (config.onRetry) {
            config.onRetry(attempt + 1, delay, 'HTTP ' + response.status);
          }
          await new Promise((resolve) => setTimeout(resolve, delay));
          continue;
        } else {
          const text = await response.text().catch(() => '');
          throw new SyncTransientError(
            'HTTP ' + response.status + ' after ' + maxRetries + ' retries: ' + text,
            response.status
          );
        }
      }

      if (response.status >= 400 && response.status < 500) {
        const text = await response.text().catch(() => '');
        throw new SyncPermanentError('HTTP ' + response.status + ': ' + text, response.status);
      }

      return response;
    } catch (err: unknown) {
      lastError = err;

      if (err instanceof SyncPermanentError || err instanceof SyncConflictError) {
        throw err;
      }

      if (isTransientNetworkError(err) || err instanceof SyncTransientError) {
        if (attempt < maxRetries) {
          const delay = calculateBackoffWithJitter(attempt, baseDelayMs, maxDelayMs);
          const reason = err instanceof Error ? err.message : 'Network error';
          if (config.onRetry) {
            config.onRetry(attempt + 1, delay, reason);
          }
          await new Promise((resolve) => setTimeout(resolve, delay));
          continue;
        }
      }

      throw err;
    }
  }

  throw lastError;
}
