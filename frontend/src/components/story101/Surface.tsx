import * as React from "react";
import { Slot } from "radix-ui";

import { cn } from "@/lib/utils";

type SurfaceVariant = "reading" | "raised" | "subtle" | "overlay";

const surfaceClasses: Record<SurfaceVariant, string> = {
  reading: "border border-[var(--border-default)] bg-[var(--surface-reading)] rounded-[var(--radius-surface)]",
  raised: "border border-[var(--border-default)] bg-[var(--surface-raised)] rounded-[var(--radius-surface)]",
  subtle: "border border-[var(--border-default)] bg-[var(--surface-subtle)] rounded-[var(--radius-surface)]",
  overlay: "border border-[var(--border-default)] bg-[var(--surface-overlay)] rounded-[var(--radius-overlay)] shadow-[var(--shadow-overlay)]",
};

export interface SurfaceProps extends React.ComponentPropsWithoutRef<"section"> {
  variant?: SurfaceVariant;
  asChild?: boolean;
}

export function Surface({
  className,
  variant = "reading",
  asChild = false,
  ...props
}: SurfaceProps) {
  const Component = asChild ? Slot.Root : "section";

  return (
    <Component
      data-slot="surface"
      data-variant={variant}
      className={cn(surfaceClasses[variant], className)}
      {...props}
    />
  );
}
