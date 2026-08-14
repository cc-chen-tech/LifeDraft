/**
 * stores/useUserStore.ts Tests
 * Tests for user authentication state
 * Uses real API module + global.fetch mocking
 */
import { act } from '@testing-library/react';
import { useUserStore } from '@/stores/useUserStore';
import { jsonResponse, errorResponse } from '@/__tests__/helpers/fetch';

describe('useUserStore', () => {
  beforeEach(() => {
    act(() => {
      useUserStore.setState({
        user: null,
        isAuthenticated: false,
      });
    });
    jest.clearAllMocks();
    global.fetch = jest.fn();
  });

  describe('Initial state', () => {
    it('has correct initial values', () => {
      const state = useUserStore.getState();
      expect(state.user).toBeNull();
      expect(state.isAuthenticated).toBe(false);
    });
  });

  describe('Registration', () => {
    it('registers a new user', async () => {
      const mockResponse = {
        token: 'register-token',
        user: { user_id: 1, public_id: 'pub123', display_name: 'Test User', private_id: 'priv123' },
      };
      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse(mockResponse));

      let result;
      await act(async () => {
        result = await useUserStore.getState().register('Test User');
      });

      expect(global.fetch).toHaveBeenCalledWith('/api/auth/register', expect.objectContaining({
        method: 'POST',
      }));
      expect(result).toEqual(mockResponse.user);
      const state = useUserStore.getState();
      expect(state.user).toEqual(mockResponse.user);
      expect(state.isAuthenticated).toBe(true);
    });

    it('handles registration error', async () => {
      (global.fetch as jest.Mock).mockRejectedValue(new Error('Registration failed'));

      await expect(useUserStore.getState().register('Test User')).rejects.toThrow('Registration failed');
    });
  });

  describe('Login', () => {
    it('logs in a user', async () => {
      const mockResponse = {
        token: 'login-token',
        user: { user_id: 1, public_id: 'pub123', display_name: 'Test User', private_id: 'priv123' },
      };
      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse(mockResponse));

      let result;
      await act(async () => {
        result = await useUserStore.getState().login('priv123');
      });

      expect(global.fetch).toHaveBeenCalledWith('/api/auth/login', expect.objectContaining({
        method: 'POST',
      }));
      expect(result).toEqual(mockResponse.user);
      const state = useUserStore.getState();
      expect(state.user).toEqual(mockResponse.user);
      expect(state.isAuthenticated).toBe(true);
    });

    it('handles login error', async () => {
      (global.fetch as jest.Mock).mockRejectedValue(new Error('Invalid credentials'));

      await expect(useUserStore.getState().login('wrong-id')).rejects.toThrow('Invalid credentials');
    });
  });

  describe('Logout', () => {
    it('logs out the user', async () => {
      act(() => {
        useUserStore.setState({
          user: { user_id: 1, public_id: 'pub', display_name: 'Test', private_id: 'priv' },
          isAuthenticated: true,
        });
      });
      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse(null));

      await act(async () => {
        useUserStore.getState().logout();
      });

      expect(global.fetch).toHaveBeenCalledWith('/api/auth/logout', expect.objectContaining({ method: 'POST' }));
      const state = useUserStore.getState();
      expect(state.user).toBeNull();
      expect(state.isAuthenticated).toBe(false);
    });
  });

  describe('Fetch current user', () => {
    it('fetches current user info', async () => {
      const mockUser = { user_id: 1, public_id: 'pub123', display_name: 'Test User', private_id: 'priv123' };
      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse(mockUser));

      await act(async () => {
        await useUserStore.getState().fetchMe();
      });

      expect(global.fetch).toHaveBeenCalledWith('/api/auth/me', expect.objectContaining({ credentials: 'include' }));
      const state = useUserStore.getState();
      expect(state.user).toEqual(mockUser);
      expect(state.isAuthenticated).toBe(true);
    });

    it('clears auth state on fetch error', async () => {
      act(() => {
        useUserStore.setState({
          user: { user_id: 1, public_id: 'pub', display_name: 'Test', private_id: 'priv' },
          isAuthenticated: true,
        });
      });
      (global.fetch as jest.Mock).mockResolvedValue(errorResponse(401));

      await act(async () => {
        await useUserStore.getState().fetchMe();
      });

      const state = useUserStore.getState();
      expect(state.user).toBeNull();
      expect(state.isAuthenticated).toBe(false);
    });

    it('does not let a stale 401 clear a newer registration', async () => {
      let resolveFetchMe!: (response: Response) => void;
      const pendingFetchMe = new Promise<Response>((resolve) => {
        resolveFetchMe = resolve;
      });
      const registeredUser = {
        user_id: 7,
        public_id: 'pub-new',
        display_name: 'New User',
        private_id: 'priv-new',
      };

      (global.fetch as jest.Mock)
        .mockReturnValueOnce(pendingFetchMe)
        .mockResolvedValueOnce(jsonResponse({ token: 'new-token', user: registeredUser }));

      const staleFetch = useUserStore.getState().fetchMe();
      await act(async () => {
        await useUserStore.getState().register('New User');
      });
      resolveFetchMe(errorResponse(401));
      await act(async () => {
        await staleFetch;
      });

      expect(useUserStore.getState().user).toEqual(registeredUser);
      expect(useUserStore.getState().isAuthenticated).toBe(true);
    });
  });

  describe('setUser', () => {
    it('sets user and token directly', () => {
      const mockUser = { user_id: 1, public_id: 'pub', display_name: 'Test', private_id: 'priv' };
      act(() => {
        useUserStore.getState().setUser(mockUser);
      });
      const state = useUserStore.getState();
      expect(state.user).toEqual(mockUser);
      expect(state.isAuthenticated).toBe(true);
    });
  });

  describe('Persistence', () => {
    it('persist config is correct', () => {
      expect(useUserStore.getState()).toHaveProperty('user');
      expect(useUserStore.getState()).toHaveProperty('isAuthenticated');
    });
  });
});
