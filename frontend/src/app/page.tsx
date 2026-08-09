"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
  SheetClose,
} from "@/components/ui/sheet";
import {
  FeedbackNotice,
  FormField,
  PageTransition,
  Surface,
} from "@/components/story101";
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
  X,
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

  const authFieldId = authMode === "register" ? "display-name-input" : "private-id-input";
  const authErrorId = `${authFieldId}-server-error`;

  return (
    <PageTransition
      aria-label="story101 首页"
      className="mx-auto flex min-h-[100dvh] w-full max-w-3xl flex-col justify-center px-4 py-10 sm:px-6"
    >
      <header className="mb-7 text-center sm:mb-9">
        <h1 className="font-brand text-4xl font-semibold tracking-[-0.04em] text-[var(--text-primary)] sm:text-5xl">
          story101
        </h1>
        <p className="mt-2 text-sm tracking-[0.16em] text-[var(--text-secondary)]">
          人生草稿本
        </p>
      </header>

      <Surface variant="reading" className="w-full p-4 sm:p-6">
        <div className="grid gap-3">
          {hasActiveGame && (
            <Button
              size="touch"
              className="w-full text-base"
              onClick={() => router.push("/play")}
            >
              <Play className="size-5" />
              继续游戏
            </Button>
          )}

          <Button
            variant={hasActiveGame ? "narrative" : "default"}
            size="touch"
            className="w-full text-base"
            asChild={isAuthenticated}
            onClick={isAuthenticated ? undefined : () => setAuthMode("register")}
          >
            {isAuthenticated ? (
              <Link
                href="/create"
                role="button"
                aria-label="新游戏"
                onClick={resetCreation}
              >
                <Sparkles className="size-5" />
                新游戏
              </Link>
            ) : (
              <>
                <Sparkles className="size-5" />
                新游戏
              </>
            )}
          </Button>

          <div className="grid gap-3 border-t border-[var(--border-default)] pt-3 sm:grid-cols-2">
            <Button
              variant="narrative"
              size="touch"
              className="w-full text-base"
              onClick={() => {
                if (!isAuthenticated) {
                  setAuthMode("login");
                } else {
                  router.push("/saves");
                }
              }}
            >
              <FolderOpen className="size-5" />
              加载存档
            </Button>

            <Button
              variant="narrative"
              size="touch"
              className="w-full text-base"
              onClick={() => {
                if (!isAuthenticated) {
                  setAuthMode("login");
                } else {
                  router.push("/presets");
                }
              }}
            >
              <BookOpen className="size-5" />
              角色预设
            </Button>
          </div>
        </div>

        <div className="mt-4 border-t border-[var(--border-default)] pt-2 text-center">
          {isAuthenticated ? (
            <div className="flex flex-wrap items-center justify-center gap-1 text-sm text-[var(--text-secondary)]">
              <span className="px-2">欢迎回来，{user?.display_name || "旅行者"}</span>
              <Button variant="quiet" size="touch" onClick={logout}>
                登出
              </Button>
            </div>
          ) : (
            <div className="flex flex-wrap items-center justify-center gap-1">
              <Button variant="quiet" size="touch" onClick={() => setAuthMode("login")}>
                <LogIn className="size-4" />
                登录
              </Button>
              <Button variant="quiet" size="touch" onClick={() => setAuthMode("register")}>
                <UserPlus className="size-4" />
                注册
              </Button>
            </div>
          )}
        </div>
      </Surface>

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
        <SheetContent
          side="bottom"
          showCloseButton={false}
          className="border-0 bg-transparent p-0 shadow-none"
          overlayClassName="bg-black/60"
        >
          <Surface
            variant="overlay"
            className="relative mx-auto w-full max-w-2xl rounded-b-none border-b-0 px-4 pb-[calc(1rem+var(--safe-area-inset-bottom))] pt-4 sm:px-6"
          >
            <SheetClose asChild>
              <Button
                type="button"
                variant="quiet"
                size="icon-touch"
                className="absolute right-2 top-2"
                aria-label="关闭认证面板"
              >
                <X className="size-4" />
              </Button>
            </SheetClose>

            <SheetHeader className="p-0 pr-12 text-left">
              <SheetTitle className="text-[var(--text-primary)]">
                {authMode === "register" ? "创建账户" : "登录"}
              </SheetTitle>
              <SheetDescription className="text-[var(--text-secondary)]">
                {authMode === "register"
                  ? "输入一个显示名称开始你的人生旅程"
                  : "使用你的私有密钥登录"}
              </SheetDescription>
            </SheetHeader>

            <form
              className="mt-5 grid gap-4"
              aria-label={authMode === "register" ? "创建账户" : "登录账户"}
              aria-busy={isLoading}
              onSubmit={(event) => {
                event.preventDefault();
                if (authMode === "register") {
                  void handleRegister();
                } else {
                  void handleLogin();
                }
              }}
            >
              {authMode === "register" ? (
                <FormField
                  id="display-name-input"
                  label="显示名称"
                  description="将在首页这样称呼你"
                  required
                >
                  {({ describedBy, required }) => (
                    <Input
                      id="display-name-input"
                      name="displayName"
                      value={displayName}
                      onChange={(event) => setDisplayName(event.target.value)}
                      placeholder="你的名字"
                      surface="filled"
                      controlSize="touch"
                      className="text-base"
                      disabled={isLoading}
                      autoFocus
                      required={required}
                      aria-required={required}
                      aria-invalid={Boolean(error)}
                      aria-describedby={[describedBy, error ? authErrorId : undefined].filter(Boolean).join(" ") || undefined}
                    />
                  )}
                </FormField>
              ) : (
                <FormField
                  id="private-id-input"
                  label="私有密钥"
                  description="使用注册时保存的唯一密钥"
                  required
                >
                  {({ describedBy, required }) => (
                    <Input
                      id="private-id-input"
                      name="privateId"
                      value={privateId}
                      onChange={(event) => setPrivateId(event.target.value)}
                      placeholder="私有密钥 (如: XXXX-XXXX-XXXX-...)"
                      surface="filled"
                      controlSize="touch"
                      className="font-mono text-base"
                      disabled={isLoading}
                      autoFocus
                      required={required}
                      aria-required={required}
                      aria-label="私有密钥"
                      aria-invalid={Boolean(error)}
                      aria-describedby={[describedBy, error ? authErrorId : undefined].filter(Boolean).join(" ") || undefined}
                      data-testid="private-id-input"
                    />
                  )}
                </FormField>
              )}

              {error && (
                <div id={authErrorId}>
                  <FeedbackNotice
                    tone="danger"
                    title={authMode === "register" ? "无法创建账户" : "无法登录"}
                  >
                    {error}
                  </FeedbackNotice>
                </div>
              )}

              <Button
                type="submit"
                size="touch"
                className="w-full text-base"
                disabled={
                  isLoading ||
                  (authMode === "register"
                    ? !displayName.trim()
                    : !privateId.trim())
                }
              >
                {isLoading && <Loader2 className="size-4 animate-spin" aria-hidden="true" />}
                {authMode === "register" ? "创建账户" : "登录"}
              </Button>

              <Button
                type="button"
                variant="quiet"
                size="touch"
                className="w-full"
                onClick={() => {
                  setAuthMode(authMode === "register" ? "login" : "register");
                  setError("");
                }}
              >
                {authMode === "register"
                  ? "已有账户？登录"
                  : "没有账户？注册"}
              </Button>
            </form>
          </Surface>
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
        <SheetContent
          side="bottom"
          showCloseButton={false}
          className="border-0 bg-transparent p-0 shadow-none"
          overlayClassName="bg-black/60"
        >
          <Surface
            variant="overlay"
            className="relative mx-auto w-full max-w-2xl rounded-b-none border-b-0 px-4 pb-[calc(1rem+var(--safe-area-inset-bottom))] pt-4 sm:px-6"
          >
            <SheetClose asChild>
              <Button
                type="button"
                variant="quiet"
                size="icon-touch"
                className="absolute right-2 top-2"
                aria-label="关闭私有密钥面板"
              >
                <X className="size-4" />
              </Button>
            </SheetClose>

            <SheetHeader className="p-0 pr-12 text-left">
              <SheetTitle className="text-[var(--text-primary)]">
                账户创建成功！
              </SheetTitle>
              <SheetDescription className="text-[var(--text-secondary)]">
                请务必保存以下私有密钥，这是你唯一的登录凭证
              </SheetDescription>
            </SheetHeader>

            <div className="mt-5 grid gap-4">
              <Surface
                variant="subtle"
                className="flex items-center gap-2 p-3 font-mono text-sm text-[var(--text-primary)]"
              >
                <code className="min-w-0 flex-1 break-all">{showPrivateId}</code>
                <Button
                  type="button"
                  size="icon-touch"
                  variant="quiet"
                  className="shrink-0"
                  onClick={handleCopyPrivateId}
                  aria-label={copied ? "已复制私有密钥" : "复制私有密钥"}
                >
                  {copied ? (
                    <Check className="size-4 text-[var(--success-foreground)]" />
                  ) : (
                    <Copy className="size-4" />
                  )}
                </Button>
              </Surface>

              <FeedbackNotice
                tone={copied ? "success" : "warning"}
                title={copied ? "私有密钥已复制" : "仅显示一次"}
              >
                {copied
                  ? "请继续把密钥保存在只有你能访问的地方。"
                  : "此密钥仅显示一次，丢失后无法找回"}
              </FeedbackNotice>

              <Button
                size="touch"
                className="w-full text-base"
                onClick={() => {
                  setShowPrivateId(null);
                  setAuthMode(null);
                }}
              >
                我已保存密钥，开始体验
              </Button>
            </div>
          </Surface>
        </SheetContent>
      </Sheet>
    </PageTransition>
  );
}
