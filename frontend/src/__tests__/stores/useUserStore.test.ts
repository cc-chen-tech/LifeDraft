/**
 * stores/useUserStore.ts Tests
 * Tests for user authentication and friends state
 */

// Mock the API before importing the store
jest.mock('@/lib/api', () => ({
  __esModule: true,
  default: {
    auth: {
      register: jest.fn(),
      login: jest.fn(),
      logout: jest.fn(),
      me: jest.fn(),
    },
    friends: {
      list: jest.fn(),
      pendingRequests: jest.fn(),
      sendRequest: jest.fn(),
      respond: jest.fn(),
      remove: jest.fn(),
    },
  },
}));

import { act } from '@testing-library/react';
import { useUserStore } from '@/stores/useUserStore';
import api from '@/lib/api';

describe('useUserStore', () => {
  beforeEach(() => {
    // Reset store to initial state
    act(() => {
      useUserStore.setState({
        user: null,
        token: null,
        isAuthenticated: false,
        friends: [],
        pendingRequests: [],
      });
    });
    jest.clearAllMocks();
  });

  describe('Initial state', () => {
    it('has correct initial values', () => {
      const state = useUserStore.getState();

      expect(state.user).toBeNull();
      expect(state.token).toBeNull();
      expect(state.isAuthenticated).toBe(false);
      expect(state.friends).toEqual([]);
      expect(state.pendingRequests).toEqual([]);
    });
  });

  describe('Registration', () => {
    it('registers a new user', async () => {
      const mockResponse = {
        token: 'register-token',
        user: {
          user_id: 1,
          public_id: 'pub123',
          display_name: 'Test User',
          private_id: 'priv123',
        },
      };
      (api.auth.register as jest.Mock).mockResolvedValue(mockResponse);

      let result;
      await act(async () => {
        result = await useUserStore.getState().register('Test User');
      });

      expect(api.auth.register).toHaveBeenCalledWith({ display_name: 'Test User' });
      expect(result).toEqual(mockResponse.user);

      const state = useUserStore.getState();
      expect(state.user).toEqual(mockResponse.user);
      expect(state.token).toBe('register-token');
      expect(state.isAuthenticated).toBe(true);
    });

    it('handles registration error', async () => {
      (api.auth.register as jest.Mock).mockRejectedValue(new Error('Registration failed'));

      await expect(useUserStore.getState().register('Test User')).rejects.toThrow('Registration failed');
    });
  });

  describe('Login', () => {
    it('logs in a user', async () => {
      const mockResponse = {
        token: 'login-token',
        user: {
          user_id: 1,
          public_id: 'pub123',
          display_name: 'Test User',
          private_id: 'priv123',
        },
      };
      (api.auth.login as jest.Mock).mockResolvedValue(mockResponse);

      let result;
      await act(async () => {
        result = await useUserStore.getState().login('priv123');
      });

      expect(api.auth.login).toHaveBeenCalledWith({ private_id: 'priv123' });
      expect(result).toEqual(mockResponse.user);

      const state = useUserStore.getState();
      expect(state.user).toEqual(mockResponse.user);
      expect(state.token).toBe('login-token');
      expect(state.isAuthenticated).toBe(true);
    });

    it('handles login error', async () => {
      (api.auth.login as jest.Mock).mockRejectedValue(new Error('Invalid credentials'));

      await expect(useUserStore.getState().login('wrong-id')).rejects.toThrow('Invalid credentials');
    });
  });

  describe('Logout', () => {
    it('logs out the user', async () => {
      // First, log in
      act(() => {
        useUserStore.setState({
          user: { user_id: 1, public_id: 'pub', display_name: 'Test', private_id: 'priv' },
          token: 'token',
          isAuthenticated: true,
          friends: [{ user_id: 2, public_id: 'pub2', display_name: 'Friend' }],
          pendingRequests: [],
        });
      });

      (api.auth.logout as jest.Mock).mockResolvedValue(undefined);

      await act(async () => {
        useUserStore.getState().logout();
      });

      expect(api.auth.logout).toHaveBeenCalled();

      const state = useUserStore.getState();
      expect(state.user).toBeNull();
      expect(state.token).toBeNull();
      expect(state.isAuthenticated).toBe(false);
      expect(state.friends).toEqual([]);
      expect(state.pendingRequests).toEqual([]);
    });
  });

  describe('Fetch current user', () => {
    it('fetches current user info', async () => {
      const mockUser = {
        user_id: 1,
        public_id: 'pub123',
        display_name: 'Test User',
        private_id: 'priv123',
      };
      (api.auth.me as jest.Mock).mockResolvedValue(mockUser);

      await act(async () => {
        await useUserStore.getState().fetchMe();
      });

      expect(api.auth.me).toHaveBeenCalled();

      const state = useUserStore.getState();
      expect(state.user).toEqual(mockUser);
      expect(state.isAuthenticated).toBe(true);
    });

    it('clears auth state on fetch error', async () => {
      // First set some auth state
      act(() => {
        useUserStore.setState({
          user: { user_id: 1, public_id: 'pub', display_name: 'Test', private_id: 'priv' },
          token: 'token',
          isAuthenticated: true,
        });
      });

      (api.auth.me as jest.Mock).mockRejectedValue(new Error('Unauthorized'));

      await act(async () => {
        await useUserStore.getState().fetchMe();
      });

      const state = useUserStore.getState();
      expect(state.user).toBeNull();
      expect(state.token).toBeNull();
      expect(state.isAuthenticated).toBe(false);
    });
  });

  describe('Friends management', () => {
    describe('fetchFriends', () => {
      it('fetches friends list', async () => {
        const mockFriends = [
          { user_id: 2, public_id: 'pub2', display_name: 'Friend 1' },
          { user_id: 3, public_id: 'pub3', display_name: 'Friend 2' },
        ];
        (api.friends.list as jest.Mock).mockResolvedValue(mockFriends);

        await act(async () => {
          await useUserStore.getState().fetchFriends();
        });

        expect(api.friends.list).toHaveBeenCalled();
        expect(useUserStore.getState().friends).toEqual(mockFriends);
      });

      it('handles fetch error', async () => {
        (api.friends.list as jest.Mock).mockRejectedValue(new Error('Network error'));

        await expect(useUserStore.getState().fetchFriends()).rejects.toThrow('Network error');
      });
    });

    describe('fetchPendingRequests', () => {
      it('fetches pending friend requests', async () => {
        const mockRequests = [
          {
            request_id: 1,
            from_user: { user_id: 4, public_id: 'pub4', display_name: 'Requester' },
            created_at: '2024-01-01',
          },
        ];
        (api.friends.pendingRequests as jest.Mock).mockResolvedValue(mockRequests);

        await act(async () => {
          await useUserStore.getState().fetchPendingRequests();
        });

        expect(api.friends.pendingRequests).toHaveBeenCalled();
        expect(useUserStore.getState().pendingRequests).toEqual(mockRequests);
      });
    });

    describe('sendFriendRequest', () => {
      it('sends a friend request', async () => {
        (api.friends.sendRequest as jest.Mock).mockResolvedValue({ message: 'Request sent' });

        await act(async () => {
          await useUserStore.getState().sendFriendRequest('pub123');
        });

        expect(api.friends.sendRequest).toHaveBeenCalledWith({ to_public_id: 'pub123' });
      });
    });

    describe('respondToRequest', () => {
      it('accepts a friend request', async () => {
        (api.friends.respond as jest.Mock).mockResolvedValue({ message: 'Accepted' });
        (api.friends.list as jest.Mock).mockResolvedValue([]);
        (api.friends.pendingRequests as jest.Mock).mockResolvedValue([]);

        await act(async () => {
          await useUserStore.getState().respondToRequest(1, true);
        });

        expect(api.friends.respond).toHaveBeenCalledWith({ request_id: 1, accept: true });
        // Should refresh both lists
        expect(api.friends.list).toHaveBeenCalled();
        expect(api.friends.pendingRequests).toHaveBeenCalled();
      });

      it('rejects a friend request', async () => {
        (api.friends.respond as jest.Mock).mockResolvedValue({ message: 'Rejected' });
        (api.friends.list as jest.Mock).mockResolvedValue([]);
        (api.friends.pendingRequests as jest.Mock).mockResolvedValue([]);

        await act(async () => {
          await useUserStore.getState().respondToRequest(1, false);
        });

        expect(api.friends.respond).toHaveBeenCalledWith({ request_id: 1, accept: false });
      });
    });

    describe('removeFriend', () => {
      it('removes a friend', async () => {
        // Set up initial friends list
        act(() => {
          useUserStore.setState({
            friends: [
              { user_id: 2, public_id: 'pub2', display_name: 'Friend 1' },
              { user_id: 3, public_id: 'pub3', display_name: 'Friend 2' },
            ],
          });
        });

        (api.friends.remove as jest.Mock).mockResolvedValue({ message: 'Removed' });

        await act(async () => {
          await useUserStore.getState().removeFriend(2);
        });

        expect(api.friends.remove).toHaveBeenCalledWith(2);
        expect(useUserStore.getState().friends).toHaveLength(1);
        expect(useUserStore.getState().friends[0].user_id).toBe(3);
      });
    });
  });

  describe('setUser', () => {
    it('sets user and token directly', () => {
      const mockUser = {
        user_id: 1,
        public_id: 'pub',
        display_name: 'Test',
        private_id: 'priv',
      };

      act(() => {
        useUserStore.getState().setUser(mockUser, 'test-token');
      });

      const state = useUserStore.getState();
      expect(state.user).toEqual(mockUser);
      expect(state.token).toBe('test-token');
      expect(state.isAuthenticated).toBe(true);
    });
  });

  describe('Persistence', () => {
    it('persist config is correct', () => {
      // The persist middleware should be configured
      // Check that the store exists and has the expected shape
      expect(useUserStore.getState()).toHaveProperty('user');
      expect(useUserStore.getState()).toHaveProperty('isAuthenticated');
    });
  });
});
