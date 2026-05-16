"use client";

import { useState } from "react";
import { ChatBar } from "@/components/game/ChatBar";
import { MusicPlayer } from "@/components/game/MusicPlayer";
import { OptionCards } from "@/components/game/OptionCards";

const transparentPixel =
  "data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///ywAAAAAAQABAAACAUwAOw==";

export default function E2ERegressionPage() {
  const [showHistory, setShowHistory] = useState(false);
  const [historySelected, setHistorySelected] = useState(false);
  const [currentStory, setCurrentStory] = useState("当前故事尚未更新");
  const [streamedStory, setStreamedStory] = useState("");
  const [showCollection, setShowCollection] = useState(false);
  const [collectionRefreshState, setCollectionRefreshState] = useState<"idle" | "refreshing">("idle");

  const appendFirstAttempt = () => {
    setStreamedStory("雾气从码头仓门涌进来，陆明看见账册被人翻开。");
  };

  const replaceAfterRetry = () => {
    setStreamedStory("苏小二按住账册，低声提醒陆明先核对暗号。");
  };

  return (
    <main className="min-h-screen p-6 space-y-8">
      <OptionCards
        options={[
          { text: "追随江边脚印，查看雾中来客留下的痕迹。" },
          { text: "先回船舱取火折子，再探桥下暗影。" },
        ]}
        onSelect={() => undefined}
        onCustomChoice={() => undefined}
      />

      <section aria-label="故事流回归夹具" className="space-y-3">
        <div className="flex gap-3">
          <button
            type="button"
            className="rounded border px-3 py-2"
            onClick={appendFirstAttempt}
          >
            模拟首轮 stream
          </button>
          <button
            type="button"
            className="rounded border px-3 py-2"
            onClick={replaceAfterRetry}
          >
            模拟 retry 替换
          </button>
        </div>
        <p data-testid="streamed-story">{streamedStory}</p>
      </section>

      <section aria-label="历史回归夹具" className="space-y-3">
        <div className="flex gap-3">
          <button
            type="button"
            className="rounded border px-3 py-2"
            onClick={() => setShowHistory(true)}
          >
            历史回顾
          </button>
          <button
            type="button"
            className="rounded border px-3 py-2"
            onClick={() => setCurrentStory("当前故事已经更新，但历史视图保持不变")}
          >
            模拟当前故事更新
          </button>
        </div>

        <p data-testid="current-story">{currentStory}</p>

        {showHistory && (
          <div className="rounded border p-4">
            <button
              type="button"
              className="rounded border px-3 py-2"
              onClick={() => setHistorySelected(true)}
            >
              第 3 周 第 2 轮：码头边的对峙
            </button>
            {historySelected && (
              <div className="mt-3 space-y-2">
                <p data-testid="history-story">
                  第 3 周第 2 轮，码头边的对峙仍停在旧案账册被交出的瞬间。
                </p>
                <p data-testid="history-scene-image-state">week=3 round=2 stage=event</p>
                <img src={transparentPixel} alt="历史场景：码头边的对峙" className="h-8 w-8" />
              </div>
            )}
          </div>
        )}
      </section>

      <section aria-label="收集回归夹具" className="space-y-3">
        <button
          type="button"
          className="rounded border px-3 py-2"
          onClick={() => setShowCollection(true)}
        >
          收集
        </button>
        {showCollection && (
          <div className="rounded border p-4">
            <div className="flex items-center gap-3">
              <span data-testid="collection-refresh-state">{collectionRefreshState}</span>
              <button
                type="button"
                className="rounded border px-3 py-2"
                onClick={() => setCollectionRefreshState("refreshing")}
              >
                刷新收集
              </button>
            </div>
            <article className="mt-3">
              <img src={transparentPixel} alt="苏小二" className="h-8 w-8" />
              <h2 className="text-lg font-medium">苏小二</h2>
              <p>船行里的旧相识，正在刷新时也保持可见。</p>
            </article>
          </div>
        )}
      </section>

      <ChatBar
        gameId={101}
        onSave={() => undefined}
        onAdjustStory={() => undefined}
        onRegenerate={() => undefined}
      />

      <section aria-label="音乐回归夹具" className="space-y-3">
        <MusicPlayer
          gameId={101}
          storyText="雨夜的码头上，主角刚发现旧账册里藏着失踪亲人的线索。远处传来轮船汽笛声，空气紧张而潮湿。"
        />
      </section>
    </main>
  );
}
