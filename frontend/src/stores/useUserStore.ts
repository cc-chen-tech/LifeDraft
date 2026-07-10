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

/** 好友列表缓存有效期：60 秒 */
const FRIENDS_CACHE_TTL = 60 * 1000;
const AUTH_SESSION_HINT = "story2-auth-session";

export function hasAuthSessionHint(): boolean {
  return typeof window !== "undefined" && window.sessionStorage.getItem(AUTH_SESSION_HINT) === "1";
}

function setAuthSessionHint(authenticated: boolean): void {
  if (typeof window === "undefined") return;
  if (authenticated) {
    window.sessionStorage.setItem(AUTH_SESSION_HINT, "1");
  } else {
    window.sessionStorage.removeItem(AUTH_SESSION_HINT);
  }
}

interface UserState {
  // Auth
  user: UserInfo | null;
  isAuthenticated: boolean;

  // Friends
  friends: FriendInfo[];
  pendingRequests: FriendRequestInfo[];
  lastFriendsRefresh: number;

  // Actions
  register: (displayName: string) => Promise<UserInfo>;
  login: (privateId: string) => Promise<UserInfo>;
  logout: () => void;
  fetchMe: () => Promise<void>;
  fetchFriends: (force?: boolean) => Promise<void>;
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
  lastFriendsRefresh: 0,

  register: async (displayName) => {
    const res = await api.auth.register({ display_name: displayName });
    setAuthSessionHint(true);
    set({
      user: res.user,
      isAuthenticated: true,
    });
    return res.user;
  },

  login: async (privateId) => {
    const res = await api.auth.login({ private_id: privateId });
    setAuthSessionHint(true);
    set({
      user: res.user,
      isAuthenticated: true,
    });
    return res.user;
  },

  logout: () => {
    api.auth.logout().catch(() => {});
    setAuthSessionHint(false);
    set({
      user: null,
      isAuthenticated: false,
      friends: [],
      pendingRequests: [],
      lastFriendsRefresh: 0,
    });
  },

  fetchMe: async () => {
    try {
      const user = await api.auth.me();
      setAuthSessionHint(true);
      set({ user, isAuthenticated: true });
    } catch (err: unknown) {
      // 仅在 401（token 无效/过期）时清除认证状态
      // 网络错误等其他异常不应清除已有的登录状态
      const status = (err as { status?: number })?.status;
      if (status === 401) {
        setAuthSessionHint(false);
        set({ user: null, isAuthenticated: false });
      }
      // 其他错误（网络异常等）保持当前状态不变
    }
  },

  fetchFriends: async (force?: boolean) => {
    const now = Date.now();
    const { lastFriendsRefresh, friends } = get();
    // 缓存未过期且有数据时跳过请求
    if (!force && friends.length > 0 && now - lastFriendsRefresh < FRIENDS_CACHE_TTL) {
      return;
    }
    const freshFriends = await api.friends.list();
    set({ friends: freshFriends, lastFriendsRefresh: now });
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
    setAuthSessionHint(false);
    set({
      user: null,
      isAuthenticated: false,
      friends: [],
      pendingRequests: [],
      lastFriendsRefresh: 0,
    });
  },
}));
