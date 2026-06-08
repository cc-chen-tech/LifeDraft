/**
 * Unit tests for API Proxy Route (frontend/src/app/api/[...path]/route.ts)
 *
 * Covers: basic request forwarding, Cookie/Header forwarding,
 * Set-Cookie passthrough, SSE/audio streaming, JSON responses, error handling.
 */

// jsdom 环境缺少这些 API，手动注入
const { TextEncoder, TextDecoder } = require('util');
const { ReadableStream } = require('stream/web');
global.TextEncoder = TextEncoder;
global.TextDecoder = TextDecoder;
global.ReadableStream = ReadableStream as any;

// Mock next/server before importing the route module
jest.mock('next/server', () => {
  class MockNextResponse {
    body: unknown;
    status: number;
    headers: Headers;

    constructor(body: unknown, init?: { status?: number; headers?: Headers }) {
      this.body = body;
      this.status = init?.status ?? 200;
      this.headers = init?.headers ? new Headers(init.headers) : new Headers();
    }

    static json(data: unknown, init?: { status?: number }) {
      const body = JSON.stringify(data);
      const headers = new Headers({ 'content-type': 'application/json' });
      return new MockNextResponse(body, { status: init?.status ?? 200, headers });
    }
  }

  return {
    NextRequest: jest.fn(), // not directly constructed in tests; we build mock objects
    NextResponse: MockNextResponse,
  };
});

// ── helpers ──────────────────────────────────────────────────────

/** Build a minimal object that satisfies what proxyRequest reads from NextRequest */
function makeRequest(
  method: string,
  path: string,
  opts: { headers?: Record<string, string>; body?: string; cookies?: Array<{ name: string; value: string }> } = {},
) {
  const url = new URL(`http://localhost:3000${path}`);
  const headers = new Headers(opts.headers ?? {});

  return {
    method,
    nextUrl: { pathname: url.pathname, search: url.search },
    headers,
    cookies: {
      getAll: () => opts.cookies ?? [],
    },
    arrayBuffer: jest.fn().mockResolvedValue(
      opts.body ? new TextEncoder().encode(opts.body).buffer : new ArrayBuffer(0),
    ),
  } as any;
}

/** Build a mock global.fetch Response */
function mockFetchResponse(opts: {
  status?: number;
  headers?: Record<string, string>;
  body?: string | ReadableStream | ArrayBuffer;
  bodyArrayBuffer?: ArrayBuffer;
}) {
  const status = opts.status ?? 200;
  const headers = new Headers(opts.headers ?? {});

  const arrayBuf =
    opts.bodyArrayBuffer ??
    (typeof opts.body === 'string'
      ? new TextEncoder().encode(opts.body).buffer
      : new ArrayBuffer(0));

  return {
    status,
    headers,
    body: opts.body instanceof ReadableStream ? opts.body : null,
    arrayBuffer: jest.fn().mockResolvedValue(arrayBuf),
  } as unknown as Response;
}

// ── import route handlers (after mock) ──────────────────────────
import { GET, POST, PUT, DELETE, PATCH, HEAD, OPTIONS } from '@/app/api/[...path]/route';

// ── setup / teardown ────────────────────────────────────────────
const originalFetch = global.fetch;

beforeEach(() => {
  jest.useFakeTimers();
  global.fetch = jest.fn();
});

afterEach(() => {
  jest.useRealTimers();
  global.fetch = originalFetch;
  jest.restoreAllMocks();
});

