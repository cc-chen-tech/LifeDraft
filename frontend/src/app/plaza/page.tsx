"use client";

import { useEffect, useState, type FormEvent } from "react";
import Link from "next/link";
import { ArrowRight, Search } from "lucide-react";
import { PlazaHeader } from "@/components/plaza/PlazaHeader";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import type { PublicStoryCard } from "@/lib/types";

export default function PlazaPage() {
  const [input, setInput] = useState("");
  const [query, setQuery] = useState("");
  const [items, setItems] = useState<PublicStoryCard[]>([]);
  const [hasMore, setHasMore] = useState(false);
  const [nextOffset, setNextOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState(false);
  const [reload, setReload] = useState(0);

  useEffect(() => {
    let cancelled = false;
    api.plaza.list(query).then((result) => {
      if (cancelled) return;
      setItems(result.items);
      setHasMore(result.has_more);
      setNextOffset(result.next_offset);
      setError(false);
    }).catch(() => {
      if (!cancelled) setError(true);
    }).finally(() => {
      if (!cancelled) setLoading(false);
    });
    return () => { cancelled = true; };
  }, [query, reload]);

  function search(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const next = input.trim();
    setLoading(true);
    setQuery(next);
    if (next === query) setReload((value) => value + 1);
  }

  async function loadMore() {
    if (loadingMore || !hasMore) return;
    setLoadingMore(true);
    try {
      const result = await api.plaza.list(query, nextOffset);
      setItems((current) => [...current, ...result.items]);
      setHasMore(result.has_more);
      setNextOffset(result.next_offset);
    } catch {
      setError(true);
    } finally {
      setLoadingMore(false);
    }
  }

  return (
    <div className="min-h-screen bg-[var(--surface-canvas)] text-[var(--text-primary)]">
      <PlazaHeader />
      <main className="mx-auto w-full max-w-6xl px-5 pb-24 pt-12 sm:px-8 sm:pt-20">
        <section className="grid gap-10 border-b border-[var(--border-default)] pb-12 md:grid-cols-[minmax(0,1fr)_minmax(240px,340px)] md:items-end">
          <div>
            <h1 className="font-serif text-5xl leading-tight tracking-[-0.04em] sm:text-6xl">故事广场</h1>
            <p className="mt-5 max-w-xl font-serif text-lg leading-9 text-[var(--text-secondary)]">
              每一个选择，都是另一个人的人生。走进故事，读一读他们走过的日子。
            </p>
          </div>
          <form onSubmit={search} role="search" className="flex gap-2">
            <label htmlFor="plaza-search" className="sr-only">搜索故事或作者</label>
            <input id="plaza-search" value={input} onChange={(event) => setInput(event.target.value)} maxLength={100} placeholder="搜索故事或作者" className="min-h-11 min-w-0 flex-1 rounded-[var(--radius-control)] border border-[var(--border-interactive)] bg-[var(--surface-reading)] px-3 text-sm text-[var(--text-primary)] outline-none placeholder:text-[var(--text-secondary)] focus-visible:ring-2 focus-visible:ring-[var(--text-primary)]" />
            <Button type="submit" variant="narrative" size="touch" aria-label="搜索"><Search className="size-4" /></Button>
          </form>
        </section>

        <div className="flex flex-col gap-2 py-7 sm:flex-row sm:items-baseline sm:justify-between sm:gap-4">
          <h2 className="font-serif text-2xl">{query ? `搜索“${query}”` : "正在被阅读的故事"}</h2>
          <span className="text-xs text-[var(--text-secondary)]">公开故事会随作者的新章节更新</span>
        </div>

        {loading ? <p role="status" className="py-16 text-center text-[var(--text-secondary)]">正在翻开故事…</p> : error ? (
          <div role="alert" className="border border-[var(--border-default)] bg-[var(--surface-reading)] p-8">
            <p>暂时无法载入故事。</p>
            <Button type="button" variant="narrative" className="mt-5" onClick={() => { setLoading(true); setReload((value) => value + 1); }}>重试</Button>
          </div>
        ) : items.length === 0 ? (
          <div className="border border-[var(--border-default)] bg-[var(--surface-reading)] px-6 py-16 text-center">
            <p className="font-serif text-2xl">{query ? "没有找到相关故事" : "广场还没有公开的故事"}</p>
            <p className="mt-3 text-[var(--text-secondary)]">{query ? "试试其他故事名或作者名。" : "完成一章后，你可以把自己的故事分享给大家。"}</p>
            {query ? <Button type="button" variant="quiet" className="mt-5" onClick={() => { setInput(""); setLoading(true); setQuery(""); }}>查看全部故事</Button> : <Link href="/plaza/manage" className="mt-5 inline-block text-sm underline underline-offset-4">分享我的故事</Link>}
          </div>
        ) : (
          <>
            <ul className="grid gap-3 md:grid-cols-2">
              {items.map((story) => (
                <li key={story.public_id} className="min-w-0">
                  <Link href={`/plaza/${story.public_id}`} className="group flex h-full min-h-56 flex-col border border-[var(--border-default)] bg-[var(--surface-reading)] p-6 transition-colors hover:border-[var(--border-strong)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--text-primary)] sm:p-8" aria-label={`阅读${story.title}，作者${story.author_name}`}>
                    <div className="flex items-start justify-between gap-4">
                      <span aria-hidden="true" className="mt-2 h-px w-9 bg-[var(--border-strong)]" />
                      <span className="text-xs text-[var(--text-secondary)]">{story.chapter_count} 章</span>
                    </div>
                    <h3 className="mt-4 break-words font-serif text-2xl leading-tight">{story.title}</h3>
                    <p className="mt-2 text-sm text-[var(--text-secondary)]">{story.author_name}</p>
                    <p className="mt-5 line-clamp-3 flex-1 break-words font-serif text-sm leading-7 text-[var(--text-secondary)]">{story.excerpt}</p>
                    <span className="mt-6 flex items-center gap-2 border-t border-[var(--border-default)] pt-4 text-sm group-hover:text-white">开始阅读 <ArrowRight className="size-4" /></span>
                  </Link>
                </li>
              ))}
            </ul>
            {hasMore ? <div className="mt-9 text-center"><Button type="button" variant="narrative" size="touch" disabled={loadingMore} onClick={() => void loadMore()}>{loadingMore ? "载入中…" : "更多故事"}</Button></div> : null}
          </>
        )}
      </main>
    </div>
  );
}
