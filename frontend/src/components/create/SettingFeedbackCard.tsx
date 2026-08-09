"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card } from "@/components/ui/card";
import { RefreshCw, Loader2 } from "lucide-react";
import { SettingDisplay } from "@/components/game/SettingDisplay";
import { LengthIndicator } from "@/components/ui/length-indicator";
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
    <Card className="p-4 border-border">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-medium text-primary">{stepLabel}</h3>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => {
            setIsEditing(!isEditing);
            setRegenerationError("");
          }}
          disabled={isGenerating}
          aria-label={isEditing ? `取消${stepLabel}反馈编辑` : `给${stepLabel}反馈重新生成`}
          data-testid={`${stepKey}-feedback-button`}
        >
          <RefreshCw className="w-3.5 h-3.5 mr-1" />
          {isEditing ? "取消" : "给反馈重新生成"}
        </Button>
      </div>

      <div data-testid={`${stepKey}-content`}>
        <SettingDisplay stepKey={stepKey} data={data} />
      </div>

      {isEditing && (
        <div className="mt-3 space-y-2 animate-page-enter">
          <Input
            value={feedback}
            onChange={(e) => setFeedback(e.target.value)}
            placeholder="告诉AI你想怎么改..."
            disabled={isGenerating}
            data-testid={`${stepKey}-feedback-input`}
          />
          <LengthIndicator value={feedback} limit={INPUT_LIMITS.feedback} />
          {regenerationError && (
            <p className="text-xs text-destructive" role="alert">
              {regenerationError}
            </p>
          )}
          <div className="flex gap-2">
            <Button
              size="sm"
              onClick={handleRegenerate}
              disabled={
                isGenerating ||
                !feedback.trim() ||
                !isWithinInputLimit(feedback, INPUT_LIMITS.feedback)
              }
              aria-label={`重新生成${stepLabel}`}
            >
              {isGenerating ? (
                <Loader2 className="w-3.5 h-3.5 mr-1 animate-spin" />
              ) : (
                <RefreshCw className="w-3.5 h-3.5 mr-1" />
              )}
              重新生成
            </Button>
            <Button
              size="sm"
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
    </Card>
  );
}