// ═══════════════════════════════════════════════════════════════
// 1. 基础请求转发
// ═══════════════════════════════════════════════════════════════
describe('基础请求转发', () => {
  it('GET 请求正确转发到后端 http://localhost:8000', async () => {
    (global.fetch as jest.Mock).mockResolvedValue(
      mockFetchResponse({ body: '{"ok":true}', headers: { 'content-type': 'application/json' } }),
    );

    const req = makeRequest('GET', '/api/games/1');
    await GET(req);

    expect(global.fetch).toHaveBeenCalledTimes(1);
    const [url] = (global.fetch as jest.Mock).mock.calls[0];
    expect(url).toBe('http://localhost:8000/api/games/1');
  });

  it('POST 请求转发 body', async () => {
    (global.fetch as jest.Mock).mockResolvedValue(
      mockFetchResponse({ body: '{}', headers: { 'content-type': 'application/json' } }),
    );

    const payload = JSON.stringify({ name: 'test' });
    const req = makeRequest('POST', '/api/games', {
      headers: { 'content-type': 'application/json' },
      body: payload,
    });
    await POST(req);

    const [, fetchOpts] = (global.fetch as jest.Mock).mock.calls[0];
    expect(fetchOpts.method).toBe('POST');
    // body should be the ArrayBuffer of the payload
    expect(fetchOpts.body).toBeDefined();
  });

  it('路径映射正确（含 query string）', async () => {
    (global.fetch as jest.Mock).mockResolvedValue(
      mockFetchResponse({ body: '[]', headers: { 'content-type': 'application/json' } }),
    );

    const req = makeRequest('GET', '/api/games?page=2&limit=10');
    await GET(req);

    const [url] = (global.fetch as jest.Mock).mock.calls[0];
    expect(url).toBe('http://localhost:8000/api/games?page=2&limit=10');
  });

  it('所有 HTTP 方法均可导出并调用 proxyRequest', async () => {
    (global.fetch as jest.Mock).mockResolvedValue(
      mockFetchResponse({ body: '{}', headers: { 'content-type': 'application/json' } }),
    );

    for (const [handler, method] of [
      [GET, 'GET'],
      [POST, 'POST'],
      [PUT, 'PUT'],
      [DELETE, 'DELETE'],
      [PATCH, 'PATCH'],
      [HEAD, 'HEAD'],
      [OPTIONS, 'OPTIONS'],
    ] as const) {
      (global.fetch as jest.Mock).mockClear();
      const req = makeRequest(method, '/api/test');
      await (handler as any)(req);
      expect(global.fetch).toHaveBeenCalledTimes(1);
    }
  });
});

// ═══════════════════════════════════════════════════════════════
// 2. Cookie / Header 转发
// ═══════════════════════════════════════════════════════════════
describe('Cookie / Header 转发', () => {
  it('请求中的 Cookie header 被转发到后端', async () => {
    (global.fetch as jest.Mock).mockResolvedValue(
      mockFetchResponse({ body: '{}', headers: { 'content-type': 'application/json' } }),
    );

    const req = makeRequest('GET', '/api/auth/me', {
      headers: { cookie: 'session=abc123' },
    });
    await GET(req);

    const [, fetchOpts] = (global.fetch as jest.Mock).mock.calls[0];
    expect((fetchOpts.headers as Headers).get('cookie')).toBe('session=abc123');
  });

  it('Authorization header 被转发', async () => {
    (global.fetch as jest.Mock).mockResolvedValue(
      mockFetchResponse({ body: '{}', headers: { 'content-type': 'application/json' } }),
    );

    const req = makeRequest('GET', '/api/data', {
      headers: { authorization: 'Bearer token123' },
    });
    await GET(req);

    const [, fetchOpts] = (global.fetch as jest.Mock).mock.calls[0];
    expect((fetchOpts.headers as Headers).get('authorization')).toBe('Bearer token123');
  });

  it('Content-Type header 被转发', async () => {
    (global.fetch as jest.Mock).mockResolvedValue(
      mockFetchResponse({ body: '{}', headers: { 'content-type': 'application/json' } }),
    );

    const req = makeRequest('POST', '/api/data', {
      headers: { 'content-type': 'application/json' },
      body: '{}',
    });
    await POST(req);

    const [, fetchOpts] = (global.fetch as jest.Mock).mock.calls[0];
    expect((fetchOpts.headers as Headers).get('content-type')).toBe('application/json');
  });

  it('host / connection / content-length 被跳过不转发', async () => {
    (global.fetch as jest.Mock).mockResolvedValue(
      mockFetchResponse({ body: '{}', headers: { 'content-type': 'application/json' } }),
    );

    const req = makeRequest('GET', '/api/test', {
      headers: { host: 'evil.com', connection: 'keep-alive', 'content-length': '42' },
    });
    await GET(req);

    const [, fetchOpts] = (global.fetch as jest.Mock).mock.calls[0];
    const h = fetchOpts.headers as Headers;
    expect(h.has('host')).toBe(false);
    expect(h.has('connection')).toBe(false);
    expect(h.has('content-length')).toBe(false);
  });
});

