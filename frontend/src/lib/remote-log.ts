/**
 * Remote error logging utility
 */

export function installGlobalErrorReporter(): void {
  if (typeof window === 'undefined') return;

  window.addEventListener('error', (event) => {
    console.error('[Global Error]', event.error);
    // Could send to remote logging service here
  });

  window.addEventListener('unhandledrejection', (event) => {
    console.error('[Unhandled Rejection]', event.reason);
    // Could send to remote logging service here
  });
}

export function reportError(error: Error, context?: Record<string, unknown>): void {
  console.error('[Reported Error]', error, context);
  // Could send to remote logging service here
}
