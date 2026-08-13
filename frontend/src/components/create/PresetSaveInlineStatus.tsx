"use client";

import type { PresetSaveStatus } from "@/hooks/useCharacterCreation";
import { FeedbackNotice } from "@/components/story101";

interface PresetSaveInlineStatusProps {
  status: PresetSaveStatus;
  message: string;
}

export function PresetSaveInlineStatus({
  status,
  message,
}: PresetSaveInlineStatusProps) {
  if (!message || status === "idle") return null;

  return (
    <FeedbackNotice
      tone={status === "error" ? "danger" : "info"}
      className="p-3"
    >
      <p>{message}</p>
    </FeedbackNotice>
  );
}
