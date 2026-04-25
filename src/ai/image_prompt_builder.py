"""Image prompt builder module.

负责构建各种图像生成的 prompt，包括人物、场景、地点、物品等。
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

import openai

from src.ai.image_config import SENSITIVE_WORDS, get_scene_analyzer_config

logger = logging.getLogger(__name__)


class ImagePromptBuilder:
    """图像 Prompt 构建器"""

    # Sci-fi triggering words that should be removed from era descriptions
    # for image generation, as they cause the model to generate cyberpunk/
    # futuristic visuals even when negative prompts are used.
    _SCI_FI_ERA_KEYWORDS = [
        "人工智能",
        "AI",
        "数字化",
        "虚拟现实",
        "VR",
        "全息投影",
        "全息",
        "科技飞速进步",
        "科技革命",
        "赛博朋克",
        "机械义肢",
        "电子眼",
        "飞行汽车",
        "悬浮载具",
        "发光",
        "霓虹",
        "量子",
        "纳米",
        "基因编辑",
        "脑机接口",
        "元宇宙",
        "区块链",
        "数字孪生",
        "虚拟与现实交织",
        "抽象光影",
    ]

    def _sanitize_era_for_image(self, era: str) -> str:
        """清洗 era 描述中的科幻暗示词，防止图像模型生成 sci-fi 视觉。

        故事生成的 era 描述通常包含叙事性词汇（如"人工智能时代"），
        这些词汇对图像模型是强 sci-fi 暗示。本函数将其替换为中性视觉描述。

        Args:
            era: 原始 era 描述

        Returns:
            清洗后的 era 描述，保留时间/地点信息，移除科幻暗示
        """
        if not era:
            return "现代"

        era_clean = era
        # 直接移除/替换科幻触发词
        replacements = {
            "人工智能": "",
            "AI": "",
            "数字化与实体交融": "现代生活",
            "数字化": "",
            "虚拟现实": "",
            "VR": "",
            "全息投影": "",
            "全息": "",
            "科技飞速进步": "",
            "科技革命": "",
            "赛博朋克": "",
            "机械义肢": "",
            "电子眼": "",
            "飞行汽车": "",
            "悬浮载具": "",
            "发光": "",
            "霓虹": "",
            "量子": "",
            "纳米": "",
            "基因编辑": "",
            "脑机接口": "",
            "元宇宙": "",
            "区块链": "",
            "数字孪生": "",
            "虚拟与现实交织": "现实",
            "抽象光影": "自然光线",
        }

        for old, new in replacements.items():
            era_clean = era_clean.replace(old, new)

        # 清理多余的标点、空格和空片段
        import re

        era_clean = re.sub(r"[，,、]\s*[，,、]", "，", era_clean)
        era_clean = re.sub(r"[。.]\s*[。.]", "。", era_clean)
        era_clean = era_clean.strip("，,。.")

        # 如果清洗后内容过短或为空，使用默认安全描述
        if len(era_clean) < 5 or era_clean in ("现代", "当代", ""):
            # 尝试提取年份
            year_match = re.search(r"20\d{2}", era)
            year = year_match.group(0) if year_match else "2024"
            return f"{year}年中国，现代都市生活，写实主义风格"

        # 如果清洗后仍包含太多科幻残余，强制 fallback
        for kw in self._SCI_FI_ERA_KEYWORDS:
            if kw in era_clean:
                year_match = re.search(r"20\d{2}", era)
                year = year_match.group(0) if year_match else "2024"
                return f"{year}年中国，现代都市生活，写实主义风格"

        return era_clean

    def build_character_prompt(
        self,
        name: str,
        description: str,
        era: str,
        style_hint: Optional[str] = None,
        pose_hint: Optional[str] = None,
        feedback: Optional[str] = None,
    ) -> str:
        """
        构建人物形象prompt（优化版本 - 更细致的描述）

        Args:
            name: 人物名称
            description: 人物描述
            era: 时代背景
            style_hint: 风格提示
            pose_hint: 姿势提示（如：站立、行走、坐姿等）
            feedback: 用户修改意见（会被特别强调）

        Returns:
            构建好的prompt
        """
        # ★ 清洗 era 描述中的科幻暗示词，防止污染图像生成
        safe_era = self._sanitize_era_for_image(era)

        parts = []

        # 最重要：用户的修改意见放在最前面
        if feedback:
            parts.append(f"【必须执行的修改】{feedback}。这是最重要的要求，必须严格体现在图片中。")

        # ★ 写实主义红线约束放在最前面，确保模型优先关注
        parts.extend(
            [
                "【写实主义约束 - 最高优先级，违反即失败】",
                "- 必须是真实世界的自然摄影呈现，绝对禁止科幻、奇幻、超现实元素",
                "- 禁止赛博朋克：不得穿金属质感夹克、电路纹理服装、发光线条装饰、机械元素",
                "- 禁止全息投影：背景不得出现全息屏幕、悬浮信息面板、全息建筑线框",
                "- 禁止发光效果：眼睛不得发红光/蓝光，禁止任何发光物体或霓虹光效",
                "- 禁止未来科技：不得出现科幻城市、飞行汽车、高科技机械背景",
                "- 禁止品牌Logo：不得出现星巴克、苹果等任何真实商业品牌标识",
                "- 日常服装：穿着普通日常服装（棉质衬衫、T恤、针织外套、牛仔裤、休闲裤、运动鞋等）",
                "- 真实背景：日常生活场景（街道、公园、室内、办公室、咖啡厅等），自然光线",
            ]
        )

        # 基础信息
        parts.extend(
            [
                f"【人物】{name}",
                f"【时代背景】{safe_era}",
            ]
        )

        # 外貌描述（更细致）
        parts.extend(
            [
                f"【外貌特征】{description}",
                "【服装】根据时代背景设计的典型服饰，款式细节丰富，材质纹理清晰可见",
                "【表情】自然平和，眼神有故事感，符合人物性格特征",
                "【光线】柔和的自然光，从左侧45度角打光，突出面部立体感和轮廓",
            ]
        )

        # 构图要求（更精确）
        parts.extend(
            [
                "【构图要求】",
                "- 全身像，人物占画面75%-85%",
                "- 头顶留白约8%-12%，脚底留白约5%-8%",
                "- 人物纵向居中，左右适当留白",
                "- 纵向构图（竖版），突出人物全身",
                "- 背景简洁虚化，突出人物主体",
            ]
        )

        # 姿势
        if pose_hint:
            parts.append(f"【姿势】{pose_hint}")
        else:
            parts.append(
                "【姿势】自然站立姿态，双脚与肩同宽，身体略微侧向15-30度，避免完全正面呆板"
            )

        # 风格提示（更详细）
        if style_hint:
            parts.append(f"【风格】{style_hint}")
        else:
            parts.extend(
                [
                    "【风格】写实摄影风格，电影质感",
                    "- 细节丰富：面部特征、服装纹理、头发丝都清晰可见",
                    "- 光影自然：柔和过渡，避免过度平滑的AI感",
                    "- 色彩适中：饱和度适中，肤色自然真实",
                    "- 画面质感：有真实照片感，避免蜡像或塑料质感",
                ]
            )

        # 质量要求（强化）
        parts.extend(
            [
                "【质量要求】",
                "- 全身完整展示：头部、躯干、四肢、脚部全部可见",
                "- 面部清晰：五官比例协调，特征鲜明可辨",
                "- 人物一致性：如果此前已有该人物的图片，必须保持相同的脸型、五官比例和发型",
                "- 服装细节：款式、颜色、褶皱、材质都清晰呈现，符合2024年日常穿着",
                "- 光影立体：有明显的主光源方向，阴影柔和有层次",
                "- 避免畸形：手指、五官比例正确，没有明显的AI畸变",
            ]
        )

        return "。".join(parts)

    def build_location_prompt(
        self,
        name: str,
        description: str,
        era: str,
        style_hint: Optional[str] = None,
    ) -> str:
        """构建地点prompt"""
        parts = [
            f"一张高质量的场景插画，地点：{name}。",
            f"时代背景：{era}。",
            f"场景描述：{description}。",
        ]

        if style_hint:
            parts.append(f"风格：{style_hint}。")
        else:
            parts.append("风格：写实风格，细节丰富，氛围感强。")

        parts.append("要求：场景清晰、构图美观、有代入感。画面中不要出现任何人物，仅展示场景本身。")

        return "".join(parts)

    def build_item_prompt(
        self,
        name: str,
        description: str,
        era: str,
        style_hint: Optional[str] = None,
    ) -> str:
        """构建物品prompt"""
        parts = [
            f"一张高质量的物品图片，物品：{name}。",
            f"时代背景：{era}。",
            f"物品描述：{description}。",
        ]

        if style_hint:
            parts.append(f"风格：{style_hint}。")
        else:
            parts.append("风格：写实风格，细节清晰。")

        parts.append("要求：物品居中、背景简洁、光影自然。")

        return "".join(parts)

    def build_scene_prompt(
        self,
        scene_description: str,
        characters: Optional[List[Dict[str, Any]]],
        era: str,
        style_hint: Optional[str] = None,
    ) -> str:
        """构建场景prompt"""
        parts = [
            "一张高质量的故事场景插画。",
            f"时代背景：{era}。",
            f"场景描述：{scene_description}",
        ]

        if characters:
            char_desc = "、".join(
                [f"{c.get('name', '')}({c.get('description', '')})" for c in characters]
            )
            parts.append(f"场景中的人物：{char_desc}。")

        if style_hint:
            parts.append(f"风格：{style_hint}。")
        else:
            parts.append("风格：电影感，写实风格，氛围感强。")

        parts.append("要求：画面有故事感、人物表情生动、场景细节丰富。")

        return "".join(parts)

    def build_fallback_prompt(self, character_info: Dict[str, Any]) -> str:
        """DeepSeek 不可用时的备选 prompt 生成"""
        name = character_info.get("name", "人物")
        age = character_info.get("age", "25")
        gender = character_info.get("gender", "女")
        era = character_info.get("era", "现代")
        appearance = character_info.get("appearance", "")

        return f"{era}，{age}岁{gender}性，{name}。{appearance}。人物全身像，脚部可见，写实风格。"

    def simplify_prompt(self, original_prompt: str, scene_desc: str) -> Tuple[str, str]:
        """简化 prompt 作为备选方案"""
        simplified_prompt = original_prompt
        simplified_scene = scene_desc

        for word in SENSITIVE_WORDS:
            if word in simplified_prompt:
                simplified_prompt = simplified_prompt.replace(word, "室内")
            if word in simplified_scene:
                simplified_scene = simplified_scene.replace(word, "室内")

        logger.debug(f"Simplified prompt: {simplified_prompt[:100]}...")
        return simplified_scene, simplified_prompt


class DeepSeekPromptEnhancer:
    """使用 DeepSeek 增强 Prompt 的工具类"""

    def generate_image_prompt_with_deepseek(
        self,
        character_info: Dict[str, Any],
    ) -> str:
        """
        使用 DeepSeek 生成图片描述 prompt

        将人物信息喂给 deepseek，生成一个优化的图片生成 prompt

        Args:
            character_info: 人物信息字典

        Returns:
            优化后的图片生成 prompt
        """
        api_key, base_url, model = get_scene_analyzer_config()

        if not api_key:
            logger.warning("No DeepSeek API key, using fallback prompt")
            return ImagePromptBuilder().build_fallback_prompt(character_info)

        # 构建 system prompt
        system_prompt = """你是一个专业的图片描述生成专家。你的任务是将人物信息转换为一个详细、生动的图片生成提示词。

