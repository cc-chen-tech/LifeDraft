"use client";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import {
  User,
  Package,
  MapPin,
  Wand2,
  Loader2,
  AlertCircle,
} from "lucide-react";
import type { RecognizedEntity } from "@/lib/types";
import type { RecognizeDialogProps } from "./types";

/**
 * 智能识别对话框 - 从历史故事中识别重复出现的物品、人物、地点
 */
export function RecognizeDialog({
  open,
  onClose,
  onCloseAutoFocus,
  onSubmit,
  isRecognizing,
  isLoading,
  recognizedEntities,
  selectedItems,
  selectedCharacters,
  selectedLandmarks,
  onToggleItemSelection,
  onToggleCharacterSelection,
  onToggleLandmarkSelection,
}: RecognizeDialogProps) {
  const totalSelected = selectedItems.length + selectedCharacters.length + selectedLandmarks.length;

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent
        className="z-[81] max-w-lg max-h-[80vh] flex flex-col"
        overlayClassName="z-[80]"
        onCloseAutoFocus={onCloseAutoFocus}
      >
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Wand2 className="w-5 h-5" />
            智能识别
          </DialogTitle>
          <DialogDescription>
            从历史故事中识别重复出现的物品、人物、地点
          </DialogDescription>
        </DialogHeader>

        <div className="flex-1 overflow-y-auto py-4">
          {isRecognizing && !recognizedEntities ? (
            <div className="flex flex-col items-center justify-center py-8 gap-3">
              <Loader2 className="w-8 h-8 animate-spin text-primary" />
              <p className="text-sm text-muted-foreground">正在分析故事历史...</p>
            </div>
          ) : recognizedEntities ? (
            <div className="space-y-4">
              {/* 物品 */}
              {recognizedEntities.items && recognizedEntities.items.length > 0 && (
                <div>
                  <h4 className="font-medium mb-2 flex items-center gap-2">
                    <Package className="w-4 h-4" />
                    识别到的物品 ({recognizedEntities.items.length})
                  </h4>
                  <div className="space-y-2">
                    {recognizedEntities.items.map((item: RecognizedEntity) => (
                      <label
                        key={item.name}
                        className="flex items-start gap-2 p-2 rounded border hover:bg-accent cursor-pointer"
                      >
                        <input
                          type="checkbox"
                          className="mt-1"
                          checked={selectedItems.some((i) => i.name === item.name)}
                          onChange={() => onToggleItemSelection(item)}
                        />
                        <div className="flex-1 text-sm">
                          <div className="font-medium">{item.name}</div>
                          <div className="text-muted-foreground text-xs">
                            出现 {item.appear_count} 次 · {item.description.slice(0, 50)}...
                          </div>
                        </div>
                      </label>
                    ))}
                  </div>
                </div>
              )}

              {/* 人物 */}
              {recognizedEntities.characters && recognizedEntities.characters.length > 0 && (
                <div>
                  <h4 className="font-medium mb-2 flex items-center gap-2">
                    <User className="w-4 h-4" />
                    识别到的人物 ({recognizedEntities.characters.length})
                  </h4>
                  <div className="space-y-2">
                    {recognizedEntities.characters.map((char: RecognizedEntity) => (
                      <label
                        key={char.name}
                        className="flex items-start gap-2 p-2 rounded border hover:bg-accent cursor-pointer"
                      >
                        <input
                          type="checkbox"
                          className="mt-1"
                          checked={selectedCharacters.some((c) => c.name === char.name)}
                          onChange={() => onToggleCharacterSelection(char)}
                        />
                        <div className="flex-1 text-sm">
                          <div className="font-medium">{char.name}</div>
                          <div className="text-muted-foreground text-xs">
                            出现 {char.appear_count} 次 · {char.description.slice(0, 50)}...
                          </div>
                        </div>
                      </label>
                    ))}
                  </div>
                </div>
              )}

              {/* 地点 */}
              {recognizedEntities.landmarks && recognizedEntities.landmarks.length > 0 && (
                <div>
                  <h4 className="font-medium mb-2 flex items-center gap-2">
                    <MapPin className="w-4 h-4" />
                    识别到的地点 ({recognizedEntities.landmarks.length})
                  </h4>
                  <div className="space-y-2">
                    {recognizedEntities.landmarks.map((landmark: RecognizedEntity) => (
                      <label
                        key={landmark.name}
                        className="flex items-start gap-2 p-2 rounded border hover:bg-accent cursor-pointer"
                      >
                        <input
                          type="checkbox"
                          className="mt-1"
                          checked={selectedLandmarks.some((l) => l.name === landmark.name)}
                          onChange={() => onToggleLandmarkSelection(landmark)}
                        />
                        <div className="flex-1 text-sm">
                          <div className="font-medium">{landmark.name}</div>
                          <div className="text-muted-foreground text-xs">
                            出现 {landmark.appear_count} 次 · {landmark.description.slice(0, 50)}...
                          </div>
                        </div>
                      </label>
                    ))}
                  </div>
                </div>
              )}

              {/* 无结果提示 */}
              {recognizedEntities.items?.length === 0 &&
                recognizedEntities.characters?.length === 0 &&
                recognizedEntities.landmarks?.length === 0 && (
                  <div className="text-center py-8 text-muted-foreground">
                    <AlertCircle className="w-12 h-12 mx-auto mb-2 opacity-50" />
                    <p>未识别到新的实体</p>
                    <p className="text-xs mt-1">可能故事还不够长，或已有所有实体</p>
                  </div>
                )}
            </div>
          ) : (
            <div className="text-center py-8 text-muted-foreground">
              <AlertCircle className="w-12 h-12 mx-auto mb-2 opacity-50" />
              <p>未识别到新的实体</p>
              <p className="text-xs mt-1">可以稍后再试，或继续推进故事后重新识别</p>
            </div>
          )}
        </div>

        <div className="flex gap-2 pt-4 border-t">
          <Button variant="outline" onClick={onClose} className="flex-1">
            取消
          </Button>
          <Button
            onClick={onSubmit}
            disabled={(isRecognizing && !recognizedEntities) || isLoading || totalSelected === 0}
            className="flex-1"
          >
            {isRecognizing && !recognizedEntities ? (
              <>
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                分析中...
              </>
            ) : isLoading ? (
              <>
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                添加中...
              </>
            ) : (
              <>
                添加到收集
                {totalSelected > 0 && (
                  <span className="ml-1">
                    ({totalSelected})
                  </span>
                )}
              </>
            )}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
