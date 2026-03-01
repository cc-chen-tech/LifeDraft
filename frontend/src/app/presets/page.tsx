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
import {
  ArrowLeft,
  Trash2,
  Loader2,
  Calendar,
  BookOpen,
  Play,
} from "lucide-react";
import { cn } from "@/lib/utils";

export default function PresetsPage() {
  const router = useRouter();
  const { presets, fetchPresets, deletePreset, loadPreset } = useGameStore();

  const [isLoading, setIsLoading] = useState(true);
  const [deleteTarget, setDeleteTarget] = useState<number | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const [toast, setToast] = useState<{ type: "success" | "error"; message: string } | null>(null);

  const showToast = (type: "success" | "error", message: string) => {
    setToast({ type, message });
    setTimeout(() => setToast(null), 3000);
  };

  useEffect(() => {
    fetchPresets()
      .catch(console.error)
      .finally(() => setIsLoading(false));
  }, [fetchPresets]);

  const handleLoad = (presetId: number) => {
    const preset = presets.find((p) => p.preset_id === presetId);
    if (preset) {
      loadPreset(preset);
      router.push("/create");
    }
  };

  const handleDelete = async () => {
    if (deleteTarget === null) return;
    setIsDeleting(true);
    try {
      await deletePreset(deleteTarget);
      setDeleteTarget(null);
      showToast("success", "预设已删除");
    } catch (err) {
      console.error("Delete preset failed:", err);
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
          <h1 className="text-lg font-bold text-foreground ml-3">角色预设</h1>
        </div>
      </header>

      <main className="max-w-2xl mx-auto px-4 py-6">
        {isLoading ? (
          <div className="text-center py-12 text-muted-foreground">
            <Loader2 className="w-6 h-6 animate-spin mx-auto mb-2" />
            加载中...
          </div>
        ) : presets.length === 0 ? (
          <div className="text-center py-12">
            <BookOpen className="w-12 h-12 text-muted-foreground mx-auto mb-4" />
            <p className="text-muted-foreground mb-4">暂无角色预设</p>
            <Button onClick={() => router.push("/create")}>
              创建角色
            </Button>
          </div>
        ) : (
          <div className="space-y-3">
            {presets.map((preset) => (
              <Card
                key={preset.preset_id}
                className="p-4 bg-card border-border hover:border-primary/30 transition-colors"
              >
                <div className="flex items-center justify-between">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <BookOpen className="w-4 h-4 text-primary" />
                      <span className="font-medium text-foreground truncate">
                        {preset.preset_name}
                      </span>
                    </div>
                    <div className="flex items-center gap-3 text-xs text-muted-foreground">
                      <span>{preset.player_name}</span>
                      {preset.created_at && (
                        <span className="flex items-center gap-1">
                          <Calendar className="w-3 h-3" />
                          {new Date(preset.created_at).toLocaleDateString()}
                        </span>
                      )}
                    </div>
                    {preset.life_vision && (
                      <p className="text-xs text-muted-foreground mt-1 truncate">
                        {preset.life_vision}
                      </p>
                    )}
                  </div>

                  <div className="flex items-center gap-2 ml-3">
                    <Button
                      size="sm"
                      className="touch-target"
                      onClick={() => handleLoad(preset.preset_id)}
                    >
                      <Play className="w-4 h-4" />
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      className={cn("text-muted-foreground hover:text-destructive")}
                      onClick={() => setDeleteTarget(preset.preset_id)}
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

      <Dialog
        open={deleteTarget !== null}
        onOpenChange={(open) => !open && setDeleteTarget(null)}
      >
        <DialogContent className="bg-card border-border">
          <DialogHeader>
            <DialogTitle className="text-foreground">确认删除</DialogTitle>
            <DialogDescription className="text-muted-foreground">
              删除后无法恢复，确定要删除这个预设吗？
            </DialogDescription>
          </DialogHeader>
          <div className="flex gap-3 justify-end mt-4">
            <Button variant="outline" onClick={() => setDeleteTarget(null)}>
              取消
            </Button>
            <Button
              variant="destructive"
              onClick={handleDelete}
              disabled={isDeleting}
            >
              {isDeleting && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
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
