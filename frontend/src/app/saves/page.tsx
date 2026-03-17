"use client";

import { useEffect, useState } from "react";
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
import { useGameStore } from "@/stores/useGameStore";
import { cn } from "@/lib/utils";
import {
  ArrowLeft,
  Play,
  Trash2,
  Loader2,
  User,
  FolderOpen,
} from "lucide-react";
import type { GameListItem } from "@/lib/types";

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
  const [isDeleting, setIsDeleting] = useState(false);
  const [toast, setToast] = useState<{ type: "success" | "error"; message: string } | null>(null);

  const showToast = (type: "success" | "error", message: string) => {
    setToast({ type, message });
    setTimeout(() => setToast(null), 3000);
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
            {savedGames
              .filter((game) => game.player_name?.trim())
              .sort((a, b) => {
                const timeA = a.updated_at ? new Date(a.updated_at).getTime() : 0;
                const timeB = b.updated_at ? new Date(b.updated_at).getTime() : 0;
                return timeB - timeA;
              })
              .map((save) => (
              <Card key={save.game_id} className="bg-card border-border overflow-hidden">
                <div className="p-4 flex items-center justify-between hover:bg-muted/30 transition-colors">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-full bg-primary/10 flex items-center justify-center">
                      <User className="w-5 h-5 text-primary" />
                    </div>
                    <div className="text-left">
                      <div className="flex items-center gap-2">
                        <span className="font-medium text-foreground">
                          {save.player_name}
                        </span>
                        <span className="text-xs px-2 py-0.5 rounded-full bg-muted text-muted-foreground">
                          {save.age}岁 第{(save.week ?? 0) + 1}周
                        </span>
                        {(save.week ?? 0) === 0 && (
                          <span className="text-xs px-1.5 py-0.5 rounded bg-amber-500/20 text-amber-600">
                            新角色
                          </span>
                        )}
                      </div>
                      {save.updated_at && (
                        <div className="text-xs text-muted-foreground mt-0.5">
                          {new Date(save.updated_at).toLocaleDateString()} {formatChineseTime(save.updated_at)}
                        </div>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <Button
                      size="sm"
                      variant="default"
                      className="h-8"
                      onClick={() => handleLoad(save.game_id)}
                      disabled={loadingGameId === save.game_id}
                    >
                      {loadingGameId === save.game_id ? (
                        <Loader2 className="w-4 h-4 animate-spin" />
                      ) : (
                        <>
                          <Play className="w-4 h-4 mr-1" />
                          继续
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
              </Card>
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
