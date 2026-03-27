"use client";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { Trash2, Loader2 } from "lucide-react";
import type { DeleteConfirmDialogProps } from "./types";

/**
 * 删除确认对话框 - 确认删除操作
 */
export function DeleteConfirmDialog({
  open,
  onClose,
  onConfirm,
  entityToDelete,
  isDeleting,
}: DeleteConfirmDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="max-w-sm">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-destructive">
            <Trash2 className="w-5 h-5" />
            确认删除
          </DialogTitle>
          <DialogDescription>
            {entityToDelete && (
              <>
                确定要删除
                <span className="font-medium mx-1">{entityToDelete.name}</span>
                吗？此操作不可恢复。
              </>
            )}
          </DialogDescription>
        </DialogHeader>

        <div className="flex gap-2 pt-4">
          <Button variant="outline" onClick={onClose} className="flex-1">
            取消
          </Button>
          <Button
            variant="destructive"
            onClick={onConfirm}
            disabled={isDeleting}
            className="flex-1"
          >
            {isDeleting ? (
              <>
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                删除中...
              </>
            ) : (
              "删除"
            )}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