要求：
1. 描述人物的外貌特征（面部、发型、体型、肤色等）
2. 描述人物的服装和穿着风格（必须是日常写实服装，禁止科幻/赛博朋克风格）
3. 描述人物的气质和神态
4. 确保描述适合 AI 绘画模型理解
5. 输出格式为纯文本描述，不要包含任何 JSON 或其他格式
6. 描述应该足够详细，让 AI 能够生成高质量的图片
7. 强调全身像、脚部可见
8. 写实摄影风格：人物必须是真实世界的自然呈现，禁止任何科幻、奇幻、超现实元素
9. 日常服装：根据时代背景穿着普通日常服装（衬衫、T恤、外套、牛仔裤、休闲裤等），禁止金属质感、电路纹理、发光装饰
10. 真实背景：日常生活场景，自然光线，禁止科幻城市、全息投影、霓虹光效

输出应该是一段连贯的中文描述，约100-200字。"""

        # 构建 user prompt
        user_prompt = f"""请为以下人物生成一个详细的图片描述：

姓名：{character_info.get('name', '未知')}
年龄：{character_info.get('age', '25')}岁
性别：{character_info.get('gender', '女')}
时代背景：{character_info.get('era', '现代')}
外貌描述：{character_info.get('appearance', '')}
性格特点：{character_info.get('personality', '')}
职业：{character_info.get('occupation', '')}
背景故事：{character_info.get('background', '')}

