/**
 * API Proxy Route - 完整的 Cookie 转发代理
 *
 * Next.js rewrites 不转发后端响应的 Set-Cookie 头，
 * 因此使用 API Route 做真正的服务端代理。
 */
import { NextRequest, NextResponse } from 'next/server';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';
// Next.js App Router 的最大执行时长（秒），覆盖平台默认值（Vercel Hobby 10s / Pro 60s）
export const maxDuration = 300; // 5分钟

const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8000';
const PROXY_TIMEOUT = 120_000; // 普通请求 2分钟
const SSE_CONNECT_TIMEOUT = 300_000; // SSE 流式请求连接阶段 5分钟（AI 生成可能很慢）
const LONG_REQUEST_TIMEOUT = 300_000; // MiniMax 等后端生成请求最长可到 5分钟

// 已知的 SSE 流式路径模式（后端返回 text/event-stream）
const SSE_PATH_PATTERNS = [
  '/choice',
  '/custom-choice',
  '/event',
  '/regenerate-stream',
  '/rewrite-stream',
  '/opening-story',
];

const LONG_REQUEST_PATH_PATTERNS = [
  '/api/images/generate',
];

function isSSEPath(pathname: string): boolean {
  return SSE_PATH_PATTERNS.some(p => pathname.endsWith(p));
}

function isLongRequestPath(pathname: string): boolean {
  return LONG_REQUEST_PATH_PATTERNS.some(p => pathname === p);
}

// 不应转发的请求头
const SKIP_REQUEST_HEADERS = new Set([
  'host',
  'connection',
  'content-length', // 由 fetch 自动设置
]);

// 不应转发的响应头
const SKIP_RESPONSE_HEADERS = new Set([
  'connection',
  'keep-alive',
  'transfer-encoding', // 由 Next.js 自动处理
]);

async function proxyRequest(request: NextRequest): Promise<NextResponse> {
  const { pathname, search } = request.nextUrl;
  const targetUrl = `${BACKEND_URL}${pathname}${search}`;

  // 构建转发的请求头
  const headers = new Headers();
  request.headers.forEach((value, key) => {
    const lowerKey = key.toLowerCase();
    if (!SKIP_REQUEST_HEADERS.has(lowerKey)) {
      headers.set(key, value);
    }
  });

  // ★ 确保 Cookie 被正确转发
  // Next.js 可能将 cookie 解析后从 headers 中移除，需要手动重建
  const cookieHeader = request.headers.get('cookie');
  if (!cookieHeader) {
    // 从 Next.js 的 cookies() API 重建 cookie 头
    const cookies = request.cookies.getAll();
    if (cookies.length > 0) {
      const reconstructed = cookies.map(c => `${c.name}=${c.value}`).join('; ');
      headers.set('cookie', reconstructed);
      console.log(`[API Proxy] Cookie reconstructed from NextRequest.cookies for ${pathname}: ${cookies.map(c => c.name).join(', ')}`);
    } else {
      console.warn(`[API Proxy] No cookies found for ${pathname} — auth will likely fail`);
    }
  } else {
    // Cookie 头已存在，记录诊断信息
    const hasAuthToken = cookieHeader.includes('auth_token');
    if (pathname.includes('/collection') || pathname.includes('/games') || pathname.includes('/auth')) {
      console.log(`[API Proxy] Cookie forwarded for ${pathname}: has_auth_token=${hasAuthToken}`);
    }
  }

  // 转发请求体
  let body: ArrayBuffer | undefined;
  if (request.method !== 'GET' && request.method !== 'HEAD') {
    body = await request.arrayBuffer();
    if (body.byteLength === 0) {
      body = undefined;
    }
  }

  // 使用 AbortController 实现超时
  // SSE 路径使用更长的连接超时（AI 生成故事可能需要数分钟）
  const sseRequest = isSSEPath(pathname);
  const timeout = sseRequest
    ? SSE_CONNECT_TIMEOUT
    : isLongRequestPath(pathname)
      ? LONG_REQUEST_TIMEOUT
      : PROXY_TIMEOUT;
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeout);

  try {
    const response = await fetch(targetUrl, {
      method: request.method,
      headers,
      body,
      signal: controller.signal,
      // @ts-expect-error - Next.js/Node.js 需要 duplex 支持流式请求体
      duplex: 'half',
    });

    clearTimeout(timeoutId);

    // 构建响应头，正确转发 Set-Cookie
    const responseHeaders = new Headers();
    response.headers.forEach((value, key) => {
      const lowerKey = key.toLowerCase();
      if (!SKIP_RESPONSE_HEADERS.has(lowerKey)) {
        // 对于 Set-Cookie，使用 append 而不是 set，以支持多个 cookie
        if (lowerKey === 'set-cookie') {
          responseHeaders.append(key, value);
        } else {
          responseHeaders.set(key, value);
        }
      }
    });

    // 图片缓存控制 - 确保重新生成后能看到新图片
    if (pathname.startsWith('/api/images/file/')) {
      responseHeaders.set('Cache-Control', 'no-cache, no-store, must-revalidate');
      responseHeaders.set('Pragma', 'no-cache');
      responseHeaders.set('Expires', '0');
    }

    // 检查是否为流式响应（SSE 或音频流）
    const contentType = response.headers.get('content-type') || '';
    const isStreamResponse =
      contentType.includes('text/event-stream') ||
      contentType.includes('audio/') ||
      contentType.includes('application/octet-stream');

    if (isStreamResponse) {
      // SSE / 音频流：直接透传流，不缓冲完整 body
      return new NextResponse(response.body, {
        status: response.status,
        headers: responseHeaders,
      });
    }

    // ★ 记录认证相关请求的响应状态
    if (response.status === 401) {
      console.warn(`[API Proxy] 401 Unauthorized: ${pathname} — check cookie forwarding`);
    }

    // 普通响应：读取完整 body 后返回
    const responseBody = await response.arrayBuffer();
    return new NextResponse(responseBody, {
      status: response.status,
      headers: responseHeaders,
    });
  } catch (error) {
    clearTimeout(timeoutId);

    // 超时错误
    if (error instanceof Error && error.name === 'AbortError') {
      console.error(`[API Proxy] Timeout after ${timeout}ms (sse=${sseRequest}): ${pathname}`);
      return NextResponse.json(
        { error: 'Gateway timeout', message: `Request timed out after ${timeout / 1000}s` },
        { status: 504 }
      );
    }

    // 其他错误
    console.error('[API Proxy] Error:', error);
    return NextResponse.json(
      { error: 'Bad gateway', message: error instanceof Error ? error.message : 'Unknown error' },
      { status: 502 }
    );
  }
}

export async function GET(request: NextRequest) {
  return proxyRequest(request);
}

export async function POST(request: NextRequest) {
  return proxyRequest(request);
}

export async function PUT(request: NextRequest) {
  return proxyRequest(request);
}

export async function DELETE(request: NextRequest) {
  return proxyRequest(request);
}

export async function PATCH(request: NextRequest) {
  return proxyRequest(request);
}

export async function HEAD(request: NextRequest) {
  return proxyRequest(request);
}

export async function OPTIONS(request: NextRequest) {
  return proxyRequest(request);
}
