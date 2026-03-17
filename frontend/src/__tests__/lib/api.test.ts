/**
 * API client tests
 */
import api from '@/lib/api';

describe('auth', () => {
  describe('logout', () => {
    it('throws on API failure', async () => {
      // Mock fetch to simulate network error
      global.fetch = jest.fn().mockRejectedValueOnce(new Error('Network error'));

      await expect(api.auth.logout()).rejects.toThrow('Network error');
    });
  });
});
