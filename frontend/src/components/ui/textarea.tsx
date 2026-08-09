import * as React from "react"

import { cn } from "@/lib/utils"

function Textarea({
  className,
  surface = "default",
  controlSize = "default",
  ...props
}: React.ComponentProps<"textarea"> & {
  surface?: "default" | "filled" | "underline"
  controlSize?: "default" | "touch"
}) {
  return (
    <textarea
      data-slot="textarea"
      data-surface={surface}
      data-control-size={controlSize}
      className={cn(
        "border-input placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-ring/50 aria-invalid:ring-destructive/20 dark:aria-invalid:ring-destructive/40 aria-invalid:border-destructive flex field-sizing-content min-h-16 w-full rounded-md border bg-transparent px-3 py-2 text-base shadow-xs transition-[color,box-shadow] outline-none focus-visible:ring-[3px] disabled:cursor-not-allowed disabled:opacity-50 md:text-sm",
        surface === "filled" && "border-transparent bg-[var(--surface-raised)]",
        surface === "underline" &&
          "rounded-none border-x-0 border-t-0 border-b-[var(--border-default)] bg-transparent px-0 shadow-none",
        controlSize === "touch" && "min-h-20 py-3",
        className
      )}
      {...props}
    />
  )
}

export { Textarea }
