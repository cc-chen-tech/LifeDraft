"use client";

import * as React from "react";
import { flushSync } from "react-dom";
import {
  BookOpen,
  ChevronDown,
  FileText,
  History,
  Home,
  ImageIcon,
  Loader2,
  MessageCircle,
  MoreHorizontal,
  Pencil,
  RotateCcw,
  Save,
  Settings,
  X,
} from "lucide-react";

import { MobileActionDock } from "@/components/story101/MobileActionDock";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";

export type PlayConstraintLevel = "fast" | "expert" | "master";

export interface PlayNarrativeStyleOption {
  style_id: string;
  style_name: string;
  description: string;
}

export interface PlayToolsProps {
  isSaving: boolean;
  isStoryBusy: boolean;
  isViewingHistory: boolean;
  constraintLevel: PlayConstraintLevel;
  narrativeStyleId: string;
  narrativeStyles: readonly PlayNarrativeStyleOption[];
  narrativeStylesLoading?: boolean;
  rewriteDisabled?: boolean;
  rewriteDisabledReason?: string;
  enableSceneImage: boolean;
  onSave: () => void;
  onOpenHistory: () => void;
  onOpenCollection: () => void;
  onOpenChat: () => void;
  onOpenRewrite: () => void;
  onOpenSummary: () => void;
  onRegenerate: () => void;
  onHome: () => void;
  onConstraintLevelChange: (level: PlayConstraintLevel) => void;
  onNarrativeStyleChange: (styleId: string) => void;
  onSceneImageChange: (enabled: boolean) => void;
  onRequestNarrativeStyles?: () => void;
  onOpenTools?: () => void;
  onToolsOpenChange?: (open: boolean) => void;
  isDailyTimeline?: boolean;
  className?: string;
}

const PLAY_TOOLS_SHEET_ID = "play-tools-sheet";

const QUALITY_OPTIONS: readonly {
  value: PlayConstraintLevel;
  label: string;
}[] = [
  { value: "fast", label: "快速" },
  { value: "expert", label: "专家" },
  { value: "master", label: "大师" },
];

const toolRowClassName =
  "w-full justify-start rounded-none border-b border-[var(--border-default)] px-0";

