"use client";

import { Button } from "@/components/ui/button";
import { FeedbackNotice } from "@/components/story101";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { LengthIndicator } from "@/components/ui/length-indicator";
import { Loader2, Plus } from "lucide-react";
import { isWithinInputLimit } from "@/lib/inputLimits";
import { INPUT_LIMITS } from "@/types/input-limits.generated";
import type { AddEntityDialogProps } from "./types";

const entityCopy = {
  characters: {
    title: "添加人物",
    noun: "人物",
    placeholder: "例如：旧友、神秘访客...",
    helper: "输入人物名称，补充故事中的角色",
  },
  items: {
    title: "添加物品",
    noun: "物品",
    placeholder: "例如：神秘古书、银色怀表...",
    helper: "输入物品名称，可从故事历史中提取描述",
  },
  landmarks: {
    title: "添加标志物",
    noun: "标志物",
    placeholder: "例如：旧码头、山间小屋...",
    helper: "输入标志物名称，补充故事中的地点",
  },
} as const;

export function AddEntityDialog({
  activeTab,
  open,
  onClose,
  onCloseAutoFocus,
  onSubmit,
  entityName,
  onEntityNameChange,
  generateDescription,
  onGenerateDescriptionChange,
  error,
  isLoading,
}: AddEntityDialogProps) {
  const copy = entityCopy[activeTab];
  const canSubmit =
    entityName.trim().length > 0 &&
    !isLoading &&
    isWithinInputLimit(entityName, INPUT_LIMITS.name);

  const handleKeyDown = (event: React.KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "Enter" && canSubmit) {
      onSubmit();
    }
  };

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent
        className="z-[81] max-w-md"
        overlayClassName="z-[80]"
        showCloseButton={false}
        onCloseAutoFocus={onCloseAutoFocus}
      >
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Plus className="size-5" />
            {copy.title}
          </DialogTitle>
          <DialogDescription>{copy.helper}</DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-4">
          {error && <FeedbackNotice tone="danger">{error}</FeedbackNotice>}
          <div>
            <label className="mb-2 block text-sm font-medium" htmlFor="collection-entity-name">
              {copy.noun}名称
            </label>
            <input
              id="collection-entity-name"
              type="text"
              value={entityName}
              onChange={(event) => onEntityNameChange(event.target.value)}
              placeholder={copy.placeholder}
              className="min-h-11 w-full rounded-md border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
              onKeyDown={handleKeyDown}
            />
            <LengthIndicator value={entityName} limit={INPUT_LIMITS.name} />
          </div>

          {activeTab === "items" && (
            <label className="flex min-h-11 cursor-pointer items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={generateDescription}
                onChange={(event) => onGenerateDescriptionChange(event.target.checked)}
              />
              从故事历史中提取描述
            </label>
          )}
        </div>

        <div className="flex gap-2 border-t pt-4">
          <Button variant="outline" size="touch" onClick={onClose} className="flex-1">
            取消
          </Button>
          <Button size="touch" onClick={onSubmit} disabled={!canSubmit} className="flex-1">
            {isLoading ? (
              <>
                <Loader2 className="mr-2 size-4 animate-spin" />
                添加中...
              </>
            ) : (
              "添加"
            )}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
