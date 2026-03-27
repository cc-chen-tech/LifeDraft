"use client";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import {
  User,
  Image as ImageIcon,
  Loader2,
  Pencil,
  X,
  Trash2,
} from "lucide-react";
import type { CharacterDetailProps } from "./types";

/**
 * 人物详情对话框 - 显示人物详细信息和操作按钮
 */
export function CharacterDetail({
  character,
  onClose,
  onGenerateImage,
  onStartRegenerate,
  onCancelRegenerate,
  onSubmitRegenerate,
  onOpenDeleteConfirm,
  generatingImageFor,
  regeneratingImageFor,
  showRegenerateInput,
  regenerateType,
  regenerateFeedback,
  onRegenerateFeedbackChange,
  isDeleting,
}: CharacterDetailProps) {
  if (!character) return null;

  return (
    <Dialog open={!!character} onOpenChange={onClose}>
      <DialogContent className="max-w-md h-[85vh] flex flex-col p-0 gap-0">
        <DialogHeader className="px-6 pt-6 pb-2 flex-shrink-0">
          <div className="flex items-start justify-between">
            <div>
              <DialogTitle className="flex items-center gap-2">
                <User className="w-5 h-5" />
                {character.name}
              </DialogTitle>
              <DialogDescription>
                {character.role || "故事中的人物"}
              </DialogDescription>
            </div>
            {/* 删除按钮 */}
            {character.role !== "主角" && (
              <Button
                variant="ghost"
                size="icon"
                className="h-8 w-8 text-destructive hover:text-destructive hover:bg-destructive/10"
                onClick={() => onOpenDeleteConfirm(character.name)}
                disabled={isDeleting}
              >
                <Trash2 className="w-4 h-4" />
              </Button>
            )}
          </div>
        </DialogHeader>

        <div className="flex-1 overflow-y-auto px-6 pb-6">
          <div className="space-y-4">
            {/* 图片 - 使用 object-top 确保显示头部 */}
            <div className="aspect-[3/4] rounded-lg bg-muted overflow-hidden">
              {character.image_url ? (
                <img
                  src={character.image_url}
                  alt={character.name}
                  className="w-full h-full object-cover object-top"
                />
              ) : (
                <div className="w-full h-full flex items-center justify-center">
                  <div className="text-center text-muted-foreground">
                    <User className="w-16 h-16 mx-auto mb-2" />
                    <p className="text-sm">暂无图片</p>
                  </div>
                </div>
              )}
            </div>

            {/* 生成按钮 */}
            {!character.image_generated ? (
              <Button
                className="w-full"
                onClick={() => onGenerateImage(character.name)}
                disabled={generatingImageFor === character.name}
              >
                {generatingImageFor === character.name ? (
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
              <div className="space-y-2">
                {/* 已有图片时显示修改按钮 */}
                {!showRegenerateInput || regenerateType !== "character" ? (
                  <Button
                    variant="outline"
                    className="w-full"
                    onClick={onStartRegenerate}
                    disabled={regeneratingImageFor === character.name}
                  >
                    {regeneratingImageFor === character.name ? (
                      <>
                        <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                        修改中...
                      </>
                    ) : (
                      <>
                        <Pencil className="w-4 h-4 mr-2" />
                        修改画像
                      </>
                    )}
                  </Button>
                ) : (
                  // 修改输入框
                  <div className="space-y-2">
                    <Textarea
                      placeholder="输入修改意见，例如：头发变长一点、换一件蓝色衣服..."
                      value={regenerateFeedback}
                      onChange={(e) => onRegenerateFeedbackChange(e.target.value)}
                      className="min-h-[80px] resize-none"
                      disabled={regeneratingImageFor === character.name}
                    />
                    <div className="flex gap-2">
                      <Button
                        variant="outline"
                        className="flex-1"
                        onClick={onCancelRegenerate}
                        disabled={regeneratingImageFor === character.name}
                      >
                        <X className="w-4 h-4 mr-1" />
                        取消
                      </Button>
                      <Button
                        className="flex-1"
                        onClick={onSubmitRegenerate}
                        disabled={!regenerateFeedback.trim() || regeneratingImageFor === character.name}
                      >
                        {regeneratingImageFor === character.name ? (
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
            )}

            {/* 亲密度提示 */}
            {character.image_generated && character.affinity <= 50 && character.role !== "主角" && (
              <p className="text-xs text-muted-foreground text-center">
                亲密度需大于50才能修改画像
              </p>
            )}

            {/* 详细信息 */}
            <div className="space-y-3 text-sm">
              {character.description && (
                <div>
                  <span className="font-medium">描述：</span>
                  <p className="text-muted-foreground mt-1">
                    {character.description}
                  </p>
                </div>
              )}
              {character.age && (
                <div>
                  <span className="font-medium">年龄：</span>
                  <span className="text-muted-foreground">
                    {character.age} 岁
                  </span>
                </div>
              )}
              {character.occupation && (
                <div>
                  <span className="font-medium">职业：</span>
                  <span className="text-muted-foreground">
                    {character.occupation}
                  </span>
                </div>
              )}
              <div>
                <span className="font-medium">亲密度：</span>
                <span className="text-muted-foreground">
                  {character.affinity}/100
                </span>
              </div>
              {character.personality_traits.length > 0 && (
                <div>
                  <span className="font-medium">性格：</span>
                  <div className="flex flex-wrap gap-1 mt-1">
                    {character.personality_traits.map((trait, i) => (
                      <Badge key={i} variant="secondary" className="text-xs">
                        {trait}
                      </Badge>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
