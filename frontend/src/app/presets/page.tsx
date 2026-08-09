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
import type { PresetInfo } from "@/lib/types";
import { useGameStore } from "@/stores/useGameStore";

function getPresetName(preset: PresetInfo): string {
  return preset.preset_name?.trim() || "未命名预设";
}

type PageFeedback = {
  tone: "success" | "danger";
  message: string;
};

export default function PresetsPage() {
  const router = useRouter();
  const { presets, fetchPresets, deletePreset, loadPreset } = useGameStore();

  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<PresetInfo | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [pageFeedback, setPageFeedback] = useState<PageFeedback | null>(null);

  const loadPresets = useCallback(
    async (isCancelled: () => boolean = () => false) => {
      setLoadError(null);
      setPageFeedback(null);
      setIsLoading(true);
      try {
        await fetchPresets();
      } catch (err) {
        if (isCancelled()) return;
        console.error("Failed to fetch presets:", err);
        setLoadError("请检查网络后重试。");
      } finally {
        if (!isCancelled()) setIsLoading(false);
      }
    },
    [fetchPresets],
  );

  useEffect(() => {
    let cancelled = false;
    void loadPresets(() => cancelled);
    return () => {
      cancelled = true;
    };
  }, [loadPresets]);

  const handleLoad = (presetId: number) => {
    const preset = presets.find((candidate) => candidate.preset_id === presetId);
    if (preset) {
      loadPreset(preset);
      router.push("/create");
    }
  };

  const handleDelete = async () => {
    if (!deleteTarget || isDeleting) return;
    const target = deleteTarget;
    const targetName = getPresetName(target);
    setIsDeleting(true);
    setDeleteError(null);
    try {
      await deletePreset(target.preset_id);
      setDeleteTarget(null);
      setPageFeedback({
        tone: "success",
        message: `已删除角色预设“${targetName}”。`,
      });
    } catch (err) {
      console.error("Delete preset failed:", err);
      setDeleteError(`未能删除角色预设“${targetName}”，请重试。`);
    } finally {
      setIsDeleting(false);
    }
  };

  const openDeleteDialog = (preset: PresetInfo) => {
    setDeleteError(null);
    setPageFeedback(null);
    setDeleteTarget(preset);
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
            角色预设
          </h1>
          <p className="mt-2 leading-7 text-[var(--text-secondary)]">
            保存过的人物设定会出现在这里。
          </p>
        </div>

        {pageFeedback ? (
          <FeedbackNotice tone={pageFeedback.tone} className="mb-4">
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
              正在整理角色预设
            </div>
          ) : loadError ? (
            <div className="p-4 sm:p-6">
              <FeedbackNotice
                tone="danger"
                title="未能载入角色预设"
                action={
                  <Button
                    type="button"
                    variant="narrative"
                    size="touch"
                    aria-label="重试载入角色预设"
                    onClick={() => void loadPresets()}
                  >
                    重试
                  </Button>
                }
              >
                {loadError}
              </FeedbackNotice>
            </div>
          ) : presets.length === 0 ? (
            <div className="px-5 py-10 sm:px-8 sm:py-14">
              <h2 className="font-serif text-2xl text-[var(--text-primary)]">
                还没有角色预设
              </h2>
              <p className="mt-2 max-w-lg leading-7 text-[var(--text-secondary)]">
                创建角色后，可以把想再次使用的设定保存在这里。
              </p>
              <Button
                type="button"
                variant="default"
                size="touch"
                className="mt-6"
                onClick={() => router.push("/create")}
              >
                创建角色
              </Button>
            </div>
          ) : (
            <ul
              aria-label="角色预设列表"
              className="divide-y divide-[var(--border-default)]"
            >
              {presets.map((preset) => {
                const presetName = getPresetName(preset);
                return (
                  <li
                    key={preset.preset_id}
                    data-slot="management-row"
                    className="min-w-0"
                  >
                    <div className="grid min-w-0 gap-4 p-4 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center sm:p-5">
                      <div className="min-w-0">
                        <h2 className="break-words font-serif text-xl leading-8 text-[var(--text-primary)]">
                          {presetName}
                        </h2>
                        <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-[var(--text-secondary)]">
                          <span className="break-words">{preset.player_name}</span>
                          {preset.created_at ? (
                            <span>
                              {new Date(preset.created_at).toLocaleDateString()}
                            </span>
                          ) : null}
                        </div>
                        {preset.life_vision ? (
                          <p className="mt-2 break-words text-sm leading-6 text-[var(--text-subtle)]">
                            {preset.life_vision}
                          </p>
                        ) : null}
                      </div>

                      <Button
                        type="button"
                        variant="default"
                        size="touch"
                        className="w-full sm:w-auto"
                        aria-label={`使用角色预设“${presetName}”`}
                        onClick={() => handleLoad(preset.preset_id)}
                      >
                        <Play className="h-4 w-4" />
                        使用
                      </Button>
                    </div>

                    <div
                      data-slot="danger-row"
                      className="flex min-w-0 flex-col gap-2 border-t border-[var(--border-default)] bg-[var(--surface-subtle)] px-4 py-3 sm:flex-row sm:items-center sm:justify-between sm:px-5"
                    >
                      <span className="text-xs leading-5 text-[var(--text-subtle)]">
                        不再保留这份人物设定
                      </span>
                      <Button
                        type="button"
                        variant="quiet"
                        size="touch"
                        className="w-full text-[var(--danger-foreground)] hover:bg-[var(--danger-subtle)] sm:w-auto"
                        aria-label={`删除角色预设“${presetName}”`}
                        onClick={() => openDeleteDialog(preset)}
                      >
                        <Trash2 className="h-4 w-4" />
                        删除预设
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
        itemKind="角色预设"
        itemName={deleteTarget ? getPresetName(deleteTarget) : ""}
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
