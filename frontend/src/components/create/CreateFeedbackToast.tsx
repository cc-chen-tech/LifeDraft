import { FeedbackNotice } from "@/components/story101";
import type { ToastType } from "@/hooks/useCharacterCreation";

interface CreateFeedbackToastProps {
  toast: ToastType;
  suppressed?: boolean;
}

export function CreateFeedbackToast({
  toast,
  suppressed = false,
}: CreateFeedbackToastProps) {
  if (!toast || suppressed) return null;

  return (
    <FeedbackNotice
      tone={toast.type === "success" ? "success" : "danger"}
      className="fixed bottom-[var(--app-shell-feedback-bottom)] left-1/2 z-50 w-[calc(100%_-_2rem)] max-w-md -translate-x-1/2 p-3"
    >
      <p>{toast.message}</p>
    </FeedbackNotice>
  );
}
