/* eslint-disable @typescript-eslint/no-unused-vars */

/**
 * API Contract Tests - API契约测试
 *
 * 验证前端调用的API端点与后端实际路由匹配
 * 能够捕获如 /games/1/round-scenes -> /images/scene/1/1 这类路径不匹配问题
 */

import { test, expect, APIRequestContext } from '@playwright/test';

const API_URL = 'http://localhost:8000';

/**
 * 测试API端点是否存在且可访问
 */
async function testEndpoint(
  request: APIRequestContext,
  method: 'GET' | 'POST' | 'PUT' | 'DELETE',
  path: string,
  expectedStatuses: number[] = [200, 401, 404, 422, 429],
  body?: Record<string, unknown>
) {
  const url = `${API_URL}${path}`;
  let response;

  try {
    if (method === 'GET') {
      response = await request.get(url);
    } else if (method === 'POST') {
      response = await request.post(url, { data: body || {} });
    } else if (method === 'PUT') {
      response = await request.put(url, { data: body || {} });
    } else if (method === 'DELETE') {
      response = await request.delete(url);
    }

    const status = response!.status();
    const responseBody = await response!.text().catch(() => '');

    // 检查是否是路由不存在的404（而不是资源不存在的404）
    if (status === 404) {
      // FastAPI 路由不存在的错误通常包含 "detail":"Not Found"
      // 而资源不存在的错误包含类似 "Game not found" 的消息
      const isRouteNotFound = responseBody.includes('Not Found') && !responseBody.includes('game_id') && !responseBody.includes('Game not found');

      if (isRouteNotFound) {
        return {
          exists: false,
          status,
          error: `Endpoint not found: ${method} ${path}`,
        };
      }

      // 资源不存在的404，端点是存在的
      return {
        exists: true,
        status,
        isExpected: expectedStatuses.includes(status),
        error: null,
      };
    }

    // 检查状态码是否在预期范围内
    const isExpected = expectedStatuses.includes(status);

    return {
      exists: true,
      status,
      isExpected,
      error: isExpected ? null : `Unexpected status ${status} for ${method} ${path}`,
    };
  } catch (e) {
    return {
      exists: false,
      status: 0,
      error: `Request failed: ${method} ${path} - ${e}`,
    };
  }
}

test.describe('API Contract - Authentication Endpoints', () => {
  test('POST /api/auth/register should exist', async ({ request }) => {
    const result = await testEndpoint(request, 'POST', '/api/auth/register');
    expect(result.exists).toBe(true);
    expect(result.error).toBeNull();
  });

  test('POST /api/auth/login should exist', async ({ request }) => {
    const result = await testEndpoint(request, 'POST', '/api/auth/login');
    expect(result.exists).toBe(true);
    expect(result.error).toBeNull();
  });

  test('POST /api/auth/logout should exist', async ({ request }) => {
    const result = await testEndpoint(request, 'POST', '/api/auth/logout');
    expect(result.exists).toBe(true);
    expect(result.error).toBeNull();
  });

  test('GET /api/auth/me should exist', async ({ request }) => {
    const result = await testEndpoint(request, 'GET', '/api/auth/me');
    expect(result.exists).toBe(true);
    expect(result.error).toBeNull();
  });
});

