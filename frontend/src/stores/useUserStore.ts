/**
 * useUserStore — 用户认证 & 好友状态
 */
import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { UserInfo, FriendInfo, FriendRequestInfo } from "@/lib/types";
import api from "@/lib/api";

interface UserState {
  // Auth
  user: UserInfo | null;
  token: string | null;
  isAuthenticated: boolean;

  // Friends
  friends: FriendInfo[];
  pendingRequests: FriendRequestInfo[];

  // Actions
  register: (displayName: string) => Promise<UserInfo>;
  login: (privateId: string) => Promise<UserInfo>;
  logout: () => void;
  fetchMe: () => Promise<void>;
  fetchFriends: () => Promise<void>;
  fetchPendingRequests: () => Promise<void>;
  sendFriendRequest: (publicId: string) => Promise<void>;
  respondToRequest: (requestId: number, accept: boolean) => Promise<void>;
  removeFriend: (userId: number) => Promise<void>;
  setUser: (user: UserInfo, token: string) => void;
}

export const useUserStore = create<UserState>()(
  persist(
    (set, get) => ({
      user: null,
      token: null,
      isAuthenticated: false,
      friends: [],
      pendingRequests: [],

      register: async (displayName) => {
        const res = await api.auth.register({ display_name: displayName });
        set({
          user: res.user,
          token: res.token,
          isAuthenticated: true,
        });
        return res.user;
      },

      login: async (privateId) => {
        const res = await api.auth.login({ private_id: privateId });
        set({
          user: res.user,
          token: res.token,
          isAuthenticated: true,
        });
        return res.user;
      },

      logout: () => {
        api.auth.logout();
        set({
          user: null,
          token: null,
          isAuthenticated: false,
          friends: [],
          pendingRequests: [],
        });
      },

      fetchMe: async () => {
        try {
          const user = await api.auth.me();
          set({ user, isAuthenticated: true });
        } catch {
          set({ user: null, token: null, isAuthenticated: false });
        }
      },

      fetchFriends: async () => {
        const friends = await api.friends.list();
        set({ friends });
      },

      fetchPendingRequests: async () => {
        const pendingRequests = await api.friends.pendingRequests();
        set({ pendingRequests });
      },

      sendFriendRequest: async (publicId) => {
        await api.friends.sendRequest({ to_public_id: publicId });
      },

      respondToRequest: async (requestId, accept) => {
        await api.friends.respond({ request_id: requestId, accept });
        // Refresh both lists
        await Promise.all([
          get().fetchFriends(),
          get().fetchPendingRequests(),
        ]);
      },

      removeFriend: async (userId) => {
        await api.friends.remove(userId);
        set((state) => ({
          friends: state.friends.filter((f) => f.user_id !== userId),
        }));
      },

      setUser: (user, token) => {
        set({ user, token, isAuthenticated: true });
      },
    }),
    {
      name: "user-storage",
      partialize: (state) => ({
        // ★ 移除 token 持久化（由 api.ts 单独管理 auth_token）
        // token: state.token,
        user: state.user,
        isAuthenticated: state.isAuthenticated,
      }),
    }
  )
);
