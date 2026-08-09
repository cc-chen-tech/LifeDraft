import * as React from "react";

import { cn } from "@/lib/utils";

type FeedbackTone = "success" | "warning" | "danger" | "info";

const toneClasses: Record<FeedbackTone, string> = {
  success: "border-[var(--success-border)] bg-[var(--success-subtle)] text-[var(--success-foreground)]",
  warning: "border-[var(--warning-border)] bg-[var(--warning-subtle)] text-[var(--warning-foreground)]",
  danger: "border-[var(--danger-border)] bg-[var(--danger-subtle)] text-[var(--danger-foreground)]",
  info: "border-[var(--info-border)] bg-[var(--info-subtle)] text-[var(--info-foreground)]",
};

export interface FeedbackNoticeProps {
  tone: FeedbackTone;
  title?: React.ReactNode;
  children: React.ReactNode;
  action?: React.ReactElement;
  className?: string;
}

export function FeedbackNotice({
  tone,
  title,
  children,
  action,
  className,
}: FeedbackNoticeProps) {
  const isDanger = tone === "danger";

  return (
    <div className={cn("grid gap-3 rounded-[var(--radius-surface)] border p-4 text-sm", toneClasses[tone], className)} data-slot="feedback-notice">
      <div role={isDanger ? "alert" : "status"} aria-live={isDanger ? undefined : "polite"}>
        {title && <p className="font-medium">{title}</p>}
        <div className={title ? "mt-1" : undefined}>{children}</div>
      </div>
      {action}
    </div>
  );
}
