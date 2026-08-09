"use client";

import { useEffect, useState } from "react";
import { ChatBar } from "@/components/game/ChatBar";
import { MusicPlayer } from "@/components/game/MusicPlayer";
import { OptionCards } from "@/components/game/OptionCards";
import { StoryVoiceControls } from "@/components/game/StoryVoiceControls";
import { SettingDisplay } from "@/components/game/SettingDisplay";
import { SettingFeedbackCard } from "@/components/create/SettingFeedbackCard";
import { OpeningCompletionGate } from "@/components/game/OpeningCompletionGate";
import { CompletedStoryMediaGate } from "@/components/game/CompletedStoryMediaGate";
import { LifeSummaryPanel } from "@/components/game/LifeSummaryPanel";
import { NarrativeLoadingState } from "@/components/narrative-loading/NarrativeLoadingState";
import { useCharacterCreation } from "@/hooks/useCharacterCreation";
import { api } from "@/lib/api";
import { useCollectionStore } from "@/stores/useCollectionStore";
import { useGameStore } from "@/stores/useGameStore";
import { useImageStore } from "@/stores/useImageStore";
import { useMusicStore } from "@/stores/useMusicStore";
import { useStoryVoiceStore } from "@/stores/useStoryVoiceStore";

const transparentPixel =
  "data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///ywAAAAAAQABAAACAUwAOw==";

const narrativeLoadingFixtureStates = [
  "initial",
  "partial",
  "delayed",
  "reconnecting",
  "polling",
  "failed",
] as const;

export type NarrativeLoadingFixtureState = (typeof narrativeLoadingFixtureStates)[number];

const narrativeLoadingFixtureLabels: Record<NarrativeLoadingFixtureState, string> = {
  initial: "初始状态",
  partial: "部分正文",
  delayed: "延迟状态",
  reconnecting: "模拟重连",
  polling: "模拟轮询",
  failed: "模拟失败",
};

export function NarrativeLoadingFixture({
  initialState,
}: {
  initialState: NarrativeLoadingFixtureState;
}) {
  const [selectedState, setSelectedState] = useState(initialState);
  const [actionCount, setActionCount] = useState(0);

  const selectState = (state: NarrativeLoadingFixtureState) => {
    setSelectedState(state);
    setActionCount(0);
  };

  const narrativeState = (() => {
    switch (selectedState) {
      case "initial":
        return (
          <NarrativeLoadingState
            context="opening"
            layout="screen"
            phase="generating"
          />
        );
      case "partial":
        return (
          <article className="mx-auto min-h-dvh w-full max-w-3xl px-6 pb-28 pt-24 sm:px-10">
            <p className="font-serif text-base leading-8 text-[#F0ECE6] sm:text-lg">
              首段正文已经抵达。
            </p>
            <NarrativeLoadingState
              context="opening"
              layout="inline"
              phase="generating"
            />
          </article>
        );
      case "delayed":
        return (
          <div className="flex min-h-dvh items-center justify-center px-4 pb-24">
            <NarrativeLoadingState
              className="w-full max-w-3xl"
              context="gameplay"
              layout="section"
              phase="generating"
              delayed
            />
          </div>
        );
      case "reconnecting":
        return (
          <div className="flex min-h-dvh items-center justify-center px-4 pb-24">
            <NarrativeLoadingState
              className="w-full max-w-3xl"
              context="gameplay"
              layout="section"
              phase="generating"
              transport="reconnecting"
              onAction={() => setActionCount((count) => count + 1)}
            />
          </div>
        );
      case "polling":
        return (
          <div className="flex min-h-dvh items-center justify-center px-4 pb-24">
            <NarrativeLoadingState
              className="w-full max-w-3xl"
              context="gameplay"
              layout="section"
              phase="generating"
              transport="polling"
              onAction={() => setActionCount((count) => count + 1)}
            />
          </div>
        );
      case "failed":
        return (
          <div className="flex min-h-dvh items-center justify-center px-4 pb-24">
            <NarrativeLoadingState
              className="w-full max-w-3xl"
              context="gameplay"
              layout="section"
              phase="generating"
              transport="failed"
              onAction={() => setActionCount((count) => count + 1)}
            />
          </div>
        );
    }
  })();

  return (
    <section
      aria-label="叙事加载回归夹具"
      className="relative min-h-dvh overflow-x-hidden bg-[#0D0C0B] text-[#F0ECE6]"
      data-testid="narrative-loading-fixture"
    >
      <p className="sr-only" data-testid="narrative-loading-fixture-state">
        {selectedState}
      </p>
      <p className="sr-only" data-testid="narrative-loading-action-count">
        {actionCount}
      </p>
      {narrativeState}
      <nav
        aria-label="叙事加载夹具状态"
        className="fixed inset-x-3 bottom-3 z-10 mx-auto flex max-w-2xl flex-wrap justify-center gap-1.5 rounded border border-[#34302C] bg-[#11100F]/95 p-2 shadow-lg"
      >
        {narrativeLoadingFixtureStates.map((state) => (
          <button
            aria-pressed={selectedState === state}
            className="rounded-sm border border-transparent px-2.5 py-1.5 text-xs text-[#8F8881] hover:border-[#34302C] hover:text-[#F0ECE6] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#F0ECE6] aria-pressed:border-[#71675D] aria-pressed:text-[#F0ECE6]"
            key={state}
            onClick={() => selectState(state)}
            type="button"
          >
            {narrativeLoadingFixtureLabels[state]}
          </button>
        ))}
      </nav>
    </section>
  );
}

