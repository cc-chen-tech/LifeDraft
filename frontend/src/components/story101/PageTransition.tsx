import * as React from "react";

import { cn } from "@/lib/utils";

export type PageTransitionProps = React.ComponentPropsWithoutRef<"main">;

export function PageTransition({ className, ...props }: PageTransitionProps) {
  return (
    <main
      data-slot="page-transition"
      className={cn("story101-page-transition", className)}
      {...props}
    />
  );
}
