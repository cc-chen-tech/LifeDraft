const LOOPBACK_HOSTS = new Set(["localhost", "127.0.0.1", "::1"]);

/**
 * Browser API calls must stay on the Next.js proxy. A loopback URL injected
 * into a public build points at each visitor's own machine, not our backend.
 */
export function resolveApiBase(configuredBase = process.env.NEXT_PUBLIC_API_URL): string {
  const base = configuredBase?.trim();
  if (!base) return "/api";

  try {
    if (LOOPBACK_HOSTS.has(new URL(base).hostname)) {
      return "/api";
    }
  } catch {
    // Relative paths do not need URL parsing and are already same-origin.
  }

  return base.replace(/\/$/, "") || "/api";
}