请生成一段适合 AI 绘画的详细人物描述。"""

        try:
            client = openai.OpenAI(api_key=api_key, base_url=base_url)
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.8,
                max_tokens=500,
            )

            prompt = (response.choices[0].message.content or "").strip()
            logger.debug(f"DeepSeek generated prompt: {prompt[:100]}...")
            return prompt

        except Exception as e:
            logger.error(f"DeepSeek prompt generation failed: {e}")
            return ImagePromptBuilder().build_fallback_prompt(character_info)

    def analyze_story_for_illustration(
        self,
        story_text: str,
        character_info: Dict[str, Any],
    ) -> Tuple[str, str]:
        """
        使用 DeepSeek 分析故事，选择最重要/最视觉化的场景

        Args:
            story_text: 开场故事文本
            character_info: 角色信息（姓名、外貌、时代等）

        Returns:
            Tuple[str, str]: (场景描述, 插画生成提示词)
        """
        api_key, base_url, model = get_scene_analyzer_config()

        if not api_key:
            logger.warning("No DeepSeek API key, using fallback")
            return self._fallback_scene_selection(story_text, character_info)

        player_name = character_info.get("name", "主角")
        era = character_info.get("era", "现代")
        gender = character_info.get("gender", "")
        age = character_info.get("age", "")

        system_prompt = """你是一个专业的电影场景设计师和插画指导。你的任务是分析故事文本，选择最适合绘制的视觉场景。