const relationshipFixtureSettings = {
  family: { family_description: "测试家庭" },
  relationships: {
    relationships_description: "旧关系摘要：陈晓峰仍在原公司任职，周丽持续提供咨询。",
    key_people: [
      { name: "陈晓峰", role: "前同事", relationship: "仍在原公司任职" },
      { name: "周丽", role: "律师", relationship: "持续提供法律咨询" },
    ],
  },
  traits: { traits_description: "谨慎务实" },
};

function RelationshipRegenerationFixture() {
  const { characterSettings, regenerateSetting } = useCharacterCreation();
  const relationships = characterSettings.relationships as Record<string, unknown>;

  return (
    <main className="min-h-screen p-6">
      <SettingFeedbackCard
        stepKey="relationships"
        stepLabel="人际关系"
        data={relationships}
        onRegenerate={(feedback) => regenerateSetting("relationships", feedback)}
      />
    </main>
  );
}

export function E2ERegressionPageContent() {
  const setActiveStoryText = useMusicStore((state) => state.setActiveStoryText);
  const setActiveGameId = useMusicStore((state) => state.setActiveGameId);
  const setCurrentSong = useMusicStore((state) => state.setCurrentSong);
  const setQueue = useMusicStore((state) => state.setQueue);
  const currentSong = useMusicStore((state) => state.currentSong);
  const queue = useMusicStore((state) => state.queue);
  const activeStoryText = useMusicStore((state) => state.activeStoryText);
  const generateAiMusicForStory = useMusicStore((state) => state.generateAiMusicForStory);
  const addRecognizedEntities = useCollectionStore((state) => state.addRecognizedEntities);
  const entityAddLoading = useCollectionStore((state) => state.isLoading);
  const setActiveReadingTarget = useStoryVoiceStore((state) => state.setActiveReadingTarget);
  const clearActiveReadingTarget = useStoryVoiceStore((state) => state.clearActiveReadingTarget);
  const readingState = useStoryVoiceStore((state) => state.readingState);
  const currentAudioUrl = useStoryVoiceStore((state) => state.currentAudioUrl);
  const activeAutoReadReady = useStoryVoiceStore((state) => state.activeAutoReadReady);
  const [showHistory, setShowHistory] = useState(false);
  const [historySelected, setHistorySelected] = useState(false);
  const [currentStory, setCurrentStory] = useState("当前故事尚未更新");
  const [streamedStory, setStreamedStory] = useState("");
  const [showCollection, setShowCollection] = useState(false);
  const [autoCollectionState, setAutoCollectionState] = useState<
    "empty" | "recognizing" | "collected"
  >("empty");
  const [normalClickChoice, setNormalClickChoice] = useState("none");
  const [openingBackendComplete, setOpeningBackendComplete] = useState(false);
  const [openingVisibleComplete, setOpeningVisibleComplete] = useState(false);
  const [collectionRefreshState, setCollectionRefreshState] = useState<"idle" | "refreshing">("idle");
  const [showRelationshipRegenerationFixture, setShowRelationshipRegenerationFixture] = useState(false);
  const [fixtureGameId, setFixtureGameId] = useState(101);
  const [audioRegenerationFixtureEnabled, setAudioRegenerationFixtureEnabled] = useState(false);
  const [audioStoryBusy, setAudioStoryBusy] = useState(false);
  const [lifeSummaryFixtureEnabled, setLifeSummaryFixtureEnabled] = useState(false);
  const [showLifeSummaryFixture, setShowLifeSummaryFixture] = useState(false);
  const [worldFactSetting, setWorldFactSetting] = useState<Record<string, unknown> | null>(null);
  const [traitLayoutFixtureEnabled, setTraitLayoutFixtureEnabled] = useState(false);
  const [entityCollectionAddEnabled, setEntityCollectionAddEnabled] = useState(false);
  const [entityAddState, setEntityAddState] = useState<"idle" | "adding" | "saved" | "error">("idle");
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
    setEntityCollectionAddEnabled(searchParams.get("entityCollectionAdd") === "1");
    setAudioRegenerationFixtureEnabled(searchParams.get("audioRegeneration") === "1");
    setLifeSummaryFixtureEnabled(searchParams.get("lifeSummary") === "1");
    setTraitLayoutFixtureEnabled(searchParams.get("traitsLayout") === "1");
    const enableRelationshipRegenerationFixture =
      searchParams.get("relationshipRegeneration") === "1";
    if (enableRelationshipRegenerationFixture) {
      useGameStore.setState({
        creationStep: 4,
        characterSettings: relationshipFixtureSettings,
        playerName: "林见微",
        lifeVision: "现实主义创业故事",
        gameId: 901,
        sessionId: "901",
      });
      useImageStore.setState({
        playerImages: [{ image_id: 1, image_url: transparentPixel }],
        selectedImageIndex: 0,
        isGeneratingImage: false,
      });
      setShowRelationshipRegenerationFixture(true);
    }
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

  const addEntityCollectionFixture = async () => {
    setEntityAddState("adding");
    await addRecognizedEntities(fixtureGameId, {
      items: [
        {
          name: "银色戒指",
          description: "沈砚秋在故事中确认的一枚旧戒指。",
          category: "other",
          importance: "normal",
          appear_count: 1,
          appear_contexts: ["沈砚秋收起银色戒指。"],
        },
      ],
      characters: [
        {
          name: "陈远",
          description: "陈远带来了审计材料。",
          category: "person",
          importance: "important",
          appear_count: 1,
          appear_contexts: ["陈远走进会议室。"],
        },
      ],
      landmarks: [],
    });
    setEntityAddState(useCollectionStore.getState().error ? "error" : "saved");
  };

  if (showRelationshipRegenerationFixture) {
    return <RelationshipRegenerationFixture />;
  }

  return (
    <main
      className="min-h-screen p-6 space-y-8"
      data-testid="e2e-regression-legacy"
    >
      {entityCollectionAddEnabled && (
        <section aria-label="实体添加可靠性回归夹具" className="space-y-3">
          <button
            type="button"
            className="rounded border px-3 py-2"
            onClick={() => void addEntityCollectionFixture()}
            disabled={entityAddLoading}
          >
            {entityAddLoading ? "添加中..." : "添加识别实体"}
          </button>
          <p data-testid="entity-add-state">{entityAddState}</p>
        </section>
      )}
      {audioRegenerationFixtureEnabled && (
        <section aria-label="音频重新生成状态回归夹具" className="space-y-3">
          <CompletedStoryMediaGate
            text={audioStoryBusy ? "尚未完成的替换文本" : "旧故事文本"}
            context={{
              source_type: "current_story",
              game_id: 101,
              week: 2,
              round_number: 1,
              stage: "event",
              attempt_id: audioStoryBusy ? "replacement" : "old",
              text_hash: audioStoryBusy ? "partial" : "old-hash",
              text: audioStoryBusy ? "尚未完成的替换文本" : "旧故事文本",
            }}
            storyReady={!audioStoryBusy}
            storyBusy={audioStoryBusy}
            isViewingHistory={false}
          />
          <div className="flex gap-3">
            <button
              type="button"
              className="rounded border px-3 py-2"
              onClick={() => {
                useStoryVoiceStore.setState({
                  readingState: "playing",
                  currentSource: "current_story",
                  currentAudioUrl: "/api/voice-reading/audio/old.mp3",
                });
                setActiveStoryText("旧故事文本");
              }}
            >
              模拟旧故事朗读
            </button>
            <button
              type="button"
              className="rounded border px-3 py-2"
              onClick={() => setAudioStoryBusy(true)}
            >
              开始重新生成
            </button>
          </div>
          <p data-testid="audio-regeneration-reading-state">{readingState}</p>
          <p data-testid="audio-regeneration-audio-url">{currentAudioUrl || "none"}</p>
          <p data-testid="audio-regeneration-music-target">{activeStoryText || "none"}</p>
          <p data-testid="audio-regeneration-auto-ready">{String(activeAutoReadReady)}</p>
        </section>
      )}
      {lifeSummaryFixtureEnabled && (
        <section aria-label="人生总结事实边界回归夹具">
          <button
            type="button"
            className="rounded border px-3 py-2"
            onClick={() => setShowLifeSummaryFixture(true)}
          >
            打开已校验人生总结
          </button>
          {showLifeSummaryFixture && (
            <LifeSummaryPanel
              summary={{
                startWeek: 1,
                endWeek: 4,
                text: "林晓围绕隐私风险、注册材料和招标安排持续查证，冲突信息仍保持未决。",
              }}
              isLoading={false}
              error={null}
              onClose={() => setShowLifeSummaryFixture(false)}
             />
           )}
         </section>
       )}
      {worldFactSetting && (
        <section aria-label="世界事实边界回归夹具">
          <SettingDisplay stepKey="world" data={worldFactSetting} />
        </section>
      )}
      {traitLayoutFixtureEnabled && (
        <section aria-label="角色特质布局回归夹具">
          <SettingDisplay
            stepKey="traits"
            data={{
              personality: "在复杂环境中持续观察细节，并把不确定信息转化为可执行计划。",
              abilities: "能够将分散线索归纳成清晰路径，和不同背景的伙伴保持有效协作。",
              interests: "喜欢研究城市生活里隐藏的故事、旧物与人与人之间微妙的关系。",
              strengths: "面对变化时保持耐心，先核对事实，再作出不仓促的选择。",
              weaknesses: "容易把所有责任都揽在自己身上，需要学习在合适的时候寻求帮助。",
            }}
          />
        </section>
      )}
      <section aria-label="开场完成门控回归夹具" className="space-y-3">
        <div className="flex gap-3">
          <button
            type="button"
            className="rounded border px-3 py-2"
            onClick={() => setOpeningBackendComplete(true)}
          >
            模拟后端完成
          </button>
          <button
            type="button"
            className="rounded border px-3 py-2"
            onClick={() => setOpeningVisibleComplete(true)}
          >
            模拟显示完成
          </button>
        </div>
        <p data-testid="opening-visible-text">
          {openingVisibleComplete ? "最终句子已经完整显示。" : "正在显示最终句子"}
        </p>
        <OpeningCompletionGate
          backendComplete={openingBackendComplete}
          visibleComplete={openingVisibleComplete}
          onStart={() => undefined}
        />
      </section>
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
