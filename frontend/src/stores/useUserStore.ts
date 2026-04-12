/**
 * useUserStore — 用户认证 & 好友状态
 *
 * ★ 纯 Cookie 认证：
 * - Token 只存储在 httpOnly Cookie 中
 * - 应用启动时通过 /api/auth/me 验证 session
 * - 状态只保存在内存中，页面刷新后重新获取
 */
import { create } from "zustand";
import type { UserInfo, FriendInfo, FriendRequestInfo } from "@/lib/types";
import api from "@/lib/api";

interface UserState {
  // Auth
  user: UserInfo | null;
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
  setUser: (user: UserInfo) => void;
  clearAuth: () => void;
}

export const useUserStore = create<UserState>((set, get) => ({
  user: null,
  isAuthenticated: false,
  friends: [],
  pendingRequests: [],

  register: async (displayName) => {
    const res = await api.auth.register({ display_name: displayName });
    set({
      user: res.user,
      isAuthenticated: true,
    });
    return res.user;
  },

  login: async (privateId) => {
    const res = await api.auth.login({ private_id: privateId });
    set({
      user: res.user,
      isAuthenticated: true,
    });
    return res.user;
  },

  logout: () => {
    api.auth.logout().catch(() => {});
    set({
      user: null,
      isAuthenticated: false,
      friends: [],
      pendingRequests: [],
    });
  },

  fetchMe: async () => {
    try {
      const user = await api.auth.me();
      set({ user, isAuthenticated: true });
    } catch (err: unknown) {
      // 仅在 401（token 无效/过期）时清除认证状态
      // 网络错误等其他异常不应清除已有的登录状态
      const status = (err as { status?: number })?.status;
      if (status === 401) {
        set({ user: null, isAuthenticated: false });
      }
      // 其他错误（网络异常等）保持当前状态不变
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

  setUser: (user) => {
    set({ user, isAuthenticated: true });
  },

  clearAuth: () => {
    set({
      user: null,
      isAuthenticated: false,
      friends: [],
      pendingRequests: [],
    });
  },
}));
