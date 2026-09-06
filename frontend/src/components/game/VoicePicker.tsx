"use client";

import { Check, Headphones, Play, Search, X } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import type { MiniMaxVoiceOption } from "@/lib/types";
import { cn } from "@/lib/utils";

interface VoicePickerProps {
  voices: MiniMaxVoiceOption[];
  selectedVoiceId: string;
  previewingVoice: string | null;
  onSelectVoice: (voiceId: string) => void;
  onPreviewVoice: (voiceId: string) => void;
}

const STORY_LANGUAGES = ["普通话", "粤语"] as const;
const RECOMMENDED_VOICE_IDS = [
  "female-shaonv",
  "male-qn-qingse",
  "female-yujie",
  "female-chengshu",
];
const FALLBACK_VOICES: MiniMaxVoiceOption[] = [
  { voice_id: "female-shaonv", label: "少女音色", language: "普通话", group: "标准音色", recommended: true },
  { voice_id: "male-qn-qingse", label: "青涩青年音色", language: "普通话", group: "标准音色", recommended: true },
  { voice_id: "female-yujie", label: "御姐音色", language: "普通话", group: "标准音色", recommended: true },
  { voice_id: "female-chengshu", label: "成熟女性音色", language: "普通话", group: "标准音色", recommended: true },
];

function Waveform() {
  return (
    <span aria-hidden="true" className="flex h-5 items-center gap-0.5">
      {[8, 14, 20, 12, 17].map((height, index) => (
        <span
          key={index}
          className="w-0.5 rounded-full bg-[var(--text-secondary)]"
          style={{ height }}
        />
      ))}
    </span>
  );
}