// ═══════════════════════════════════════════════════════════════
// 3. Set-Cookie 响应转发
// ═══════════════════════════════════════════════════════════════
describe('Set-Cookie 响应转发', () => {
  it('后端返回的 Set-Cookie header 被透传到客户端响应', async () => {
    const backendHeaders = new Headers();
    backendHeaders.append('set-cookie', 'session=xyz; Path=/; HttpOnly');
    backendHeaders.append('content-type', 'application/json');

    (global.fetch as jest.Mock).mockResolvedValue({
      status: 200,
      headers: backendHeaders,
      body: null,
      arrayBuffer: jest.fn().mockResolvedValue(new TextEncoder().encode('{}').buffer),
    });

    const req = makeRequest('GET', '/api/auth/login');
    const res = await GET(req);

    expect(res.headers.get('set-cookie')).toContain('session=xyz');
  });
});

// ═══════════════════════════════════════════════════════════════
// 4. 流式响应处理
// ═══════════════════════════════════════════════════════════════
describe('流式响应处理', () => {
  it('content-type 为 text/event-stream 时返回流式响应（body 为 ReadableStream）', async () => {
    const stream = new ReadableStream({
      start(controller: ReadableStreamDefaultController) {
        controller.enqueue(new TextEncoder().encode('data: hello\n\n'));
        controller.close();
      },
    });

    (global.fetch as jest.Mock).mockResolvedValue({
      status: 200,
      headers: new Headers({ 'content-type': 'text/event-stream' }),
      body: stream,
      arrayBuffer: jest.fn(), // should NOT be called for streams
    });

    const req = makeRequest('GET', '/api/games/1/events');
    const res = await GET(req);

    // Stream body should be passed through directly
    expect(res.body).toBe(stream);
    // arrayBuffer should NOT have been called (no buffering)
    const resolved = await (global.fetch as jest.Mock).mock.results[0].value;
    expect(resolved.arrayBuffer).not.toHaveBeenCalled();
  });

  it('content-type 为 audio/* 时返回流式响应', async () => {
    const stream = new ReadableStream({
      start(controller: ReadableStreamDefaultController) {
        controller.enqueue(new Uint8Array([0xff, 0xfb]));
        controller.close();
      },
    });

    (global.fetch as jest.Mock).mockResolvedValue({
      status: 200,
      headers: new Headers({ 'content-type': 'audio/mpeg' }),
      body: stream,
      arrayBuffer: jest.fn(),
    });

    const req = makeRequest('GET', '/api/music/stream');
    const res = await GET(req);

    expect(res.body).toBe(stream);
    const resolved2 = await (global.fetch as jest.Mock).mock.results[0].value;
    expect(resolved2.arrayBuffer).not.toHaveBeenCalled();
  });

  it('application/octet-stream 也走流式', async () => {
    const stream = new ReadableStream();

    (global.fetch as jest.Mock).mockResolvedValue({
      status: 200,
      headers: new Headers({ 'content-type': 'application/octet-stream' }),
      body: stream,
      arrayBuffer: jest.fn(),
    });

    const req = makeRequest('GET', '/api/download');
    const res = await GET(req);

    expect(res.body).toBe(stream);
  });
});

