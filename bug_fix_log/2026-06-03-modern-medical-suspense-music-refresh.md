# 2026-06-03 现代医疗悬疑音乐推荐与刷新修复

## 问题

第 4 周现代医疗数据造假、追捕、逃亡悬疑剧情中，音乐推荐前排出现 `匆匆那年`、`告白气球`、`喜欢你` 等恋爱/流行曲目；点击“换一批”后，前端仍按普通推荐请求发送，后端也从同一组搜索词开头重建 pool，容易返回同一批候选。

## 原因

- `MusicBrief.from_analysis()` 直接信任 AI 返回的 `search_queries` / `keywords`，没有在悬疑、追捕、医疗造假语境中过滤恋爱流行曲名。
- 旧 `_build_search_keywords()` 把 `现代` / `都市` 映射到 `流行`，且古代时代词也可能被 AI keyword 挤出前排。
- `refresh=True` 只绕过 pool cache 并复用 analysis，但没有 query cursor 或 query 顺序变化。
- `MusicPlayer` 的“换一批”按钮调用推荐接口时没有传 `refresh: true`。

## 修复

- 为现代悬疑/医疗/追捕语境前置 `医疗悬疑 氛围音乐`、`追捕逃亡 紧张配乐`、`现代悬疑 纯音乐`、`悬疑 影视配乐`、`无歌词 紧张氛围` 等搜索词。
- 在该语境中过滤恋爱、情歌、甜蜜、告白、青春流行以及具体恋爱流行曲名，并补充到 `negative_cues`。
- 为 `CachedMusicPool` 增加 `query_cursor`，`refresh=True` 时递增 cursor 并轮换搜索 query，使“换一批”至少刷新搜索入口。
- 前端“换一批”按钮改为调用 `fetchMusicRecommendation(..., refresh=true)`。

## 测试

- 新增现代医疗追捕悬疑 contract 测试，确保前排 query 不再是恋爱流行曲名。
- 新增 refresh cursor 测试，确保连续刷新推进 query cursor 且首个搜索 query 改变。
- 新增 MusicPlayer 按钮测试，确保第二次推荐请求体包含 `refresh: true`。

## 验证命令

```bash
pytest -q tests/test_story_music_recommendation_contract.py tests/test_music_era_recommendation_contract.py tests/test_music_pool_cache_integration.py::TestGetOrBuildPool
npx jest --runTestsByPath src/__tests__/components/game/MusicPlayer.test.tsx --runInBand
pytest -q tests/test_music_playlist_contract.py tests/test_music_playlist_imports.py
npx jest --runTestsByPath src/__tests__/stores/useMusicStore.musicQueuePolicy.test.ts --runInBand
```
