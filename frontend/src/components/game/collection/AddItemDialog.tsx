"use client";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { Plus, Loader2 } from "lucide-react";
import type { AddItemDialogProps } from "./types";
import { LengthIndicator } from "@/components/ui/length-indicator";
import { INPUT_LIMITS } from "@/types/input-limits.generated";
import { isWithinInputLimit } from "@/lib/inputLimits";

/**
 * 手动添加物品对话框 - 允许用户手动添加物品到收集
 */
export function AddItemDialog({
  open,
  onClose,
  onCloseAutoFocus,
  onSubmit,
  itemName,
  onItemNameChange,
  generateDesc,
  onGenerateDescChange,
  isLoading,
}: AddItemDialogProps) {
  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (
      e.key === "Enter" &&
      itemName.trim() &&
      isWithinInputLimit(itemName, INPUT_LIMITS.name)
    ) {
      onSubmit();
    }
  };

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent
        className="z-[81] max-w-md"
        overlayClassName="z-[80]"
        onCloseAutoFocus={onCloseAutoFocus}
      >
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Plus className="w-5 h-5" />
            手动添加物品
          </DialogTitle>
          <DialogDescription>
            输入物品名称，AI将从故事历史中提取描述
          </DialogDescription>
        </DialogHeader>

        <div className="py-4 space-y-4">
          <div>
            <label className="text-sm font-medium mb-2 block">物品名称</label>
            <input
              type="text"
              value={itemName}
              onChange={(e) => onItemNameChange(e.target.value)}
              placeholder="例如：神秘古书、银色怀表..."
              className="w-full px-3 py-2 border rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-primary"
              onKeyDown={handleKeyDown}
            />
            <LengthIndicator value={itemName} limit={INPUT_LIMITS.name} />
          </div>

          <label className="flex items-center gap-2 text-sm cursor-pointer">
            <input
              type="checkbox"
              checked={generateDesc}
              onChange={(e) => onGenerateDescChange(e.target.checked)}
            />
            从故事历史中提取描述
          </label>
        </div>

        <div className="flex gap-2 pt-4 border-t">
          <Button variant="outline" onClick={onClose} className="flex-1">
            取消
          </Button>
          <Button
            onClick={onSubmit}
            disabled={
              !itemName.trim() ||
              isLoading ||
              !isWithinInputLimit(itemName, INPUT_LIMITS.name)
            }
            className="flex-1"
          >
            {isLoading ? (
              <>
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                创建中...
              </>
            ) : (
              "创建"
            )}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
