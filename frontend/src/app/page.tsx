"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from "@/components/ui/sheet";
import { useUserStore } from "@/stores/useUserStore";
import { useGameStore } from "@/stores/useGameStore";
import { useHydration } from "@/hooks/useHydration";
import {
  Sparkles,
  FolderOpen,
  BookOpen,
  Loader2,
  LogIn,
  UserPlus,
  Copy,
  Check,
  Play,
} from "lucide-react";

type AuthMode = "login" | "register" | null;

export default function WelcomePage() {
  const router = useRouter();
  const { isAuthenticated, user, register, login, logout, fetchMe } = useUserStore();
  const { gameId, fetchSavedGames, fetchPresets, resetCreation } = useGameStore();
  const hydrated = useHydration();
  const [authChecked, setAuthChecked] = useState(false);

  // 页面加载时检查 session（从 Cookie 恢复登录状态）
  useEffect(() => {
    if (!hydrated) return;
    if (isAuthenticated) {
      // 已经登录（可能是 store hydration 恢复），调用 fetchMe 验证 session 有效性
      Promise.resolve(fetchMe?.()).finally(() => setAuthChecked(true));
    } else {
      // 未登录，尝试从 cookie 恢复
      Promise.resolve(fetchMe?.()).catch(() => {}).finally(() => setAuthChecked(true));
    }
  }, [hydrated, fetchMe]);

  // Whether there's an active game to continue
  const hasActiveGame = hydrated && !!gameId;

  const [authMode, setAuthMode] = useState<AuthMode>(null);
  const [displayName, setDisplayName] = useState("");
  const [privateId, setPrivateId] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");
  const [showPrivateId, setShowPrivateId] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  // Prefetch data if authenticated (only after auth check completes)
  useEffect(() => {
    if (authChecked && isAuthenticated) {
      fetchSavedGames().catch(() => {});
      fetchPresets().catch(() => {});
    }
  }, [authChecked, isAuthenticated, fetchSavedGames, fetchPresets]);

  const handleRegister = async () => {
    if (!displayName.trim()) return;
    setIsLoading(true);
    setError("");
    try {
      const userInfo = await register(displayName.trim());
      // Show private ID to user — critical for login
      if (userInfo.private_id) {
        setShowPrivateId(userInfo.private_id);
      }
    } catch (err) {
      setError(String((err as Error).message || "注册失败"));
    } finally {
      setIsLoading(false);
    }
  };

  const handleLogin = async () => {
    if (!privateId.trim()) return;
    setIsLoading(true);
    setError("");
    try {
      await login(privateId.trim());
      setAuthMode(null);
    } catch (err) {
      setError(String((err as Error).message || "登录失败，请检查密钥"));
    } finally {
      setIsLoading(false);
    }
  };

  const handleCopyPrivateId = () => {
    if (showPrivateId) {
      import("@/lib/utils").then(({ copyToClipboard }) => {
        copyToClipboard(showPrivateId).then((success) => {
          if (success) {
            setCopied(true);
            setTimeout(() => setCopied(false), 2000);
          }
        });
      });
    }
  };

  return (
    <div className="min-h-screen flex flex-col items-center justify-center px-4 animate-page-enter">
      {/* Background gradient */}
      <div className="fixed inset-0 bg-gradient-to-b from-background via-background to-secondary/30 -z-10" />

      {/* Title */}
      <div className="text-center mb-12">
        <h1 className="text-4xl md:text-6xl font-serif font-bold text-foreground mb-3 tracking-tight">
          Story Life
        </h1>
        <p className="text-lg text-muted-foreground">
          AI驱动的沉浸式人生模拟
        </p>
      </div>

      {/* Main actions */}
      <div className="w-full max-w-sm space-y-3">
        {/* Continue game — only if there's an active game */}
        {hasActiveGame && (
          <Button
            className="w-full h-14 text-base touch-target bg-primary/90 hover:bg-primary"
            onClick={() => router.push("/play")}
          >
            <Play className="w-5 h-5 mr-2" />
            继续游戏
          </Button>
        )}

        <Button
          variant={hasActiveGame ? "outline" : "default"}
          className="w-full h-14 text-base touch-target"
          onClick={() => {
            if (!isAuthenticated) {
              setAuthMode("register");
            } else {
              // ★ 清空之前的角色创建数据
              resetCreation();
              router.push("/create");
            }
          }}
        >
          <Sparkles className="w-5 h-5 mr-2" />
          新游戏
        </Button>

        <Button
          variant="outline"
          className="w-full h-14 text-base touch-target"
          onClick={() => {
            if (!isAuthenticated) {
              setAuthMode("login");
            } else {
              router.push("/saves");
            }
          }}
        >
          <FolderOpen className="w-5 h-5 mr-2" />
          加载存档
        </Button>

        <Button
          variant="outline"
          className="w-full h-14 text-base touch-target"
          onClick={() => {
            if (!isAuthenticated) {
              setAuthMode("login");
            } else {
              router.push("/presets");
            }
          }}
        >
          <BookOpen className="w-5 h-5 mr-2" />
          角色预设
        </Button>
      </div>

      {/* Auth status */}
      <div className="mt-8 text-center">
        {isAuthenticated ? (
          <div className="text-sm text-muted-foreground">
            <span>
              欢迎回来，{user?.display_name || "旅行者"}
            </span>
            <button
              className="ml-3 text-primary hover:underline"
              onClick={logout}
            >
              登出
            </button>
          </div>
        ) : (
          <div className="flex gap-4 justify-center text-sm">
            <button
              className="text-primary hover:underline flex items-center gap-1"
              onClick={() => setAuthMode("login")}
            >
              <LogIn className="w-3 h-3" />
              登录
            </button>
            <button
              className="text-muted-foreground hover:text-foreground flex items-center gap-1"
              onClick={() => setAuthMode("register")}
            >
              <UserPlus className="w-3 h-3" />
              注册
            </button>
          </div>
        )}
      </div>

      {/* Auth Sheet */}
      <Sheet
        open={authMode !== null && !showPrivateId}
        onOpenChange={(open) => {
          if (!open) {
            setAuthMode(null);
            setError("");
          }
        }}
      >
        <SheetContent side="bottom" className="bg-card border-t border-border">
          <SheetHeader>
            <SheetTitle className="text-foreground">
              {authMode === "register" ? "创建账户" : "登录"}
            </SheetTitle>
            <SheetDescription className="text-muted-foreground">
              {authMode === "register"
                ? "输入一个显示名称开始你的人生旅程"
                : "使用你的私有密钥登录"}
            </SheetDescription>
          </SheetHeader>

          <div className="space-y-4 mt-4">
            {authMode === "register" ? (
              <Input
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                placeholder="你的名字"
                className="bg-secondary border-border h-12 text-base"
                disabled={isLoading}
                onKeyDown={(e) => {
                  if (e.key === "Enter") handleRegister();
                }}
                autoFocus
              />
            ) : (
              <Input
                value={privateId}
                onChange={(e) => setPrivateId(e.target.value)}
                placeholder="私有密钥 (如: XXXX-XXXX-XXXX-...)"
                className="bg-secondary border-border h-12 text-base font-mono"
                disabled={isLoading}
                onKeyDown={(e) => {
                  if (e.key === "Enter") handleLogin();
                }}
                autoFocus
              />
            )}

            {error && (
              <p className="text-sm text-destructive">{error}</p>
            )}

            <Button
              className="w-full h-12 touch-target"
              disabled={
                isLoading ||
                (authMode === "register"
                  ? !displayName.trim()
                  : !privateId.trim())
              }
              onClick={
                authMode === "register" ? handleRegister : handleLogin
              }
            >
              {isLoading && (
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
              )}
              {authMode === "register" ? "创建账户" : "登录"}
            </Button>

            <button
              className="w-full text-center text-sm text-muted-foreground hover:text-foreground"
              onClick={() => {
                setAuthMode(authMode === "register" ? "login" : "register");
                setError("");
              }}
            >
              {authMode === "register"
                ? "已有账户？登录"
                : "没有账户？注册"}
            </button>
          </div>
        </SheetContent>
      </Sheet>

      {/* Private ID display after registration */}
      <Sheet
        open={!!showPrivateId}
        onOpenChange={(open) => {
          if (!open) {
            setShowPrivateId(null);
            setAuthMode(null);
          }
        }}
      >
        <SheetContent side="bottom" className="bg-card border-t border-border">
          <SheetHeader>
            <SheetTitle className="text-foreground">
              账户创建成功！
            </SheetTitle>
            <SheetDescription className="text-muted-foreground">
              请务必保存以下私有密钥，这是你唯一的登录凭证
            </SheetDescription>
          </SheetHeader>

          <div className="space-y-4 mt-4">
            <div className="bg-secondary rounded-lg p-4 font-mono text-sm text-primary break-all flex items-center gap-2">
              <span className="flex-1">{showPrivateId}</span>
              <Button
                size="icon"
                variant="ghost"
                className="flex-shrink-0"
                onClick={handleCopyPrivateId}
              >
                {copied ? (
                  <Check className="w-4 h-4 text-success" />
                ) : (
                  <Copy className="w-4 h-4" />
                )}
              </Button>
            </div>

            <p className="text-xs text-warning">
              ⚠ 此密钥仅显示一次，丢失后无法找回
            </p>

            <Button
              className="w-full h-12 touch-target"
              onClick={() => {
                setShowPrivateId(null);
                setAuthMode(null);
              }}
            >
              我已保存密钥，开始体验
            </Button>
          </div>
        </SheetContent>
      </Sheet>
    </div>
  );
}