test.describe('API Contract - Game Endpoints', () => {
  test('GET /api/games should exist', async ({ request }) => {
    const result = await testEndpoint(request, 'GET', '/api/games');
    expect(result.exists).toBe(true);
    expect(result.error).toBeNull();
  });

  test('POST /api/games should exist', async ({ request }) => {
    const result = await testEndpoint(request, 'POST', '/api/games');
    expect(result.exists).toBe(true);
    expect(result.error).toBeNull();
  });

  test('GET /api/games/:id should exist', async ({ request }) => {
    const result = await testEndpoint(request, 'GET', '/api/games/1');
    expect(result.exists).toBe(true);
    expect(result.error).toBeNull();
  });

  test('POST /api/games/:id/save should exist', async ({ request }) => {
    const result = await testEndpoint(request, 'POST', '/api/games/1/save');
    expect(result.exists).toBe(true);
    expect(result.error).toBeNull();
  });

  test('POST /api/games/:id/choice should exist', async ({ request }) => {
    const result = await testEndpoint(request, 'POST', '/api/games/1/choice');
    expect(result.exists).toBe(true);
    expect(result.error).toBeNull();
  });

  test('POST /api/games/:id/custom-choice should exist', async ({ request }) => {
    const result = await testEndpoint(request, 'POST', '/api/games/1/custom-choice');
    expect(result.exists).toBe(true);
    expect(result.error).toBeNull();
  });

  test('GET /api/games/:id/event should exist', async ({ request }) => {
    const result = await testEndpoint(request, 'GET', '/api/games/1/event');
    expect(result.exists).toBe(true);
    expect(result.error).toBeNull();
  });

  test('GET /api/games/:id/regenerate-stream should exist', async ({ request }) => {
    const result = await testEndpoint(request, 'GET', '/api/games/1/regenerate-stream');
    expect(result.exists).toBe(true);
    expect(result.error).toBeNull();
  });

  test('POST /api/games/:id/rewrite-stream should exist', async ({ request }) => {
    const result = await testEndpoint(request, 'POST', '/api/games/1/rewrite-stream');
    expect(result.exists).toBe(true);
    expect(result.error).toBeNull();
  });
});

test.describe('API Contract - Image Endpoints', () => {
  test('GET /api/images/game/:gameId should exist', async ({ request }) => {
    const result = await testEndpoint(request, 'GET', '/api/images/game/1');
    expect(result.exists).toBe(true);
    expect(result.error).toBeNull();
  });

  test('POST /api/images/generate should exist', async ({ request }) => {
    const result = await testEndpoint(request, 'POST', '/api/images/generate');
    expect(result.exists).toBe(true);
    expect(result.error).toBeNull();
  });

  test('POST /api/images/regenerate should exist', async ({ request }) => {
    const result = await testEndpoint(request, 'POST', '/api/images/regenerate');
    expect(result.exists).toBe(true);
    expect(result.error).toBeNull();
  });

  test('POST /api/images/regenerate-fresh should exist', async ({ request }) => {
    const result = await testEndpoint(request, 'POST', '/api/images/regenerate-fresh');
    expect(result.exists).toBe(true);
    expect(result.error).toBeNull();
  });

  test('GET /api/images/scene/:game_id/:round_number should exist', async ({ request }) => {
    const result = await testEndpoint(request, 'GET', '/api/images/scene/1/1');
    expect(result.exists).toBe(true);
    expect(result.error).toBeNull();
  });

  test('GET /api/images/scenes/:game_id should exist', async ({ request }) => {
    const result = await testEndpoint(request, 'GET', '/api/images/scenes/1');
    expect(result.exists).toBe(true);
    expect(result.error).toBeNull();
  });

  test('POST /api/images/scene/generate should exist', async ({ request }) => {
    const result = await testEndpoint(request, 'POST', '/api/images/scene/generate');
    expect(result.exists).toBe(true);
    expect(result.error).toBeNull();
  });

  test('POST /api/images/scene/regenerate should exist', async ({ request }) => {
    const result = await testEndpoint(request, 'POST', '/api/images/scene/regenerate');
    expect(result.exists).toBe(true);
    expect(result.error).toBeNull();
  });
});

