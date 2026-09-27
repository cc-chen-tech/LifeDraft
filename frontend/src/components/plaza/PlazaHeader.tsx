import Link from "next/link";

export function PlazaHeader({ manage = false }: { manage?: boolean }) {
  return (
    <header className="border-b border-[var(--border-default)]">
      <div className="mx-auto flex min-h-16 w-full max-w-6xl items-center justify-between gap-4 px-5 sm:px-8">
        <Link href="/" className="font-brand text-lg font-semibold tracking-[-0.04em] text-[var(--text-primary)] focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-[var(--text-primary)]">
          story101
        </Link>
        <nav aria-label="广场导航" className="flex items-center gap-5 text-sm">
          <Link href="/plaza" className="text-[var(--text-secondary)] hover:text-[var(--text-primary)] focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-[var(--text-primary)]">故事广场</Link>
          <Link href={manage ? "/saves" : "/plaza/manage"} className="text-[var(--text-secondary)] hover:text-[var(--text-primary)] focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-[var(--text-primary)]">
            {manage ? "我的存档" : "分享我的故事"}
          </Link>
        </nav>
      </div>
    </header>
  );
}
