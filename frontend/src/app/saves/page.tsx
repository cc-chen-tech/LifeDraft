"use client";

import { useEffect, useState, useMemo } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { useGameStore } from "@/stores/useGameStore";
import { cn } from "@/lib/utils";
import api from "@/lib/api";
import {
  ArrowLeft,
  Play,
  Trash2,
  Loader2,
  Calendar,
  User,
  ChevronDown,
  FolderOpen,
} from "lucide-react";
import type { GameListItem } from "@/lib/types";

// ★ 将存档按角色名分组
interface CharacterGroup {
  playerName: string;
  saves: GameListItem[];
  latestSave: GameListItem;
}

// ★ 格式化时间为中文时段
function formatChineseTime(dateStr: string | null): string {
  if (!dateStr) return "";
  const date = new Date(dateStr);
  const hour = date.getHours();
  const minute = date.getMinutes();
  
  let period = "";
  if (hour >= 0 && hour < 6) period = "凌晨";
  else if (hour >= 6 && hour < 12) period = "上午";
  else if (hour >= 12 && hour < 18) period = "下午";
  else period = "晚上";
  
  const displayHour = hour > 12 ? hour - 12 : hour;
  return `${period}${displayHour}:${minute.toString().padStart(2, "0")}`;
}

export default function SavesPage() {
  const router = useRouter();
  const {
    savedGames,
    fetchSavedGames,
    deleteGame,
    loadGameState,
    setGameSession,
    resetCreation,
  } = useGameStore();

  const [isLoading, setIsLoading] = useState(true);
  const [loadingGameId, setLoadingGameId] = useState<number | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<number | null>(null);
  const [deleteGroupTarget, setDeleteGroupTarget] = useState<string | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const [toast, setToast] = useState<{ type: "success" | "error"; message: string } | null>(null);
  const [expandedGroups, setExpandedGroups] = useState<Set<string>>(new Set());

  const showToast = (type: "success" | "error", message: string) => {
    setToast({ type, message });
    setTimeout(() => setToast(null), 3000);
  };

  // ★ 将存档按角色名分组，每组按更新时间排序
  // ★ 过滤掉未开始游戏的存档（第0周 = 只创建了角色）
  const groupedSaves = useMemo<CharacterGroup[]>(() => {
    const groups: Record<string, GameListItem[]> = {};
    
    savedGames.forEach((game) => {
      const name = game.player_name || "";
      // ★ 跳过未命名的存档（空字符串）
      if (!name.trim()) return;
      // ★ 不再过滤 week=0 的存档，让用户看到所有角色
      // if (game.week === 0) return;
      
      if (!groups[name]) {
        groups[name] = [];
      }
      groups[name].push(game);
    });
    
    // 每组按更新时间排序（最新在前）
    return Object.entries(groups)
      .map(([playerName, saves]) => {
        const sortedSaves = saves.sort((a, b) => {
          const timeA = a.updated_at ? new Date(a.updated_at).getTime() : 0;
          const timeB = b.updated_at ? new Date(b.updated_at).getTime() : 0;
          return timeB - timeA;
        });
        return {
          playerName,
          saves: sortedSaves,
          latestSave: sortedSaves[0],
        };
      })
      // 组间也按最新存档时间排序
      .sort((a, b) => {
        const timeA = a.latestSave.updated_at ? new Date(a.latestSave.updated_at).getTime() : 0;
        const timeB = b.latestSave.updated_at ? new Date(b.latestSave.updated_at).getTime() : 0;
        return timeB - timeA;
      });
  }, [savedGames]);

  const toggleGroup = (playerName: string) => {
    setExpandedGroups((prev) => {
      const next = new Set(prev);
      if (next.has(playerName)) {
        next.delete(playerName);
      } else {
        next.add(playerName);
      }
      return next;
    });
  };

  useEffect(() => {
    fetchSavedGames()
      .catch(console.error)
      .finally(() => setIsLoading(false));
  }, [fetchSavedGames]);

  const handleLoad = async (gameId: number) => {
    setLoadingGameId(gameId);
    try {
      await loadGameState(gameId);
      setGameSession(gameId, `session_${gameId}`);
      router.push("/play");
    } catch (err) {
      console.error("Load game failed:", err);
      showToast("error", "加载存档失败，请重试");
    } finally {
      setLoadingGameId(null);
    }
  };

  const handleDelete = async () => {
    if (deleteTarget === null) return;
    setIsDeleting(true);
    try {
      await deleteGame(deleteTarget);
      setDeleteTarget(null);
      showToast("success", "存档已删除");
    } catch (err) {
      console.error("Delete failed:", err);
      showToast("error", "删除失败，请重试");
    } finally {
      setIsDeleting(false);
    }
  };

  // ★ 删除整个角色的所有存档
  const handleDeleteGroup = async () => {
    if (deleteGroupTarget === null) return;
    setIsDeleting(true);
    try {
      // 找到该角色的所有存档并删除
      const group = groupedSaves.find(g => g.playerName === deleteGroupTarget);
      if (group) {
        for (const save of group.saves) {
          await deleteGame(save.game_id);
        }
      }
      setDeleteGroupTarget(null);
      showToast("success", `已删除 ${deleteGroupTarget} 的所有存档`);
    } catch (err) {
      console.error("Delete group failed:", err);
      showToast("error", "删除失败，请重试");
    } finally {
      setIsDeleting(false);
    }
  };

  // ★ 展开时切换分组
  const handleToggleGroup = (playerName: string) => {
    toggleGroup(playerName);
  };

  return (
    <div className="min-h-screen bg-background animate-page-enter">
      <header className="sticky top-0 z-40 bg-background/80 backdrop-blur-sm border-b border-border">
        <div className="max-w-2xl mx-auto px-4 h-14 flex items-center">
          <Button variant="ghost" size="sm" onClick={() => router.push("/")}>
            <ArrowLeft className="w-4 h-4 mr-1" />
            返回
          </Button>
          <h1 className="text-lg font-bold text-foreground ml-3">存档管理</h1>
        </div>
      </header>

      <main className="max-w-2xl mx-auto px-4 py-6">
        {isLoading ? (
          <div className="text-center py-12 text-muted-foreground">
            <Loader2 className="w-6 h-6 animate-spin mx-auto mb-2" />
            加载中...
          </div>
        ) : savedGames.length === 0 ? (
          <div className="text-center py-12">
            <p className="text-muted-foreground mb-4">暂无存档</p>
            <Button onClick={() => {
              resetCreation();
              router.push("/create");
            }}>
              开始新游戏
            </Button>
          </div>
        ) : (
          <div className="space-y-3">
            {groupedSaves.map((group) => (
              <Collapsible
                key={group.playerName}
                open={expandedGroups.has(group.playerName)}
                onOpenChange={() => handleToggleGroup(group.playerName)}
              >
                <Card className="bg-card border-border overflow-hidden">
                  {/* ★ 组头部：角色名 + 存档数 + 最新进度 + 删除按钮 */}
                  <div className="p-4 flex items-center justify-between hover:bg-muted/30 transition-colors">
                    <CollapsibleTrigger className="flex-1 flex items-center">
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-full bg-primary/10 flex items-center justify-center">
                          <User className="w-5 h-5 text-primary" />
                        </div>
                        <div className="text-left">
                          <div className="flex items-center gap-2">
                            <span className="font-medium text-foreground">
                              {group.playerName}
                            </span>
                            <span className="text-xs px-2 py-0.5 rounded-full bg-muted text-muted-foreground">
                              {group.saves.length}个存档
                            </span>
                          </div>
                          <div className="text-xs text-muted-foreground mt-0.5">
                            最新: {group.latestSave.age}岁 第{group.latestSave.week + 1}周
                            {group.latestSave.updated_at && (
                              <span className="ml-2">
                                {new Date(group.latestSave.updated_at).toLocaleDateString()}
                              </span>
                            )}
                          </div>
                        </div>
                      </div>
                    </CollapsibleTrigger>
                    <div className="flex items-center gap-2">
                      <Button
                        size="sm"
                        variant="ghost"
                        className="h-8 text-muted-foreground hover:text-destructive"
                        onClick={() => setDeleteGroupTarget(group.playerName)}
                      >
                        <Trash2 className="w-4 h-4" />
                      </Button>
                      <CollapsibleTrigger asChild>
                        <Button
                          size="sm"
                          variant="ghost"
                          className="h-8 w-8 p-0"
                        >
                          <ChevronDown
                            className={cn(
                              "w-5 h-5 text-muted-foreground transition-transform",
                              expandedGroups.has(group.playerName) && "rotate-180"
                            )}
                          />
                        </Button>
                      </CollapsibleTrigger>
                    </div>
                  </div>

                  {/* ★ 展开内容：显示该角色的所有游戏存档 */}
                  <CollapsibleContent>
                    <div className="border-t border-border">
                      {/* 显示该角色名下的所有游戏存档 */}
                      <div className="divide-y divide-border/50">
                        {group.saves.map((save, idx) => (
                          <div
                            key={save.game_id}
                            className={cn(
                              "px-4 py-3 flex items-center justify-between hover:bg-muted/20 transition-colors",
                              idx === 0 && "bg-primary/5"
                            )}
                          >
                            <div className="flex items-center gap-3">
                              <div className="w-6 flex justify-center">
                                {idx === 0 ? (
                                  <span className="text-xs px-1.5 py-0.5 rounded bg-primary/20 text-primary font-medium">
                                    最新
                                  </span>
                                ) : (
                                  <FolderOpen className="w-4 h-4 text-muted-foreground" />
                                )}
                              </div>
                              <div>
                                <div className="flex items-center gap-2">
                                  <span className="text-sm text-foreground">
                                    {save.age}岁 第{save.week + 1}周
                                  </span>
                                  {save.week === 0 && (
                                    <span className="text-xs px-1.5 py-0.5 rounded bg-muted text-muted-foreground">
                                      角色创建
                                    </span>
                                  )}
                                </div>
                                {save.updated_at && (
                                  <div className="text-xs text-muted-foreground">
                                    {new Date(save.updated_at).toLocaleDateString()} {formatChineseTime(save.updated_at)}
                                  </div>
                                )}
                              </div>
                            </div>

                            <div className="flex items-center gap-2">
                              <Button
                                size="sm"
                                variant={idx === 0 ? "default" : "outline"}
                                className="h-8"
                                onClick={() => handleLoad(save.game_id)}
                                disabled={loadingGameId === save.game_id}
                              >
                                {loadingGameId === save.game_id ? (
                                  <Loader2 className="w-4 h-4 animate-spin" />
                                ) : idx === 0 ? (
                                  <>
                                    <Play className="w-4 h-4 mr-1" />
                                    继续
                                  </>
                                ) : (
                                  <>
                                    <FolderOpen className="w-4 h-4 mr-1" />
                                    加载
                                  </>
                                )}
                              </Button>
                              <Button
                                size="sm"
                                variant="ghost"
                                className="h-8 text-muted-foreground hover:text-destructive"
                                onClick={() => setDeleteTarget(save.game_id)}
                              >
                                <Trash2 className="w-4 h-4" />
                              </Button>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  </CollapsibleContent>
                </Card>
              </Collapsible>
            ))}
          </div>
        )}
      </main>

      {/* Delete confirmation */}
      <Dialog
        open={deleteTarget !== null}
        onOpenChange={(open) => !open && setDeleteTarget(null)}
      >
        <DialogContent className="bg-card border-border">
          <DialogHeader>
            <DialogTitle className="text-foreground">确认删除</DialogTitle>
            <DialogDescription className="text-muted-foreground">
              删除后无法恢复，确定要删除这个存档吗？
            </DialogDescription>
          </DialogHeader>
          <div className="flex gap-3 justify-end mt-4">
            <Button
              variant="outline"
              onClick={() => setDeleteTarget(null)}
            >
              取消
            </Button>
            <Button
              variant="destructive"
              onClick={handleDelete}
              disabled={isDeleting}
            >
              {isDeleting && (
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
              )}
              删除
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Delete group confirmation */}
      <Dialog
        open={deleteGroupTarget !== null}
        onOpenChange={(open) => !open && setDeleteGroupTarget(null)}
      >
        <DialogContent className="bg-card border-border">
          <DialogHeader>
            <DialogTitle className="text-foreground">确认删除角色</DialogTitle>
            <DialogDescription className="text-muted-foreground">
              确定要删除 "{deleteGroupTarget}" 的所有存档吗？此操作无法撤销。
            </DialogDescription>
          </DialogHeader>
          <div className="flex gap-3 justify-end mt-4">
            <Button
              variant="outline"
              onClick={() => setDeleteGroupTarget(null)}
            >
              取消
            </Button>
            <Button
              variant="destructive"
              onClick={handleDeleteGroup}
              disabled={isDeleting}
            >
              {isDeleting && (
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
              )}
              删除全部
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Toast */}
      {toast && (
        <div
          className={cn(
            "fixed bottom-20 left-1/2 -translate-x-1/2 px-4 py-2 rounded-lg text-sm z-50 animate-fade-in",
            toast.type === "success"
              ? "bg-green-500/90 text-white"
              : "bg-red-500/90 text-white"
          )}
        >
          {toast.message}
        </div>
      )}
    </div>
  );
}