选择标准：
1. 场景应该有强烈的视觉感（环境、光影、动作）
2. 场景应该能够展现主角的性格或处境
3. 避免选择过于抽象或内心独白的片段
4. 优先选择有明确动作和环境描述的场景

重要约束（严格遵守）：
- 写实主义：画面必须是真实世界的自然呈现，禁止任何科幻、奇幻、超现实元素
- 禁止全息投影、悬浮信息面板、发光特效等科幻视觉元素
- 禁止赛博朋克风格：金属质感服装、电路纹理、发光线条
- 禁止品牌Logo：不得出现星巴克、苹果等真实商业品牌
- 人物服装必须是日常便装（衬衫、T恤、外套、牛仔裤等）
- 背景必须是真实环境（街道、室内、公园等），自然光线

输出格式（严格遵守）：
【场景描述】简短描述你选择的场景（50字以内）
【画面构图】详细描述画面构图、人物姿态、环境细节、光影效果（100-200字）
【氛围】描述画面应传达的情感氛围

请只输出上述格式内容，不要添加其他解释。"""

        user_prompt = f"""请分析以下开场故事，选择最适合绘制插画的场景：

故事文本：
{story_text}

主角信息：
- 姓名：{player_name}
- 性别：{gender}
- 年龄：{age}
- 时代：{era}

请选择一个最能展现故事氛围和主角特点的场景，并生成插画指导。"""

        try:
            client = openai.OpenAI(api_key=api_key, base_url=base_url)
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.7,
                max_tokens=800,
            )

            result = (response.choices[0].message.content or "").strip()
            logger.info(f"DeepSeek scene analysis: {result[:200]}...")

            # 解析结果
            scene_desc = ""
            composition = ""
            atmosphere = ""

            for line in result.split("\n"):
                line = line.strip()
                if line.startswith("【场景描述】"):
                    scene_desc = line.replace("【场景描述】", "").strip()
                elif line.startswith("【画面构图】"):
                    composition = line.replace("【画面构图】", "").strip()
                elif line.startswith("【氛围】"):
                    atmosphere = line.replace("【氛围】", "").strip()

            # 构建插画提示词
            prompt_parts = []
            if era:
                prompt_parts.append(f"时代背景：{era}。")
            if scene_desc:
                prompt_parts.append(f"场景：{scene_desc}。")
            if composition:
                prompt_parts.append(f"画面描述：{composition}。")
            if atmosphere:
                prompt_parts.append(f"氛围：{atmosphere}。")

            # 添加风格指导
            prompt_parts.append("风格：电影感，写实风格，光影自然，故事感强。")

            illustration_prompt = "".join(prompt_parts)

            if not scene_desc:
                scene_desc = story_text[:100] + "..."

            return scene_desc, illustration_prompt

        except Exception as e:
            logger.error(f"DeepSeek scene analysis failed: {e}")
            return self._fallback_scene_selection(story_text, character_info)

    def _fallback_scene_selection(
        self,
        story_text: str,
        character_info: Dict[str, Any],
    ) -> Tuple[str, str]:
        """备选：基于规则选择场景"""
        player_name = character_info.get("name", "主角")
        era = character_info.get("era", "现代")

        # 简单截取故事开头作为场景
        scene_desc = story_text[:150] if len(story_text) > 150 else story_text

        illustration_prompt = f"""{era}场景插画。
