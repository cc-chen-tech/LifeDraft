"use client";

import type { ComponentProps } from "react";
import { Button } from "@/components/ui/button";
import {
  Sheet,
  SheetClose,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from "@/components/ui/sheet";
import { ScrollArea } from "@/components/ui/scroll-area";
import { History, ChevronRight, Calendar, X } from "lucide-react";
import { cn } from "@/lib/utils";

/** 场景图片信息 */
export interface SceneImageInfo {
  scene_id: number;
  image_url: string;
  scene_description: string;
  stage?: string;
  created_at?: string;
}

/** 历史轮次数据结构 */
export interface RoundHistoryItem {
  week: number;
  round: number;
  summary?: string;
  event_description?: string;
  story_continuation?: string;
  choice?: string;
  effects?: Record<string, unknown>;
  date_info?: {
    date_string?: string;
    year?: number;
    month?: number;
  };
  /** 场景插画信息 */
  scene_image?: SceneImageInfo | null;
  day_index?: number;
  story_date?: string;
}

interface RoundHistoryDrawerProps {
  /** 是否打开抽屉 */
  open: boolean;
  /** 打开/关闭回调 */
  onOpenChange: (open: boolean) => void;
  /** 关闭后将焦点交还给打开抽屉的真实动作 */
  onCloseAutoFocus?: ComponentProps<typeof SheetContent>["onCloseAutoFocus"];
  /** 历史轮次数据 */
  roundHistory: RoundHistoryItem[];
  /** 当前选中的轮次索引 */
  selectedIndex: number | null;
  /** 选择轮次回调 */
  onSelect: (index: number) => void;
  /** 返回当前轮次回调 */
  onBackToCurrent: () => void;
  /** 是否正在查看历史（非当前轮次） */
  isViewingHistory: boolean;
}

const ROUND_NAMES = ["周一", "周中", "周末"];

export function RoundHistoryDrawer({
  open,
  onOpenChange,
  onCloseAutoFocus,
  roundHistory,
  selectedIndex,
  onSelect,
  onBackToCurrent,
  isViewingHistory,
}: RoundHistoryDrawerProps) {
  // 按周分组
  const groupedByWeek = roundHistory.reduce((acc, item, index) => {
    const week = item.week;
    if (!acc[week]) {
      acc[week] = [];
    }
    acc[week].push({ ...item, originalIndex: index });
    return acc;
  }, {} as Record<number, (RoundHistoryItem & { originalIndex: number })[]>);

  const sortedWeeks = Object.keys(groupedByWeek)
    .map(Number)
    .sort((a, b) => a - b);

  return (
    <Sheet modal open={open} onOpenChange={onOpenChange}>
      <SheetContent
        side="left"
        showCloseButton={false}
        onCloseAutoFocus={onCloseAutoFocus}
        className="z-[71] w-full max-w-[min(100vw,24rem)] p-0"
        overlayClassName="z-[70] bg-transparent"
      >
        <SheetClose asChild>
          <Button
            variant="quiet"
            size="icon-touch"
            className="absolute right-2 top-2 z-[72]"
            aria-label="关闭历史回顾"
          >
            <X className="size-4" aria-hidden="true" />
          </Button>
        </SheetClose>

        <SheetHeader className="border-b p-4 pr-16">
          <SheetTitle className="flex items-center gap-2">
            <History className="w-5 h-5" />
            历史回顾
          </SheetTitle>
          <SheetDescription>
            查看之前轮次的故事（只读模式）
          </SheetDescription>
        </SheetHeader>

        <ScrollArea className="flex-1 h-[calc(100vh-180px)]">
          <div className="p-4 space-y-4">
            {/* 当前轮次提示 */}
            {isViewingHistory && (
              <Button
                variant="narrative"
                size="touch"
                className="w-full justify-start gap-2"
                onClick={onBackToCurrent}
              >
                <ChevronRight className="w-4 h-4 rotate-180" />
                返回当前轮次
              </Button>
            )}

            {sortedWeeks.length === 0 ? (
              <p className="text-muted-foreground text-sm text-center py-8">
                暂无历史记录
              </p>
            ) : (
              sortedWeeks.map((week) => {
                const rounds = groupedByWeek[week];
                return (
                  <div key={week} className="space-y-0">
                    {/* 周标题 */}
                    <div className="flex items-center gap-2 border-b border-[var(--border-default)] py-3 text-sm font-medium text-muted-foreground">
                      <Calendar className="w-4 h-4" />
                      {rounds[0]?.story_date ? `第 ${week + 1} 周` : `第 ${week + 1} 周`}
                      {rounds[0]?.date_info?.date_string && (
                        <span className="text-xs">
                          ({rounds[0].date_info.date_string})
                        </span>
                      )}
                    </div>

                    {/* 轮次列表 */}
                    {rounds.map((item) => {
                      const roundName = item.story_date
                        ? `${item.story_date} · 第 ${(item.day_index ?? item.round) + 1} 天`
                        : ROUND_NAMES[item.round] || `第${item.round + 1}轮`;
                      const isSelected = selectedIndex === item.originalIndex;
                      const hasStory =
                        item.event_description || item.story_continuation;

                      return (
                        <div
                          key={`${item.week}-${item.round}`}
                          className="space-y-0"
                        >
                          <button
                            aria-label={item.story_date
                              ? `${roundName}：${hasStory ? "阅读正文" : "查看摘要"}`
                              : `第 ${item.week + 1} 周 ${roundName}：${hasStory ? "阅读正文" : "查看摘要"}`}
                            onClick={() => {
                              onSelect(item.originalIndex);
                              onOpenChange(false);
                            }}
                            className={cn(
                              "min-h-11 w-full rounded-none border-x-0 border-t-0 border-b bg-transparent px-0 py-3 text-left shadow-none transition-colors",
                              "hover:border-[var(--border-strong)] hover:bg-transparent",
                              "focus-visible:relative focus-visible:z-10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)] focus-visible:ring-inset",
                              isSelected
                                ? "border-[var(--border-strong)]"
                                : "border-[var(--border-default)]"
                            )}
                          >
                            <div className="flex items-center justify-between mb-1">
                              <span className="font-medium text-sm">
                                {roundName}
                              </span>
                              {hasStory && (
                                <span
                                  data-slot="history-recorded"
                                  className="text-xs tracking-[0.12em] text-[var(--text-secondary)]"
                                >
                                  已记录
                                </span>
                              )}
                            </div>

                            {/* 选择的内容 */}
                            {item.choice && (
                              <p className="text-xs text-muted-foreground line-clamp-1 mb-1">
                                选择: {item.choice}
                              </p>
                            )}

                            {/* 摘要 */}
                            {item.summary && (
                              <p className="text-xs text-muted-foreground line-clamp-2">
                                {item.summary}
                              </p>
                            )}
                            {hasStory && (
                              <p className="mt-2 text-xs text-[var(--text-secondary)]">
                                点击阅读正文
                              </p>
                            )}
                          </button>

                          {isSelected && hasStory && (
                            <div
                              data-slot="history-round-body"
                              className="space-y-3 rounded-none border-x-0 border-t-0 border-b border-[var(--border-default)] bg-transparent px-0 py-4 text-sm leading-6 text-foreground shadow-none"
                            >
                              {item.event_description && (
                                <p className="whitespace-pre-wrap">
                                  {item.event_description}
                                </p>
                              )}
                              {item.story_continuation && (
                                <div className="space-y-2">
                                  <p className="font-medium text-[var(--text-primary)]">
                                    选择后的故事发展
                                  </p>
                                  <p className="whitespace-pre-wrap">
                                    {item.story_continuation}
                                  </p>
                                </div>
                              )}
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                );
              })
            )}
          </div>
        </ScrollArea>

        {/* 底部提示 */}
        <div className="border-t border-[var(--border-default)] p-4">
          <p className="text-xs text-muted-foreground text-center">
            共 {roundHistory.length} {roundHistory.some((item) => item.story_date) ? "个故事日" : "轮历史记录"}
          </p>
        </div>
      </SheetContent>
    </Sheet>
  );
}