// ═══════════════════════════════════════════════════════════════
// 5. 普通 JSON 响应
// ═══════════════════════════════════════════════════════════════
describe('普通 JSON 响应', () => {
  it('JSON 响应正确返回 body 和 status code', async () => {
    const data = { id: 1, name: 'Game 1' };
    const encoded = new TextEncoder().encode(JSON.stringify(data));

    (global.fetch as jest.Mock).mockResolvedValue(
      mockFetchResponse({
        status: 200,
        body: JSON.stringify(data),
        bodyArrayBuffer: encoded.buffer,
        headers: { 'content-type': 'application/json' },
      }),
    );

    const req = makeRequest('GET', '/api/games/1');
    const res = await GET(req);

    expect(res.status).toBe(200);
    // body should be an ArrayBuffer (cross-realm, so check constructor name)
    expect(res.body).toBeTruthy();
    expect(res.body?.constructor.name).toBe('ArrayBuffer');
  });

  it('非 200 状态码正确透传', async () => {
    (global.fetch as jest.Mock).mockResolvedValue(
      mockFetchResponse({
        status: 404,
        body: '{"detail":"Not found"}',
        headers: { 'content-type': 'application/json' },
      }),
    );

    const req = makeRequest('GET', '/api/games/999');
    const res = await GET(req);

    expect(res.status).toBe(404);
  });

  it('500 状态码正确透传', async () => {
    (global.fetch as jest.Mock).mockResolvedValue(
      mockFetchResponse({
        status: 500,
        body: '{"detail":"Internal error"}',
        headers: { 'content-type': 'application/json' },
      }),
    );

    const req = makeRequest('GET', '/api/error');
    const res = await GET(req);

    expect(res.status).toBe(500);
  });
});

// ═══════════════════════════════════════════════════════════════
// 6. 错误处理
// ═══════════════════════════════════════════════════════════════
describe('错误处理', () => {
  it('fetch 网络错误返回 502', async () => {
    (global.fetch as jest.Mock).mockRejectedValue(new Error('ECONNREFUSED'));

    const req = makeRequest('GET', '/api/test');
    const res = await GET(req);

    expect(res.status).toBe(502);
  });

  it('超时返回 504', async () => {
    // fetch never resolves; simulate AbortError
    (global.fetch as jest.Mock).mockImplementation(() => {
      return new Promise((_, reject) => {
        // Listen to the abort signal passed by proxyRequest
        const signal = (global.fetch as jest.Mock).mock.calls.at(-1)?.[1]?.signal as AbortSignal;
        if (signal) {
          signal.addEventListener('abort', () => {
            const err = new DOMException('The operation was aborted.', 'AbortError');
            reject(err);
          });
        }
      });
    });

    const req = makeRequest('GET', '/api/slow');
    const resPromise = GET(req);

    // Advance timers past the 120s timeout
    jest.advanceTimersByTime(120_001);

    const res = await resPromise;
    expect(res.status).toBe(504);
  });

  it('/api/music/generate 使用长请求超时，避免 MiniMax 生成被 120 秒代理截断', async () => {
    (global.fetch as jest.Mock).mockImplementation((_url, opts?: { signal?: AbortSignal }) => {
      return new Promise((_, reject) => {
        opts?.signal?.addEventListener('abort', () => {
          reject(new DOMException('The operation was aborted.', 'AbortError'));
        });
      });
    });

    const req = makeRequest('POST', '/api/music/generate', {
      body: JSON.stringify({ story_text: 'long story', game_id: 1, analysis: {} }),
    });
    const resPromise = POST(req);

    await Promise.resolve();
    jest.advanceTimersByTime(300_001);
    const res = await resPromise;
    expect(res.status).toBe(504);
    expect(String((res as { body: unknown }).body)).toContain('300s');
  });
});

// ═══════════════════════════════════════════════════════════════
// 7. 图片缓存控制
// ═══════════════════════════════════════════════════════════════
describe('图片缓存控制', () => {
  it('/api/images/file/ 路径设置 no-cache 头', async () => {
    (global.fetch as jest.Mock).mockResolvedValue(
      mockFetchResponse({
        status: 200,
        body: 'binary',
        headers: { 'content-type': 'image/png' },
      }),
    );

    const req = makeRequest('GET', '/api/images/file/abc.png');
    const res = await GET(req);

    expect(res.headers.get('Cache-Control')).toBe('no-cache, no-store, must-revalidate');
    expect(res.headers.get('Pragma')).toBe('no-cache');
  });
});

