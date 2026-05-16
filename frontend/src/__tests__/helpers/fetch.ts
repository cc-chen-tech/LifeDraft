/**
 * Fetch mock helpers — let real @/lib/api code run, intercept only at the network level.
 */
export function jsonResponse(data: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(data),
    text: () => Promise.resolve(JSON.stringify(data)),
    headers: new Headers({ "content-type": "application/json" }),
  } as Response;
}

export function errorResponse(status: number, detail = "error"): Response {
  return jsonResponse({ detail }, status);
}

/** Spy on global.fetch and return request URL + options for assertion */
export function fetchSpy(): jest.Mock {
  // cast: global.fetch may already be a jest mock from jest.setup.js
  return global.fetch as jest.Mock;
}

/** Shortcut: mock all fetch calls to return the given JSON */
export function mockFetchJson(data: unknown, status = 200): jest.Mock {
  const spy = jest.fn().mockResolvedValue(jsonResponse(data, status));
  global.fetch = spy;
  return spy;
}
