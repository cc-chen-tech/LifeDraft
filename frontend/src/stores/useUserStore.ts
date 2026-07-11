/**
 * useUserStore — 用户认证状态
 *
 * ★ 纯 Cookie 认证：
 * - Token 只存储在 httpOnly Cookie 中
 * - 应用启动时通过 /api/auth/me 验证 session
 * - 状态只保存在内存中，页面刷新后重新获取
 */
import { create } from "zustand";
import type { UserInfo } from "@/lib/types";
import api from "@/lib/api";

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

  // Actions
  register: (displayName: string) => Promise<UserInfo>;
  login: (privateId: string) => Promise<UserInfo>;
  logout: () => void;
  fetchMe: () => Promise<void>;
  setUser: (user: UserInfo) => void;
  clearAuth: () => void;
}

export const useUserStore = create<UserState>((set) => ({
  user: null,
  isAuthenticated: false,

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

  setUser: (user) => {
    set({ user, isAuthenticated: true });
  },

  clearAuth: () => {
    setAuthSessionHint(false);
    set({
      user: null,
      isAuthenticated: false,
    });
  },
}));
