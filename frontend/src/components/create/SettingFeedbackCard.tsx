"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card } from "@/components/ui/card";
import { RefreshCw, Loader2 } from "lucide-react";
import { SettingDisplay } from "@/components/game/SettingDisplay";

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

  const handleRegenerate = async () => {
    if (!feedback.trim()) return;
    setIsGenerating(true);
    try {
      await onRegenerate(feedback.trim());
      setFeedback("");
      setIsEditing(false);
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
          onClick={() => setIsEditing(!isEditing)}
          disabled={isGenerating}
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
          <div className="flex gap-2">
            <Button
              size="sm"
              onClick={handleRegenerate}
              disabled={isGenerating || !feedback.trim()}
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
