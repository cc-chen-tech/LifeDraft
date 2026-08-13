"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowLeft, Play, Trash2 } from "lucide-react";

import {
  DestructiveConfirmDialog,
  FeedbackNotice,
  Surface,
} from "@/components/story101";
import { Button } from "@/components/ui/button";
import { useHydration } from "@/hooks/useHydration";
import type { GameListItem } from "@/lib/types";
import { useGameStore } from "@/stores/useGameStore";
import { hasAuthSessionHint, useUserStore } from "@/stores/useUserStore";

const SAVE_DISPLAY_TIME_ZONE = "Asia/Shanghai";

function getSaveDate(dateStr: string): Date | null {
  const date = new Date(dateStr);
  return Number.isNaN(date.getTime()) ? null : date;
}

function formatSaveDate(dateStr: string): string {
  const date = getSaveDate(dateStr);
  if (!date) return "";
  return new Intl.DateTimeFormat("zh-CN", {
    timeZone: SAVE_DISPLAY_TIME_ZONE,
    year: "numeric",
    month: "numeric",
    day: "numeric",
  }).format(date);
}

function formatChineseTime(dateStr: string | null): string {
  if (!dateStr) return "";
  const date = getSaveDate(dateStr);
  if (!date) return "";
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone: SAVE_DISPLAY_TIME_ZONE,
    hour: "numeric",
    minute: "2-digit",
    hourCycle: "h23",
  }).formatToParts(date);
  const hour = Number(parts.find((part) => part.type === "hour")?.value);
  const minute = Number(parts.find((part) => part.type === "minute")?.value);

  let period = "";
  if (hour >= 0 && hour < 6) period = "凌晨";
  else if (hour >= 6 && hour < 12) period = "上午";
  else if (hour >= 12 && hour < 18) period = "下午";
  else period = "晚上";

  const displayHour = hour > 12 ? hour - 12 : hour;
  return `${period}${displayHour}:${minute.toString().padStart(2, "0")}`;
}

function getSaveName(save: GameListItem): string {
  return save.player_name?.trim() || "未知角色";
}

type PageFeedback = {
  tone: "success" | "danger";
  message: string;
};