export function PlayTools({
  isSaving,
  isStoryBusy,
  isViewingHistory,
  constraintLevel,
  narrativeStyleId,
  narrativeStyles,
  narrativeStylesLoading = false,
  rewriteDisabled = false,
  rewriteDisabledReason,
  enableSceneImage,
  onSave,
  onOpenHistory,
  onOpenCollection,
  onOpenChat,
  onOpenRewrite,
  onOpenSummary,
  onRegenerate,
  onHome,
  onConstraintLevelChange,
  onNarrativeStyleChange,
  onSceneImageChange,
  onRequestNarrativeStyles,
  onOpenTools,
  onToolsOpenChange,
  isDailyTimeline = false,
  className,
}: PlayToolsProps) {
  const [toolsOpen, setToolsOpen] = React.useState(false);
  const [stylesOpen, setStylesOpen] = React.useState(false);
  const desktopTriggerRef = React.useRef<HTMLButtonElement>(null);
  const mobileMoreTriggerRef = React.useRef<HTMLButtonElement>(null);
  const returnFocusRef = React.useRef<HTMLButtonElement | null>(null);
  const restoreFocusOnCloseRef = React.useRef(true);
  const previousRestrictionsRef = React.useRef({
    isStoryBusy,
    isViewingHistory,
  });
  const storyToolsDisabled = isStoryBusy || isViewingHistory;
  const unavailableDescriptionId = storyToolsDisabled
    ? "play-story-tools-unavailable"
    : undefined;
  const rewriteUnavailableDescriptionId =
    !storyToolsDisabled && rewriteDisabled
      ? "play-rewrite-unavailable"
      : undefined;

  const handleOpenChange = React.useCallback(
    (open: boolean) => {
      if (open) {
        onOpenTools?.();
      } else {
        setStylesOpen(false);
      }
      onToolsOpenChange?.(open);
      setToolsOpen(open);
    },
    [onOpenTools, onToolsOpenChange],
  );

  const handleStylesOpenChange = React.useCallback(
    (open: boolean) => {
      setStylesOpen(open);
      if (open) onRequestNarrativeStyles?.();
    },
    [onRequestNarrativeStyles],
  );

  const openTools = React.useCallback(
    (trigger: HTMLButtonElement | null) => {
      returnFocusRef.current = trigger;
      restoreFocusOnCloseRef.current = true;
      handleOpenChange(true);
    },
    [handleOpenChange],
  );

  const closeBefore = React.useCallback((action: () => void) => {
    const returnTarget = returnFocusRef.current;
    restoreFocusOnCloseRef.current = false;
    onToolsOpenChange?.(false);
    flushSync(() => setToolsOpen(false));
    returnTarget?.focus();
    action();
  }, [onToolsOpenChange]);

  React.useEffect(() => {
    const previous = previousRestrictionsRef.current;
    const becameRestricted =
      (isStoryBusy && !previous.isStoryBusy) ||
      (isViewingHistory && !previous.isViewingHistory);

    previousRestrictionsRef.current = { isStoryBusy, isViewingHistory };

    if (becameRestricted) {
      onToolsOpenChange?.(false);
      setToolsOpen(false);
    }
  }, [isStoryBusy, isViewingHistory, onToolsOpenChange]);

  const mobileActions = React.useMemo(
    () => [
      {
        id: "save",
        label: isSaving ? "保存中" : "保存",
        icon: isSaving ? (
          <Loader2 className="h-4 w-4 animate-spin" />
        ) : (
          <Save className="h-4 w-4" />
        ),
        onSelect: onSave,
        disabled: isSaving,
        busy: isSaving,
      },
      {
        id: "history",
        label: "历史",
        icon: <History className="h-4 w-4" />,
        onSelect: onOpenHistory,
      },
      {
        id: "collection",
        label: "收集",
        icon: <BookOpen className="h-4 w-4" />,
        onSelect: onOpenCollection,
      },
      {
        id: "more",
        label: "更多",
        icon: <MoreHorizontal className="h-4 w-4" />,
        onSelect: () => openTools(mobileMoreTriggerRef.current),
        buttonRef: mobileMoreTriggerRef,
        controls: PLAY_TOOLS_SHEET_ID,
        expanded: toolsOpen,
      },
    ],
    [
      isSaving,
      onOpenCollection,
      onOpenHistory,
      onSave,
      openTools,
      toolsOpen,
    ],
  );

  return (
    <div className={className} data-slot="play-tools">
      <Button
        ref={desktopTriggerRef}
        type="button"
        variant="chrome"
        size="touch"
        className="hidden md:inline-flex"
        aria-controls={PLAY_TOOLS_SHEET_ID}
        aria-expanded={toolsOpen}
        onClick={() => openTools(desktopTriggerRef.current)}
      >
        <Settings className="h-4 w-4" />
        打开工具
      </Button>

      <MobileActionDock actions={mobileActions} />

      <Sheet modal open={toolsOpen} onOpenChange={handleOpenChange}>
        <SheetContent
          id={PLAY_TOOLS_SHEET_ID}
          side="bottom"
          showCloseButton={false}
          overlayClassName="z-[60]"
          className="z-[61] max-h-[88dvh] gap-0 overflow-y-auto rounded-t-[var(--radius-overlay)] border-[var(--border-default)] bg-[var(--surface-overlay)] p-0"
          onCloseAutoFocus={(event) => {
            event.preventDefault();
            if (restoreFocusOnCloseRef.current) {
              returnFocusRef.current?.focus();
            }
          }}
        >
          <SheetHeader className="border-b border-[var(--border-default)] px-5 py-4 pr-16 text-left">
            <SheetTitle>游戏工具</SheetTitle>
            <SheetDescription>
              管理当前故事、阅读工具与叙事设置
            </SheetDescription>
          </SheetHeader>
          <Button
            type="button"
            variant="quiet"
            size="icon-touch"
            className="absolute right-3 top-3"
            aria-label="关闭工具"
            onClick={() => handleOpenChange(false)}
          >
            <X className="h-4 w-4" />
          </Button>

          <div className="grid gap-0 px-5 pb-[max(1.25rem,var(--safe-area-inset-bottom))]">
            <section aria-labelledby="play-tools-current-heading" className="py-5">
              <h3
                id="play-tools-current-heading"
                className="mb-2 text-sm font-medium text-[var(--text-primary)]"
              >
                当前人生
              </h3>
              <div className="border-t border-[var(--border-default)]">
                <Button
                  type="button"
                  variant="quiet"
                  size="touch"
                  className={toolRowClassName}
                  disabled={isSaving}
                  aria-busy={isSaving}
                  onClick={() => closeBefore(onSave)}
                >
                  <Save className="h-4 w-4" />
                  保存游戏
                </Button>
                <Button
                  type="button"
                  variant="quiet"
                  size="touch"
                  className={toolRowClassName}
                  onClick={() => closeBefore(onOpenHistory)}
                >
                  <History className="h-4 w-4" />
                  打开历史回顾
                </Button>
                <Button
                  type="button"
                  variant="quiet"
                  size="touch"
                  className={toolRowClassName}
                  onClick={() => closeBefore(onOpenCollection)}
                >
                  <BookOpen className="h-4 w-4" />
                  打开收集
                </Button>
              </div>
            </section>

            <section
              aria-labelledby="play-tools-story-heading"
              className="border-t border-[var(--border-default)] py-5"
            >
              <h3
                id="play-tools-story-heading"
                className="mb-2 text-sm font-medium text-[var(--text-primary)]"
              >
                故事工具
              </h3>
              {storyToolsDisabled && (
                <p
                  id={unavailableDescriptionId}
                  className="mb-3 text-xs text-[var(--text-secondary)]"
                >
                  {isViewingHistory
                    ? "历史回顾为只读模式"
                    : "故事生成完成后可使用这些工具"}
                </p>
              )}
              {rewriteUnavailableDescriptionId && (
                <p
                  id={rewriteUnavailableDescriptionId}
                  className="mb-3 text-xs text-[var(--text-secondary)]"
                >
                  {rewriteDisabledReason ?? "当前故事暂时不能改写"}
                </p>
              )}
              <div className="border-t border-[var(--border-default)]">
                <Button
                  type="button"
                  variant="quiet"
                  size="touch"
                  className={toolRowClassName}
                  disabled={storyToolsDisabled}
                  aria-describedby={unavailableDescriptionId}
                  onClick={() => closeBefore(onOpenChat)}
                >
                  <MessageCircle className="h-4 w-4" />
                  打开剧情助手
                </Button>
                <Button
                  type="button"
                  variant="quiet"
                  size="touch"
                  className={toolRowClassName}
                  disabled={storyToolsDisabled || rewriteDisabled}
                  aria-describedby={
                    unavailableDescriptionId ?? rewriteUnavailableDescriptionId
                  }
                  onClick={() => closeBefore(onOpenRewrite)}
                >
                  <Pencil className="h-4 w-4" />
                  {isDailyTimeline ? "改写今天" : "改写当前故事"}
                </Button>
                <Button
                  type="button"
                  variant="quiet"
                  size="touch"
                  className={toolRowClassName}
                  disabled={storyToolsDisabled}
                  aria-describedby={unavailableDescriptionId}
                  onClick={() => closeBefore(onOpenSummary)}
                >
                  <FileText className="h-4 w-4" />
                  生成人生总结
                </Button>
                <Button
                  type="button"
                  variant="quiet"
                  size="touch"
                  className={toolRowClassName}
                  disabled={storyToolsDisabled}
                  aria-describedby={unavailableDescriptionId}
                  onClick={() => closeBefore(onRegenerate)}
                >
                  <RotateCcw className="h-4 w-4" />
                  {isDailyTimeline ? "重新生成今天" : "重新生成当前故事"}
                </Button>
              </div>
            </section>

            <section
              aria-labelledby="play-tools-settings-heading"
              className="border-t border-[var(--border-default)] py-5"
            >
              <h3
                id="play-tools-settings-heading"
                className="mb-4 text-sm font-medium text-[var(--text-primary)]"
              >
                叙事设置
              </h3>

              <fieldset>
                <legend className="text-sm text-[var(--text-primary)]">
                  叙事质量
                </legend>
                <div className="mt-2 border-t border-[var(--border-default)]">
                  {QUALITY_OPTIONS.map((option) => (
                    <label
                      key={option.value}
                      className="flex min-h-11 cursor-pointer items-center gap-3 border-b border-[var(--border-default)] text-sm"
                    >
                      <input
                        type="radio"
                        name="play-constraint-level"
                        value={option.value}
                        checked={constraintLevel === option.value}
                        onChange={() => onConstraintLevelChange(option.value)}
                      />
                      <span>{option.label}</span>
                    </label>
                  ))}
                </div>
              </fieldset>

              <fieldset className="mt-5">
                <legend className="sr-only">叙事风格</legend>
                <Button
                  type="button"
                  variant="quiet"
                  size="touch"
                  className="w-full justify-between rounded-none border-y border-[var(--border-default)] px-0"
                  aria-expanded={stylesOpen}
                  aria-controls="play-narrative-style-options"
                  onClick={() => handleStylesOpenChange(!stylesOpen)}
                >
                  叙事风格
                  <ChevronDown
                    aria-hidden="true"
                    className={cn(
                      "h-4 w-4 transition-transform",
                      stylesOpen && "rotate-180",
                    )}
                  />
                </Button>
                {stylesOpen && (
                  <div
                    id="play-narrative-style-options"
                    className="border-t border-[var(--border-default)]"
                  >
                  {narrativeStylesLoading ? (
                    <p className="py-3 text-sm text-[var(--text-secondary)]" role="status">
                      正在加载叙事风格
                    </p>
                  ) : narrativeStyles.length > 0 ? (
                    narrativeStyles.map((style) => (
                      <label
                        key={style.style_id}
                        className="flex min-h-11 cursor-pointer items-start gap-3 border-b border-[var(--border-default)] py-2 text-sm"
                      >
                        <input
                          type="radio"
                          name="play-narrative-style"
                          value={style.style_id}
                          checked={narrativeStyleId === style.style_id}
                          className="mt-1"
                          onChange={() => onNarrativeStyleChange(style.style_id)}
                        />
                        <span className="min-w-0">
                          <span className="block text-[var(--text-primary)]">
                            {style.style_name}
                          </span>
                          {style.description && (
                            <span className="block text-xs leading-5 text-[var(--text-secondary)]">
                              {style.description}
                            </span>
                          )}
                        </span>
                      </label>
                    ))
                  ) : (
                    <p className="py-3 text-sm text-[var(--text-secondary)]">
                      暂无可选叙事风格
                    </p>
                  )}
                  </div>
                )}
              </fieldset>

              <label className="mt-5 flex min-h-11 cursor-pointer items-center gap-3 border-y border-[var(--border-default)] text-sm">
                <input
                  type="checkbox"
                  aria-label="场景插画"
                  checked={enableSceneImage}
                  onChange={(event) => onSceneImageChange(event.currentTarget.checked)}
                />
                <ImageIcon className="h-4 w-4" aria-hidden="true" />
                <span>场景插画</span>
              </label>
            </section>

            <section
              aria-labelledby="play-tools-other-heading"
              className="border-t border-[var(--border-default)] py-5"
            >
              <h3
                id="play-tools-other-heading"
                className="mb-2 text-sm font-medium text-[var(--text-primary)]"
              >
                其他
              </h3>
              <div className="border-t border-[var(--border-default)]">
                <Button
                  type="button"
                  variant="quiet"
                  size="touch"
                  className={toolRowClassName}
                  onClick={() => closeBefore(onHome)}
                >
                  <Home className="h-4 w-4" />
                  返回首页
                </Button>
              </div>
            </section>
          </div>
        </SheetContent>
      </Sheet>
    </div>
  );
}
