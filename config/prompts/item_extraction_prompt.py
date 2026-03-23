"""物品提取Prompt。

用于从故事中提取重要物品的AI提示词。
"""

from typing import Any, Dict, List


def get_item_extraction_prompt(
    story_text: str,
    existing_items: List[Dict[str, Any]],
    character_settings: Dict[str, Any],
    current_week: int,
    language: str = "zh",
) -> str:
    """生成物品提取的提示词。

    Args:
        story_text: 故事文本
        existing_items: 已存在的物品列表
        character_settings: 角色设定
        current_week: 当前周数
        language: 语言代码

    Returns:
        提示词字符串
    """
    # 构建已存在物品的上下文
    existing_context = ""
    if existing_items:
        if language == "zh":
            existing_context = "【已记录的重要物品】\n"
            for item in existing_items:
                existing_context += f"- {item.get('name', '未知')}: {item.get('description', '')[:50]}...\n"
        else:
            existing_context = "[Recorded Important Items]\n"
            for item in existing_items:
                existing_context += f"- {item.get('name', 'Unknown')}: {item.get('description', '')[:50]}...\n"

    # 获取主角名字
    player_name = character_settings.get("player_name", "主角")

    if language == "zh":
        return f"""请分析以下故事，提取其中的重要物品。

**重要物品的定义：**
1. 对剧情有重大影响的物品（关键道具、线索物品）
2. 具有特殊意义或价值的物品（纪念品、宝物、传家宝）
3. 可能在未来剧情中发挥作用的物品（武器、工具、文件）
4. 与角色情感相关的物品（礼物、信物、纪念品）

**不是重要物品：**
- 普通的日常用品（笔、纸、普通衣服等）
- 随处可得的普通物品
- 仅作为场景装饰的物品

**主角：** {player_name}
**当前周数：** {current_week + 1}

{existing_context}

**故事文本：**
{story_text}

**输出格式（JSON）：**
{{
  "items": [
    {{
      "action": "new",
      "name": "物品名称",
      "description": "物品描述（2-4句话，包含外观、来源、意义）",
      "importance": "critical/important/normal",
      "category": "weapon/tool/keepsake/treasure/document/other",
      "acquired_context": "获得场景简述",
      "is_key_item": true/false,
      "metadata": {{
        "appearance": "外观描述",
        "special_abilities": "特殊能力（如有）",
        "owner": "持有者"
      }}
    }}
  ]
}}

**注意事项：**
1. description 必须详细，便于后续生成图片
2. importance 判断标准：
   - critical: 剧情关键物品，缺失将影响故事走向
   - important: 有特殊意义或价值的物品
   - normal: 值得记录但非关键
3. category 分类说明：
   - weapon: 武器
   - tool: 工具
   - keepsake: 纪念品/信物
   - treasure: 宝物/珍品
   - document: 文件/书籍
   - other: 其他
4. 如果没有发现新的重要物品，返回空数组 {{"items": []}}
5. 不要重复添加已存在的物品
"""
    else:
        return f"""Please analyze the following story and extract important items.

**Definition of Important Items:**
1. Items with significant plot impact (key props, clue items)
2. Items with special meaning or value (keepsakes, treasures, heirlooms)
3. Items that may play a role in future plot (weapons, tools, documents)
4. Items with emotional significance to characters (gifts, tokens, mementos)

**NOT Important Items:**
- Ordinary daily items (pens, paper, regular clothes, etc.)
- Common items available everywhere
- Items serving only as scene decoration

**Protagonist:** {player_name}
**Current Week:** {current_week + 1}

{existing_context}

**Story Text:**
{story_text}

**Output Format (JSON):**
{{
  "items": [
    {{
      "action": "new",
      "name": "Item Name",
      "description": "Item description (2-4 sentences including appearance, origin, significance)",
      "importance": "critical/important/normal",
      "category": "weapon/tool/keepsake/treasure/document/other",
      "acquired_context": "Brief description of acquisition scene",
      "is_key_item": true/false,
      "metadata": {{
        "appearance": "Appearance description",
        "special_abilities": "Special abilities (if any)",
        "owner": "Owner"
      }}
    }}
  ]
}}

**Notes:**
1. description must be detailed enough for image generation
2. importance criteria:
   - critical: Plot-critical items, missing will affect story direction
   - important: Items with special meaning or value
   - normal: Worth recording but not critical
3. category explanations:
   - weapon: Weapons
   - tool: Tools
   - keepsake: Keepsakes/Tokens
   - treasure: Treasures/Valuables
   - document: Documents/Books
   - other: Other
4. If no new important items found, return empty array {{"items": []}}
5. Do not duplicate already existing items
"""


def get_item_description_generation_prompt(
    item_name: str,
    item_category: str,
    acquired_context: str,
    story_context: str,
    language: str = "zh",
) -> str:
    """生成物品描述生成的提示词。

    Args:
        item_name: 物品名称
        item_category: 物品类别
        acquired_context: 获得场景
        story_context: 相关故事上下文
        language: 语言代码

    Returns:
        提示词字符串
    """
    category_names = {
        "weapon": {"zh": "武器", "en": "Weapon"},
        "tool": {"zh": "工具", "en": "Tool"},
        "keepsake": {"zh": "纪念品", "en": "Keepsake"},
        "treasure": {"zh": "宝物", "en": "Treasure"},
        "document": {"zh": "文件", "en": "Document"},
        "other": {"zh": "其他", "en": "Other"},
    }

    category_name = category_names.get(item_category, {"zh": "其他", "en": "Other"})[
        language
    ]

    if language == "zh":
        return f"""请为以下物品生成详细的描述。

**物品名称：** {item_name}
**物品类别：** {category_name}
**获得场景：** {acquired_context}

**相关故事片段：**
{story_context}

**要求：**
1. 描述应包含物品的外观特征（形状、颜色、材质、大小）
2. 描述物品的历史或来源（如果有）
3. 描述物品的意义或价值
4. 描述应生动具体，便于读者想象物品的样子
5. 字数在100-200字之间

**输出格式（JSON）：**
{{
  "name": "{item_name}",
  "description": "详细描述...",
  "appearance": "外观特征简述",
  "significance": "物品意义或价值"
}}
"""
    else:
        return f"""Please generate a detailed description for the following item.

**Item Name:** {item_name}
**Item Category:** {category_name}
**Acquisition Context:** {acquired_context}

**Related Story Fragment:**
{story_context}

**Requirements:**
1. Description should include appearance features (shape, color, material, size)
2. Describe the item's history or origin (if any)
3. Describe the item's significance or value
4. Description should be vivid and specific, helping readers visualize the item
5. Word count between 100-200 words

**Output Format (JSON):**
{{
  "name": "{item_name}",
  "description": "Detailed description...",
  "appearance": "Brief appearance description",
  "significance": "Item significance or value"
}}
"""
