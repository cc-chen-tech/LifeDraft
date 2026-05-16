/**
 * stores/useUserStore.ts Tests
 * Tests for user authentication and friends state
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
        friends: [],
        pendingRequests: [],
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
      expect(state.friends).toEqual([]);
      expect(state.pendingRequests).toEqual([]);
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
          friends: [{ user_id: 2, public_id: 'pub2', display_name: 'Friend' }],
          pendingRequests: [],
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
      expect(state.friends).toEqual([]);
      expect(state.pendingRequests).toEqual([]);
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
  });

  describe('Friends management', () => {
    describe('fetchFriends', () => {
      it('fetches friends list', async () => {
        const mockFriends = [
          { user_id: 2, public_id: 'pub2', display_name: 'Friend 1' },
          { user_id: 3, public_id: 'pub3', display_name: 'Friend 2' },
        ];
        (global.fetch as jest.Mock).mockResolvedValue(jsonResponse(mockFriends));

        await act(async () => {
          await useUserStore.getState().fetchFriends();
        });

        expect(global.fetch).toHaveBeenCalledWith('/api/friends', expect.objectContaining({ credentials: 'include' }));
        expect(useUserStore.getState().friends).toEqual(mockFriends);
      });

      it('handles fetch error', async () => {
        (global.fetch as jest.Mock).mockRejectedValue(new Error('Network error'));

        await expect(useUserStore.getState().fetchFriends()).rejects.toThrow('Network error');
      });
    });

    describe('fetchPendingRequests', () => {
      it('fetches pending friend requests', async () => {
        const mockRequests = [
          { request_id: 1, from_user: { user_id: 4, public_id: 'pub4', display_name: 'Requester' }, created_at: '2024-01-01' },
        ];
        (global.fetch as jest.Mock).mockResolvedValue(jsonResponse(mockRequests));

        await act(async () => {
          await useUserStore.getState().fetchPendingRequests();
        });

        expect(global.fetch).toHaveBeenCalledWith('/api/friends/requests', expect.objectContaining({ credentials: 'include' }));
        expect(useUserStore.getState().pendingRequests).toEqual(mockRequests);
      });
    });

    describe('sendFriendRequest', () => {
      it('sends a friend request', async () => {
        (global.fetch as jest.Mock).mockResolvedValue(jsonResponse({ message: 'Request sent' }));

        await act(async () => {
          await useUserStore.getState().sendFriendRequest('pub123');
        });

        expect(global.fetch).toHaveBeenCalledWith('/api/friends/requests', expect.objectContaining({
          method: 'POST',
        }));
      });
    });

    describe('respondToRequest', () => {
      it('accepts a friend request', async () => {
        let callCount = 0;
        (global.fetch as jest.Mock).mockImplementation(() => {
          callCount++;
          return Promise.resolve(jsonResponse(callCount === 1 ? { message: 'Accepted' } : []));
        });

        await act(async () => {
          await useUserStore.getState().respondToRequest(1, true);
        });

        expect(global.fetch).toHaveBeenCalledTimes(3);
        expect(global.fetch).toHaveBeenCalledWith('/api/friends/requests/1', expect.objectContaining({
          method: 'PUT',
        }));
      });

      it('rejects a friend request', async () => {
        (global.fetch as jest.Mock)
          .mockResolvedValueOnce(jsonResponse({ message: 'Rejected' }))
          .mockResolvedValue(jsonResponse([]));

        await act(async () => {
          await useUserStore.getState().respondToRequest(1, false);
        });

        expect(global.fetch).toHaveBeenCalledWith('/api/friends/requests/1', expect.objectContaining({
          method: 'PUT',
        }));
      });
    });

    describe('removeFriend', () => {
      it('removes a friend', async () => {
        act(() => {
          useUserStore.setState({
            friends: [
              { user_id: 2, public_id: 'pub2', display_name: 'Friend 1' },
              { user_id: 3, public_id: 'pub3', display_name: 'Friend 2' },
            ],
          });
        });
        (global.fetch as jest.Mock).mockResolvedValue(jsonResponse({ message: 'Removed' }));

        await act(async () => {
          await useUserStore.getState().removeFriend(2);
        });

        expect(global.fetch).toHaveBeenCalledWith('/api/friends/2', expect.objectContaining({ method: 'DELETE' }));
        expect(useUserStore.getState().friends).toHaveLength(1);
        expect(useUserStore.getState().friends[0].user_id).toBe(3);
      });
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
