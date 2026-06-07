# MiniMax 生成音频资产 Git 忽略修复记录

## 问题
运行 MiniMax 故事朗读和 AI 音乐相关本地测试后，会在 `data/music_assets/` 与 `data/voice_assets/` 下生成 wav 音频文件。此前 `.gitignore` 没有忽略这两个目录，导致测试产物出现在工作区未跟踪文件中，容易被误提交。

## 复现
1. 运行包含 MiniMax 本地音频模式的测试，例如 `./test.sh preflight` 或 `./test.sh contract`。
2. 查看 `git status --short`。
3. 可看到 `data/music_assets/`、`data/voice_assets/` 作为未跟踪文件出现。

## 修复
1. 当前分支已在 `tests/test_gate_preflight_no_mock.py` 中加入 preflight 规则，要求 `.gitignore` 覆盖 MiniMax 生成音频目录。
2. 当前分支已在 `.gitignore` 中加入：
   - `data/music_assets/`
   - `data/voice_assets/`

## 验证
- 本轮核实 `.gitignore` 与 preflight 测试均已存在。
- 重跑：
  - `python -m pytest tests/test_gate_preflight_no_mock.py::test_generated_minimax_audio_assets_are_gitignored -q`
- 验证通过，生成资产变为 ignored，不再污染待提交文件列表。
