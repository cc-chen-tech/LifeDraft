import * as React from "react";

import { PageTransition } from "./PageTransition";

export interface GlobalStatePageProps {
  title: string;
  description: string;
  action: React.ReactElement;
}

export function GlobalStatePage({ title, description, action }: GlobalStatePageProps) {
  return (
    <PageTransition
      aria-label={title}
      className="flex min-h-[100dvh] flex-col items-center justify-center gap-4 px-6 text-center"
    >
      <h1 className="text-2xl font-semibold text-[var(--text-primary)]">{title}</h1>
      <p className="max-w-md text-sm leading-6 text-[var(--text-secondary)]">{description}</p>
      {action}
    </PageTransition>
  );
}
