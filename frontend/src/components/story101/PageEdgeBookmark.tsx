import * as React from "react";

import { cn } from "@/lib/utils";

export interface PageEdgeBookmarkProps
  extends React.ComponentPropsWithoutRef<"aside"> {
  label: string;
  detail?: string;
}

export function PageEdgeBookmark({
  label,
  detail,
  className,
  ...props
}: PageEdgeBookmarkProps) {
  return (
    <aside
      data-slot="page-edge-bookmark"
      aria-label="当前页面位置"
      className={cn(
        "min-w-0 border-l-2 border-[var(--border-interactive)] py-1 pl-3",
        "md:sticky md:top-24 md:self-start md:pl-4",
        className,
      )}
      {...props}
    >
      <p className="break-words text-sm font-medium text-[var(--text-primary)]">
        {label}
      </p>
      {detail && (
        <p className="mt-1 break-words text-xs text-[var(--text-secondary)]">
          {detail}
        </p>
      )}
    </aside>
  );
}