场景描述：{scene_desc}
画面中展现{player_name}在故事中的关键时刻。
风格：电影感，写实风格，光影自然，故事感强。"""

        return scene_desc, illustration_prompt

    def rewrite_prompt_for_content_safety(
        self,
        original_prompt: str,
        scene_desc: str,
        character_info: Dict[str, Any],
        api_error_message: Optional[str] = None,
    ) -> Tuple[str, str]:
        """
        使用 DeepSeek 改写 prompt 以规避内容审核

        Args:
            original_prompt: 原始 prompt
            scene_desc: 场景描述
            character_info: 角色信息
            api_error_message: 阿里云返回的审核错误信息

        Returns:
            Tuple[str, str]: (改写后的场景描述, 改写后的完整 prompt)
        """
        api_key, base_url, model = get_scene_analyzer_config()

        if not api_key:
            logger.warning("No DeepSeek API key for prompt rewrite, using simplified prompt")
            return ImagePromptBuilder().simplify_prompt(original_prompt, scene_desc)

        player_name = character_info.get("name", "主角")
        era = character_info.get("era", "现代")

        # 根据是否有具体错误信息，构建不同的 system prompt
        if api_error_message:
            system_prompt = """你是一个专业的内容安全审核专家和图片提示词优化师。你的任务是分析图片生成API返回的内容审核失败原因，然后改写提示词使其能够通过审核。

重要：图片生成API已经明确拒绝了原始提示词，你需要根据具体的错误信息来判断问题所在并修复。

改写原则：
1. 仔细分析API返回的错误信息，理解被拒绝的具体原因
2. 移除或替换可能触发审核的内容（如敏感场所、敏感行为、敏感词汇等）
3. 保持场景的核心视觉元素和故事感
4. 使用更中性、安全的描述方式
5. 常见的敏感内容包括：网吧、酒吧、深夜场景、赌博相关、暴力血腥、性暗示等

输出格式（严格遵守）：
【场景描述】改写后的简短场景描述（50字以内）
【提示词】改写后的完整图片生成提示词

请只输出上述格式内容，不要添加其他解释。"""

            user_prompt = f"""图片生成API拒绝了以下提示词，请根据错误信息改写：

【API返回的错误信息】
{api_error_message}

【原始场景描述】
{scene_desc}

【原始提示词】
{original_prompt}

【主角信息】
- 姓名：{player_name}
- 时代：{era}

请根据API的错误信息，改写提示词使其能够通过内容审核。"""
        else:
            # 没有具体错误信息时，使用通用策略
            system_prompt = """你是一个专业的内容安全审核专家和图片提示词优化师。你的任务是改写图片生成提示词，使其能够通过内容安全审核，同时保持原有的视觉表达效果。

改写原则：
1. 移除可能触发审核的敏感词汇（如：网吧、深夜、酒吧、赌博、暴力、血腥、性暗示等）
2. 将敏感场景替换为安全的替代场景（如：网吧→图书馆/书房，深夜→傍晚，酒吧→咖啡厅）
3. 保持场景的核心视觉元素（人物动作、环境氛围、光影效果）
4. 使用更中性、描述性的语言
5. 保持画面的艺术感和故事感

输出格式（严格遵守）：
【场景描述】改写后的简短场景描述（50字以内）
【提示词】改写后的完整图片生成提示词

请只输出上述格式内容，不要添加其他解释。"""

            user_prompt = f"""请改写以下图片生成提示词，使其能够通过内容安全审核：

原始场景描述：
{scene_desc}

原始提示词：
{original_prompt}

主角信息：
- 姓名：{player_name}
- 时代：{era}

