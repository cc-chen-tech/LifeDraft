"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { RefreshCw, Loader2 } from "lucide-react";
import { SettingDisplay } from "@/components/game/SettingDisplay";
import { LengthIndicator } from "@/components/ui/length-indicator";
import { FeedbackNotice, FormField } from "@/components/story101";
import { INPUT_LIMITS } from "@/types/input-limits.generated";
import { isWithinInputLimit } from "@/lib/inputLimits";

interface SettingFeedbackCardProps {
  stepKey: string;
  stepLabel: string;
  data: Record<string, unknown>;
  onRegenerate: (feedback: string) => Promise<void>;
}

export function SettingFeedbackCard({
  stepKey,
  stepLabel,
  data,
  onRegenerate,
}: SettingFeedbackCardProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [feedback, setFeedback] = useState("");
  const [isGenerating, setIsGenerating] = useState(false);
  const [regenerationError, setRegenerationError] = useState("");
  const isOverLimit = !isWithinInputLimit(feedback, INPUT_LIMITS.feedback);

  const handleRegenerate = async () => {
    if (!feedback.trim() || !isWithinInputLimit(feedback, INPUT_LIMITS.feedback)) return;
    setIsGenerating(true);
    setRegenerationError("");
    try {
      await onRegenerate(feedback.trim());
      setFeedback("");
      setIsEditing(false);
    } catch (error) {
      setRegenerationError(
        error instanceof Error && error.message.trim()
          ? error.message
          : "重新生成失败，已保留原设定，请重试",
      );
    } finally {
      setIsGenerating(false);
    }
  };

  return (
    <section
      className="min-w-0 border-t border-[var(--border-default)] py-5"
      data-slot="setting-feedback"
    >
      <div className="mb-3 flex min-w-0 flex-wrap items-center justify-between gap-3">
        <h3 className="break-words text-sm font-medium text-[var(--text-primary)]">
          {stepLabel}
        </h3>
        <Button
          variant="quiet"
          size="touch"
          onClick={() => {
            setIsEditing(!isEditing);
            setRegenerationError("");
          }}
          disabled={isGenerating}
          aria-label={isEditing ? `取消${stepLabel}反馈编辑` : `给${stepLabel}反馈重新生成`}
          data-testid={`${stepKey}-feedback-button`}
        >
          <RefreshCw />
          {isEditing ? "取消" : "给反馈重新生成"}
        </Button>
      </div>

      <div data-testid={`${stepKey}-content`}>
        <SettingDisplay stepKey={stepKey} data={data} />
      </div>

      {isEditing && (
        <div className="mt-5 grid gap-4 border-t border-[var(--border-default)] pt-5">
          <FormField
            id={`${stepKey}-feedback`}
            label={`${stepLabel}修改意见`}
            description="写清想保留的部分和需要调整的方向。"
            error={isOverLimit ? `修改意见不能超过 ${INPUT_LIMITS.feedback} 字` : undefined}
          >
            {({ describedBy, invalid }) => (
              <>
                <Textarea
                  id={`${stepKey}-feedback`}
                  value={feedback}
                  onChange={(e) => setFeedback(e.target.value)}
                  placeholder="写下你想调整的方向"
                  surface="underline"
                  controlSize="touch"
                  className="min-h-24 resize-y"
                  disabled={isGenerating}
                  aria-describedby={[describedBy, `${stepKey}-feedback-count`].filter(Boolean).join(" ")}
                  aria-invalid={invalid}
                  data-testid={`${stepKey}-feedback-input`}
                />
                <LengthIndicator
                  id={`${stepKey}-feedback-count`}
                  value={feedback}
                  limit={INPUT_LIMITS.feedback}
                  announce={false}
                />
              </>
            )}
          </FormField>
          {regenerationError && (
            <FeedbackNotice tone="danger" className="p-3">
              <p>{regenerationError}</p>
            </FeedbackNotice>
          )}
          <div className="flex flex-col gap-2 sm:flex-row">
            <Button
              size="touch"
              onClick={handleRegenerate}
              disabled={
                isGenerating ||
                !feedback.trim() ||
                isOverLimit
              }
              aria-label={`重新生成${stepLabel}`}
            >
              {isGenerating ? (
                <Loader2 className="animate-spin" />
              ) : (
                <RefreshCw />
              )}
              重新生成
            </Button>
            <Button
              size="touch"
              variant="outline"
              onClick={() => {
                setIsEditing(false);
                setFeedback("");
                setRegenerationError("");
              }}
              disabled={isGenerating}
            >
              取消
            </Button>
          </div>
        </div>
      )}
    </section>
  );
}
