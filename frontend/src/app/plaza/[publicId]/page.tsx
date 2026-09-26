"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { ArrowLeft, ArrowRight } from "lucide-react";
import { PlazaHeader } from "@/components/plaza/PlazaHeader";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import type { PublicStory } from "@/lib/types";

export default function PublicStoryPage() {
  const { publicId } = useParams<{ publicId: string }>();
  const [story, setStory] = useState<PublicStory | null>(null);
  const [chapterIndex, setChapterIndex] = useState(0);
  const [loading, setLoading] = useState(true);
  const [unavailable, setUnavailable] = useState(false);
  const [reload, setReload] = useState(0);

  useEffect(() => {
    let cancelled = false;
    api.plaza.get(publicId).then((result) => {
      if (cancelled) return;
      setStory(result);
      setChapterIndex(0);
      setUnavailable(false);
    }).catch(() => {
      if (!cancelled) setUnavailable(true);
    }).finally(() => {
      if (!cancelled) setLoading(false);
    });
    return () => { cancelled = true; };
  }, [publicId, reload]);

  const chapter = story?.chapters[chapterIndex];
  return (
    <div className="min-h-screen bg-[var(--surface-canvas)] text-[var(--text-primary)]">
      <PlazaHeader />
      <main className="mx-auto w-full max-w-6xl px-5 pb-24 pt-8 sm:px-8 sm:pt-12">
        <Link href="/plaza" className="inline-flex items-center gap-2 text-sm text-[var(--text-secondary)] hover:text-[var(--text-primary)]"><ArrowLeft className="size-4" /> 返回故事广场</Link>
        {loading ? <p role="status" className="py-20 text-center text-[var(--text-secondary)]">正在翻开故事…</p> : unavailable || !story || !chapter ? (
          <section className="mx-auto max-w-xl py-20 text-center">
            <h1 className="font-serif text-3xl">这个故事暂时无法阅读</h1>
            <p className="mt-4 leading-7 text-[var(--text-secondary)]">作者可能已关闭公开，或链接已失效。</p>
            <Button type="button" variant="narrative" className="mt-8" onClick={() => { setLoading(true); setReload((value) => value + 1); }}>重试</Button>
          </section>
        ) : (
          <>
            <div className="mt-10 border-b border-[var(--border-default)] pb-10 sm:mt-14">
              <h1 className="font-serif text-4xl leading-tight sm:text-5xl">{story.title}</h1>
              <p className="mt-4 text-sm text-[var(--text-secondary)]">{story.author_name} · {story.chapter_count} 章</p>
            </div>
            <div className="grid gap-10 pt-9 lg:grid-cols-[220px_minmax(0,1fr)] lg:gap-16">
              <aside aria-label="章节目录" className="lg:sticky lg:top-8 lg:self-start">
                <p className="mb-3 text-sm text-[var(--text-secondary)]">章节目录</p>
                <ol className="flex gap-2 overflow-x-auto pb-2 lg:block lg:space-y-1 lg:overflow-visible">
                  {story.chapters.map((item, index) => (
                    <li key={item.number} className="shrink-0">
                      <button type="button" onClick={() => setChapterIndex(index)} aria-current={index === chapterIndex ? "true" : undefined} className={`min-h-11 min-w-20 border-l-2 px-3 py-2 text-left text-sm focus-visible:outline-2 focus-visible:outline-[var(--text-primary)] lg:w-full ${index === chapterIndex ? "border-[var(--text-primary)] bg-[var(--surface-raised)] text-[var(--text-primary)]" : "border-transparent text-[var(--text-secondary)] hover:bg-[var(--surface-raised)]"}`}>
                        第 {item.number} 章
                      </button>
                    </li>
                  ))}
                </ol>
              </aside>
              <article className="min-w-0 max-w-3xl">
                <header className="mb-9 border-b border-[var(--border-default)] pb-6">
                  <span className="text-sm text-[var(--text-secondary)]">第 {chapter.number} 章{chapter.date ? ` · ${chapter.date}` : ""}</span>
                </header>
                <div className="plaza-prose break-words font-serif text-[1.1rem] leading-[2.1] text-[var(--text-primary)] sm:text-[1.18rem]">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>{chapter.text}</ReactMarkdown>
                </div>
                <nav aria-label="章节翻页" className="mt-14 flex items-center justify-between gap-4 border-t border-[var(--border-default)] pt-6">
                  <Button type="button" variant="quiet" size="touch" disabled={chapterIndex === 0} onClick={() => setChapterIndex((value) => value - 1)}><ArrowLeft className="size-4" /> 上一章</Button>
                  <span className="text-xs text-[var(--text-secondary)]">{chapterIndex + 1} / {story.chapter_count}</span>
                  <Button type="button" variant="narrative" size="touch" disabled={chapterIndex >= story.chapters.length - 1} onClick={() => setChapterIndex((value) => value + 1)}>下一章 <ArrowRight className="size-4" /></Button>
                </nav>
              </article>
            </div>
          </>
        )}
      </main>
    </div>
  );
}
