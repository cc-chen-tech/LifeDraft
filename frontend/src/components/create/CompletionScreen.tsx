"use client";

import { useState, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from "@/components/ui/sheet";
import { SettingDisplay } from "@/components/game/SettingDisplay";
import { SettingFeedbackCard } from "./SettingFeedbackCard";
import { CREATION_STEPS } from "@/stores/useGameStore";
import {
  ArrowLeft,
  Loader2,
  Save,
  Play,
  Sparkles,
  ChevronDown,
  ChevronUp,
  Eye,
  RefreshCw,
  RotateCcw,
  User,
} from "lucide-react";

const STEP_LABELS: Record<string, string> = {
  era: "时代背景",
  age: "年龄阶段",
  gender: "性别",
  world: "世界观",
  portrait: "人物形象",
  family: "家庭背景",
  relationships: "人际关系",
  traits: "性格特征",
  wealth: "财富状况",
};

const AUTO_ADVANCE_STEPS = ["family", "relationships", "traits", "wealth"];

interface CompletionScreenProps {
  playerName: string;
  playerImages: Array<{ image_id: number; image_url: string }>;
  selectedImageIndex: number;
  characterSettings: Record<string, unknown>;
  isPresetLoaded: boolean;
  isGenerating: boolean;
  hasBasicInfo: boolean;
  showDetails: boolean;
  showPresetSheet: boolean;
  presetName: string;
  isSavingPreset: boolean;
  // Image regeneration
  isGeneratingImage: boolean;
  imageFeedback: string;
  onImageFeedbackChange: (feedback: string) => void;
  onRegenerateImage: () => Promise<void>;
  onRegenerateFreshImage: () => Promise<void>;
  showToast: (type: "success" | "error", message: string) => void;
  onSetShowDetails: (show: boolean) => void;
  onSetShowPresetSheet: (show: boolean) => void;
  onSetPresetName: (name: string) => void;
  onBack: () => void;
  onStartGame: () => Promise<void>;
  onSavePreset: () => Promise<void>;
  onRegenerateSetting: (stepKey: string, feedback: string) => Promise<void>;
}

export function CompletionScreen({
  playerName,
  playerImages,
  selectedImageIndex,
  characterSettings,
  isPresetLoaded,
  isGenerating,
  hasBasicInfo,
  showDetails,
  showPresetSheet,
  presetName,
  isSavingPreset,
  isGeneratingImage,
  imageFeedback,
  onImageFeedbackChange,
  onRegenerateImage,
  onRegenerateFreshImage,
  showToast,
  onSetShowDetails,
  onSetShowPresetSheet,
  onSetPresetName,
  onBack,
  onStartGame,
  onSavePreset,
  onRegenerateSetting,
}: CompletionScreenProps) {
  const [isGoingBack, setIsGoingBack] = useState(false);
  const [isRegeneratingFresh, setIsRegeneratingFresh] = useState(false);
  const [isRegeneratingImage, setIsRegeneratingImage] = useState(false);
  const [imageError, setImageError] = useState(false);

  const handleImageError = useCallback(() => {
    setImageError(true);
  }, []);

  const handleBack = async () => {
    setIsGoingBack(true);
    try {
      await onBack();
    } finally {
      setIsGoingBack(false);
    }
  };

  const handleRegenerateFresh = async () => {
    setIsRegeneratingFresh(true);
    try {
      await onRegenerateFreshImage();
    } catch (err) {
      showToast("error", String(err) || "重新生成失败");
    } finally {
      setIsRegeneratingFresh(false);
    }
  };

  const handleRegenerateImage = async () => {
    setIsRegeneratingImage(true);
    try {
      await onRegenerateImage();
      onImageFeedbackChange("");
    } catch (err) {
      showToast("error", String(err) || "重新生成失败");
    } finally {
      setIsRegeneratingImage(false);
    }
  };

  return (
    <div className="min-h-screen bg-background animate-page-enter flex flex-col">
      <header className="sticky top-0 z-40 bg-background/80 backdrop-blur-sm border-b border-border">
        <div className="max-w-2xl mx-auto px-4 h-14 flex items-center justify-between">
          <Button
            variant="ghost"
            size="sm"
            onClick={handleBack}
            disabled={isGoingBack}
            data-testid="back-button"
          >
            {isGoingBack ? (
              <Loader2 className="w-4 h-4 mr-1 animate-spin" />
            ) : (
              <ArrowLeft className="w-4 h-4 mr-1" />
            )}
            返回修改
          </Button>
          <span className="text-sm text-muted-foreground">角色创建完成</span>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => onSetShowPresetSheet(true)}
          >
            <Save className="w-4 h-4 mr-1" />
            保存为预设
          </Button>
        </div>
      </header>

      {/* Centered completion message */}
      <main className="flex-1 flex flex-col items-center justify-center px-4 py-8">
        {/* 主角图片展示 + 重新生成 */}
        {playerImages.length > 0 && (
          <div className="mb-6 flex flex-col items-center w-full max-w-xs">
            {isGeneratingImage ? (
              <div className="w-32 h-48 bg-secondary rounded-lg flex items-center justify-center">
                <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
              </div>
            ) : !imageError ? (
              <img
                src={playerImages[selectedImageIndex]?.image_url || playerImages[0]?.image_url}
                alt={playerName || "主角"}
                className="w-32 h-48 object-cover rounded-lg border-2 border-primary/30 shadow-lg"
                onError={handleImageError}
              />
            ) : (
              <div className="w-32 h-48 bg-secondary rounded-lg flex flex-col items-center justify-center border-2 border-primary/30 shadow-lg">
                <User className="w-8 h-8 text-muted-foreground mb-2" />
                <span className="text-xs text-muted-foreground">图片加载失败</span>
              </div>
            )}
            <span className="text-sm font-medium text-foreground mt-2">{playerName}</span>

            {/* 图片反馈重新生成 */}
            {!isGeneratingImage && (
              <div className="w-full mt-3 space-y-2">
                <Input
                  value={imageFeedback}
                  onChange={(e) => onImageFeedbackChange(e.target.value)}
                  placeholder="不满意？描述你想要的修改..."
                  className="bg-secondary border-border text-sm h-9"
                />
                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    className="flex-1 h-8 text-xs"
                    disabled={!imageFeedback.trim() || isRegeneratingImage}
                    title={!imageFeedback.trim() ? "请先输入修改意见" : undefined}
                    onClick={handleRegenerateImage}
                  >
                    {isRegeneratingImage ? (
                      <Loader2 className="w-3 h-3 mr-1 animate-spin" />
                    ) : (
                      <RefreshCw className="w-3 h-3 mr-1" />
                    )}
                    根据意见修改
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-8 text-xs text-muted-foreground"
                    disabled={isRegeneratingFresh}
                    onClick={handleRegenerateFresh}
                  >
                    {isRegeneratingFresh ? (
                      <Loader2 className="w-3 h-3 mr-1 animate-spin" />
                    ) : (
                      <RotateCcw className="w-3 h-3 mr-1" />
                    )}
                    完全重生成
                  </Button>
                </div>
              </div>
            )}
          </div>
        )}
        
        <Sparkles className="w-14 h-14 text-primary mb-4" />
        <h2 className="text-xl font-bold text-foreground mb-1">角色设定完成</h2>
        <p className="text-sm text-muted-foreground text-center mb-6">
          {isPresetLoaded ? "已加载预设角色背景" : "已为你自动生成角色背景"}
        </p>

        {/* View details toggle */}
        <Button
          variant="ghost"
          size="sm"
          className="mb-4 text-muted-foreground"
          onClick={() => onSetShowDetails(!showDetails)}
        >
          <Eye className="w-4 h-4 mr-1" />
          查看设定详情
          {showDetails ? (
            <ChevronUp className="w-4 h-4 ml-1" />
          ) : (
            <ChevronDown className="w-4 h-4 ml-1" />
          )}
        </Button>

        {/* Collapsible details */}
        {showDetails && (
          <div className="w-full max-w-lg space-y-4 mb-6 animate-page-enter">
            {AUTO_ADVANCE_STEPS.map((step) => {
              const data = characterSettings[step];
              if (!data) return null;
              return (
                <SettingFeedbackCard
                  key={step}
                  stepKey={step}
                  stepLabel={STEP_LABELS[step]}
                  data={data as Record<string, unknown>}
                  onRegenerate={(feedback) => onRegenerateSetting(step, feedback)}
                />
              );
            })}
          </div>
        )}

        {/* Action buttons */}
        <div className="flex flex-col gap-3 w-full max-w-xs">
          <Button
            className="w-full touch-target h-12"
            onClick={onStartGame}
            disabled={isGenerating || !hasBasicInfo}
          >
            {isGenerating ? (
              <Loader2 className="w-4 h-4 mr-2 animate-spin" />
            ) : (
              <Play className="w-4 h-4 mr-2" />
            )}
            {hasBasicInfo ? "开始游戏" : "请先输入角色姓名"}
          </Button>
          <Button
            variant="outline"
            className="w-full touch-target"
            onClick={() => onSetShowPresetSheet(true)}
          >
            <Save className="w-4 h-4 mr-1" />
            保存为预设
          </Button>
        </div>
      </main>

      {/* Save preset sheet */}
      <Sheet open={showPresetSheet} onOpenChange={onSetShowPresetSheet}>
        <SheetContent side="bottom" className="bg-card border-t border-border">
          <SheetHeader>
            <SheetTitle className="text-foreground">保存角色预设</SheetTitle>
            <SheetDescription className="text-muted-foreground">
              保存当前角色设定以便下次使用
            </SheetDescription>
          </SheetHeader>
          <div className="space-y-4 mt-4">
            <Input
              value={presetName}
              onChange={(e) => onSetPresetName(e.target.value)}
              placeholder="预设名称"
              className="bg-secondary border-border h-12"
              autoFocus
            />
            <Button
              className="w-full touch-target"
              disabled={!presetName.trim() || isSavingPreset}
              onClick={onSavePreset}
            >
              {isSavingPreset && (
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
              )}
              确认保存
            </Button>
          </div>
        </SheetContent>
      </Sheet>
    </div>
  );
}
