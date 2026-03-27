"use client";

import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import {
  Package,
  Image as ImageIcon,
  FileText,
  Loader2,
  Pencil,
  X,
  Sparkles,
  Trash2,
} from "lucide-react";
import { CATEGORY_LABELS, IMPORTANCE_LABELS } from "./types";
import type { ItemDetailProps } from "./types";

/**
 * 物品详情对话框 - 显示物品详细信息和操作按钮
 */
export function ItemDetail({
  item,
  onClose,
  onGenerateImage,
  onGenerateDescription,
  onStartRegenerate,
  onCancelRegenerate,
  onSubmitRegenerate,
  onOpenDeleteConfirm,
  generatingImageFor,
  generatingDescriptionFor,
  regeneratingImageFor,
  showRegenerateInput,
  regenerateType,
  regenerateFeedback,
  onRegenerateFeedbackChange,
  isDeleting,
}: ItemDetailProps) {
  if (!item) return null;

  return (
    <Dialog open={!!item} onOpenChange={onClose}>
      <DialogContent className="max-w-md h-[85vh] flex flex-col p-0 gap-0">
        <DialogHeader className="px-6 pt-6 pb-2 flex-shrink-0">
          <div className="flex items-start justify-between">
            <div>
              <DialogTitle className="flex items-center gap-2">
                <Package className="w-5 h-5" />
                {item.name}
                {item.is_key_item && (
                  <Sparkles className="w-4 h-4 text-amber-500" />
                )}
              </DialogTitle>
              <DialogDescription>
                {CATEGORY_LABELS[item.category] || item.category}
                · {IMPORTANCE_LABELS[item.importance]?.label || "普通"}
              </DialogDescription>
            </div>
            {/* 删除按钮 */}
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8 text-destructive hover:text-destructive hover:bg-destructive/10"
              onClick={() => onOpenDeleteConfirm(item.name)}
              disabled={isDeleting}
            >
              <Trash2 className="w-4 h-4" />
            </Button>
          </div>
        </DialogHeader>

        <div className="flex-1 overflow-y-auto px-6 pb-6">
          <div className="space-y-4">
            {/* 图片 */}
            <div className="aspect-square rounded-lg bg-muted overflow-hidden">
              {item.image_url ? (
                <img
                  src={item.image_url}
                  alt={item.name}
                  className="w-full h-full object-cover"
                />
              ) : (
                <div className="w-full h-full flex items-center justify-center">
                  <div className="text-center text-muted-foreground">
                    <Package className="w-16 h-16 mx-auto mb-2" />
                    <p className="text-sm">暂无图片</p>
                  </div>
                </div>
              )}
            </div>

            {/* 生成按钮 */}
            <div className="space-y-2">
              <div className="flex gap-2">
                {!item.image_generated ? (
                  <Button
                    className="flex-1"
                    onClick={() => onGenerateImage(item.name)}
                    disabled={generatingImageFor === item.name}
                  >
                    {generatingImageFor === item.name ? (
                      <>
                        <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                        生成中...
                      </>
                    ) : (
                      <>
                        <ImageIcon className="w-4 h-4 mr-2" />
                        生成图片
                      </>
                    )}
                  </Button>
                ) : (
                  // 已有图片时显示修改按钮
                  <Button
                    variant="outline"
                    className="flex-1"
                    onClick={onStartRegenerate}
                    disabled={regeneratingImageFor === item.name}
                  >
                    {regeneratingImageFor === item.name ? (
                      <>
                        <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                        修改中...
                      </>
                    ) : (
                      <>
                        <Pencil className="w-4 h-4 mr-2" />
                        修改图片
                      </>
                    )}
                  </Button>
                )}
                {!item.description_generated && !item.description && (
                  <Button
                    variant="outline"
                    className="flex-1"
                    onClick={() => onGenerateDescription(item.name)}
                    disabled={generatingDescriptionFor === item.name}
                  >
                    {generatingDescriptionFor === item.name ? (
                      <>
                        <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                        生成中...
                      </>
                    ) : (
                      <>
                        <FileText className="w-4 h-4 mr-2" />
                        生成描述
                      </>
                    )}
                  </Button>
                )}
              </div>

              {/* 修改图片输入框 */}
              {showRegenerateInput && regenerateType === "item" && item.image_generated && (
                <div className="space-y-2">
                  <Textarea
                    placeholder="输入修改意见，例如：颜色改深一点、增加细节..."
                    value={regenerateFeedback}
                    onChange={(e) => onRegenerateFeedbackChange(e.target.value)}
                    className="min-h-[80px] resize-none"
                    disabled={regeneratingImageFor === item.name}
                  />
                  <div className="flex gap-2">
                    <Button
                      variant="outline"
                      className="flex-1"
                      onClick={onCancelRegenerate}
                      disabled={regeneratingImageFor === item.name}
                    >
                      <X className="w-4 h-4 mr-1" />
                      取消
                    </Button>
                    <Button
                      className="flex-1"
                      onClick={onSubmitRegenerate}
                      disabled={!regenerateFeedback.trim() || regeneratingImageFor === item.name}
                    >
                      {regeneratingImageFor === item.name ? (
                        <>
                          <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                          修改中...
                        </>
                      ) : (
                        <>
                          <Pencil className="w-4 h-4 mr-2" />
                          提交修改
                        </>
                      )}
                    </Button>
                  </div>
                </div>
              )}
            </div>

            {/* 详细信息 */}
            <div className="space-y-3 text-sm">
              {item.description && (
                <div>
                  <span className="font-medium">描述：</span>
                  <p className="text-muted-foreground mt-1">
                    {item.description}
                  </p>
                </div>
              )}
              {item.acquired_context && (
                <div>
                  <span className="font-medium">获得场景：</span>
                  <p className="text-muted-foreground mt-1">
                    {item.acquired_context}
                  </p>
                </div>
              )}
              <div>
                <span className="font-medium">获得时间：</span>
                <span className="text-muted-foreground">
                  第 {item.acquired_week + 1} 周
                </span>
              </div>
            </div>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
