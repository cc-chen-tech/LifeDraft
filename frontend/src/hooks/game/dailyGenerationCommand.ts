import type { GenerationFailurePayload } from "@/lib/sse";
import type { EventOption } from "@/lib/types";

export type DailyGenerationCommandStatus =
  | "idle"
  | "starting"
  | "running"
  | "succeeded"
  | "failed";

export type DailyGenerationMode = "generate_missing" | "replace_current";

export interface DailyGenerationCommandState {
  status: DailyGenerationCommandStatus;
  mode: DailyGenerationMode | null;
  operationId: string | null;
  attempt: number | null;
  maxAttempts: number | null;
  failure: GenerationFailurePayload | null;
}

export const INITIAL_DAILY_GENERATION_COMMAND: DailyGenerationCommandState = {
  status: "idle",
  mode: null,
  operationId: null,
  attempt: null,
  maxAttempts: null,
  failure: null,
};

interface ClientEventLike {
  story?: string;
  event_description?: string;
  options?: EventOption[];
  event_id?: string;
  revision?: number;
}

export function isCompleteClientEvent(
  event: ClientEventLike | null | undefined,
): event is ClientEventLike & {
  options: EventOption[];
  event_id: string;
  revision: number;
} {
  const story = event?.story || event?.event_description || "";
  return Boolean(
    event
      && story.trim()
      && event.options
      && event.options.length >= 2
      && event.event_id?.trim()
      && typeof event.revision === "number"
      && event.revision >= 1,
  );
}
