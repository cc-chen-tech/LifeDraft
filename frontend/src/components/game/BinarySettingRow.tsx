import type { ChangeEventHandler, ReactNode } from "react";

import { cn } from "@/lib/utils";

interface BinarySettingRowProps {
  label: string;
  description: string;
  checked: boolean;
  onChange: ChangeEventHandler<HTMLInputElement>;
  icon?: ReactNode;
  className?: string;
}

export function BinarySettingRow({
  label,
  description,
  checked,
  onChange,
  icon,
  className,
}: BinarySettingRowProps) {
  return (
    <label
      data-state={checked ? "on" : "off"}
      className={cn(
        "flex min-h-[4.5rem] cursor-pointer items-center justify-between gap-4 border-y border-[var(--border-default)] px-3 py-2 text-sm",
        "transition-colors hover:bg-[var(--surface-subtle)]",
        "has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-[var(--ring)]",
        className,
      )}
    >
      <input
        type="checkbox"
        aria-label={label}
        checked={checked}
        onChange={onChange}
        className="sr-only"
      />

      <span className="flex min-w-0 items-center gap-3">
        {icon}
        <span className="min-w-0">
          <span className="block font-medium text-[var(--text-primary)]">
            {label}
          </span>
          <span className="mt-0.5 block text-xs leading-5 text-[var(--text-secondary)]">
            {checked ? "已开启" : "已关闭"} · {description}
          </span>
        </span>
      </span>

      <span
        aria-hidden="true"
        className="grid min-h-9 shrink-0 grid-cols-2 overflow-hidden rounded-[var(--radius-control)] border border-[var(--border-strong)] bg-[var(--surface-canvas)]"
      >
        <span
          className={cn(
            "grid min-w-10 place-items-center px-2 text-xs text-[var(--text-secondary)] transition-colors",
            !checked &&
              "bg-[var(--text-primary)] font-semibold text-[var(--surface-canvas)]",
          )}
        >
          关
        </span>
        <span
          className={cn(
            "grid min-w-10 place-items-center border-l border-[var(--border-default)] px-2 text-xs text-[var(--text-secondary)] transition-colors",
            checked &&
              "bg-[var(--text-primary)] font-semibold text-[var(--surface-canvas)]",
          )}
        >
          开
        </span>
      </span>
    </label>
  );
}
