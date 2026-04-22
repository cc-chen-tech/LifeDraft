# 音乐混合缓存池设计文档

> 状态：已落地（历史设计记录）  
> 最后核对：2026-04-19

## 背景与问题

当前音乐推荐流程：
1. AI 分析故事（temperature=0.7，每次结果不同）
2. 搜索 8 关键词 × 15 首 = 120 首结果
3. 去重保留 30 首
4. 批量获取每首的播放 URL
5. **过滤掉没有 URL 的**（网易云版权限制，约 70% 被过滤）

最终 30 首 → 过滤后只剩约 9 首，用户体验差。

## 设计目标

- **目标可播放歌曲数**：5-8 首（用户选择 A）
- **缓存策略**：混合方案（方案 C）
  - 缓存 AI 分析结果（避免重复调用 AI）
  - 缓存已验证 URL 的歌曲池（避免重复搜索+验证）
  - 每次从池中随机选 5-8 首返回

## 架构设计

### 核心数据结构

```python
@dataclass
class CachedSong:
    id: int
    name: str
    artists: List[str]
    album: str
    duration: int
    url: str                        # 已验证的播放 URL
    url_expires_at: float           # URL 过期时间（8 分钟）
    verified_at: float              # 验证时间

@dataclass
class CachedMusicPool:
    analysis: Dict[str, Any]        # AI 分析结果（mood、keywords 等）
    verified_songs: List[CachedSong]  # 已验证 URL 的歌曲池
    created_at: float               # 池创建时间
```

### 缓存策略

| 属性 | 值 | 说明 |
|------|---|------|
| 键 | `story_hash`（前 500 字 MD5） | 区分不同故事场景 |
| 池大小 | 最多 25 首已验证歌曲 | 过滤后目标 5-8 首，留余量 |
| 每次返回 | 随机选 5-8 首（不重复） | 同一场景每次有变化 |
| 池 TTL | 60 分钟 | 重建整个池（重新 AI 分析 + 搜索） |
| URL TTL | 8 分钟 | 单独刷新过期 URL，不重建整个池 |

### 数据流

```
POST /music/recommend
  ↓
计算 story_hash
  ↓
缓存命中？
  ├─ YES（池未过期）：
  │    检查池中每首歌的 URL 是否过期
  │    过期的异步重新获取
  │    获取失败的从池中移除
  │    从剩余歌曲中随机选 5-8 首
  │    返回
  └─ NO（无缓存 or 池过期）：
       AI 分析故事 → 获取关键词
       搜索歌曲（8 关键词 × 15 首）
       批量获取 URL，只保留有 URL 的
       存入缓存池（目标 20-25 首）
       从池中随机选 5-8 首
       返回
```

### URL 过期处理

- 每首歌记录 `url_expires_at = now + 480 秒`
- 返回前检查：URL 过期 → 调用 `get_song_url()` 重新获取
- 重新获取失败 → 从池中移除
- 池中歌曲 < 5 首 → 触发补充搜索（用通用关键词）

### 错误处理

| 场景 | 处理 |
|------|------|
| 缓存池存在但歌曲太少（< 5 首） | 补充搜索 + 更新池 |
| URL 刷新全部失败 | 清空池，重建 |
| AI 分析失败 | 用默认关键词，继续搜索 |
| Netease API 失败 | 返回缓存池中的歌曲（如果有） |

## 刷新行为

刷新按钮触发 `refresh=true`：
1. 复用缓存的 AI 分析结果（不重新调用 AI）
2. 打乱关键词顺序（前 3 固定 + 其余随机）
3. 重新搜索歌曲
4. 更新缓存池

## 测试策略

### 新增测试文件

| 测试文件 | 层级 | 覆盖内容 |
|---------|------|---------|
| `test_music_pool_cache_contract.py` | Layer 3 | 缓存池结构、TTL 契约 |
| `test_music_pool_cache_integration.py` | Layer 4 | 缓存命中/ miss / 过期 / 重建 |
| `test_music_pool_random_selection.py` | Layer 4 | 随机选择 5-8 首、不重复 |
| `test_music_pool_url_refresh.py` | Layer 4 | URL 过期刷新、失败移除 |
| `test_music_pool_supplemental_search.py` | Layer 4 | 歌曲 < 5 首时补充搜索 |

### 测试清单

- [ ] `test_pool_cache_hit_returns_random_subset` — 缓存命中返回 5-8 首
- [ ] `test_pool_cache_miss_builds_pool` — 缓存未命中构建新池
- [ ] `test_pool_random_selection_no_duplicates` — 随机选择不重复
- [ ] `test_pool_returns_5_to_8_songs` — 返回数量在 5-8 之间
- [ ] `test_pool_expired_url_refreshes` — URL 过期自动刷新
- [ ] `test_pool_url_refresh_failure_removes_song` — URL 刷新失败移除歌曲
- [ ] `test_pool_rebuilds_after_ttl` — 60 分钟后重建池
- [ ] `test_pool_supplemental_search_when_low` — 歌曲 < 5 首补充搜索
- [ ] `test_pool_all_cached_songs_have_url` — 返回的歌曲全部有 URL
- [ ] `test_refresh_reuses_analysis` — 刷新复用 AI 分析结果
- [ ] `test_refresh_shuffles_keywords` — 刷新打乱关键词顺序
- [ ] `test_pool_size_target_20_25` — 池大小目标 20-25 首

## 兼容性

- 向后兼容：现有 API 接口不变（`/music/recommend`）
- `NeteaseMusicClient._url_cache` 继续保留，作为底层 URL 缓存
- 新增 `MusicService._analysis_cache` 和 `_pool_cache` 作为上层缓存
