"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Copy, ExternalLink } from "lucide-react";
import { PlazaHeader } from "@/components/plaza/PlazaHeader";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import type { OwnedPublicStory } from "@/lib/types";
import { copyToClipboard } from "@/lib/utils";
import { useUserStore } from "@/stores/useUserStore";

export default function ManagePlazaPage() {
  const setUser = useUserStore((state) => state.setUser);
  const clearAuth = useUserStore((state) => state.clearAuth);
  const [authStatus, setAuthStatus] = useState<"checking" | "authenticated" | "anonymous" | "error">("checking");
  const [authRetry, setAuthRetry] = useState(0);
  const [stories, setStories] = useState<OwnedPublicStory[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);
  const [busyId, setBusyId] = useState<number | null>(null);
  const [feedback, setFeedback] = useState<{ storyId: number; message: string; error: boolean } | null>(null);
  const [reload, setReload] = useState(0);

  useEffect(() => {
    let cancelled = false;
    api.auth.me().then((user) => {
      if (cancelled) return;
      setUser(user);
      setAuthStatus("authenticated");
    }).catch((error: unknown) => {
      if (cancelled) return;
      if ((error as { status?: number })?.status === 401) {
        clearAuth();
        setAuthStatus("anonymous");
      } else {
        setAuthStatus("error");
      }
    });
    return () => { cancelled = true; };
  }, [authRetry, clearAuth, setUser]);

  useEffect(() => {
    if (authStatus !== "authenticated") return;
    let cancelled = false;
    api.plaza.mine().then((result) => {
      if (cancelled) return;
      setStories(result);
      setLoadError(false);
    }).catch(() => {
      if (!cancelled) setLoadError(true);
    }).finally(() => {
      if (!cancelled) setLoading(false);
    });
    return () => { cancelled = true; };
  }, [authStatus, reload]);

  async function toggle(story: OwnedPublicStory) {
    if (busyId !== null) return;
    setBusyId(story.game_id);
    setFeedback(null);
    try {
      const result = await api.plaza.setPublication(story.game_id, !story.enabled);
      setStories((current) => current.map((item) => item.game_id === story.game_id ? result : item));
      setFeedback({
        storyId: story.game_id,
        message: result.enabled ? `“${story.title}”已分享到故事广场，今后完成的章节也会自动出现。` : `“${story.title}”已关闭分享，原链接现在无法阅读。`,
        error: false,
      });
    } catch {
      setFeedback({ storyId: story.game_id, message: "更改分享状态失败，请重试。", error: true });
    } finally {
      setBusyId(null);
    }
  }

  async function copyLink(storyId: number, publicId: string) {
    const success = await copyToClipboard(`${window.location.origin}/plaza/${publicId}`);
    setFeedback({ storyId, message: success ? "公开链接已复制。" : "复制失败，请重试。", error: !success });
  }

  return (
    <div className="min-h-screen bg-[var(--surface-canvas)] text-[var(--text-primary)]">
      <PlazaHeader manage />
      <main className="mx-auto w-full max-w-4xl px-5 pb-24 pt-12 sm:px-8 sm:pt-20">
        <div className="border-b border-[var(--border-default)] pb-9">
          <h1 className="font-serif text-4xl sm:text-5xl">分享我的故事</h1>
          <p className="mt-5 max-w-2xl leading-8 text-[var(--text-supporting)]">选择一个故事，点“分享到故事广场”即可公开全部已完成章节；新章节完成后会自动更新。你可以随时关闭分享，公开链接也会立即失效。</p>
        </div>
        {authStatus === "checking" ? <p role="status" className="py-16 text-center text-[var(--text-secondary)]">正在确认登录…</p> : authStatus === "error" ? (
          <div role="alert" className="mt-8 border border-[var(--border-default)] bg-[var(--surface-reading)] p-8">
            <p>无法确认登录状态，请稍后重试。</p>
            <Button type="button" variant="narrative" className="mt-5" onClick={() => { setAuthStatus("checking"); setAuthRetry((value) => value + 1); }}>重试确认登录</Button>
          </div>
        ) : authStatus === "anonymous" ? (
          <div className="mt-8 border border-[var(--border-default)] bg-[var(--surface-reading)] p-8">
            <h2 className="font-serif text-2xl">登录后管理分享</h2>
            <p className="mt-3 text-[var(--text-secondary)]">阅读广场故事无需登录。要公开或关闭自己的故事，请先登录。</p>
            <Link href="/" className="mt-6 inline-block text-sm underline underline-offset-4">返回首页登录</Link>
          </div>
        ) : loading ? <p role="status" className="py-16 text-center text-[var(--text-secondary)]">正在整理故事…</p> : loadError ? (
          <div role="alert" className="mt-8 border border-[var(--border-default)] bg-[var(--surface-reading)] p-8">
            <p>无法载入你的故事。请登录或稍后重试。</p>
            <div className="mt-5 flex gap-3"><Button type="button" variant="narrative" onClick={() => { setLoading(true); setReload((value) => value + 1); }}>重试</Button><Link href="/">返回首页</Link></div>
          </div>
        ) : stories.length === 0 ? (
          <div className="mt-8 border border-[var(--border-default)] bg-[var(--surface-reading)] p-8">
            <h2 className="font-serif text-2xl">还没有可以管理的故事</h2>
            <p className="mt-3 text-[var(--text-secondary)]">创建故事并完成一章后，就能在这里选择是否公开。</p>
            <Link href="/" className="mt-6 inline-block text-sm underline underline-offset-4">返回首页</Link>
          </div>
        ) : (
          <ul className="mt-8 space-y-3">
            {stories.map((story) => (
              <li key={story.game_id} className={`border bg-[var(--surface-reading)] p-5 sm:p-7 ${story.enabled ? "border-[var(--success-border)]" : "border-[var(--border-default)]"}`}>
                <div className="flex flex-col gap-5 sm:flex-row sm:items-start sm:justify-between">
                  <div className="min-w-0 flex-1">
                    <h2 className="break-words font-serif text-2xl">{story.title}</h2>
                    <p className="mt-2 text-sm text-[var(--text-primary)]">{story.chapter_count} 章已完成</p>
                  </div>
                  <div className="flex shrink-0 flex-col items-start gap-3 sm:items-end">
                    <button type="button" disabled={busyId !== null || (!story.can_publish && !story.enabled)} onClick={() => void toggle(story)} className={`inline-flex min-h-11 items-center justify-center rounded-[var(--radius-control)] border px-5 py-2.5 text-sm font-medium transition-colors focus-visible:outline-2 focus-visible:outline-offset-3 focus-visible:outline-[var(--text-primary)] disabled:cursor-not-allowed ${story.enabled ? "border-[var(--danger-border)] bg-[var(--danger-subtle)] text-[var(--danger-foreground)] hover:bg-[var(--danger-border)] hover:text-[var(--text-primary)]" : story.can_publish ? "border-[var(--text-primary)] bg-[var(--text-primary)] text-[var(--surface-canvas)] hover:bg-[var(--text-secondary)]" : "border-[var(--border-strong)] bg-[var(--surface-raised)] text-[var(--text-primary)]"}`}>
                      {busyId === story.game_id ? (story.enabled ? "正在关闭分享…" : "正在分享…") : story.enabled ? "关闭分享" : story.can_publish ? "分享到故事广场" : "完成第一章后可分享"}
                    </button>
                    <span className={`rounded-[var(--radius-control)] border px-3 py-1 text-xs font-medium ${story.enabled ? "border-[var(--success-border)] bg-[var(--success-subtle)] text-[var(--success-foreground)]" : "border-[var(--border-strong)] bg-[var(--surface-raised)] text-[var(--text-primary)]"}`}>
                      {story.enabled ? "已分享到故事广场" : "仅自己可见"}
                    </span>
                  </div>
                </div>
                <p className="mt-5 border-t border-[var(--border-default)] pt-4 text-sm leading-6 text-[var(--text-supporting)]">
                  {story.enabled ? "已完成章节全部公开，后续完成的章节会自动更新。" : story.can_publish ? "分享后，整个故事的已完成章节都会在广场公开。" : "完成第一章后，就能把整个故事分享到广场。"}
                </p>
                {story.enabled && story.public_id ? (
                  <div className="mt-4 flex flex-wrap gap-3">
                    <Link href={`/plaza/${story.public_id}`} className="inline-flex min-h-11 items-center gap-2 rounded-[var(--radius-control)] border border-[var(--border-interactive)] px-4 text-sm hover:bg-[var(--surface-raised)]" aria-label="查看公开故事"><ExternalLink className="size-4" /> 查看公开故事</Link>
                    <Button type="button" variant="narrative" size="touch" onClick={() => void copyLink(story.game_id, story.public_id!)}><Copy className="size-4" /> 复制链接</Button>
                  </div>
                ) : null}
                {feedback?.storyId === story.game_id ? <p role={feedback.error ? "alert" : "status"} className={`mt-4 border px-4 py-3 text-sm ${feedback.error ? "border-[var(--danger-border)] bg-[var(--danger-subtle)] text-[var(--danger-foreground)]" : "border-[var(--success-border)] bg-[var(--success-subtle)] text-[var(--text-primary)]"}`}>{feedback.message}</p> : null}
              </li>
            ))}
          </ul>
        )}
      </main>
    </div>
  );
}