// ═══════════════════════════════════════════════════════════════
// 8. 响应头过滤
// ═══════════════════════════════════════════════════════════════
describe('响应头过滤', () => {
  it('connection / keep-alive / transfer-encoding 不出现在响应中', async () => {
    const backendHeaders = new Headers();
    backendHeaders.set('content-type', 'application/json');
    backendHeaders.set('connection', 'keep-alive');
    backendHeaders.set('keep-alive', 'timeout=5');
    backendHeaders.set('transfer-encoding', 'chunked');

    (global.fetch as jest.Mock).mockResolvedValue({
      status: 200,
      headers: backendHeaders,
      body: null,
      arrayBuffer: jest.fn().mockResolvedValue(new ArrayBuffer(0)),
    });

    const req = makeRequest('GET', '/api/test');
    const res = await GET(req);

    expect(res.headers.has('connection')).toBe(false);
    expect(res.headers.has('keep-alive')).toBe(false);
    expect(res.headers.has('transfer-encoding')).toBe(false);
    expect(res.headers.get('content-type')).toBe('application/json');
  });
});

// ═══════════════════════════════════════════════════════════════
// 9. Cookie 重建机制
// ═══════════════════════════════════════════════════════════════
describe('Cookie 重建机制', () => {
  it('当 headers.cookie 为空时，从 request.cookies 重建', async () => {
    (global.fetch as jest.Mock).mockResolvedValue(
      mockFetchResponse({ body: '{}', headers: { 'content-type': 'application/json' } }),
    );

    // headers 中不放 cookie，但 cookies.getAll() 返回 cookie 列表
    const req = makeRequest('GET', '/api/auth/me', {
      cookies: [{ name: 'auth_token', value: 'abc123' }],
    });
    await GET(req);

    const [, fetchOpts] = (global.fetch as jest.Mock).mock.calls[0];
    expect((fetchOpts.headers as Headers).get('cookie')).toBe('auth_token=abc123');
  });

  it('当 headers.cookie 已有值时，不需要重建', async () => {
    (global.fetch as jest.Mock).mockResolvedValue(
      mockFetchResponse({ body: '{}', headers: { 'content-type': 'application/json' } }),
    );

    // headers 中已有 cookie，cookies.getAll() 也返回值
    const req = makeRequest('GET', '/api/auth/me', {
      headers: { cookie: 'session=original' },
      cookies: [{ name: 'auth_token', value: 'should_not_appear' }],
    });
    await GET(req);

    const [, fetchOpts] = (global.fetch as jest.Mock).mock.calls[0];
    // 应该使用 headers 中的原始 cookie，不覆盖
    expect((fetchOpts.headers as Headers).get('cookie')).toBe('session=original');
  });

  it('多个 cookies 正确重建为分号分隔的字符串', async () => {
    (global.fetch as jest.Mock).mockResolvedValue(
      mockFetchResponse({ body: '{}', headers: { 'content-type': 'application/json' } }),
    );

    const req = makeRequest('GET', '/api/games/1', {
      cookies: [
        { name: 'auth_token', value: 'token123' },
        { name: 'session', value: 'sess456' },
      ],
    });
    await GET(req);

    const [, fetchOpts] = (global.fetch as jest.Mock).mock.calls[0];
    expect((fetchOpts.headers as Headers).get('cookie')).toBe('auth_token=token123; session=sess456');
  });

  it('cookies 为空数组时不设置 cookie 头', async () => {
    (global.fetch as jest.Mock).mockResolvedValue(
      mockFetchResponse({ body: '{}', headers: { 'content-type': 'application/json' } }),
    );

    const req = makeRequest('GET', '/api/test', { cookies: [] });
    await GET(req);

    const [, fetchOpts] = (global.fetch as jest.Mock).mock.calls[0];
    expect((fetchOpts.headers as Headers).get('cookie')).toBeNull();
  });
});
