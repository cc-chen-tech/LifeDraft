"""Round illustration service - 每轮对话场景插画生成服务.

负责在每一轮对话结束时生成场景插画：
1. 使用 DeepSeek 分析故事选择重要场景
2. 检查涉及的人物/物件是否已有图片，没有则异步生成
3. 使用图生图生成场景插画
4. 异步执行，不阻塞游戏流程
"""

import logging
from typing import Any, Callable, Dict, List, Optional, Tuple

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from config.settings import settings
from src.ai.image_client import ImageClient
from src.ai.image_exceptions import (ContentInspectionError,
                                     ImageGenerationError)
from src.database.models import Image as ImageModel
from src.database.models import SceneImage
from src.services.image_service import get_image_thread_pool  # C-05: 使用共享线程池
from src.services.image_storage import ImageStorageService

logger = logging.getLogger(__name__)


class RoundIllustrationService:
    """Service for generating round event illustrations."""

    def __init__(
        self,
        image_client: ImageClient,
        image_storage: ImageStorageService,
        db_session: Session,
    ):
        """
        Args:
            image_client: ImageClient instance for image generation
            image_storage: ImageStorageService for saving images
            db_session: Database session
        """
        self.image_client = image_client
        self.image_storage = image_storage
        self.db = db_session

    def generate_round_illustration_async(
        self,
        game_id: int,
        round_number: int,
        story_text: str,
        character_settings: Dict[str, Any],
        player_name: str,
        existing_images: List[Dict[str, Any]],
        stage: str = "event",  # ★ 新增 stage 参数
        week: Optional[int] = None,  # ★ 新增 week 参数
        world_model_data: Optional[Dict[str, Any]] = None,
        established_facts: Optional[List[Dict[str, Any]]] = None,
        story_date: Optional[str] = None,
        day_index: Optional[int] = None,
        validity_callback: Optional[Callable[[], bool]] = None,
    ) -> None:
        """
        异步生成每轮场景插画（不阻塞主流程）

        Args:
            game_id: 游戏ID
            round_number: 轮次
            story_text: 故事文本
            character_settings: 角色设定
            player_name: 玩家名称
            existing_images: 已有的图片列表 [{image_id, entity_name, image_type, image_url}]
            stage: 场景阶段 (event=事件故事, result=结果故事)
            week: 周数
            world_model_data: 世界模型数据（用于识别跨轮次反复出现的实体/物品）
            established_facts: 已建立的世界事实列表（含 category="item" 的重要物品）
        """
        # C-05: 使用线程池替代裸线程
        get_image_thread_pool().submit(
            self._generate_round_illustration_sync,
            game_id,
            round_number,
            story_text,
            character_settings,
            player_name,
            existing_images,
            stage,  # ★ 传递 stage 参数
            week,  # ★ 传递 week 参数
            world_model_data,
            established_facts,
            story_date,
            day_index,
            validity_callback,
        )
        week_display = f"第{week + 1}周" if week is not None else "未知周"
        logger.info(
            f"[RoundIllustration] 启动异步生成: game={game_id}, {week_display}, round {round_number}, stage={stage}"
        )

    def generate_round_illustration(
        self,
        game_id: int,
        round_number: int,
        story_text: str,
        character_settings: Dict[str, Any],
        player_name: str,
        existing_images: List[Dict[str, Any]],
        stage: str = "event",
        week: Optional[int] = None,
        world_model_data: Optional[Dict[str, Any]] = None,
        established_facts: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        """Generate a scene on the caller's already-bounded worker."""
        self._generate_round_illustration_sync(
            game_id,
            round_number,
            story_text,
            character_settings,
            player_name,
            existing_images,
            stage,
            week,
            world_model_data,
            established_facts,
        )

    def _generate_round_illustration_sync(
        self,
        game_id: int,
        round_number: int,
        story_text: str,
        character_settings: Dict[str, Any],
        player_name: str,
        existing_images: List[Dict[str, Any]],
        stage: str = "event",  # ★ 新增 stage 参数
        week: Optional[int] = None,  # ★ 新增 week 参数
        world_model_data: Optional[Dict[str, Any]] = None,
        established_facts: Optional[List[Dict[str, Any]]] = None,
        story_date: Optional[str] = None,
        day_index: Optional[int] = None,
        validity_callback: Optional[Callable[[], bool]] = None,
    ) -> None:
        """同步生成每轮场景插画（在后台线程中执行）

        Args:
            stage: 场景阶段 (event=事件故事, result=结果故事)
            week: 周数
            world_model_data: 世界模型数据（用于识别跨轮次反复出现的实体/物品）
            established_facts: 已建立的世界事实列表（含 category="item" 的重要物品）
        """
        try:
            # ★ 如果没有传入 week，尝试从数据库获取
            if week is None:
                week = self._get_current_week_from_db(game_id)
            # Step 1: 使用 DeepSeek 分析故事选择场景
            char_info = {
                "name": player_name,
                "era": self._extract_era_from_settings(character_settings),
            }

            scene_desc, illustration_prompt = self.image_client.analyze_story_for_illustration(
                story_text=story_text[:2000],  # 限制长度避免token超限
                character_info=char_info,
            )

            logger.info(f"[RoundIllustration] Selected scene: {scene_desc[:50]}...")

            # Step 2: 检查并获取参考图片
            reference_urls = []
            referenced_image_ids = []

            # 优先使用玩家主形象作为参考
            player_image = self._get_player_image(existing_images)
            if player_image:
                ref_url = self._get_image_url_as_base64(
                    player_image, game_id=game_id
                )  # ★ 传递 game_id 验证归属
                if ref_url:
                    reference_urls.append(ref_url)
                    referenced_image_ids.append(player_image.get("image_id"))

            # 检查故事中涉及的其他人物/物件/地点
            involved_entities = self._extract_involved_entities(
                story_text,
                character_settings,
                world_model_data=world_model_data,
                established_facts=established_facts,
            )
            for entity in involved_entities:
                entity_name = entity.get("name")
                entity_type = entity.get("type", "character")
                entity_desc = entity.get("description", "")

                entity_image = self._find_entity_image(existing_images, entity_name or "")
                if entity_image:
                    ref_url = self._get_image_url_as_base64(
                        entity_image, game_id=game_id
                    )  # ★ 传递 game_id 验证归属
                    if ref_url:
                        reference_urls.append(ref_url)
                        referenced_image_ids.append(entity_image.get("image_id"))
                elif settings.AUTO_GENERATE_ENTITY_IMAGES_FOR_SCENES:
                    # ★ 如果实体没有图片，自动生成
                    logger.info(
                        f"[RoundIllustration] {entity_type} '{entity_name}' has no image, auto-generating..."
                    )
                    try:
                        new_image = self._generate_entity_image(
                            game_id=game_id,
                            entity_name=entity_name or "",
                            entity_type=entity_type,
                            description=entity_desc,
                            era=char_info["era"],
                        )
                        if new_image:
                            # 生成成功，加入参考列表（新图片已属于当前游戏，无需再验证）
                            ref_url = self._get_image_url_as_base64(
                                {
                                    "image_id": new_image.image_id,
                                    "storage_path": new_image.storage_path,
                                    "storage_type": new_image.storage_type,
                                },
                                game_id=game_id,
                            )  # ★ 传递 game_id
                            if ref_url:
                                reference_urls.append(ref_url)
                                referenced_image_ids.append(new_image.image_id)
                                logger.info(
                                    f"[RoundIllustration] Auto-generated {entity_type} image for '{entity_name}': image_id={new_image.image_id}"
                                )
                    except Exception as e:
                        logger.warning(
                            f"[RoundIllustration] Failed to auto-generate {entity_type} image for '{entity_name}': {e}"
                        )
                else:
                    logger.info(
                        f"[RoundIllustration] Skipping auto-generation for {entity_type} '{entity_name}'"
                    )

            # Step 3: 生成场景插画
            image_data, final_prompt = self._generate_scene_image(
                scene_desc=scene_desc,
                illustration_prompt=illustration_prompt,
                reference_urls=reference_urls,
                era=char_info["era"],
            )

            # A rewrite/regeneration may have replaced this event while image
            # generation was running. Never write media derived from a stale
            # revision back into the current day's cache.
            if validity_callback is not None and not validity_callback():
                logger.info(
                    "[RoundIllustration] Discarding stale daily illustration: "
                    "game=%s day=%s",
                    game_id,
                    day_index,
                )
                return

            # Step 4: 保存图片 - 包含完整层级信息
            # ★ week 从0开始，entity_name 显示时 +1，与前端一致
            display_week = (week + 1) if week is not None else 0
            storage_path, storage_type = self.image_storage.save_image(
                image_data=image_data,
                game_id=game_id,
                image_type="round_scene",
                entity_name=f"{player_name}_week_{display_week}_round_{round_number}",
                week=week,
                round_number=round_number,
                stage=stage,
            )

            # Step 5: 创建数据库记录 - 包含 week 字段
            scene_image = SceneImage(
                game_id=game_id,
                week=week,  # ★ 新增：周数
                round_number=round_number,
                stage=stage,  # ★ 设置 stage 字段
                scene_description=scene_desc,
                final_prompt=final_prompt,
                storage_path=storage_path,
                storage_type=storage_type,
                referenced_images=referenced_image_ids,
                importance_score="high",  # 由DeepSeek分析得出
                story_date=story_date,
                day_index=day_index,
            )

            self.db.add(scene_image)
            try:
                self.db.commit()
            except IntegrityError as exc:
                self.db.rollback()
                error_text = str(exc)
                if "UNIQUE constraint failed" not in error_text or "scene_images" not in error_text:
                    raise

                existing_scene = (
                    self.db.query(SceneImage)
                    .filter(
                        SceneImage.game_id == game_id,
                        SceneImage.week == week,
                        SceneImage.round_number == round_number,
                        SceneImage.stage == stage,
                    )
                    .first()
                )
                if existing_scene is None:
                    raise
                logger.warning(
                    "[RoundIllustration] 场景插画唯一约束冲突: "
                    "game=%s, week=%s, round=%s, stage=%s，跳过重复记录",
                    game_id,
                    week,
                    round_number,
                    stage,
                )
                return

            week_display = f"第{week + 1}周" if week is not None else "未知周"
            logger.info(
                f"[RoundIllustration] 场景插画生成完成: scene_id={scene_image.scene_id}, {week_display}, stage={stage}"
            )

        except ContentInspectionError as e:
            logger.warning(f"[RoundIllustration] Content inspection failed: {e}")
            raise  # ★ 重新抛出，让调用方知悉失败
        except ImageGenerationError as e:
            logger.error(f"[RoundIllustration] Image generation failed: {e}")
            raise  # ★ 重新抛出，避免外层打印虚假的 "success" 日志
        except Exception as e:
            logger.error(f"[RoundIllustration] Unexpected error: {e}")
            self.db.rollback()
            raise  # ★ 重新抛出未知异常

    def _generate_scene_image(
        self,
        scene_desc: str,
        illustration_prompt: str,
        reference_urls: List[str],
        era: str,
    ) -> Tuple[bytes, str]:
        """
        生成场景图片

        如果有参考图片，使用图生图；否则使用文生图
        """
        # 构建最终prompt
        final_prompt = f"""电影感故事场景插画。
时代背景：{era}。
场景：{scene_desc}
{illustration_prompt}
风格：写实风格，光影自然，故事感强，电影构图。"""

        if reference_urls:
            # 使用第一个参考图片进行图生图
            # 如果有多个人物，可以叠加使用
            edit_prompt = f"""基于参考图片，重新绘制以下场景：
{scene_desc}
{illustration_prompt}
保持人物的外貌特征和服装不变，融入新的场景环境中。"""

            try:
                results = self.image_client.edit_image(
                    reference_image=reference_urls[0],  # 使用主参考图
                    prompt=edit_prompt,
                    size="1664*928",  # 16:9 宽屏
                    num_images=1,
                )

                if results:
                    image_data, _ = results[0]
                    return image_data, final_prompt
            except ContentInspectionError:
                # 内容审核错误不重试，直接抛出（降级也无意义，prompt 本身有问题）
                raise
            except ImageGenerationError as e:
                logger.warning(
                    f"[RoundIllustration] Edit image failed: {e}, "
                    f"falling back to text-to-image (reference_urls={len(reference_urls)})"
                )

            # ★ 降级到文生图：edit 失败时仍要保证用户能看到场景插画
            logger.info("[RoundIllustration] Falling back to text-to-image generation")
            image_data, _ = self.image_client.generate_image(
                prompt=final_prompt,
                size="1664*928",
                extra_params={"prompt_extend": True},
            )
            return image_data, final_prompt
        else:
            # 没有参考图片，使用文生图
            image_data, _ = self.image_client.generate_image(
                prompt=final_prompt,
                size="1664*928",
                extra_params={"prompt_extend": True},
            )
            return image_data, final_prompt

    def _get_player_image(self, existing_images: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """获取玩家主形象图片"""
        for img in existing_images:
            if img.get("image_type") == "character" and img.get("entity_key") == "player_main":
                return img
        # 如果没有标记为player_main的，返回第一个character图片
        for img in existing_images:
            if img.get("image_type") == "character":
                return img
        return None

    def _find_entity_image(
        self,
        existing_images: List[Dict[str, Any]],
        entity_name: str,
    ) -> Optional[Dict[str, Any]]:
        """查找指定实体的图片"""
        for img in existing_images:
            if img.get("entity_name") == entity_name:
                return img
        return None

    def _get_image_url_as_base64(
        self, image_info: Dict[str, Any], game_id: Optional[int] = None
    ) -> Optional[str]:
        """获取图片的base64格式（用于图生图API）

        Args:
            image_info: 图片信息字典，包含 image_id
            game_id: 可选的游戏ID，用于验证图片归属
        """
        try:
            image_id = image_info.get("image_id")
            if not image_id:
                return None

            # 从数据库获取图片数据
            # ★ 如果提供了 game_id，验证图片归属，避免跨游戏数据泄漏
            if game_id is not None:
                image_model = (
                    self.db.query(ImageModel)
                    .filter(
                        ImageModel.image_id == image_id,
                        ImageModel.game_id == game_id,  # ★ 必须属于当前游戏
                    )
                    .first()
                )
            else:
                # 向后兼容：如果没有提供 game_id，只按 image_id 查询（不推荐）
                image_model = (
                    self.db.query(ImageModel).filter(ImageModel.image_id == image_id).first()
                )

            if not image_model:
                return None

            # 读取图片文件
            image_data = self.image_storage.get_image_data(
                str(image_model.storage_path), str(image_model.storage_type) if image_model.storage_type else None  # type: ignore[arg-type]
            )
            if not image_data:
                return None

            # ★ 压缩参考图片：图生图 API 不需要高分辨率参考图，
            # 过大的 base64 payload 会导致上传超时（如 2.3MB PNG → ~3MB base64）
            image_data = self._compress_reference_image(image_data)

            # 转换为base64
            import base64

            # 压缩后统一用 JPEG（更小），即使是原 PNG
            mime_type = "image/jpeg"
            base64_data = base64.b64encode(image_data).decode("utf-8")

            return f"data:{mime_type};base64,{base64_data}"

        except Exception as e:
            logger.warning(f"[RoundIllustration] Failed to get image as base64: {e}")
            return None

    def _compress_reference_image(
        self, image_data: bytes, max_dimension: int = 512, quality: int = 85
    ) -> bytes:
        """压缩参考图片，减小图生图 API 的 base64 payload 大小。

        Args:
            image_data: 原始图片二进制数据
            max_dimension: 最长边限制（默认 512px，图生图 API 足够）
            quality: JPEG 质量

        Returns:
            压缩后的 JPEG 二进制数据
        """
        try:
            import io

            from PIL import Image

            img: Image.Image = Image.open(io.BytesIO(image_data))

            # 如果图片尺寸超过限制，等比缩放
            width, height = img.size
            if max(width, height) > max_dimension:
                ratio = max_dimension / max(width, height)
                new_size = (int(width * ratio), int(height * ratio))
                img = img.resize(new_size, Image.Resampling.LANCZOS)
                logger.info(
                    f"[RoundIllustration] Resized reference image: {width}x{height} → {new_size[0]}x{new_size[1]}"
                )

            # 转为 RGB（去除透明通道）并保存为 JPEG
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")

            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=quality, optimize=True)
            compressed = buf.getvalue()

            original_kb = len(image_data) / 1024
            compressed_kb = len(compressed) / 1024
            reduction = (1 - len(compressed) / len(image_data)) * 100 if image_data else 0
            logger.info(
                f"[RoundIllustration] Compressed reference image: "
                f"{original_kb:.1f}KB → {compressed_kb:.1f}KB ({reduction:.0f}% reduction)"
            )

            return compressed

        except Exception as e:
            logger.warning(f"[RoundIllustration] Image compression failed, using original: {e}")
            return image_data

    def _extract_involved_entities(
        self,
        story_text: str,
        character_settings: Dict[str, Any],
        world_model_data: Optional[Dict[str, Any]] = None,
        established_facts: Optional[List[Dict[str, Any]]] = None,
    ) -> List[Dict[str, Any]]:
        """
        从故事文本中提取涉及的实体（人物/物品/地标）

        优先级：人物 > 物品 > 地标
        总数限制：最多5个

        Returns:
            List of dicts: [{"name": "实体名", "type": "character|item|location", "description": "描述"}]
        """
        characters = []
        items = []
        landmarks = []

        # ========== 1. 提取人物（最高优先级） ==========
        known_characters = []
        if "relationships" in character_settings:
            key_people = character_settings["relationships"].get("key_people", [])
            for p in key_people:
                if p.get("name"):
                    known_characters.append(
                        {
                            "name": p.get("name"),
                            "description": self._build_character_desc(p),
                        }
                    )

        if "family" in character_settings:
            family_members = character_settings["family"].get("family_members", [])
            for m in family_members:
                if m.get("name"):
                    known_characters.append(
                        {
                            "name": m.get("name"),
                            "description": self._build_character_desc(m),
                        }
                    )

        # 检查故事中是否提到这些人物
        for char in known_characters:
            if char["name"] in story_text:
                characters.append(
                    {
                        "name": char["name"],
                        "type": "character",
                        "description": char["description"],
                    }
                )

        # ========== 2. 提取重要物品（中等优先级） ==========
        # 只提取已建立的重要物品，从 established_facts 或 world_model_data 获取
        important_items = self._extract_important_items(
            story_text, world_model_data, established_facts
        )
        items = important_items

        # ========== 3. 提取重要地标建筑（低优先级） ==========
        # 从 established_facts 中提取已建立的地标建筑
        important_landmarks = self._extract_important_landmarks(
            story_text,
            world_model_data,
            established_facts,
        )
        landmarks = important_landmarks

        # ========== 按优先级组合，总数不超过5个 ==========
        # 优先级：人物(最多3个) > 物品(最多1个) > 地标(最多1个)
        result = []

        # 人物优先，最多3个
        result.extend(characters[:3])

        # 物品次之，最多1个
        for item in items[:1]:
            if len(result) >= 5:
                break
            if not any(e["name"] == item["name"] for e in result):
                result.append(item)

        # 地标最后，最多1个
        for landmark in landmarks[:1]:
            if len(result) >= 5:
                break
            if not any(e["name"] == landmark["name"] for e in result):
                result.append(landmark)

        return result[:5]

    def _extract_important_items(
        self,
        story_text: str,
        world_model_data: Optional[Dict[str, Any]] = None,
        established_facts: Optional[List[Dict[str, Any]]] = None,
    ) -> List[Dict[str, Any]]:
        """
        提取重要物品（已建立的、影响场景一致性的物品）

        重要物品来源：
        1. established_facts 中 category 为 "item" 的事实
        2. world_model_data 中记录的动态事实（fact_type="possession"）

        只有**在多个场景/事实中反复出现（≥3次）**的物品才会被认为是「重要物品」，用于触发图片生成。

        ★ 完全依赖 AI 识别，不使用正则匹配，以支持古代/现代/科幻等多场景泛化。
        """
        items: List[Dict[str, Any]] = []
        candidate_items: List[Dict[str, Any]] = []

        # ---------- 1. 从 established_facts 提取已建立的重要物品 ----------
        if established_facts:
            for fact in established_facts:
                category = fact.get("category", "")
                if category == "item":
                    item_name = fact.get("subject") or fact.get("fact", "")
                    if not item_name:
                        continue
                    if item_name and item_name in story_text:
                        candidate_items.append(
                            {
                                "name": item_name,
                                "type": "item",
                                "description": fact.get("fact", f"重要物品：{item_name}"),
                            }
                        )

        # ---------- 2. 从 world_model_data.dynamic_facts 提取物品 ----------
        # 补充：提取 possession 类型的动态事实中的物品
        if world_model_data:
            for df in world_model_data.get("dynamic_facts", []):
                try:
                    if df.get("fact_type") != "possession":
                        continue
                    subject = df.get("subject", "")
                    desc = df.get("description", "") or ""
                    if subject and subject in story_text:
                        # 避免重复添加
                        if not any(i["name"] == subject for i in candidate_items):
                            candidate_items.append(
                                {
                                    "name": subject,
                                    "type": "item",
                                    "description": desc or f"重要物品：{subject}",
                                }
                            )
                except (AttributeError, TypeError):
                    continue

        if not candidate_items:
            return []

        # ---------- 3. 计算每个物品在世界模型/事实中的出现次数 ----------
        def _count_occurrences(name: str) -> int:
            count = 0
            # 在 established_facts 中出现的次数
            if established_facts:
                for fact in established_facts:
                    text = (fact.get("subject", "") or "") + " " + (fact.get("fact", "") or "")
                    if name and name in text:
                        count += 1
            # 在 world_model_data.dynamic_facts 中出现的次数（possession 类型）
            if world_model_data:
                for df in world_model_data.get("dynamic_facts", []):
                    try:
                        if df.get("fact_type") != "possession":
                            continue
                        desc = df.get("description", "") or ""
                        constraint = df.get("constraint_text", "") or ""
                        related = " ".join(df.get("related_entities", []) or [])
                        blob = desc + " " + constraint + " " + related
                        if name and name in blob:
                            count += 1
                    except (AttributeError, TypeError):
                        continue
            return count

        for item in candidate_items:
            name = item.get("name", "")
            if not name:
                continue
            occ = _count_occurrences(name)
            # 至少在 3 个不同事实/场景中被提及，才认为是「反复出现的物品」
            if occ >= 3:
                items.append(item)

        # 如果没有任何满足「反复出现」条件的物品，则不返回物品，避免一次性道具触发图片生成
        return items

    def _extract_important_landmarks(
        self,
        story_text: str,
        world_model_data: Optional[Dict[str, Any]] = None,
        established_facts: Optional[List[Dict[str, Any]]] = None,
    ) -> List[Dict[str, Any]]:
        """
        提取重要地标建筑（会反复出现的场景）

        重要地标来源：
        1. established_facts 中 category 为 "location" 或 "landmark" 的事实
        2. world_model_data 中记录的重要地点
        """
        landmarks = []

        # 从 established_facts 提取已建立的重要地标
        if established_facts:
            for fact in established_facts:
                category = fact.get("category", "")
                if category in ("location", "landmark"):
                    landmark_name = fact.get("subject") or fact.get("fact", "")
                    # 提取地标名称（可能是完整地址，取关键部分）
                    if landmark_name:
                        # 尝试匹配故事中的地标
                        if landmark_name in story_text:
                            landmarks.append(
                                {
                                    "name": landmark_name,
                                    "type": "location",
                                    "description": fact.get("fact", f"重要地标：{landmark_name}"),
                                }
                            )

        # 从 world_model_data 提取反复出现的地点
        if not landmarks and world_model_data:
            # 统计每个地点出现的次数，选择最重要的
            location_counts: dict[str, int] = {}
            char_locations = world_model_data.get("character_locations", {})
            for char_name, loc_info in char_locations.items():
                location = loc_info.get("location", "")
                if location:
                    location_counts[location] = location_counts.get(location, 0) + 1

            # 选择出现次数最多的地点（说明是反复出现的场景）
            for location, count in sorted(location_counts.items(), key=lambda x: -x[1]):
                if location in story_text:
                    landmarks.append(
                        {
                            "name": location,
                            "type": "location",
                            "description": f"重要地标：{location}",
                        }
                    )
                    break  # 只取最重要的一个

        return landmarks

    def _build_character_desc(self, char_data: Dict[str, Any]) -> str:
        """构建人物描述"""
        desc_parts = []
        if char_data.get("age"):
            desc_parts.append(f"{char_data['age']}岁")
        if char_data.get("gender"):
            desc_parts.append(str(char_data["gender"]))
        if char_data.get("relationship_desc") or char_data.get("relationship"):
            desc_parts.append(
                str(char_data.get("relationship_desc") or char_data.get("relationship"))
            )
        return "，".join(desc_parts) if desc_parts else "一个普通人"

    def _extract_items_from_story(self, story_text: str) -> List[Dict[str, Any]]:
        """
        从故事文本中智能提取重要物品

        使用简单的关键词匹配识别重要物品
        """
        items = []

        # 常见物品关键词模式
        import re

        # 匹配 "XX剑" "XX刀" 等武器
        weapon_pattern = r"([\u4e00-\u9fa5]{1,3}[剑刀枪棍斧弓])"
        weapons = re.findall(weapon_pattern, story_text)
        for w in weapons[:1]:  # 最多1个武器
            items.append(
                {
                    "name": w,
                    "type": "item",
                    "description": f"一把{w}",
                }
            )

        # 匹配 "XX玉" "XX珠" 等宝物（只匹配以玉、珠结尾的词）
        treasure_pattern = r"([\u4e00-\u9fa5]{1,3}[玉珠])"
        treasures = re.findall(treasure_pattern, story_text)
        for t in treasures[:1]:  # 最多1个宝物
            if not any(i["name"] == t for i in items):
                items.append(
                    {
                        "name": t,
                        "type": "item",
                        "description": f"一件{t}",
                    }
                )

        return items

    def _extract_era_from_settings(self, character_settings: Dict[str, Any]) -> str:
        """从角色设定中提取时代信息"""
        era = character_settings.get("era")
        if era:
            if isinstance(era, dict):
                return era.get("era_name") or era.get("era_description") or "现代"
            elif isinstance(era, str):
                return era
        return "现代"

    def _get_current_week_from_db(self, game_id: int) -> int:
        """
        从数据库获取游戏当前的周数

        Args:
            game_id: 游戏ID

        Returns:
            当前周数，默认返回 0
        """
        from src.database.models import Game, GameState

        try:
            # 尝试从最新的 GameState 获取
            game_state = (
                self.db.query(GameState)
                .filter(GameState.game_id == game_id)
                .order_by(GameState.state_id.desc())
                .first()
            )

            if game_state and game_state.state_json:
                week = game_state.state_json.get("week")
                if week is not None:
                    return week  # type: ignore[no-any-return]

            # 如果没有 GameState，从 Game.initial_state 获取
            game = self.db.query(Game).filter(Game.game_id == game_id).first()
            if game and game.initial_state:
                week = game.initial_state.get("week")
                if week is not None:
                    return week  # type: ignore[no-any-return]
        except Exception as e:
            logger.warning(f"[RoundIllustration] Failed to get current week from database: {e}")

        return 0  # 默认返回 0

    def _generate_entity_image(
        self,
        game_id: int,
        entity_name: str,
        entity_type: str,  # character | location | item
        description: str,
        era: str,
    ) -> Optional[ImageModel]:
        """
        自动生成实体图片（人物/地点/物品）

        Args:
            game_id: 游戏ID
            entity_name: 实体名称
            entity_type: 实体类型 (character | location | item)
            description: 实体描述
            era: 时代背景

        Returns:
            生成的 ImageModel，失败返回 None
        """
        from src.services.image_service import ImageService

        try:
            image_service = ImageService(
                db=self.db,
                image_client=self.image_client,
                storage_service=self.image_storage,
            )

            if entity_type == "character":
                # 生成人物图片
                images = image_service.generate_character_image(
                    game_id=game_id,
                    name=entity_name,
                    description=description,
                    era=era,
                    entity_key=f"npc_{entity_name}",
                    num_images=1,
                )
                if images:
                    return images[0]

            elif entity_type == "location":
                # 生成地点图片
                return image_service.generate_location_image(
                    game_id=game_id,
                    name=entity_name,
                    description=description,
                    era=era,
                )

            elif entity_type == "item":
                # 生成物品图片
                return image_service.generate_item_image(
                    game_id=game_id,
                    name=entity_name,
                    description=description,
                    era=era,
                )

            return None

        except Exception as e:
            logger.error(
                f"[RoundIllustration] Failed to generate {entity_type} image for {entity_name}: {e}",
                exc_info=True,
            )
            return None
