/**
 * Remote error logging utility
 */

const STALE_ASSET_RELOAD_KEY = 'story101:stale-asset-reload-at';
const STALE_ASSET_RELOAD_COOLDOWN_MS = 60_000;
let inMemoryStaleAssetReloadAt = 0;

type GlobalErrorReporterOptions = {
  reload?: () => void;
  now?: () => number;
};

function stringifyErrorLike(value: unknown): string {
  if (value instanceof Error) {
    return `${value.name} ${value.message} ${value.stack ?? ''}`;
  }

  if (typeof value === 'string') {
    return value;
  }

  if (value && typeof value === 'object') {
    const record = value as Record<string, unknown>;
    return `${String(record.name ?? '')} ${String(record.message ?? '')} ${String(record.stack ?? '')}`;
  }

  return String(value ?? '');
}

function getFailedAssetUrl(target: EventTarget | null): string | null {
  if (target instanceof HTMLScriptElement) {
    return target.src;
  }

  if (target instanceof HTMLLinkElement) {
    return target.href;
  }

  return null;
}

function isNextStaticAssetUrl(url: string | null): boolean {
  return Boolean(url && url.includes('/_next/static/'));
}

function isStaleBuildErrorText(text: string): boolean {
  return /ChunkLoadError|Loading chunk|failed to fetch dynamically imported module|Importing a module script failed/i.test(text);
}

function getLastStaleAssetReloadAt(): number {
  try {
    return Number(window.sessionStorage.getItem(STALE_ASSET_RELOAD_KEY) ?? inMemoryStaleAssetReloadAt);
  } catch {
    return inMemoryStaleAssetReloadAt;
  }
}

function setLastStaleAssetReloadAt(now: number): void {
  inMemoryStaleAssetReloadAt = now;
  try {
    window.sessionStorage.setItem(STALE_ASSET_RELOAD_KEY, String(now));
  } catch {
    // Keep the in-memory guard for browsers that block sessionStorage.
  }
}

function maybeRecoverFromStaleAsset(
  source: unknown,
  options: Required<GlobalErrorReporterOptions>
): boolean {
  const eventTarget = source instanceof Event ? source.target : null;
  const failedAssetUrl = getFailedAssetUrl(eventTarget);
  const staleAssetByUrl = isNextStaticAssetUrl(failedAssetUrl);
  const staleAssetByText = isStaleBuildErrorText(stringifyErrorLike(source));

  if (!staleAssetByUrl && !staleAssetByText) {
    return false;
  }

  const lastReloadAt = getLastStaleAssetReloadAt();
  const now = options.now();

  if (lastReloadAt > 0 && now - lastReloadAt < STALE_ASSET_RELOAD_COOLDOWN_MS) {
    console.warn('[Stale Asset Recovery] Suppressed repeated reload for stale build asset', {
      failedAssetUrl,
      lastReloadAt,
      now,
    });
    return true;
  }

  setLastStaleAssetReloadAt(now);
  try {
    console.warn('[Stale Asset Recovery] Reloading after stale build asset failure', {
      failedAssetUrl,
    });
    options.reload();
    return true;
  } catch (error) {
    console.error('[Stale Asset Recovery] Failed to recover from stale build asset', error);
    return true;
  }
}

let _installedErrorHandler: ((event: ErrorEvent) => void) | null = null;
let _installedRejectionHandler: ((event: PromiseRejectionEvent) => void) | null = null;

export function installGlobalErrorReporter(options: GlobalErrorReporterOptions = {}): void {
  if (typeof window === 'undefined') return;

  const reporterOptions: Required<GlobalErrorReporterOptions> = {
    reload: options.reload ?? (() => window.location.reload()),
    now: options.now ?? (() => Date.now()),
  };

  // P-修复：重复安装（StrictMode 双挂载等）先移除旧监听器，避免叠加重复上报。
  if (_installedErrorHandler) {
    window.removeEventListener('error', _installedErrorHandler);
  }
  if (_installedRejectionHandler) {
    window.removeEventListener('unhandledrejection', _installedRejectionHandler);
  }

  const errorHandler = (event: ErrorEvent) => {
    if (maybeRecoverFromStaleAsset(event, reporterOptions)) {
      return;
    }

    console.error('[Global Error]', event.error);
    reportDiagnostic('global_error', { phase: 'global' });
  };

  const rejectionHandler = (event: PromiseRejectionEvent) => {
    if (maybeRecoverFromStaleAsset(event.reason, reporterOptions)) {
      return;
    }

    console.error('[Unhandled Rejection]', event.reason);
    reportDiagnostic('unhandled_rejection', { phase: 'global' });
  };

  window.addEventListener('error', errorHandler);
  window.addEventListener('unhandledrejection', rejectionHandler);
  _installedErrorHandler = errorHandler;
  _installedRejectionHandler = rejectionHandler;
}

export function reportError(error: Error, context?: Record<string, unknown>): void {
  console.error('[Reported Error]', error, context);
  reportDiagnostic('reported_error', { phase: typeof context?.context === 'string' ? context.context : 'client' });
}


type DiagnosticContext = {
  outcome?: 'failed' | 'recovered' | 'retry' | 'cancelled';
  phase?: string; gameId?: number; jobId?: number; assetId?: number;
  operationId?: string; requestId?: string; httpStatus?: number; attempt?: number;
};
const recentDiagnostics = new Map<string, number>();
const safeDiagnosticToken = /^[A-Za-z0-9_.:-]{1,128}$/;

/** Send metadata only. Failure of logging never interrupts gameplay or recurses. */
export function reportDiagnostic(errorCode: string, context: DiagnosticContext = {}): void {
  if (typeof window === 'undefined' || typeof fetch !== 'function') return;
  const payload: Record<string, string | number> = {
    error_code: safeDiagnosticToken.test(errorCode) ? errorCode.slice(0, 96) : 'client_error',
  };
  for (const [key, value] of Object.entries(context)) {
    const names: Record<string, string> = { outcome: 'outcome', phase: 'phase', gameId: 'game_id', jobId: 'job_id',
      assetId: 'asset_id', operationId: 'operation_id', requestId: 'request_id',
      httpStatus: 'http_status', attempt: 'attempt' };
    if (!names[key]) continue;
    if (typeof value === 'number' && Number.isSafeInteger(value)) {
      const valid = key === 'httpStatus' ? value >= 100 && value <= 599
        : key === 'attempt' ? value >= 0 && value <= 10000 : value >= 1;
      if (valid) payload[names[key]] = value;
    }
    if (typeof value === 'string' && safeDiagnosticToken.test(value)) {
      if (key === 'phase' && value.length > 64) continue;
      if (key === 'outcome' && !['failed', 'recovered', 'retry', 'cancelled'].includes(value)) continue;
      payload[names[key]] = value;
    }
  }
  const now = Date.now();
  for (const [key, at] of recentDiagnostics) if (now - at >= 60_000) recentDiagnostics.delete(key);
  const key = JSON.stringify(payload);
  if (recentDiagnostics.has(key) || recentDiagnostics.size >= 30) return;
  recentDiagnostics.set(key, now);
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  if (payload.operation_id) headers['X-Operation-ID'] = String(payload.operation_id);
  if (payload.request_id) headers['X-Request-ID'] = String(payload.request_id);
  try {
    void Promise.resolve(fetch('/api/client-log', { method: 'POST', credentials: 'include', keepalive: true,
      headers, body: JSON.stringify(payload) })).catch(() => undefined);
  } catch { /* Offline/teardown must not create a second error. */ }
}
