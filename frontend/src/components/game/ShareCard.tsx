"use client";

import { useRef, useState, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { Download, Share2 } from "lucide-react";

interface ShareCardProps {
  playerName: string;
  endingName: string;
  lifeMotto: string;
  achievementCount: number;
  playDuration: number;
  children: React.ReactNode;
}

export function ShareCard({
  playerName,
  endingName,
  lifeMotto,
  achievementCount,
  playDuration,
  children,
}: ShareCardProps) {
  const captureRef = useRef<HTMLDivElement>(null);
  const [isGenerating, setIsGenerating] = useState(false);

  const handleDownload = useCallback(async () => {
    if (!captureRef.current) return;
    setIsGenerating(true);

    try {
      const html2canvas = (await import("html2canvas")).default;
      const canvas = await html2canvas(captureRef.current, {
        backgroundColor: "#0f172a",
        scale: 2,
        useCORS: true,
        logging: false,
      });

      const link = document.createElement("a");
      link.download = `${playerName}_人生回顾.png`;
      link.href = canvas.toDataURL("image/png");
      link.click();
    } catch (err) {
      console.error("Failed to generate share image:", err);
    } finally {
      setIsGenerating(false);
    }
  }, [playerName]);

  return (
    <div className="space-y-4">
      <div
        ref={captureRef}
        className="bg-slate-900 p-8 rounded-xl space-y-4"
        style={{ width: 640 }}
      >
        <div className="text-center space-y-2">
          <h2 className="text-2xl font-serif font-bold text-white">
            {endingName}
          </h2>
          <p className="text-slate-300">{playerName} 的人生旅程</p>
        </div>

        <div className="text-center py-4">
          <p className="text-lg font-serif italic text-slate-400">
            &ldquo;{lifeMotto}&rdquo;
          </p>
        </div>

        <div className="text-slate-200">{children}</div>

        <div className="flex justify-center gap-6 pt-4 border-t border-slate-700">
          <div className="text-center">
            <p className="text-xl font-bold text-white">{achievementCount}</p>
            <p className="text-xs text-slate-400">成就</p>
          </div>
          <div className="text-center">
            <p className="text-xl font-bold text-white">{playDuration}分</p>
            <p className="text-xs text-slate-400">时长</p>
          </div>
        </div>

        <p className="text-center text-xs text-slate-500 pt-4">
          人生草稿本 — 用 AI 书写你的故事
        </p>
      </div>

      <div className="flex justify-center">
        <Button
          onClick={handleDownload}
          disabled={isGenerating}
          className="touch-target"
        >
          {isGenerating ? (
            <Share2 className="w-4 h-4 mr-2 animate-spin" />
          ) : (
            <Download className="w-4 h-4 mr-2" />
          )}
          {isGenerating ? "生成中..." : "保存分享卡片"}
        </Button>
      </div>
    </div>
  );
}
