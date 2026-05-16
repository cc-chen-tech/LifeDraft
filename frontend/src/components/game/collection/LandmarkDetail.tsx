"use client";

import { useState, useCallback } from "react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import {
  MapPin,
  Image as ImageIcon,
  FileText,
  Loader2,
  Sparkles,
  Trash2,
} from "lucide-react";
import { LANDMARK_CATEGORY_LABELS, IMPORTANCE_LABELS } from "./types";
import type { LandmarkDetailProps } from "./types";

/**
 * 地标详情对话框 - 显示地标详细信息和操作按钮
 */
export function LandmarkDetail({
  landmark,
  onClose,
  onGenerateImage,
  onGenerateDescription,
  onOpenDeleteConfirm,
  generatingImageFor,
  generatingDescriptionFor,
  isDeleting,
}: LandmarkDetailProps) {
  const [imageError, setImageError] = useState(false);
  const handleImageError = useCallback(() => setImageError(true), []);

  if (!landmark) return null;

  return (
    <Dialog open={!!landmark} onOpenChange={onClose}>
      <DialogContent className="max-w-md h-[85vh] flex flex-col p-0 gap-0">
        <DialogHeader className="px-6 pt-6 pb-2 flex-shrink-0">
          <div className="flex items-start justify-between">
            <div>
              <DialogTitle className="flex items-center gap-2">
                <MapPin className="w-5 h-5" />
                {landmark.name}
                {landmark.is_key_location && (
                  <Sparkles className="w-4 h-4 text-amber-500" />
                )}
              </DialogTitle>
              <DialogDescription>
                {LANDMARK_CATEGORY_LABELS[landmark.category] || landmark.category}
                · {IMPORTANCE_LABELS[landmark.importance]?.label || "普通"}
              </DialogDescription>
            </div>
            {/* 删除按钮 */}
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8 text-destructive hover:text-destructive hover:bg-destructive/10"
              onClick={() => onOpenDeleteConfirm(landmark.name)}
              disabled={isDeleting}
            >
              <Trash2 className="w-4 h-4" />
            </Button>
          </div>
        </DialogHeader>

        <div className="flex-1 overflow-y-auto px-6 pb-6">
          <div className="space-y-4">
            {/* 图片 */}
            <div className="aspect-video rounded-lg bg-muted overflow-hidden">
              {landmark.image_url && !imageError ? (
                <img
                  src={landmark.image_url}
                  alt={landmark.name}
                  className="w-full h-full object-cover"
                  loading="lazy"
                  onError={handleImageError}
                />
              ) : (
                <div className="w-full h-full flex items-center justify-center">
                  <div className="text-center text-muted-foreground">
                    <MapPin className="w-16 h-16 mx-auto mb-2" />
                    <p className="text-sm">暂无图片</p>
                  </div>
                </div>
              )}
            </div>

            {/* 生成按钮 */}
            <div className="flex gap-2">
              {!landmark.image_generated ? (
                <Button
                  className="flex-1"
                  onClick={() => onGenerateImage(landmark.name)}
                  disabled={generatingImageFor === landmark.name}
                >
                  {generatingImageFor === landmark.name ? (
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
              ) : null}
              {!landmark.description && (
                <Button
                  variant="outline"
                  className="flex-1"
                  onClick={() => onGenerateDescription(landmark.name)}
                  disabled={generatingDescriptionFor === landmark.name}
                >
                  {generatingDescriptionFor === landmark.name ? (
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

            {/* 详细信息 */}
            <div className="space-y-3 text-sm">
              {landmark.description && (
                <div>
                  <span className="font-medium">描述：</span>
                  <p className="text-muted-foreground mt-1">
                    {landmark.description}
                  </p>
                </div>
              )}
              {landmark.context && (
                <div>
                  <span className="font-medium">场景：</span>
                  <p className="text-muted-foreground mt-1">
                    {landmark.context}
                  </p>
                </div>
              )}
              <div className="flex gap-4">
                <div>
                  <span className="font-medium">首次出现：</span>
                  <span className="text-muted-foreground">
                    第 {landmark.first_appear_week + 1} 周
                  </span>
                </div>
                <div>
                  <span className="font-medium">出现次数：</span>
                  <span className="text-muted-foreground">
                    {landmark.appear_count} 次
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
