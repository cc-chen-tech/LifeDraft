 

/**
 * API Contract Tests - API契约测试
 *
 * 验证前端调用的API端点与后端实际路由匹配
 * 能够捕获如 /games/1/round-scenes -> /images/scene/1/1 这类路径不匹配问题
 */

import { test, expect, APIRequestContext } from '@playwright/test';
import { API_URL } from './helpers/auth';

/**
 * 测试API端点是否存在且可访问
 */
async function testEndpoint(
  request: APIRequestContext,
  method: 'GET' | 'POST' | 'PUT' | 'DELETE',
  path: string,
  expectedStatuses: number[] = [200, 401, 404, 422, 429],
  body?: Record<string, unknown>,
  requestTimeout: number = 15000
) {
  const url = `${API_URL}${path}`;
  const headers = { 'X-E2E-Contract-Probe': '1' };
  let response;

  try {
    if (method === 'GET') {
      response = await request.get(url, { headers, timeout: requestTimeout });
    } else if (method === 'POST') {
      response = await request.post(url, { data: body || {}, headers, timeout: requestTimeout });
    } else if (method === 'PUT') {
      response = await request.put(url, { data: body || {}, headers, timeout: requestTimeout });
    } else if (method === 'DELETE') {
      response = await request.delete(url, { headers, timeout: requestTimeout });
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

  test('DELETE /api/games/:id should exist', async ({ request }) => {
    const result = await testEndpoint(request, 'DELETE', '/api/games/999999');
    expect(result.exists).toBe(true);
    expect(result.error).toBeNull();
  });

  test('GET /api/games/active should exist', async ({ request }) => {
    const result = await testEndpoint(request, 'GET', '/api/games/active');
    expect(result.exists).toBe(true);
    expect(result.error).toBeNull();
  });

  test('POST /api/games/:id/save should exist', async ({ request }) => {
    const result = await testEndpoint(request, 'POST', '/api/games/1/save');
    expect(result.exists).toBe(true);
    expect(result.error).toBeNull();
  });

  test('POST /api/games/:id/clear-cache should exist', async ({ request }) => {
    const result = await testEndpoint(request, 'POST', '/api/games/999999/clear-cache');
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

  test('POST /api/games/:id/choice-sync should exist', async ({ request }) => {
    const result = await testEndpoint(request, 'POST', '/api/games/1/choice-sync', [200, 401, 404, 422, 429], { option_index: 0 });
    expect(result.exists).toBe(true);
    expect(result.error).toBeNull();
  });

  test('POST /api/games/:id/custom-choice-sync should exist', async ({ request }) => {
    const result = await testEndpoint(request, 'POST', '/api/games/1/custom-choice-sync', [200, 401, 404, 422, 429], { custom_text: 'test' });
    expect(result.exists).toBe(true);
    expect(result.error).toBeNull();
  });

  test('GET /api/games/:id/event should exist', async ({ request }) => {
    const result = await testEndpoint(request, 'GET', '/api/games/1/event');
    expect(result.exists).toBe(true);
    expect(result.error).toBeNull();
  });

  test('POST /api/games/:id/event-sync should exist', async ({ request }) => {
    const result = await testEndpoint(request, 'POST', '/api/games/1/event-sync');
    expect(result.exists).toBe(true);
    expect(result.error).toBeNull();
  });

  test('GET /api/games/:id/state should exist', async ({ request }) => {
    const result = await testEndpoint(request, 'GET', '/api/games/1/state');
    expect(result.exists).toBe(true);
    expect(result.error).toBeNull();
  });

  test('GET /api/games/:id/ending should exist', async ({ request }) => {
    const result = await testEndpoint(request, 'GET', '/api/games/999999/ending');
    expect(result.exists).toBe(true);
    expect(result.error).toBeNull();
  });

  test('POST /api/games/:id/summary should exist', async ({ request }) => {
    const result = await testEndpoint(request, 'POST', '/api/games/1/summary', [200, 401, 404, 422, 429], { weeks: 4 });
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

test.describe('API Contract - Save Point Endpoints', () => {
  test('POST /api/games/:id/save-point should exist', async ({ request }) => {
    const result = await testEndpoint(request, 'POST', '/api/games/999999/save-point');
    expect(result.exists).toBe(true);
    expect(result.error).toBeNull();
  });

  test('GET /api/games/:id/save-points should exist', async ({ request }) => {
    const result = await testEndpoint(request, 'GET', '/api/games/999999/save-points');
    expect(result.exists).toBe(true);
    expect(result.error).toBeNull();
  });

  test('GET /api/games/:id/timeline should exist', async ({ request }) => {
    const result = await testEndpoint(request, 'GET', '/api/games/999999/timeline');
    expect(result.exists).toBe(true);
    expect(result.error).toBeNull();
  });

  test('GET /api/games/load-save-point/:stateId should exist', async ({ request }) => {
    const result = await testEndpoint(request, 'GET', '/api/games/load-save-point/999999');
    expect(result.exists).toBe(true);
    expect(result.error).toBeNull();
  });

  test('DELETE /api/games/save-point/:stateId should exist', async ({ request }) => {
    const result = await testEndpoint(request, 'DELETE', '/api/games/save-point/999999');
    expect(result.exists).toBe(true);
    expect(result.error).toBeNull();
  });
});

test.describe('API Contract - Story Endpoints', () => {
  test('POST /api/games/:id/chat should exist', async ({ request }) => {
    const result = await testEndpoint(request, 'POST', '/api/games/1/chat', [200, 401, 404, 422, 429, 500], { message: 'test' });
    expect(result.exists).toBe(true);
    expect(result.error).toBeNull();
  });

  test('POST /api/games/:id/rewrite should exist', async ({ request }) => {
    const result = await testEndpoint(request, 'POST', '/api/games/1/rewrite', [200, 401, 404, 422, 429, 500], { full_story: 'test', user_instruction: 'test' });
    expect(result.exists).toBe(true);
    expect(result.error).toBeNull();
  });

  test('POST /api/games/:id/regenerate should exist', async ({ request }) => {
    const result = await testEndpoint(request, 'POST', '/api/games/1/regenerate', [200, 401, 404, 422, 429, 500]);
    expect(result.exists).toBe(true);
    expect(result.error).toBeNull();
  });

  test('DELETE /api/games/:id/session-debug should exist', async ({ request }) => {
    const result = await testEndpoint(request, 'DELETE', '/api/games/999999/session-debug');
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

  test('POST /api/images/batch-characters should exist', async ({ request }) => {
    const result = await testEndpoint(request, 'POST', '/api/images/batch-characters');
    expect(result.exists).toBe(true);
    expect(result.error).toBeNull();
  });

  test('POST /api/images/opening-illustration should exist', async ({ request }) => {
    const result = await testEndpoint(request, 'POST', '/api/images/opening-illustration');
    expect(result.exists).toBe(true);
    expect(result.error).toBeNull();
  });

  test('POST /api/images/opening-illustration/regenerate should exist', async ({ request }) => {
    const result = await testEndpoint(request, 'POST', '/api/images/opening-illustration/regenerate');
    expect(result.exists).toBe(true);
    expect(result.error).toBeNull();
  });

  test('GET /api/images/:imageId should exist', async ({ request }) => {
    const result = await testEndpoint(request, 'GET', '/api/images/999999');
    expect(result.exists).toBe(true);
    expect(result.error).toBeNull();
  });

  test('DELETE /api/images/:imageId should exist', async ({ request }) => {
    const result = await testEndpoint(request, 'DELETE', '/api/images/999999');
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

  test('GET /api/collection/:gameId/details should exist', async ({ request }) => {
    const result = await testEndpoint(request, 'GET', '/api/collection/1/details');
    expect(result.exists).toBe(true);
    expect(result.error).toBeNull();
  });

  test('POST /api/collection/:gameId/characters/:name/generate-image should exist', async ({ request }) => {
    const result = await testEndpoint(request, 'POST', '/api/collection/1/characters/Test/generate-image');
    expect(result.exists).toBe(true);
    expect(result.error).toBeNull();
  });

  test('POST /api/collection/:gameId/characters/:name/generate-description should exist', async ({ request }) => {
    const result = await testEndpoint(request, 'POST', '/api/collection/1/characters/Test/generate-description');
    expect(result.exists).toBe(true);
    expect(result.error).toBeNull();
  });

  test('POST /api/collection/:gameId/characters/:name/regenerate-image should exist', async ({ request }) => {
    const result = await testEndpoint(request, 'POST', '/api/collection/1/characters/Test/regenerate-image', [200, 401, 404, 422, 429], { feedback: 'test' });
    expect(result.exists).toBe(true);
    expect(result.error).toBeNull();
  });

  test('POST /api/collection/:gameId/items/:name/generate-image should exist', async ({ request }) => {
    const result = await testEndpoint(request, 'POST', '/api/collection/1/items/Test/generate-image');
    expect(result.exists).toBe(true);
    expect(result.error).toBeNull();
  });

  test('POST /api/collection/:gameId/items/:name/regenerate-image should exist', async ({ request }) => {
    const result = await testEndpoint(request, 'POST', '/api/collection/1/items/Test/regenerate-image', [200, 401, 404, 422, 429], { feedback: 'test' });
    expect(result.exists).toBe(true);
    expect(result.error).toBeNull();
  });

  test('POST /api/collection/:gameId/items/:name/generate-description should exist', async ({ request }) => {
    const result = await testEndpoint(request, 'POST', '/api/collection/1/items/Test/generate-description');
    expect(result.exists).toBe(true);
    expect(result.error).toBeNull();
  });

  test('POST /api/collection/:gameId/landmarks/:name/generate-image should exist', async ({ request }) => {
    const result = await testEndpoint(request, 'POST', '/api/collection/1/landmarks/Test/generate-image');
    expect(result.exists).toBe(true);
    expect(result.error).toBeNull();
  });

  test('POST /api/collection/:gameId/landmarks/:name/generate-description should exist', async ({ request }) => {
    const result = await testEndpoint(request, 'POST', '/api/collection/1/landmarks/Test/generate-description');
    expect(result.exists).toBe(true);
    expect(result.error).toBeNull();
  });

  test('POST /api/collection/:gameId/recognize-entities should exist', async ({ request }) => {
    const result = await testEndpoint(request, 'POST', '/api/collection/1/recognize-entities', [200, 401, 404, 422, 429, 500], { min_appearances: 3 });
    expect(result.exists).toBe(true);
    expect(result.error).toBeNull();
  });

  test('POST /api/collection/:gameId/add-entities should exist', async ({ request }) => {
    const result = await testEndpoint(request, 'POST', '/api/collection/1/add-entities', [200, 401, 404, 422, 429, 500], { items: [], landmarks: [] });
    expect(result.exists).toBe(true);
    expect(result.error).toBeNull();
  });

  test('POST /api/collection/:gameId/items/create should exist', async ({ request }) => {
    const result = await testEndpoint(request, 'POST', '/api/collection/1/items/create', [200, 401, 404, 422, 429, 500], { name: 'TestItem' });
    expect(result.exists).toBe(true);
    expect(result.error).toBeNull();
  });

  test('DELETE /api/collection/:gameId/items/:name should exist', async ({ request }) => {
    const result = await testEndpoint(request, 'DELETE', '/api/collection/999999/items/Test');
    expect(result.exists).toBe(true);
    expect(result.error).toBeNull();
  });

  test('DELETE /api/collection/:gameId/characters/:name should exist', async ({ request }) => {
    const result = await testEndpoint(request, 'DELETE', '/api/collection/999999/characters/Test');
    expect(result.exists).toBe(true);
    expect(result.error).toBeNull();
  });

  test('DELETE /api/collection/:gameId/landmarks/:name should exist', async ({ request }) => {
    const result = await testEndpoint(request, 'DELETE', '/api/collection/999999/landmarks/Test');
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

  test('POST /api/character/relationships-summary should exist', async ({ request }) => {
    const result = await testEndpoint(request, 'POST', '/api/character/relationships-summary');
    expect(result.exists).toBe(true);
    expect(result.error).toBeNull();
  });
});

test.describe('API Contract - Preset Endpoints', () => {
  test('GET /api/presets should exist', async ({ request }) => {
    const result = await testEndpoint(request, 'GET', '/api/presets');
    expect(result.exists).toBe(true);
    expect(result.error).toBeNull();
  });

  test('POST /api/presets should exist', async ({ request }) => {
    const result = await testEndpoint(request, 'POST', '/api/presets', [200, 201, 401, 422, 429, 500], { preset_name: 'test', player_name: 'test' });
    expect(result.exists).toBe(true);
    expect(result.error).toBeNull();
  });

  test('GET /api/presets/:id should exist', async ({ request }) => {
    const result = await testEndpoint(request, 'GET', '/api/presets/999999');
    expect(result.exists).toBe(true);
    expect(result.error).toBeNull();
  });

  test('DELETE /api/presets/:id should exist', async ({ request }) => {
    const result = await testEndpoint(request, 'DELETE', '/api/presets/999999');
    expect(result.exists).toBe(true);
    expect(result.error).toBeNull();
  });
});

test.describe('API Contract - Music Endpoints', () => {
  // 音乐 API 依赖外部网易云服务，响应可能较慢，给更长的超时
  const MUSIC_API_TIMEOUT = 30000;

  test('POST /api/music/recommend should exist', async ({ request }) => {
    // Contract existence should stay fast and should not depend on live AI/music providers.
    const result = await testEndpoint(request, 'POST', '/api/music/recommend', [422, 429], {});
    expect(result.exists).toBe(true);
    expect(result.error).toBeNull();
  });

  test('GET /api/music/song-url should exist', async ({ request }) => {
    const result = await testEndpoint(request, 'GET', '/api/music/song-url?song_id=1', undefined, undefined, MUSIC_API_TIMEOUT);
    expect(result.exists).toBe(true);
    expect(result.error).toBeNull();
  });

  test('GET /api/music/search should exist', async ({ request }) => {
    const result = await testEndpoint(request, 'GET', '/api/music/search?keyword=test', undefined, undefined, MUSIC_API_TIMEOUT);
    expect(result.exists).toBe(true);
    expect(result.error).toBeNull();
  });

  test('GET /api/music/stream/:songId should exist', async ({ request }) => {
    const result = await testEndpoint(request, 'GET', '/api/music/stream/1', [200, 206, 404, 500, 502], undefined, MUSIC_API_TIMEOUT);
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

test.describe('API Contract - Schema Validation', () => {
  /**
   * 对关键端点的响应进行基础 schema 验证。
   * 验证关键字段存在性和基本类型。
   * 未登录时预期 401，登录时验证 200 响应的 schema。
   */

  test('GET /api/auth/me should return valid user schema or 401', async ({ request }) => {
    const url = `${API_URL}/api/auth/me`;
    const response = await request.get(url);
    const status = response.status();

    if (status === 200) {
      const body = await response.json();
      expect(body).toHaveProperty('user_id');
      expect(typeof body.user_id).toBe('number');
      expect(body).toHaveProperty('public_id');
      expect(typeof body.public_id).toBe('string');
      expect(body).toHaveProperty('display_name');
      expect(typeof body.display_name).toBe('string');
    } else {
      expect([401, 403]).toContain(status);
    }
  });

  test('GET /api/games should return array or 401', async ({ request }) => {
    const url = `${API_URL}/api/games`;
    const response = await request.get(url);
    const status = response.status();

    if (status === 200) {
      const body = await response.json();
      expect(Array.isArray(body)).toBe(true);
      if (body.length > 0) {
        const game = body[0];
        expect(game).toHaveProperty('game_id');
        expect(typeof game.game_id).toBe('number');
        expect(game).toHaveProperty('player_name');
        expect(typeof game.player_name).toBe('string');
      }
    } else {
      expect([401]).toContain(status);
    }
  });

  test('GET /api/presets should return array or valid response', async ({ request }) => {
    const url = `${API_URL}/api/presets`;
    const response = await request.get(url);
    const status = response.status();

    if (status === 200) {
      const body = await response.json();
      expect(Array.isArray(body)).toBe(true);
      if (body.length > 0) {
        const preset = body[0];
        expect(preset).toHaveProperty('preset_id');
        expect(typeof preset.preset_id).toBe('number');
        expect(preset).toHaveProperty('preset_name');
        expect(typeof preset.preset_name).toBe('string');
        expect(preset).toHaveProperty('player_name');
        expect(typeof preset.player_name).toBe('string');
      }
    } else {
      expect([401]).toContain(status);
    }
  });

  test('GET /api/music/song-url should return url field or error', async ({ request }) => {
    const url = `${API_URL}/api/music/song-url?song_id=1`;
    const response = await request.get(url);
    const status = response.status();

    if (status === 200) {
      const body = await response.json();
      expect(body).toHaveProperty('url');
      expect(typeof body.url).toBe('string');
    } else {
      // 404 (song not found) or 500 (service unavailable) are acceptable
      expect([404, 500]).toContain(status);
    }
  });

  test('GET /api/music/search should return songs array or error', async ({ request }) => {
    const url = `${API_URL}/api/music/search?keyword=test`;
    const response = await request.get(url);
    const status = response.status();

    if (status === 200) {
      const body = await response.json();
      expect(body).toHaveProperty('songs');
      expect(Array.isArray(body.songs)).toBe(true);
      if (body.songs.length > 0) {
        const song = body.songs[0];
        expect(song).toHaveProperty('id');
        expect(typeof song.id).toBe('number');
        expect(song).toHaveProperty('name');
        expect(typeof song.name).toBe('string');
        expect(song).toHaveProperty('artists');
        expect(Array.isArray(song.artists)).toBe(true);
      }
    } else {
      // 500 if music service is unavailable
      expect([500]).toContain(status);
    }
  });
});
