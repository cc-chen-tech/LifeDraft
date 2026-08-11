import * as React from "react";

import { cn } from "@/lib/utils";

export interface MobileActionDockAction {
  id: string;
  label: string;
  icon: React.ReactNode;
  onSelect: () => void;
  buttonRef?: React.Ref<HTMLButtonElement>;
  disabled?: boolean;
  busy?: boolean;
  controls?: string;
  expanded?: boolean;
}

export interface MobileActionDockProps
  extends Omit<React.ComponentPropsWithoutRef<"nav">, "children"> {
  actions: readonly MobileActionDockAction[];
  label?: string;
}

export function MobileActionDock({
  actions,
  className,
  label = "游戏快捷工具",
  ...props
}: MobileActionDockProps) {
  if (actions.length > 4) {
    throw new Error("MobileActionDock supports at most four actions");
  }

  return (
    <nav
      aria-label={label}
      data-slot="mobile-action-dock"
      className={cn(
        "safe-area-pb fixed inset-x-0 bottom-0 z-50 border-t border-[var(--border-default)] bg-[var(--surface-overlay)] md:hidden",
        className,
      )}
      {...props}
    >
      <div className="grid auto-cols-fr grid-flow-col gap-1 px-2 py-2">
        {actions.map((action) => (
          <button
            key={action.id}
            ref={action.buttonRef}
            type="button"
            aria-controls={action.controls}
            aria-expanded={action.controls ? action.expanded : undefined}
            aria-busy={action.busy || undefined}
            className={cn(
              "flex min-h-11 min-w-11 flex-col items-center justify-center gap-1 rounded-[var(--radius-control)] px-2 py-1",
              "text-sm text-[var(--text-secondary)] transition-colors",
              "hover:bg-[var(--surface-subtle)] hover:text-[var(--text-primary)]",
              "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--text-primary)]",
              "disabled:pointer-events-none disabled:opacity-50",
            )}
            disabled={action.disabled}
            onClick={action.onSelect}
          >
            <span aria-hidden="true" className="flex h-4 w-4 items-center justify-center">
              {action.icon}
            </span>
            <span>{action.label}</span>
          </button>
        ))}
      </div>
    </nav>
  );
}
