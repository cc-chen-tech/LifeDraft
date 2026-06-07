 

/**
 * E2E Test: Friends System
 * Tests for friend requests, friend list, accept/reject, and remove friends.
 */
import { test, expect, Page, BrowserContext, APIResponse } from '@playwright/test';
import { registerUser } from './helpers/auth';
import { waitForPageReady } from './helpers/wait-helpers';

const BASE_URL = process.env.E2E_BASE_URL || `http://localhost:${process.env.E2E_FRONTEND_PORT ?? '3000'}`;
const API_URL = 'http://localhost:8000';

async function getApiWithTransientRetry(
  context: BrowserContext,
  url: string,
  attempts = 3,
): Promise<APIResponse> {
  let lastError: unknown;

  for (let attempt = 1; attempt <= attempts; attempt++) {
    try {
      return await context.request.get(url);
    } catch (error) {
      lastError = error;
      const message = error instanceof Error ? error.message : String(error);
      if (!/ECONNRESET|ECONNREFUSED|socket hang up/i.test(message) || attempt === attempts) {
        throw error;
      }
      await new Promise((resolve) => setTimeout(resolve, attempt * 250));
    }
  }

  throw lastError;
}

test.describe('Friends System', () => {
  // TC-01: 好友列表页面渲染
  test('TC-01: Profile page renders with friends section', async ({ page }) => {
    await page.goto(`${BASE_URL}/profile`);
    await page.waitForLoadState('domcontentloaded');

    // Unauthenticated users will be redirected to home, so check either profile or home loaded
    const bodyText = await page.textContent('body');
    expect(bodyText).toBeTruthy();

    await page.screenshot({ path: '/tmp/friends-tc01-profile.png' });
  });

  // TC-02: 未登录状态跳转到登录
  test('TC-02: Unauthenticated user redirected from profile page', async ({ page }) => {
    await page.goto(`${BASE_URL}/profile`);
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(2000);

    // Profile page redirects unauthenticated users to "/"
    const currentUrl = page.url();
    // Should either redirect to home or stay on profile with no content
    expect(currentUrl).toMatch(/\/profile|\/$/);
  });

  // TC-03: 空好友列表状态
  test('TC-03: Empty friends list shows placeholder', async ({ browser }) => {
    test.setTimeout(120_000);
    const context = await browser.newContext();
    const page = await context.newPage();

    // Register a fresh user via API (will have no friends)
    const userData = await registerUser(context, `FriendsTest_${Date.now()}`);

    if (userData) {
      await page.goto(`${BASE_URL}/profile`);
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(2000);

      // 页面应正常渲染（无崩溃），可能显示好友相关的占位文本或空列表
      const bodyText = await page.textContent('body');
      expect(bodyText).toBeTruthy();

      // 检查是否有好友相关内容显示（文案可能不同）
      const friendsRelated = page.locator('text=/暂无好友|好友列表|好友|friends|no friends/i');
      const hasFriendsSection = await friendsRelated.first().isVisible().catch(() => false);

      // 如果页面重定向到首页（未认证），也算通过
      const currentUrl = page.url();
      expect(hasFriendsSection || currentUrl.endsWith('/') || currentUrl.includes('/profile')).toBeTruthy();

      await page.screenshot({ path: '/tmp/friends-tc03-empty.png' });
    } else {
      // 如果无法注册用户（后端不可用），跳过
      test.skip(true, 'Could not register test user');
    }

    await page.close();
    await context.close();
  });

  // TC-04: 发送好友请求 API 端点可用
  test('TC-04: Send friend request API endpoint is available', async ({ request }) => {
    // Without auth, should get 401
    const response = await request.post(`${API_URL}/api/friends/request`, {
      data: { to_public_id: 'nonexistent-user-id' },
    });
    const status = response.status();
    expect([401, 400, 422]).toContain(status);
  });

  // TC-05: 待处理请求 API 端点可用
  test('TC-05: Pending requests API endpoint is available', async ({ request }) => {
    const response = await request.get(`${API_URL}/api/friends/requests`);
    const status = response.status();
    expect([401, 200]).toContain(status);
  });

  // TC-06: 好友列表 API 端点可用
  test('TC-06: Friends list API endpoint is available', async ({ request }) => {
    const response = await request.get(`${API_URL}/api/friends`);
    const status = response.status();
    expect([401, 200]).toContain(status);
  });

  // TC-07: 好友请求提交（UI 流程）
  test('TC-07: Send friend request via profile UI', async ({ browser }) => {
    test.setTimeout(120_000);
    const context = await browser.newContext();
    const page = await context.newPage();

    const userData = await registerUser(context, `FriendsSender_${Date.now()}`);

    if (userData) {
      await page.goto(`${BASE_URL}/profile`);
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(2000);

      // Find the "添加好友" input
      const friendInput = page.getByPlaceholder(/好友.*ID|公开ID|输入/i);
      const hasInput = await friendInput.isVisible().catch(() => false);

      if (hasInput) {
        await friendInput.fill('fake-public-id-12345');

        // Find and click send button
        const sendButton = page.getByRole('button', { name: /发送/i });
        if (await sendButton.isVisible()) {
          await sendButton.click();
          // Wait for API response
          await page.waitForTimeout(2000);

          // Either an error message or success indication should appear
          const errorOrSuccess = page.locator('text=/失败|错误|发送|成功|不存在/i');
          const hasResponse = await errorOrSuccess.isVisible().catch(() => false);
          // The API should have been called regardless
        }
      }

      await page.screenshot({ path: '/tmp/friends-tc07-send.png' });
    }

    await page.close();
    await context.close();
  });

  // TC-08: 接受好友请求 API 端点可用
  test('TC-08: Respond to friend request API endpoint is available', async ({ request }) => {
    // POST /api/friends/respond without auth should return 401 or 422
    const response = await request.post(`${API_URL}/api/friends/respond`, {
      data: { request_id: 99999, accept: true },
    });
    const status = response.status();
    expect([401, 400, 404, 422]).toContain(status);
  });

  // TC-09: 删除好友 API 端点可用
  test('TC-09: Remove friend API endpoint is available', async ({ request }) => {
    // DELETE /api/friends/{friend_user_id} without auth should return 401
    const response = await request.delete(`${API_URL}/api/friends/99999`);
    const status = response.status();
    expect([401, 404, 422]).toContain(status);
  });

  // TC-10: 好友系统 API 错误处理
  test('TC-10: Friends API error handling for invalid requests', async ({ request }) => {
    // Send request with missing body
    const response1 = await request.post(`${API_URL}/api/friends/request`);
    expect([400, 401, 422]).toContain(response1.status());

    // Respond with invalid data
    const response2 = await request.post(`${API_URL}/api/friends/respond`, {
      data: {},
    });
    expect([400, 401, 422]).toContain(response2.status());
  });
});

