## Root Cause

`negative_cues` are currently checked as literal substrings against title, album, and artist metadata. That catches explicit terms such as `等你下课`, but it misses catalog results where the title itself is a known vocal-pop or meme track while the negative cue is a category such as `情歌`, `人声`, or `流行人声`. Separately, recommendations only dedupe by NetEase id, so covers and edited versions of the same title can fill the whole queue.

## Design

- Add canonical title normalization:
  - remove parenthetical suffixes such as `（心动版）` or `(0.98x)`;
  - strip punctuation, whitespace, and common version labels;
  - compare normalized lowercase/casefolded titles.
- Add a small curated rejection set for report-observed vocal-pop/meme failures and existing blocked pop titles.
- Treat generic no-vocal negative cues as a signal to reject those curated vocal-pop/meme titles even if the exact category word is absent from metadata.
- Expose a production `MusicResultRanker.filter_and_dedupe` method and use it in `_random_select_songs`.
- Keep result ranking behavior for compatible instrumental/background tracks.

## Non-goals

- Building a full music classifier.
- Blocking all vocal music forever; this only applies to gameplay background briefs that already ask for no vocals/no lyrics or list vocal negative cues.
- Changing MiniMax generated music behavior.
- Calling the external NetEase service from tests.
