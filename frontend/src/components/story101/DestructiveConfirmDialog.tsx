"use client";

import * as React from "react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

import { FeedbackNotice } from "./FeedbackNotice";

export interface DestructiveConfirmDialogProps {
  open: boolean;
  itemKind: "存档" | "角色预设";
  itemName: string;
  busy: boolean;
  error?: string | null;
  onOpenChange(open: boolean): void;
  onConfirm(): void;
}

export function DestructiveConfirmDialog({
  open,
  itemKind,
  itemName,
  busy,
  error,
  onOpenChange,
  onConfirm,
}: DestructiveConfirmDialogProps) {
  const cancelButtonRef = React.useRef<HTMLButtonElement>(null);
  const confirmRequestedRef = React.useRef(false);

  React.useEffect(() => {
    if (!busy) {
      confirmRequestedRef.current = false;
    }
  }, [busy]);

  const handleOpenChange = (nextOpen: boolean) => {
    if (!nextOpen && busy) return;
    onOpenChange(nextOpen);
  };

  const handleConfirm = () => {
    if (busy || confirmRequestedRef.current) return;
    confirmRequestedRef.current = true;
    onConfirm();
  };

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent
        aria-busy={busy}
        className="border-[var(--border-default)] bg-[var(--surface-overlay)]"
        showCloseButton={false}
        onEscapeKeyDown={(event) => {
          if (busy) event.preventDefault();
        }}
        onPointerDownOutside={(event) => {
          if (busy) event.preventDefault();
        }}
        onInteractOutside={(event) => {
          if (busy) event.preventDefault();
        }}
        onOpenAutoFocus={(event) => {
          event.preventDefault();
          cancelButtonRef.current?.focus();
        }}
      >
        <DialogHeader>
          <DialogTitle className="break-words font-serif text-xl leading-8 text-[var(--text-primary)]">
            删除{itemKind}“{itemName}”？
          </DialogTitle>
          <DialogDescription className="break-words leading-6 text-[var(--text-secondary)]">
            删除后无法恢复。这个{itemKind}及其中保存的内容将永久移除。
          </DialogDescription>
        </DialogHeader>

        {error ? (
          <FeedbackNotice tone="danger">{error}</FeedbackNotice>
        ) : null}

        <DialogFooter>
          <Button
            ref={cancelButtonRef}
            type="button"
            variant="narrative"
            size="touch"
            disabled={busy}
            onClick={() => handleOpenChange(false)}
          >
            取消
          </Button>
          <Button
            type="button"
            variant="destructive"
            size="touch"
            disabled={busy}
            onClick={handleConfirm}
          >
            {busy ? "正在删除" : "删除"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
