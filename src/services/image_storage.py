"""Image storage service - 抽象存储层.

支持本地存储和阿里云OSS存储，可通过配置切换。
"""

import hashlib
import logging
import os
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from config.settings import settings

logger = logging.getLogger(__name__)


class ImageStorageError(Exception):
    """图片存储错误"""

    pass


class ImageStorageService:
    """图片存储服务 - 支持本地存储和OSS存储"""

    def __init__(
        self,
        storage_type: Optional[str] = None,
        local_path: Optional[Path] = None,
    ):
        """
        初始化存储服务

        Args:
            storage_type: 存储类型 "local" 或 "oss"
            local_path: 本地存储路径
        """
        self.storage_type = storage_type or settings.IMAGE_STORAGE_TYPE
        self.local_path = local_path or settings.IMAGE_LOCAL_PATH

        # 确保本地目录存在
        if self.storage_type == "local":
            self._ensure_local_dir()

        # OSS客户端（延迟初始化）
        self._oss_client = None

    def _ensure_local_dir(self) -> None:
        """确保本地存储目录存在"""
        try:
            self.local_path.mkdir(parents=True, exist_ok=True)
            logger.info(f"Image storage directory: {self.local_path}")
        except PermissionError as e:
            logger.error(f"Permission denied creating image storage directory: {e}")
            raise ImageStorageError(f"无法创建图片存储目录（权限不足）: {e}")
        except OSError as e:
            logger.error(f"OS error creating image storage directory: {e}")
            raise ImageStorageError(f"无法创建图片存储目录: {e}")

    def save_image(
        self,
        image_data: bytes,
        game_id: int,
        image_type: str,
        entity_name: str,
        extension: str = "png",
        metadata: Optional[Dict[str, Any]] = None,
        week: Optional[int] = None,
        round_number: Optional[int] = None,
        stage: Optional[str] = None,
    ) -> Tuple[str, str]:
        """
        保存图片

        Args:
            image_data: 图片二进制数据
            game_id: 游戏ID
            image_type: 图片类型 (character/location/item/round_scene)
            entity_name: 实体名称
            extension: 文件扩展名
            metadata: 元数据
            week: 周数（仅 round_scene 需要）
            round_number: 轮次（仅 round_scene 需要）
            stage: 阶段（仅 round_scene 需要）

        Returns:
            Tuple[str, str]: (存储路径, 存储类型)

        Raises:
            ImageStorageError: 保存失败
        """
        # 生成唯一文件名
        filename = self._generate_filename(
            game_id,
            image_type,
            entity_name,
            extension,
            week=week,
            round_number=round_number,
            stage=stage,
        )

        if self.storage_type == "local":
            return self._save_local(image_data, filename)
        elif self.storage_type == "oss":
            return self._save_oss(image_data, filename, metadata)
        else:
            raise ImageStorageError(f"不支持的存储类型: {self.storage_type}")

    def _generate_filename(
        self,
        game_id: int,
        image_type: str,
        entity_name: str,
        extension: str,
        week: Optional[int] = None,
        round_number: Optional[int] = None,
        stage: Optional[str] = None,
    ) -> str:
        """
        生成唯一文件名

        对于场景图片(round_scene)，文件名包含 week/round/stage 信息
        对于其他图片(character/location/item)，保持原有格式
        """
        # 清理实体名称（移除特殊字符）
        # 物品命名规则：
        # - 优先提取类似“XX剑”“XX刀”“XX玉”“XX珠”等简短名作为文件名主体
        # - 避免整句故事文本直接进文件名（例如“起去练剑”“地的巨剑”等）
        # - 最终仍做一次安全字符过滤，限制长度
        base_name = entity_name or "item"
        # 提取武器/宝物短名称
        match = re.search(r"([\u4e00-\u9fa5]{1,4}[剑刀枪棍斧弓玉珠])", base_name)
        if match:
            base_name = match.group(1)
        # 安全化处理
        safe_name = "".join(c for c in base_name if c.isalnum() or c in "._- ")[:30]
        if not safe_name:
            safe_name = "item"

        # 生成时间戳和随机ID
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_id = uuid.uuid4().hex[:8]

        # 构建文件名 - 场景图片包含完整层级信息
        if image_type == "round_scene" and week is not None:
            # 场景图片: {game_id}/round_scene/week_{week+1}_round_{round}_{stage}_{uuid}.png
            # ★ week 从0开始，文件名显示时 +1，与前端一致
            stage_str = stage or "result"
            display_week = week + 1  # ★ 显示用周数（人类可读，从1开始）
            filename = f"{game_id}/{image_type}/week_{display_week}_round_{round_number}_{stage_str}_{unique_id}.{extension}"
        else:
            # 其他图片: {game_id}/{image_type}/{timestamp}_{name}_{uuid}.png
            filename = f"{game_id}/{image_type}/{timestamp}_{safe_name}_{unique_id}.{extension}"

        return filename

    def _save_local(self, image_data: bytes, filename: str) -> Tuple[str, str]:
        """
        保存到本地

        Args:
            image_data: 图片数据
            filename: 文件名（相对路径）

        Returns:
            Tuple[str, str]: (存储路径, 存储类型)
        """
        # 构建完整路径
        full_path = self.local_path / filename

        # 确保目录存在
        full_path.parent.mkdir(parents=True, exist_ok=True)

        # 写入文件
        try:
            with open(full_path, "wb") as f:
                f.write(image_data)

            logger.info(f"Image saved to: {full_path}")
            # ★ 返回相对路径（相对于 self.local_path），而非绝对路径
            return filename, "local"

        except PermissionError as e:
            logger.error(f"Permission denied saving image locally: {e}")
            raise ImageStorageError(f"保存图片失败（权限不足）: {e}")
        except OSError as e:
            logger.error(f"OS error saving image locally: {e}")
            raise ImageStorageError(f"保存图片失败: {e}")

    def _save_oss(
        self,
        image_data: bytes,
        filename: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Tuple[str, str]:
        """
        保存到阿里云OSS

        Args:
            image_data: 图片数据
            filename: 文件名（相对路径）
            metadata: 元数据

        Returns:
            Tuple[str, str]: (存储路径, 存储类型)
        """
        try:
            # 获取OSS客户端
            client = self._get_oss_client()

            # 上传文件
            bucket_name = settings.OSS_BUCKET_NAME
            client.put_object(
                bucket_name,
                filename,
                image_data,
                metadata=metadata,
            )

            # 返回OSS路径
            oss_path = f"oss://{bucket_name}/{filename}"
            logger.info(f"Image saved to OSS: {oss_path}")
            return oss_path, "oss"

        except ImportError:
            raise ImageStorageError("OSS SDK未安装，请运行: pip install oss2")
        except ConnectionError as e:
            logger.error(f"OSS connection error: {e}")
            raise ImageStorageError(f"OSS连接失败: {e}")
        except TimeoutError as e:
            logger.error(f"OSS timeout: {e}")
            raise ImageStorageError(f"OSS连接超时: {e}")
        except Exception as e:
            logger.exception(f"OSS upload unexpected error: {e}")
            raise ImageStorageError(f"保存图片到OSS失败: {e}")

    def _get_oss_client(self):
        """获取OSS客户端（延迟初始化）"""
        if self._oss_client is None:
            try:
                import oss2

                auth = oss2.Auth(
                    settings.OSS_ACCESS_KEY_ID,
                    settings.OSS_ACCESS_KEY_SECRET,
                )
                self._oss_client = oss2.Bucket(
                    auth,
                    settings.OSS_ENDPOINT,
                    settings.OSS_BUCKET_NAME,
                )
            except ImportError:
                raise ImageStorageError("OSS SDK未安装，请运行: pip install oss2")
            except (ValueError, TypeError) as e:
                raise ImageStorageError(f"OSS配置错误: {e}")
            except Exception as e:
                logger.exception(f"OSS client init unexpected error: {e}")
                raise ImageStorageError(f"OSS客户端初始化失败: {e}")

        return self._oss_client

    def get_full_path(self, storage_path: str) -> Path:
        """
        将存储路径转为完整文件系统路径

        支持：
        - 相对路径（新格式）: 296/character/xxx.png -> self.local_path / 296/character/xxx.png
        - 绝对路径（旧格式，向后兼容）: /Users/.../data/images/296/character/xxx.png -> 原样返回

        Args:
            storage_path: 存储路径（相对或绝对）

        Returns:
            完整的文件系统路径
        """
        if os.path.isabs(storage_path):
            # 向后兼容：旧的绝对路径直接返回
            return Path(storage_path)
        return self.local_path / storage_path

    def get_image_url(self, storage_path: str, storage_type: Optional[str] = None) -> str:
        """
        获取图片访问URL

        Args:
            storage_path: 存储路径
            storage_type: 存储类型（默认使用实例配置）

        Returns:
            图片访问URL
        """
        storage_type = storage_type or self.storage_type

        if storage_type == "local":
            # 本地存储返回API路径
            # 判断是相对路径（新格式）还是绝对路径（旧格式，向后兼容）
            if os.path.isabs(storage_path):
                # 向后兼容：旧的绝对路径，需要提取相对路径
                if storage_path.startswith(str(self.local_path)):
                    relative_path = os.path.relpath(storage_path, self.local_path)
                else:
                    # 通过查找 "data/images/" 模式提取相对路径
                    # 处理项目目录迁移（如从 /Users/luicy/story2 到 /Users/luicy/AI/story2）
                    marker = "data/images/"
                    marker_idx = storage_path.find(marker)
                    if marker_idx != -1:
                        relative_path = storage_path[marker_idx + len(marker) :]
                    else:
                        relative_path = storage_path
            else:
                # ★ 新格式：已经是相对路径，直接使用
                relative_path = storage_path

            # ★ URL 编码路径中的非ASCII字符（如中文）
            from urllib.parse import quote

            encoded_path = quote(relative_path, safe="/")  # 保留 / 字符

            # 返回API路径
            return f"/api/images/file/{encoded_path}"

        elif storage_type == "oss":
            # OSS返回公开URL或签名URL
            return self._get_oss_url(storage_path)

        else:
            raise ImageStorageError(f"不支持的存储类型: {storage_type}")

    def _get_oss_url(self, storage_path: str) -> str:
        """获取OSS图片URL"""
        try:
            # 解析OSS路径
            # 格式: oss://bucket-name/path/to/file.png
            if storage_path.startswith("oss://"):
                path_without_prefix = storage_path[6:]
                _, object_key = path_without_prefix.split("/", 1)
            else:
                object_key = storage_path

            # 生成签名URL（有效期1小时）
            client = self._get_oss_client()
            url = client.sign_url("GET", object_key, 3600)
            return url  # type: ignore[no-any-return]

        except (ValueError, KeyError) as e:
            logger.error(f"Invalid OSS path format: {e}")
            raise ImageStorageError(f"获取OSS URL失败（路径格式错误）: {e}")
        except ConnectionError as e:
            logger.error(f"OSS connection error generating URL: {e}")
            raise ImageStorageError(f"获取OSS URL失败（连接错误）: {e}")
        except Exception as e:
            logger.exception(f"Unexpected error generating OSS URL: {e}")
            raise ImageStorageError(f"获取OSS URL失败: {e}")

    def get_image_data(self, storage_path: str, storage_type: Optional[str] = None) -> bytes:
        """
        获取图片二进制数据

        Args:
            storage_path: 存储路径
            storage_type: 存储类型

        Returns:
            图片二进制数据
        """
        storage_type = storage_type or self.storage_type

        if storage_type == "local":
            return self._get_local_image_data(storage_path)
        elif storage_type == "oss":
            return self._get_oss_image_data(storage_path)
        else:
            raise ImageStorageError(f"不支持的存储类型: {storage_type}")

    def _get_local_image_data(self, storage_path: str) -> bytes:
        """读取本地图片"""
        full_path = self.get_full_path(storage_path)
        try:
            with open(full_path, "rb") as f:
                return f.read()
        except FileNotFoundError as e:
            logger.error(f"Local image not found: {full_path}")
            raise ImageStorageError(f"读取本地图片失败（文件不存在）: {e}")
        except PermissionError as e:
            logger.error(f"Permission denied reading local image: {full_path}")
            raise ImageStorageError(f"读取本地图片失败（权限不足）: {e}")
        except OSError as e:
            logger.error(f"OS error reading local image: {full_path}")
            raise ImageStorageError(f"读取本地图片失败: {e}")

    def _get_oss_image_data(self, storage_path: str) -> bytes:
        """读取OSS图片"""
        try:
            client = self._get_oss_client()

            # 解析路径
            if storage_path.startswith("oss://"):
                path_without_prefix = storage_path[6:]
                _, object_key = path_without_prefix.split("/", 1)
            else:
                object_key = storage_path

            result = client.get_object(object_key)
            return result.read()  # type: ignore[no-any-return]

        except (ValueError, KeyError) as e:
            logger.error(f"Invalid OSS path format: {e}")
            raise ImageStorageError(f"读取OSS图片失败（路径格式错误）: {e}")
        except ConnectionError as e:
            logger.error(f"OSS connection error reading image: {e}")
            raise ImageStorageError(f"读取OSS图片失败（连接错误）: {e}")
        except Exception as e:
            logger.exception(f"Unexpected error reading OSS image: {e}")
            raise ImageStorageError(f"读取OSS图片失败: {e}")

    def delete_image(self, storage_path: str, storage_type: Optional[str] = None) -> bool:
        """
        删除图片

        Args:
            storage_path: 存储路径
            storage_type: 存储类型

        Returns:
            是否删除成功
        """
        storage_type = storage_type or self.storage_type

        try:
            if storage_type == "local":
                full_path = str(self.get_full_path(storage_path))
                os.remove(full_path)
                logger.info(f"Deleted local image: {full_path}")
                return True
            elif storage_type == "oss":
                client = self._get_oss_client()
                if storage_path.startswith("oss://"):
                    path_without_prefix = storage_path[6:]
                    _, object_key = path_without_prefix.split("/", 1)
                else:
                    object_key = storage_path

                client.delete_object(object_key)
                logger.info(f"Deleted OSS image: {storage_path}")
                return True
            else:
                raise ImageStorageError(f"不支持的存储类型: {storage_type}")

        except FileNotFoundError:
            logger.warning(f"Image not found for deletion: {storage_path}")
            return False  # 文件不存在，返回删除失败
        except PermissionError as e:
            logger.error(f"Permission denied deleting image: {e}")
            return False
        except OSError as e:
            logger.error(f"OS error deleting image: {e}")
            return False
        except Exception as e:
            logger.exception(f"Unexpected error deleting image: {e}")
            return False

    def image_exists(self, storage_path: str, storage_type: Optional[str] = None) -> bool:
        """
        检查图片是否存在

        Args:
            storage_path: 存储路径
            storage_type: 存储类型

        Returns:
            是否存在
        """
        storage_type = storage_type or self.storage_type

        try:
            if storage_type == "local":
                full_path = str(self.get_full_path(storage_path))
                return os.path.exists(full_path)
            elif storage_type == "oss":
                client = self._get_oss_client()
                if storage_path.startswith("oss://"):
                    path_without_prefix = storage_path[6:]
                    _, object_key = path_without_prefix.split("/", 1)
                else:
                    object_key = storage_path

                return client.object_exists(object_key)  # type: ignore[no-any-return]
            else:
                return False

        except (ValueError, KeyError) as e:
            logger.error(f"Invalid path format checking image existence: {e}")
            return False
        except ConnectionError as e:
            logger.error(f"Connection error checking image existence: {e}")
            return False
        except Exception as e:
            logger.exception(f"Unexpected error checking image existence: {e}")
            return False

    def compute_hash(self, image_data: bytes) -> str:
        """计算图片哈希值"""
        return hashlib.sha256(image_data).hexdigest()
