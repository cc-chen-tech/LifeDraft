import * as React from "react"

import { cn } from "@/lib/utils"

function Input({
  className,
  type,
  surface = "default",
  controlSize = "default",
  ...props
}: React.ComponentProps<"input"> & {
  surface?: "default" | "filled" | "underline"
  controlSize?: "default" | "touch"
}) {
  return (
    <input
      type={type}
      data-slot="input"
      data-surface={surface}
      data-control-size={controlSize}
      className={cn(
        "file:text-foreground placeholder:text-muted-foreground selection:bg-primary selection:text-primary-foreground border-[var(--border-interactive)] h-9 w-full min-w-0 rounded-[var(--radius-control)] border bg-transparent px-3 py-1 text-base shadow-xs transition-[color,box-shadow] outline-none file:inline-flex file:h-7 file:border-0 file:bg-transparent file:text-sm file:font-medium disabled:pointer-events-none disabled:cursor-not-allowed disabled:opacity-50 md:text-sm",
        "focus-visible:border-ring focus-visible:ring-ring/50 focus-visible:ring-[3px]",
        "aria-invalid:ring-destructive/20 dark:aria-invalid:ring-destructive/40 aria-invalid:border-destructive",
        surface === "filled" && "bg-[var(--surface-raised)]",
        surface === "underline" &&
          "border-x-0 border-t-0 border-b-[var(--border-interactive)] bg-transparent px-0 shadow-none",
        controlSize === "touch" && "h-11 min-h-11 py-2.5",
        className
      )}
      {...props}
    />
  )
}

export { Input }