export default function SavesPage() {
  const router = useRouter();
  const {
    savedGames,
    fetchSavedGames,
    deleteGame,
    loadGameState,
    setGameSession,
    resetCreation,
  } = useGameStore();
  const { isAuthenticated, user, fetchMe } = useUserStore();
  const currentUserId = user?.user_id ?? null;
  const hydrated = useHydration();

  const [isLoading, setIsLoading] = useState(true);
  const [authChecked, setAuthChecked] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [loadedUserId, setLoadedUserId] = useState<number | null>(null);
  const [loadingGameId, setLoadingGameId] = useState<number | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<GameListItem | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [pageFeedback, setPageFeedback] = useState<PageFeedback | null>(null);

  const visibleSavedGames =
    isAuthenticated && loadedUserId === currentUserId ? savedGames : [];

  const loadSavedGames = useCallback(
    async (
      userId: number | null,
      isCancelled: () => boolean = () => false,
    ) => {
      setLoadError(null);
      setPageFeedback(null);
      setIsLoading(true);

      try {
        await fetchSavedGames();
        if (isCancelled()) return;
        setLoadedUserId(userId);
        setIsLoading(false);
      } catch (err: unknown) {
        if (isCancelled()) return;
        const error = err as { status?: number; name?: string };
        if (error.status !== 401 && error.name !== "AbortError") {
          console.error("Failed to fetch saved games:", err);
          setLoadError("请检查网络后重试。");
          setIsLoading(false);
        }
      }
    },
    [fetchSavedGames],
  );

  useEffect(() => {
    if (!hydrated) return;

    if (isAuthenticated) {
      setAuthChecked(true);
      return;
    }

    if (!hasAuthSessionHint()) {
      setAuthChecked(true);
      return;
    }

    let cancelled = false;
    fetchMe().finally(() => {
      if (!cancelled) setAuthChecked(true);
    });
    return () => {
      cancelled = true;
    };
  }, [hydrated, isAuthenticated, fetchMe]);

  useEffect(() => {
    let cancelled = false;

    if (!authChecked) {
      return () => {
        cancelled = true;
      };
    }

    if (!isAuthenticated) {
      setLoadedUserId(null);
      setLoadError(null);
      setIsLoading(false);
      return () => {
        cancelled = true;
      };
    }

    setLoadedUserId(null);
    void loadSavedGames(currentUserId, () => cancelled);
    return () => {
      cancelled = true;
    };
  }, [authChecked, isAuthenticated, currentUserId, loadSavedGames]);

  const handleLoad = async (save: GameListItem) => {
    const saveName = getSaveName(save);
    setLoadingGameId(save.game_id);
    setPageFeedback(null);
    try {
      await loadGameState(save.game_id);
      setGameSession(save.game_id, `session_${save.game_id}`);
      router.push("/play");
    } catch (err) {
      console.error("Load game failed:", err);
      setPageFeedback({
        tone: "danger",
        message: `无法打开存档“${saveName}”，请重试。`,
      });
    } finally {
      setLoadingGameId(null);
    }
  };

  const handleDelete = async () => {
    if (!deleteTarget || isDeleting) return;
    const target = deleteTarget;
    const targetName = getSaveName(target);
    setIsDeleting(true);
    setDeleteError(null);
    try {
      await deleteGame(target.game_id);
      setDeleteTarget(null);
      setPageFeedback({
        tone: "success",
        message: `已删除存档“${targetName}”。`,
      });
    } catch (err) {
      console.error("Delete failed:", err);
      setDeleteError(`未能删除存档“${targetName}”，请重试。`);
    } finally {
      setIsDeleting(false);
    }
  };

  const openDeleteDialog = (save: GameListItem) => {
    setDeleteError(null);
    setPageFeedback(null);
    setDeleteTarget(save);
  };

  return (
    <div className="min-h-screen bg-[var(--surface-canvas)] text-[var(--text-primary)]">
      <header className="border-b border-[var(--border-default)] bg-[var(--surface-canvas)]">
        <div className="mx-auto flex min-h-16 max-w-4xl items-center justify-between gap-4 px-4 sm:px-6">
          <Button
            type="button"
            variant="quiet"
            size="touch"
            aria-label="返回首页"
            onClick={() => router.push("/")}
          >
            <ArrowLeft className="h-4 w-4" />
            返回
          </Button>
          <span className="font-brand text-sm font-semibold tracking-[-0.03em] text-[var(--text-secondary)]">
            story101
          </span>
        </div>
      </header>

      <main className="mx-auto w-full max-w-4xl px-4 py-8 sm:px-6 sm:py-12">
        <div className="mb-6 max-w-2xl">
          <h1 className="font-serif text-3xl leading-tight text-[var(--text-primary)] sm:text-4xl">
            存档
          </h1>
          <p className="mt-2 leading-7 text-[var(--text-secondary)]">
            从上次停下的地方，继续这一页人生。
          </p>
        </div>

        {pageFeedback ? (
          <FeedbackNotice
            tone={pageFeedback.tone}
            className="mb-4"
          >
            {pageFeedback.message}
          </FeedbackNotice>
        ) : null}

        <Surface variant="reading" className="overflow-hidden">
          {isLoading ? (
            <div
              role="status"
              aria-live="polite"
              className="px-5 py-12 text-center text-sm text-[var(--text-secondary)]"
            >
              正在整理存档
            </div>
          ) : loadError ? (
            <div className="p-4 sm:p-6">
              <FeedbackNotice
                tone="danger"
                title="未能载入存档"
                action={
                  <Button
                    type="button"
                    variant="narrative"
                    size="touch"
                    aria-label="重试载入存档"
                    onClick={() => {
                      if (!isAuthenticated) return;
                      void loadSavedGames(currentUserId);
                    }}
                  >
                    重试
                  </Button>
                }
              >
                {loadError}
              </FeedbackNotice>
            </div>
          ) : visibleSavedGames.length === 0 ? (
            <div className="px-5 py-10 sm:px-8 sm:py-14">
              <h2 className="font-serif text-2xl text-[var(--text-primary)]">
                还没有存档
              </h2>
              <p className="mt-2 max-w-lg leading-7 text-[var(--text-secondary)]">
                开始一段人生后，可以从这里继续。
              </p>
              <Button
                type="button"
                variant="default"
                size="touch"
                className="mt-6"
                onClick={() => {
                  resetCreation();
                  router.push("/create");
                }}
              >
                开始新游戏
              </Button>
            </div>
          ) : (
            <ul aria-label="存档列表" className="divide-y divide-[var(--border-default)]">
              {visibleSavedGames
                .sort((a, b) => {
                  const timeA = a.updated_at
                    ? new Date(a.updated_at).getTime()
                    : 0;
                  const timeB = b.updated_at
                    ? new Date(b.updated_at).getTime()
                    : 0;
                  return timeB - timeA;
                })
                .map((save) => {
                  const saveName = getSaveName(save);
                  const isOpening = loadingGameId === save.game_id;
                  return (
                    <li
                      key={save.game_id}
                      data-slot="management-row"
                      className="min-w-0"
                    >
                      <div className="grid min-w-0 gap-4 p-4 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center sm:p-5">
                        <div className="min-w-0">
                          <h2 className="break-words font-serif text-xl leading-8 text-[var(--text-primary)]">
                            {saveName}
                          </h2>
                          <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-[var(--text-secondary)]">
                            <span>
                              {save.age}岁 · 第{(save.week ?? 0) + 1}周
                            </span>
                            {(save.week ?? 0) === 0 ? (
                              <span className="text-[var(--warning-foreground)]">
                                新角色
                              </span>
                            ) : null}
                            {save.updated_at ? (
                              <span>
                                {formatSaveDate(save.updated_at)} {formatChineseTime(save.updated_at)}
                              </span>
                            ) : null}
                          </div>
                        </div>

                        <Button
                          type="button"
                          variant="default"
                          size="touch"
                          className="w-full sm:w-auto"
                          aria-busy={isOpening}
                          aria-label={
                            isOpening
                              ? `正在打开“${saveName}”的人生`
                              : `继续“${saveName}”的人生`
                          }
                          disabled={isOpening}
                          onClick={() => void handleLoad(save)}
                        >
                          <Play className="h-4 w-4" />
                          {isOpening ? "正在打开" : "继续"}
                        </Button>
                      </div>

                      <div
                        data-slot="danger-row"
                        className="flex min-w-0 flex-col gap-2 border-t border-[var(--border-default)] bg-[var(--surface-subtle)] px-4 py-3 sm:flex-row sm:items-center sm:justify-between sm:px-5"
                      >
                        <span className="text-xs leading-5 text-[var(--text-subtle)]">
                          不再保留这段人生
                        </span>
                        <Button
                          type="button"
                          variant="quiet"
                          size="touch"
                          className="w-full text-[var(--danger-foreground)] hover:bg-[var(--danger-subtle)] sm:w-auto"
                          aria-label={`删除存档“${saveName}”（存档 ${save.game_id}）`}
                          onClick={() => openDeleteDialog(save)}
                        >
                          <Trash2 className="h-4 w-4" />
                          删除存档
                        </Button>
                      </div>
                    </li>
                  );
                })}
            </ul>
          )}
        </Surface>
      </main>

      <DestructiveConfirmDialog
        open={deleteTarget !== null}
        itemKind="存档"
        itemName={deleteTarget ? getSaveName(deleteTarget) : ""}
        busy={isDeleting}
        error={deleteError}
        onOpenChange={(open) => {
          if (!open) {
            setDeleteTarget(null);
            setDeleteError(null);
          }
        }}
        onConfirm={() => void handleDelete()}
      />
    </div>
  );
}
