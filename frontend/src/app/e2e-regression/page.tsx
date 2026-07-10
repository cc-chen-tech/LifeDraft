"use client";

import { useEffect, useState } from "react";
import { ChatBar } from "@/components/game/ChatBar";
import { MusicPlayer } from "@/components/game/MusicPlayer";
import { OptionCards } from "@/components/game/OptionCards";
import { StoryVoiceControls } from "@/components/game/StoryVoiceControls";
import { SettingDisplay } from "@/components/game/SettingDisplay";
import { api } from "@/lib/api";
import { useMusicStore } from "@/stores/useMusicStore";
import { useStoryVoiceStore } from "@/stores/useStoryVoiceStore";

const transparentPixel =
  "data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///ywAAAAAAQABAAACAUwAOw==";

export default function E2ERegressionPage() {
  const setActiveStoryText = useMusicStore((state) => state.setActiveStoryText);
  const setActiveGameId = useMusicStore((state) => state.setActiveGameId);
  const setCurrentSong = useMusicStore((state) => state.setCurrentSong);
  const setQueue = useMusicStore((state) => state.setQueue);
  const currentSong = useMusicStore((state) => state.currentSong);
  const queue = useMusicStore((state) => state.queue);
  const generateAiMusicForStory = useMusicStore((state) => state.generateAiMusicForStory);
  const setActiveReadingTarget = useStoryVoiceStore((state) => state.setActiveReadingTarget);
  const clearActiveReadingTarget = useStoryVoiceStore((state) => state.clearActiveReadingTarget);
  const [showHistory, setShowHistory] = useState(false);
  const [historySelected, setHistorySelected] = useState(false);
  const [currentStory, setCurrentStory] = useState("当前故事尚未更新");
  const [streamedStory, setStreamedStory] = useState("");
  const [showCollection, setShowCollection] = useState(false);
  const [autoCollectionState, setAutoCollectionState] = useState<
    "empty" | "recognizing" | "collected"
  >("empty");
  const [normalClickChoice, setNormalClickChoice] = useState("none");
  const [collectionRefreshState, setCollectionRefreshState] = useState<"idle" | "refreshing">("idle");
  const [fixtureGameId, setFixtureGameId] = useState(101);
  const [worldFactSetting, setWorldFactSetting] = useState<Record<string, unknown> | null>(null);
  const [musicQueueFixture, setMusicQueueFixture] = useState<{
    current: { title: string; source: string };
    queue: string[];
    generated?: { title: string; source: string; provider: string; url: string };
  } | null>(null);
  const autoReadText = streamedStory.includes("苏小二按住账册")
    ? "苏小二按住账册"
    : streamedStory.includes("账册被人翻开")
      ? "账册被人翻开"
      : "";
  const autoReadReady = streamedStory.includes("苏小二按住账册");

  useEffect(() => {
    const searchParams = new URLSearchParams(window.location.search);
    const configuredGameId = Number(searchParams.get("gameId"));
    const enableGlobalVoiceFixture = searchParams.get("globalVoice") === "1";
    if (Number.isFinite(configuredGameId) && configuredGameId > 0) {
      setFixtureGameId(configuredGameId);
    }
    if (
      searchParams.get("worldFact") === "1" &&
      Number.isFinite(configuredGameId) &&
      configuredGameId > 0
    ) {
      void api.games.load(configuredGameId).then((game) => {
        setWorldFactSetting(
          (game.player_state.character_settings.world as Record<string, unknown>) ?? null,
        );
      });
    }
    setActiveStoryText(
      enableGlobalVoiceFixture
        ? "雨夜码头的旧账册被风吹开，主角正在追查失踪亲人的线索。"
        : null,
    );
    setActiveGameId(enableGlobalVoiceFixture ? configuredGameId || 101 : null);
    setCurrentSong({
      id: 9101,
      name: "全局音乐夹具",
      artists: ["测试"],
      album: "回归夹具",
      duration: 120,
      source: "netease",
    });
    if (enableGlobalVoiceFixture) {
      setActiveReadingTarget({
        context: {
          source_type: "current_story",
          game_id: configuredGameId || 101,
          week: 1,
          round_number: 1,
          stage: "event",
          attempt_id: "global-sound-fixture",
          text_hash: "fixture-global-sound",
          text: "雨夜码头的旧账册被风吹开。",
        },
        autoReadText: "雨夜码头的旧账册被风吹开。",
        autoReadReady: true,
      });
    } else {
      clearActiveReadingTarget();
    }
    setQueue([]);

    return () => {
      setActiveStoryText(null);
      setActiveGameId(null);
      clearActiveReadingTarget();
      setCurrentSong(null);
      setQueue([]);
    };
  }, [
    clearActiveReadingTarget,
    setActiveReadingTarget,
    setActiveStoryText,
    setActiveGameId,
    setCurrentSong,
    setQueue,
  ]);

  const appendFirstAttempt = () => {
    setStreamedStory("雾气从码头仓门涌进来，陆明看见账册被人翻开。");
  };

  const replaceAfterRetry = () => {
    setStreamedStory("苏小二按住账册，低声提醒陆明先核对暗号。");
  };

  return (
    <main className="min-h-screen p-6 space-y-8">
      {worldFactSetting && (
        <section aria-label="世界事实边界回归夹具">
          <SettingDisplay stepKey="world" data={worldFactSetting} />
        </section>
      )}
      <section aria-label="选项可访问名称回归夹具">
        <OptionCards
          options={[
            { text: "追随江边脚印，查看雾中来客留下的痕迹。" },
            { text: "先回船舱取火折子，再探桥下暗影。" },
          ]}
          onSelect={() => undefined}
          onCustomChoice={() => undefined}
        />
      </section>

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

      <section
        aria-label="周中浏览器点击回归夹具"
        className="relative h-[calc(100vh-3rem)] rounded border border-border p-4"
      >
        <div className="absolute bottom-6 left-4 right-4">
          <OptionCards
            options={[
              { text: "周中先追问账册来源，再决定是否赴约。" },
              { text: "周中暂避锋芒，等夜深后再去码头。" },
            ]}
            onSelect={(index) =>
              setNormalClickChoice(index === 0 ? "midweek-source" : "midweek-dock")
            }
            onCustomChoice={(text) => setNormalClickChoice(`custom:${text}`)}
          />
          <p data-testid="normal-click-choice" className="mt-3 text-sm">
            {normalClickChoice}
          </p>
          <button
            type="button"
            data-testid="reset-normal-click-choice"
            className="sr-only"
            onClick={() => setNormalClickChoice("none")}
          >
            重置周中点击状态
          </button>
        </div>
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
          onClick={() => {
            setShowCollection(true);
            setAutoCollectionState("recognizing");
            window.setTimeout(() => setAutoCollectionState("collected"), 50);
          }}
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
            <section aria-label="自动实体收集状态" className="mt-3 rounded border p-3">
              <p data-testid="auto-collection-state">{autoCollectionState}</p>
              {autoCollectionState === "collected" && (
                <>
                  <h3>赵掌柜</h3>
                  <p>铜钥匙</p>
                </>
              )}
            </section>
          </div>
        )}
      </section>

      <section aria-label="故事朗读回归夹具" className="space-y-3">
        <StoryVoiceControls
          currentContext={{
            source_type: "current_story",
            game_id: 101,
            week: 1,
            round_number: 1,
            stage: "event",
            attempt_id: "current-preview",
            text_hash: "fixture-current-preview",
            text: "雨夜码头的旧账册被风吹开。",
          }}
          autoReadText={autoReadText}
          autoReadReady={false}
        />
        <StoryVoiceControls
          currentContext={{
            source_type: "current_story",
            game_id: 101,
            week: 1,
            round_number: 1,
            stage: "event",
            attempt_id: "current",
            text_hash: "fixture-current",
            text: "雨夜码头的旧账册被风吹开。",
          }}
          historyContext={
            historySelected
              ? {
                  source_type: "history_round",
                  game_id: 101,
                  week: 3,
                  round_number: 2,
                  stage: "event",
                  attempt_id: "history-3-2",
                  text_hash: "fixture-history",
                  text: "第 3 周第 2 轮，码头边的对峙仍停在旧案账册被交出的瞬间。",
                }
              : null
          }
          autoReadText={autoReadText}
          autoReadReady={autoReadReady}
          showTestControls
        />
      </section>

      <ChatBar
        gameId={101}
        onSave={() => undefined}
        onRegenerate={() => undefined}
        storyText="雨夜码头的旧账册被风吹开。"
        onRewriteComplete={() => undefined}
      />

      <section aria-label="音乐回归夹具" className="space-y-3">
        <MusicPlayer
          gameId={fixtureGameId}
          storyText="雨夜的码头上，主角刚发现旧账册里藏着失踪亲人的线索。远处传来轮船汽笛声，空气紧张而潮湿。"
          autoFetchRecommendation={false}
        />
        <button
          type="button"
          className="rounded border px-3 py-2"
          onClick={() => {
            setQueue([
              {
                id: 9201,
                name: "网易云 下一曲",
                artists: ["测试"],
                album: "回归夹具",
                duration: 120,
                source: "netease",
              },
              {
                id: 9202,
                name: "网易云 后续曲",
                artists: ["测试"],
                album: "回归夹具",
                duration: 120,
                source: "netease",
              },
            ]);
            void generateAiMusicForStory(
              "雨夜码头的旧账册被风吹开，主角刚发现失踪亲人的线索。",
              fixtureGameId,
              {
                mood: "紧张",
                scene_type: "雨夜追逐",
                environment: "民国码头",
              }
            );
          }}
        >
          触发 MiniMax 音乐生成
        </button>
        <button
          type="button"
          className="rounded border px-3 py-2"
          onClick={() =>
            setMusicQueueFixture({
              current: { title: "网易云 当前曲", source: "netease" },
              queue: ["网易云 下一曲", "AI 雨夜码头", "网易云 后续曲"],
            })
          }
        >
          加载会员音乐队列夹具
        </button>
        <button
          type="button"
          className="rounded border px-3 py-2"
          onClick={() =>
            setMusicQueueFixture({
              current: { title: "网易云 当前曲", source: "netease" },
              queue: ["网易云 下一曲", "AI MiniMax 雨夜追逐", "网易云 后续曲"],
              generated: {
                title: "AI MiniMax 雨夜追逐",
                source: "ai_generated",
                provider: "minimax",
                url: "/api/voice-reading/audio/minimax-music-fixture-warm_female.wav",
              },
            })
          }
        >
          触发 MiniMax 音乐生成夹具
        </button>
        {musicQueueFixture && (
          <div aria-label="会员音乐队列状态" className="rounded border p-3">
            <p data-testid="current-music-source">{musicQueueFixture.current.source}</p>
            <p data-testid="current-music-title">{musicQueueFixture.current.title}</p>
            <p data-testid="music-queue-order">{musicQueueFixture.queue.join(" | ")}</p>
            {musicQueueFixture.generated && (
              <>
                <p data-testid="generated-music-provider">
                  {musicQueueFixture.generated.provider}
                </p>
                <p data-testid="generated-music-source">{musicQueueFixture.generated.source}</p>
                <audio
                  data-testid="generated-music-audio"
                  src={musicQueueFixture.generated.url}
                  preload="auto"
                />
              </>
            )}
          </div>
        )}
        <div aria-label="真实音乐队列状态" className="rounded border p-3">
          <p data-testid="real-current-music-title">{currentSong?.name ?? ""}</p>
          <p data-testid="real-music-queue-order">
            {queue.map((item) => item.name).join(" | ")}
          </p>
          <p data-testid="real-generated-music-url">
            {queue.find((item) => item.source === "ai_generated")?.url ?? ""}
          </p>
        </div>
      </section>
    </main>
  );
}
