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

export function installGlobalErrorReporter(options: GlobalErrorReporterOptions = {}): void {
  if (typeof window === 'undefined') return;

  const reporterOptions: Required<GlobalErrorReporterOptions> = {
    reload: options.reload ?? (() => window.location.reload()),
    now: options.now ?? (() => Date.now()),
  };

  window.addEventListener('error', (event) => {
    if (maybeRecoverFromStaleAsset(event, reporterOptions)) {
      return;
    }

    console.error('[Global Error]', event.error);
    // Could send to remote logging service here
  });

  window.addEventListener('unhandledrejection', (event) => {
    if (maybeRecoverFromStaleAsset(event.reason, reporterOptions)) {
      return;
    }

    console.error('[Unhandled Rejection]', event.reason);
    // Could send to remote logging service here
  });
}

export function reportError(error: Error, context?: Record<string, unknown>): void {
  console.error('[Reported Error]', error, context);
  // Could send to remote logging service here
}