请改写提示词，移除敏感内容，保持视觉表达效果。"""

        try:
            client = openai.OpenAI(api_key=api_key, base_url=base_url)
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.7,
                max_tokens=800,
            )

            result = (response.choices[0].message.content or "").strip()
            logger.debug(
                f"DeepSeek prompt rewrite (api_error={bool(api_error_message)}): {result[:200]}..."
            )

            # 解析结果
            new_scene_desc = scene_desc  # 默认保持原场景
            new_prompt = original_prompt  # 默认保持原 prompt

            for line in result.split("\n"):
                line = line.strip()
                if line.startswith("【场景描述】"):
                    new_scene_desc = line.replace("【场景描述】", "").strip()
                elif line.startswith("【提示词】"):
                    new_prompt = line.replace("【提示词】", "").strip()

            logger.info(f"Rewritten scene: {new_scene_desc}")
            logger.debug(f"Rewritten prompt: {new_prompt[:100]}...")

            return new_scene_desc, new_prompt

        except Exception as e:
            logger.error(f"DeepSeek prompt rewrite failed: {e}")
            return ImagePromptBuilder().simplify_prompt(original_prompt, scene_desc)

    def generate_appearance_anchor(
        self,
        name: str,
        description: str,
        era: str = "现代",
        character_settings: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """生成人物外貌特征锚点（文本层面）.

        基于原始描述和角色设定，生成结构化的外貌特征描述，
        用于后续场景生成时保持人物视觉一致性。

        Args:
            name: 人物名称
            description: 原始人物描述
            era: 时代背景
            character_settings: 角色设定字典（可选）

        Returns:
            锚点字典，可直接存入 metadata_json
        """
        api_key, base_url, model = get_scene_analyzer_config()

        if not api_key:
            logger.warning("No API key for anchor generation, using fallback")
            return self._fallback_appearance_anchor(name, description, era, character_settings)

        # 提取额外的角色信息
        age = ""
        gender = ""
        personality = ""
        if character_settings:
            age_info = character_settings.get("age", {})
            if isinstance(age_info, dict):
                age = str(age_info.get("age", ""))
            gender_info = character_settings.get("gender", {})
            if isinstance(gender_info, dict):
                gender = gender_info.get("gender", "")
            traits = character_settings.get("traits", {})
            if isinstance(traits, dict):
                personality = traits.get("personality", "")

        system_prompt = """你是一个专业的角色设计师和视觉描述专家。
你的任务是基于给定的角色描述，生成一个详细、结构化的外貌特征锚点（Appearance Anchor）。

这个锚点将被用于：
1. 在后续不同场景生成时，确保角色外貌保持一致
2. 作为图片生成的详细描述依据

输出要求：
1. 每个字段都要具体、可视觉化，避免抽象词汇
2. 面部特征要详细（脸型、五官具体形状）
3. 发型要具体到长度、颜色、造型细节
4. 体型和体态要描述到位
5. 服装要符合时代背景，具体到款式、颜色、材质
6. 配饰要具体（如果有）
7. 整体气质要与性格描述匹配

输出格式（JSON）：
{
    "face_shape": "脸型描述，如：标准的鹅蛋脸",
    "facial_features": "五官详细描述，如：单眼皮但眼睛有神，鼻梁挺直，嘴唇薄而线条分明",
    "facial_signature": "面部比例签名，用于精确识别该人物。必须包含可测量的面部比例描述，如：两眼间距约等于一眼宽度，鼻梁中等高度从眉心自然延伸，嘴唇厚度适中上唇略薄于下唇，下巴微尖与颧骨形成柔和过渡，面部整体呈上宽下窄的倒三角比例",
    "expression": "常设表情，如：温和中带着一丝坚毅",
    "skin_tone": "肤色，如：健康的小麦色",
    "hair_style": "发型，如：黑色中长发，自然垂落至肩部",
    "hair_color": "发色，如：乌黑发亮",
    "hair_details": "发型细节，如：刘海自然向右侧分开，发梢微微内卷",
    "body_type": "体型，如：中等偏瘦的身材，身形修长",
    "height_impression": "身高印象，如：看起来比实际年龄显高挑",
    "posture": "体态，如：站姿挺拔， shoulders放松",
    "distinctive_marks": ["独特标记1", "独特标记2"],
    "typical_outfit": "典型服装，如：深蓝色修身牛仔裤，白色简约T恤，外搭一件浅灰色休闲西装外套",
    "clothing_style": "服装风格，如：简约休闲中带点文艺气息",
    "accessories": ["配饰1", "配饰2"],
    "aura": "整体气质，如：书卷气与都市感并存，给人可靠而温和的印象",
    "age_appearance": "年龄感，如：看起来比实际年龄年轻两三岁",
    "lighting_preference": "适合的光线，如：柔和的侧光能突出面部轮廓",
    "angle_preference": "适合的角度，如：略微侧脸比正面更有立体感"
}

