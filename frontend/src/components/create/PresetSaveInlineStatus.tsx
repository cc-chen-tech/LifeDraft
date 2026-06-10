"use client";

import type { PresetSaveStatus } from "@/hooks/useCharacterCreation";

interface PresetSaveInlineStatusProps {
  status: PresetSaveStatus;
  message: string;
}

export function PresetSaveInlineStatus({
  status,
  message,
}: PresetSaveInlineStatusProps) {
  if (!message || status === "idle") return null;

  const isError = status === "error";

  return (
    <p
      role={isError ? "alert" : "status"}
      aria-live={isError ? "assertive" : "polite"}
      className={
        isError
          ? "rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive"
          : "rounded-md border border-primary/20 bg-primary/10 px-3 py-2 text-sm text-primary"
      }
    >
      {message}
    </p>
  );
}