export function VoicePicker({
  voices,
  selectedVoiceId,
  previewingVoice,
  onSelectVoice,
  onPreviewVoice,
}: VoicePickerProps) {
  const [libraryOpen, setLibraryOpen] = useState(false);
  const [language, setLanguage] = useState<(typeof STORY_LANGUAGES)[number]>("普通话");
  const [search, setSearch] = useState("");
  const catalog = voices.length > 0 ? voices : FALLBACK_VOICES;
  const selectedVoice = catalog.find((voice) => voice.voice_id === selectedVoiceId) ?? catalog[0];
  const recommendedVoices = RECOMMENDED_VOICE_IDS
    .map((voiceId) => catalog.find((voice) => voice.voice_id === voiceId))
    .filter((voice): voice is MiniMaxVoiceOption => Boolean(voice));
  const visibleVoices = useMemo(() => {
    const query = search.trim().toLowerCase();
    return catalog.filter((voice) => {
      if (voice.language !== language) return false;
      return !query || [voice.label, voice.language, voice.group]
        .some((value) => value.toLowerCase().includes(query));
    });
  }, [catalog, language, search]);
  const groupedVoices = useMemo(() => {
    const groups = new Map<string, MiniMaxVoiceOption[]>();
    visibleVoices.forEach((voice) => {
      const group = groups.get(voice.group) ?? [];
      group.push(voice);
      groups.set(voice.group, group);
    });
    return [...groups.entries()];
  }, [visibleVoices]);

  useEffect(() => {
    if (!libraryOpen) return undefined;
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setLibraryOpen(false);
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [libraryOpen]);

  const closeLibrary = () => setLibraryOpen(false);
  const selectVoice = (voiceId: string) => {
    onSelectVoice(voiceId);
    closeLibrary();
  };

  return (
    <div className="mt-7 border-y border-[var(--border-default)] py-6">
      <div className="mb-4 flex items-center justify-between gap-4">
        <div>
          <p className="text-xs text-[var(--text-secondary)]">旁白音色</p>
          <p className="mt-1 text-sm text-[var(--text-primary)]">选一个适合故事气质的声音，随时可以试听。</p>
        </div>
        <button
          type="button"
          className="min-h-11 shrink-0 rounded-[var(--radius-control)] px-3 text-sm text-[var(--text-secondary)] transition-colors hover:bg-[var(--surface-subtle)] hover:text-[var(--text-primary)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)]"
          onClick={() => setLibraryOpen(true)}
          aria-label="查看全部中文音色"
          aria-haspopup="dialog"
          aria-expanded={libraryOpen}
        >
          查看全部中文音色
          <span aria-hidden="true" className="ml-1">→</span>
        </button>
      </div>

      <div className="mb-6 flex flex-col justify-between gap-4 rounded-[var(--radius-control)] border border-[var(--border-strong)] bg-[var(--surface-raised)] px-4 py-4 sm:flex-row sm:items-center sm:px-5">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <p className="text-lg font-semibold text-[var(--text-primary)]">{selectedVoice.label}</p>
            <span className="rounded-full border border-[var(--border-strong)] bg-[var(--surface-subtle)] px-2 py-1 text-[11px] text-[var(--text-secondary)]">
              {selectedVoice.language} · 当前使用
            </span>
          </div>
          <p className="mt-1 text-xs text-[var(--text-secondary)]">MiniMax 官方中文音色</p>
        </div>
        <button
          type="button"
          className="inline-flex min-h-10 shrink-0 items-center justify-center gap-1.5 rounded-[var(--radius-control)] border border-[var(--border-interactive)] px-3 text-sm text-[var(--text-primary)] transition-colors hover:bg-[var(--surface-subtle)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)]"
          onClick={() => onPreviewVoice(selectedVoice.voice_id)}
          disabled={previewingVoice === selectedVoice.voice_id}
          aria-label="试听当前音色"
        >
          <Headphones className="h-4 w-4" />
          {previewingVoice === selectedVoice.voice_id ? "试听中" : "试听当前音色"}
        </button>
      </div>

      <div className="mb-3 flex items-center justify-between gap-4">
        <h3 className="text-sm font-semibold text-[var(--text-primary)]">为故事推荐</h3>
        <span className="text-xs text-[var(--text-secondary)]">点击卡片即可选择</span>
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        {recommendedVoices.map((voice) => (
          <div
            key={voice.voice_id}
            className={cn(
              "relative rounded-[var(--radius-control)] border bg-[var(--surface-raised)] p-4 transition-colors",
              voice.voice_id === selectedVoice.voice_id
                ? "border-[var(--border-strong)] bg-[var(--surface-subtle)]"
                : "border-[var(--border-default)] hover:border-[var(--border-strong)]",
            )}
          >
            <button
              type="button"
              className="block min-h-24 w-full text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--surface-reading)]"
              onClick={() => selectVoice(voice.voice_id)}
              aria-label={`选择${voice.label}`}
            >
              <Waveform />
              <span className="mt-3 block text-sm font-semibold text-[var(--text-primary)]">{voice.label}</span>
              <span className="mt-1 block text-xs text-[var(--text-secondary)]">{voice.language}</span>
            </button>
            <button
              type="button"
              className="absolute bottom-3 right-3 inline-flex min-h-9 items-center gap-1 rounded px-2 text-xs text-[var(--text-secondary)] transition-colors hover:bg-[var(--surface-subtle)] hover:text-[var(--text-primary)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)]"
              onClick={() => onPreviewVoice(voice.voice_id)}
              disabled={previewingVoice === voice.voice_id}
              aria-label={`试听${voice.label}`}
            >
              <Play className="h-3 w-3" />
              {previewingVoice === voice.voice_id ? "试听中" : "试听"}
            </button>
          </div>
        ))}
      </div>

      {libraryOpen ? (
        <div
          className="fixed inset-0 z-50 flex justify-end bg-black/50"
          role="presentation"
          onClick={(event) => { if (event.target === event.currentTarget) closeLibrary(); }}
        >
          <section
            className="h-full w-full max-w-md overflow-y-auto border-l border-[var(--border-default)] bg-[var(--surface-reading)] px-5 py-6 shadow-2xl sm:px-7"
            role="dialog"
            aria-modal="true"
            aria-labelledby="voice-library-title"
          >
            <div className="mb-5 flex items-start justify-between gap-4">
              <div>
                <p className="text-xs tracking-[0.16em] text-[var(--text-secondary)]">官方音色</p>
                <h2 id="voice-library-title" className="mt-1 text-xl font-semibold text-[var(--text-primary)]">全部中文音色</h2>
              </div>
              <button
                type="button"
                className="inline-flex h-10 w-10 items-center justify-center rounded-[var(--radius-control)] text-[var(--text-secondary)] hover:bg-[var(--surface-subtle)] hover:text-[var(--text-primary)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)]"
                onClick={closeLibrary}
                aria-label="关闭全部中文音色"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <label className="flex min-h-11 items-center gap-2 rounded-[var(--radius-control)] border border-[var(--border-default)] bg-[var(--surface-canvas)] px-3 text-[var(--text-secondary)]" htmlFor="voice-search">
              <Search className="h-4 w-4 shrink-0" />
              <input
                id="voice-search"
                type="search"
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder="搜索名称，例如：少女、男声、旁白、粤语"
                className="min-w-0 flex-1 bg-transparent text-sm text-[var(--text-primary)] outline-none placeholder:text-[var(--text-secondary)]"
                aria-label="搜索音色"
              />
            </label>

            <div className="my-5 flex gap-2" role="tablist" aria-label="语言筛选">
              {STORY_LANGUAGES.map((item) => (
                <button
                  key={item}
                  type="button"
                  role="tab"
                  aria-selected={language === item}
                  className={cn(
                    "rounded-full border px-3 py-1.5 text-xs transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)]",
                    language === item
                      ? "border-[var(--border-strong)] bg-[var(--surface-subtle)] text-[var(--text-primary)]"
                      : "border-[var(--border-default)] text-[var(--text-secondary)] hover:text-[var(--text-primary)]",
                  )}
                  onClick={() => setLanguage(item)}
                >
                  {item}
                </button>
              ))}
            </div>

            <div aria-live="polite">
              {groupedVoices.length > 0 ? groupedVoices.map(([group, groupVoices]) => (
                <section key={group} className="mt-5">
                  <h3 className="mb-2 text-xs font-medium text-[var(--text-secondary)]">{group}</h3>
                  <div className="space-y-1">
                    {groupVoices.map((voice) => {
                      const selected = voice.voice_id === selectedVoice.voice_id;
                      return (
                        <div
                          key={voice.voice_id}
                          className={cn(
                            "flex min-h-12 w-full items-center justify-between gap-2 rounded-[var(--radius-control)] px-3 text-left text-sm transition-colors",
                            selected
                              ? "bg-[var(--surface-subtle)] text-[var(--text-primary)]"
                              : "text-[var(--text-primary)] hover:bg-[var(--surface-subtle)]",
                          )}
                        >
                          <button
                            type="button"
                            className="flex min-h-10 min-w-0 flex-1 items-center gap-2 rounded-[var(--radius-control)] text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)]"
                            onClick={() => selectVoice(voice.voice_id)}
                            aria-label={`选择${voice.label}`}
                          >
                            <span className="truncate">{voice.label}</span>
                            {selected ? <Check className="h-3.5 w-3.5 shrink-0 text-[var(--text-secondary)]" /> : null}
                          </button>
                          <button
                            type="button"
                            className="inline-flex min-h-9 shrink-0 items-center gap-1 rounded px-2 text-xs text-[var(--text-secondary)] transition-colors hover:bg-[var(--surface-canvas)] hover:text-[var(--text-primary)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)]"
                            onClick={() => onPreviewVoice(voice.voice_id)}
                            disabled={previewingVoice === voice.voice_id}
                            aria-label={`试听${voice.label}`}
                          >
                            <Play className="h-3 w-3" />
                            {previewingVoice === voice.voice_id ? "试听中" : "试听"}
                          </button>
                        </div>
                      );
                    })}
                  </div>
                </section>
              )) : (
                <p className="py-10 text-center text-sm text-[var(--text-secondary)]">没有找到匹配的中文音色</p>
              )}
            </div>
            <p className="mt-7 border-t border-[var(--border-default)] pt-4 text-xs text-[var(--text-secondary)]">只显示中文音色 · 选择后会用于下一次生成</p>
          </section>
        </div>
      ) : null}
    </div>
  );
}