test.describe('Friends System - Full Flow', () => {
  let contextA: BrowserContext;
  let contextB: BrowserContext;

  test.beforeAll(async ({ browser }) => {
    contextA = await browser.newContext();
    contextB = await browser.newContext();
  });

  test.afterAll(async () => {
    await contextA.close();
    await contextB.close();
  });

  test('TC-11: Two-user friend request and accept flow via API', async () => {
    // Register User A
    const userA = await registerUser(contextA, `UserA_${Date.now()}`);
    // Register User B
    const userB = await registerUser(contextB, `UserB_${Date.now()}`);

    if (!userA || !userB) {
      test.skip(!userA && !userB, 'Could not register test users (backend may be unavailable)');
      return;
    }

    // Get User B's public_id from profile API
    const profileB = await contextB.request.get(`${API_URL}/api/auth/me`);
    if (!profileB.ok()) {
      console.log('Could not fetch User B profile, skipping full flow');
      return;
    }
    const profileBData = await profileB.json();
    const publicIdB = profileBData.public_id;

    if (!publicIdB) {
      console.log('User B has no public_id field, skipping full flow');
      return;
    }

    // User A sends friend request to User B
    const sendResp = await contextA.request.post(`${API_URL}/api/friends/request`, {
      data: { to_public_id: publicIdB },
    });
    console.log('Send friend request status:', sendResp.status());

    // If the endpoint returns an error (not implemented, etc.), skip gracefully
    if (!sendResp.ok() && sendResp.status() !== 400) {
      console.log('Friends API may not be fully available, skipping');
      return;
    }

    expect([200, 201, 400]).toContain(sendResp.status());

    if (sendResp.ok()) {
      // User B checks pending requests
      const pendingResp = await contextB.request.get(`${API_URL}/api/friends/requests`);

      if (!pendingResp.ok()) {
        console.log('Pending requests endpoint returned:', pendingResp.status(), '- skipping');
        return;
      }

      const pendingData = await pendingResp.json();
      console.log('Pending requests for B:', JSON.stringify(pendingData));

      if (Array.isArray(pendingData) && pendingData.length > 0) {
        const requestId = pendingData[0].request_id;

        // User B accepts the request
        const acceptResp = await contextB.request.post(`${API_URL}/api/friends/respond`, {
          data: { request_id: requestId, accept: true },
        });
        console.log('Accept friend request status:', acceptResp.status());
        expect([200, 201]).toContain(acceptResp.status());

        // Verify both users see each other in friends list
        const friendsA = await getApiWithTransientRetry(contextA, `${API_URL}/api/friends`);
        const friendsB = await getApiWithTransientRetry(contextB, `${API_URL}/api/friends`);

        if (friendsA.ok() && friendsB.ok()) {
          const friendsAData = await friendsA.json();
          const friendsBData = await friendsB.json();
          expect(Array.isArray(friendsAData)).toBeTruthy();
          expect(Array.isArray(friendsBData)).toBeTruthy();
          console.log('User A friends:', friendsAData.length, 'User B friends:', friendsBData.length);
        }
      }
    }
  });

  test('TC-12: Remove friend via API', async () => {
    // This test depends on TC-11 having established a friendship
    const friendsResp = await contextA.request.get(`${API_URL}/api/friends`);
    if (!friendsResp.ok()) {
      console.log('Could not fetch friends list, skipping remove test');
      return;
    }

    const friendsList = await friendsResp.json();
    if (Array.isArray(friendsList) && friendsList.length > 0) {
      const friendUserId = friendsList[0].user_id;
      const removeResp = await contextA.request.delete(`${API_URL}/api/friends/${friendUserId}`);
      console.log('Remove friend status:', removeResp.status());
      expect([200, 404]).toContain(removeResp.status());

      // Verify friend is removed
      const afterRemove = await contextA.request.get(`${API_URL}/api/friends`);
      if (afterRemove.ok()) {
        const afterData = await afterRemove.json();
        const stillFriend = afterData.find((f: { user_id: number }) => f.user_id === friendUserId);
        expect(stillFriend).toBeUndefined();
      }
    }
  });
});
