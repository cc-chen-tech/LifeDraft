/** E2E retirement contract for the removed friends feature. */
import { expect, test } from '@playwright/test';
import { API_URL } from './helpers/auth';

const BASE_URL = process.env.E2E_BASE_URL
  || `http://localhost:${process.env.E2E_FRONTEND_PORT ?? '3000'}`;

const retiredRoutes = [
  { method: 'GET', path: '/api/friends' },
  { method: 'GET', path: '/api/friends/requests' },
  { method: 'POST', path: '/api/friends/request', data: { to_public_id: 'ABC123' } },
  { method: 'POST', path: '/api/friends/respond', data: { request_id: 1, accept: true } },
  { method: 'DELETE', path: '/api/friends/2' },
  { method: 'POST', path: '/api/friends/requests', data: { to_public_id: 'ABC123' } },
  { method: 'PUT', path: '/api/friends/requests/1', data: { accept: true } },
] as const;

test.describe('Retired friends feature', () => {
  test('profile page is no longer a product route', async ({ request }) => {
    const response = await request.get(`${BASE_URL}/profile`);

    expect(response.status()).toBe(404);
    expect(await response.text()).not.toContain('添加好友');
  });

  test('former backend friend endpoints return not found', async ({ request }) => {
    for (const route of retiredRoutes) {
      const response = await request.fetch(`${API_URL}${route.path}`, {
        method: route.method,
        data: 'data' in route ? route.data : undefined,
      });

      expect(response.status(), `${route.method} ${route.path}`).toBe(404);
    }
  });

  test('frontend proxy does not revive the retired friend API', async ({ request }) => {
    const response = await request.get(`${BASE_URL}/api/friends`);

    expect(response.status()).toBe(404);
  });
});
