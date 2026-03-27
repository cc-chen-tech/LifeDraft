/**
 * API client tests
 */
import api from '@/lib/api';

describe('auth', () => {
  describe('logout', () => {
    it('throws on API failure', async () => {
      // Mock fetch to simulate network error for all retry attempts
      global.fetch = jest.fn().mockRejectedValue(new Error('Network error'));

      await expect(api.auth.logout()).rejects.toThrow('Network error');
    }, 15000); // Increase timeout to account for retry delays
  });
});