要求：
- 所有描述必须是视觉化的，能看到的外貌特征
- 避免模糊词汇如"美丽""帅气"，要具体描述是什么让角色好看
- distinctive_marks 是可选的，但如果有要特别注明（如疤痕、痣、胎记等）
- 服装要具体到可以画出来的程度"""

        user_prompt = f"""请为以下角色生成外貌特征锚点：

角色名称：{name}
时代背景：{era}
原始描述：{description}
"""
        if age:
            user_prompt += f"年龄：{age}\n"
        if gender:
            user_prompt += f"性别：{gender}\n"
        if personality:
            user_prompt += f"性格特点：{personality}\n"

        user_prompt += """
请生成详细的外貌特征锚点，确保描述足够具体，可以用于指导后续所有场景的图片生成。
"""

        try:
            client = openai.OpenAI(api_key=api_key, base_url=base_url)
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.7,
                max_tokens=1500,
                response_format={"type": "json_object"},
            )

            result = (response.choices[0].message.content or "").strip()
            logger.info(f"Generated appearance anchor for {name}")
            logger.debug(f"Anchor content: {result[:300]}...")

            # 解析 JSON
            import json

            anchor_data = json.loads(result)

            # 添加元信息
            anchor_data["name"] = name
            anchor_data["era"] = era
            anchor_data["generated_from"] = description[:200]  # 保存原始描述的前200字
            anchor_data["version"] = 1

            return anchor_data  # type: ignore[no-any-return]

        except Exception as e:
            logger.error(f"Failed to generate appearance anchor: {e}")
            return self._fallback_appearance_anchor(name, description, era, character_settings)

    def _fallback_appearance_anchor(
        self,
        name: str,
        description: str,
        era: str = "现代",
        character_settings: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """当API不可用时，从描述中提取基础锚点信息."""
        logger.warning(f"Using fallback anchor generation for {name}")

        # 简单的关键词提取逻辑
        anchor = {
            "name": name,
            "era": era,
            "face_shape": "",
            "facial_features": description,  # 直接使用原始描述
            "expression": "",
            "skin_tone": "",
            "hair_style": "",
            "hair_color": "",
            "hair_details": "",
            "body_type": "",
            "height_impression": "",
            "posture": "",
            "distinctive_marks": [],
            "typical_outfit": "",
            "clothing_style": "",
            "accessories": [],
            "aura": "",
            "age_appearance": "",
            "lighting_preference": "",
            "angle_preference": "",
            "generated_from": description[:200],
            "version": 1,
            "is_fallback": True,  # 标记为fallback生成的
        }

        # 简单的关键词匹配
        desc_lower = description.lower()

        # 脸型
        if any(w in desc_lower for w in ["圆脸", "圆脸"]):
            anchor["face_shape"] = "圆脸"
        elif any(w in desc_lower for w in ["瓜子脸", "瓜子臉"]):
            anchor["face_shape"] = "瓜子脸"
        elif any(w in desc_lower for w in ["方脸", "方臉"]):
            anchor["face_shape"] = "方脸"

        # 发型/发色
        if "长发" in desc_lower:
            anchor["hair_style"] = "长发"
        elif "短发" in desc_lower:
            anchor["hair_style"] = "短发"

        if any(w in desc_lower for w in ["黑发", "黑色头发", "乌黑"]):
            anchor["hair_color"] = "黑色"
        elif any(w in desc_lower for w in ["金发", "金色"]):
            anchor["hair_color"] = "金色"
        elif "棕发" in desc_lower or "棕色头发" in desc_lower:
            anchor["hair_color"] = "棕色"

        # 生成基础面部签名（fallback情况下）
        if anchor["face_shape"] or anchor["facial_features"]:
            sig_parts = []
            if anchor["face_shape"]:
                sig_parts.append(f"{anchor['face_shape']}，面部轮廓清晰可辨")
            if anchor["facial_features"]:
                sig_parts.append(str(anchor["facial_features"]))
            anchor["facial_signature"] = "。".join(sig_parts) if sig_parts else ""

        return anchor