test.describe('API Contract - Collection Endpoints', () => {
  test('GET /api/collection/:gameId should exist', async ({ request }) => {
    const result = await testEndpoint(request, 'GET', '/api/collection/1');
    expect(result.exists).toBe(true);
    expect(result.error).toBeNull();
  });

  test('POST /api/collection/:gameId/characters/:name/generate-image should exist', async ({ request }) => {
    const result = await testEndpoint(request, 'POST', '/api/collection/1/characters/Test/generate-image');
    expect(result.exists).toBe(true);
    expect(result.error).toBeNull();
  });

  test('POST /api/collection/:gameId/items/:name/generate-image should exist', async ({ request }) => {
    const result = await testEndpoint(request, 'POST', '/api/collection/1/items/Test/generate-image');
    expect(result.exists).toBe(true);
    expect(result.error).toBeNull();
  });

  test('POST /api/collection/:gameId/items/:name/generate-description should exist', async ({ request }) => {
    const result = await testEndpoint(request, 'POST', '/api/collection/1/items/Test/generate-description');
    expect(result.exists).toBe(true);
    expect(result.error).toBeNull();
  });
});

test.describe('API Contract - Character Endpoints', () => {
  test('POST /api/character/opening-story should exist', async ({ request }) => {
    const result = await testEndpoint(request, 'POST', '/api/character/opening-story');
    expect(result.exists).toBe(true);
    expect(result.error).toBeNull();
  });

  test('POST /api/character/setting should exist', async ({ request }) => {
    const result = await testEndpoint(request, 'POST', '/api/character/setting');
    expect(result.exists).toBe(true);
    expect(result.error).toBeNull();
  });

  test('POST /api/character/relationship should exist', async ({ request }) => {
    const result = await testEndpoint(request, 'POST', '/api/character/relationship');
    expect(result.exists).toBe(true);
    expect(result.error).toBeNull();
  });

  test('POST /api/character/attributes should exist', async ({ request }) => {
    const result = await testEndpoint(request, 'POST', '/api/character/attributes');
    expect(result.exists).toBe(true);
    expect(result.error).toBeNull();
  });
});

test.describe('API Contract - Deprecated Endpoint Detection', () => {
  /**
   * 这些测试用于检测前端是否还在调用已废弃的端点
   * 如果返回200而不是404，说明后端仍支持这些旧端点（可能需要清理）
   */
  test('should detect old round-scenes endpoint (should be 404)', async ({ request }) => {
    const result = await testEndpoint(request, 'GET', '/api/games/1/round-scenes/1');
    // 这个端点应该返回404，因为已迁移到 /api/images/scene/:game_id/:round_number
    if (result.exists && result.status === 200) {
      console.warn('Warning: Old endpoint /api/games/1/round-scenes/1 still exists. Consider removing it.');
    }
  });

  test('should detect old regenerate/stream endpoint (should be 404)', async ({ request }) => {
    const result = await testEndpoint(request, 'POST', '/api/games/1/regenerate/stream');
    if (result.exists && result.status === 200) {
      console.warn('Warning: Old endpoint /api/games/1/regenerate/stream still exists.');
    }
  });

  test('should detect old rewrite/stream endpoint (should be 404)', async ({ request }) => {
    const result = await testEndpoint(request, 'POST', '/api/games/1/rewrite/stream');
    if (result.exists && result.status === 200) {
      console.warn('Warning: Old endpoint /api/games/1/rewrite/stream still exists.');
    }
  });

  test('should detect old choices/stream endpoint (should be 404)', async ({ request }) => {
    const result = await testEndpoint(request, 'POST', '/api/games/1/choices/stream');
    if (result.exists && result.status === 200) {
      console.warn('Warning: Old endpoint /api/games/1/choices/stream still exists.');
    }
  });

  test('should detect old choices/custom/stream endpoint (should be 404)', async ({ request }) => {
    const result = await testEndpoint(request, 'POST', '/api/games/1/choices/custom/stream');
    if (result.exists && result.status === 200) {
      console.warn('Warning: Old endpoint /api/games/1/choices/custom/stream still exists.');
    }
  });

  test('should detect old images/:id/regenerate endpoint (should be 404)', async ({ request }) => {
    const result = await testEndpoint(request, 'POST', '/api/images/1/regenerate');
    if (result.exists && result.status === 200) {
      console.warn('Warning: Old endpoint /api/images/1/regenerate still exists.');
    }
  });
});
