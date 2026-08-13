import * as React from "react";

import { cn } from "@/lib/utils";

export interface AppShellProps extends React.ComponentPropsWithoutRef<"div"> {
  fixedRegions?: React.ReactNode;
}

export function AppShell({
  children,
  className,
  fixedRegions,
  ...props
}: AppShellProps) {
  return (
    <div
      data-slot="app-shell"
      className={cn("story101-app-shell", className)}
      {...props}
    >
      <div data-slot="app-shell-content">{children}</div>
      {fixedRegions != null && (
        <div data-slot="app-shell-fixed-regions">{fixedRegions}</div>
      )}
    </div>
  );
}
