## Context

Music recommendations are produced in two stages: NetEase search results are filtered into a verified pool, then selected recommendations are persisted into a per-game playlist. The previous fix filters exact negative-cue substrings and duplicate ids, but the UX report shows duplicate title families and reported vocal-pop mismatches still leaking through as different ids or title variants.

## Goals / Non-Goals

**Goals:**

- Reject reported negative-cue title families after NetEase search.
- Treat title variants from the same reported family as duplicates.
- Prevent duplicate title-family variants from being persisted into the future queue.
- Preserve the current song when refreshing recommendations.

**Non-Goals:**

- Build a general-purpose music classifier.
- Replace NetEase recommendation with generated music.
- Change the audio playback UI.
- Block every vocal song globally; filtering applies to briefs that request no vocals/lyrics or include vocal-pop negative cues.

## Decisions

1. Use deterministic title-family normalization.

   The service already normalizes version suffixes. This change extends normalization with reported aliases/families such as "绅士", "红尘客栈", "非你莫属", and "给我一首歌的时间". This is more predictable than adding another LLM judgment call inside the hot recommendation path.

2. Filter before URL verification and again before returning ranked songs.

   Filtering before URL verification avoids spending requests on known-bad results. Filtering before final selection protects cached pools created before the new policy and keeps refresh behavior stable.

3. Dedupe playlist merges by song id and title family.

   NetEase can return the same title family under multiple ids. The persistent playlist is the consumer-facing queue, so it must enforce the same quality contract rather than trusting the upstream recommendation list.

## Risks / Trade-offs

- Reported-family filtering may reject a legitimate instrumental cover with the same title -> Only applies when the music brief requests no vocals/lyrics or contains vocal-pop negative cues, which matches background gameplay usage.
- Deterministic lists can lag future reports -> The list is centralized and contract-tested so future tail failures can be added without changing queue semantics.
- Title-family dedupe can reduce queue size -> Better to return fewer suitable songs than many repeated mismatches; generated music remains a supplement.
