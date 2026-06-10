## Why

The 2026-06-08 UX report shows a regression where a new modern save started with a classical chapter title such as "第三回 ...". The current prompt logic only treats a story as modern when explicit modern keywords are present, so ordinary age/career settings can fall back to classical chapter constraints.

## What Changes

- Treat non-ancient Chinese character settings as modern by default for chapter title constraints.
- Keep explicit ancient/wuxia/xianxia settings on the classical chapter path.
- Make inline/segment rewrite prompts inherit the same title constraint, so an existing bad "第X回" title is corrected instead of preserved.
- Add a contract regression and wire it into `test.sh contract`.

## Impact

- Prompt construction only.
- No API or database schema changes.
