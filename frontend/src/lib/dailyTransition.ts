import type { DayHistoryEntry, PlayerState } from "@/lib/types";


const DAILY_TRANSITION_FALLBACKS = [
  "话音落下，未散的余韵正悄然走向明日。",
  "决定留在身后，新的晨光已在时间深处亮起。",
  "这一刻渐渐安静，明日的光已落在前路。",
  "余音慢慢沉静，时间轻轻翻向了新的一页。",
  "未尽的话留在原地，日子已缓缓迈向清晨。",
  "心绪尚未平复，远处的天光已替明日开场。",
  "这番取舍有了回声，而日历正无声翻页。",
  "目光从此刻移开时，新的一日已悄然临近。",
  "决定的余温仍在，时间却已把故事带向明日。",
  "沉默收拢了这一刻，下一页正随天光展开。",
  "今日的回声渐远，明日已从静处缓缓靠近。",
  "那份心意安静落定，时间随之走向新的一天。",
  "片刻之后风声渐轻，日子又向前走了一格。",
  "这一念被妥善收下，明日的门扉正缓缓开启。",
  "尚存的余韵没有消散，却已随时间越过今夜。",
  "此刻终于沉静下来，新的一天正从远处靠近。",
] as const;

const DAILY_TRANSITION_FALLBACKS_EN = [
  "The choice settles quietly as tomorrow draws nearer.",
  "Its aftertaste lingers while the day turns forward.",
  "The moment grows still, and a new day approaches.",
  "What was decided remains as time opens the next page.",
  "The echo stays behind while morning edges closer.",
  "The thought settles, and time carries it toward tomorrow.",
  "The moment closes gently as another day comes into view.",
  "Its quiet weight remains while the calendar turns.",
  "The choice finds its place, and the next day draws near.",
  "The lingering feeling follows time into a new morning.",
  "The day releases its hold as the next one approaches.",
  "What remains unsaid grows quiet before another day.",
  "The moment recedes, leaving tomorrow just ahead.",
  "Its meaning lingers while time moves one day onward.",
  "The last echo softens as a new day begins to gather.",
  "The choice rests quietly on the threshold of tomorrow.",
] as const;


function normalizeTransition(text: string): string {
  return text.replace(/[\s，。！？、,.!?;；:：—\-]+/g, "").toLocaleLowerCase();
}


export function resolveDailyTransitionLanguage(
  playerState: PlayerState | null,
): "zh" | "en" {
  const explicit = playerState?.language;
  if (explicit === "zh" || explicit === "en") return explicit;

  const settings = playerState?.character_settings as Record<string, unknown> | undefined;
  const era = settings?.era as Record<string, unknown> | undefined;
  const description = typeof era?.era_description === "string"
    ? era.era_description
    : "";
  const compact = description.replace(/\s/g, "");
  return compact && [...compact].every((character) => character.charCodeAt(0) < 128)
    ? "en"
    : "zh";
}


export function deterministicDailyTransition(
  dayIndex: number,
  optionIndex = 0,
  recentTransitions: string[] = [],
  language: "zh" | "en" = "zh",
): string {
  const pool = language === "en"
    ? DAILY_TRANSITION_FALLBACKS_EN
    : DAILY_TRANSITION_FALLBACKS;
  const excluded = new Set(recentTransitions.map(normalizeTransition));
  const start = (Math.max(0, dayIndex) * 3 + Math.max(0, optionIndex))
    % pool.length;
  for (let offset = 0; offset < pool.length; offset += 1) {
    const candidate = pool[
      (start + offset) % pool.length
    ];
    if (!excluded.has(normalizeTransition(candidate))) return candidate;
  }
  return pool[start];
}


export function transitionForHistoryEntry(
  entry: DayHistoryEntry,
  history: DayHistoryEntry[],
  language: "zh" | "en" = "zh",
): string {
  const pool = language === "en"
    ? DAILY_TRANSITION_FALLBACKS_EN
    : DAILY_TRANSITION_FALLBACKS;
  if (typeof entry.transition_text === "string") {
    const persisted = entry.transition_text.trim();
    if ((pool as readonly string[]).includes(persisted)) {
      return persisted;
    }
  }
  const recent = history
    .filter((candidate) => candidate.day_index < entry.day_index)
    .slice(-12)
    .map((candidate) => candidate.transition_text || "")
    .filter(Boolean);
  return deterministicDailyTransition(
    entry.day_index,
    entry.choice_option_index ?? 0,
    recent,
    language,
  );
}


export function formatDailyDate(date: string): string {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(date);
  if (!match) return date;
  return `公元 ${match[1]} 年 ${Number(match[2])} 月 ${Number(match[3])} 日`;
}
