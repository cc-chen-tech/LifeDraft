"""实体识别Prompt。

用于从历史故事中识别重复出现的物品、人物、地点的AI提示词。
"""

from typing import Any, Dict, List


def get_entity_recognition_prompt(
    story_text: str,
    existing_items: List[str],
    existing_characters: List[str],
    existing_landmarks: List[str],
    min_appearances: int = 3,
    language: str = "zh",
) -> str:
    """生成实体识别的提示词。

    Args:
        story_text: 完整的故事文本（由round_history构建）
        existing_items: 已存在的物品名称列表
        existing_characters: 已存在的人物名称列表
        existing_landmarks: 已存在的地点名称列表
        min_appearances: 最少出现次数（默认3次）
        language: 语言代码

    Returns:
        提示词字符串
    """
    # 构建已存在实体的上下文
    existing_context = ""
    if existing_items:
        existing_context += f"\n【已存在的物品】{', '.join(existing_items)}\n"
    if existing_characters:
        existing_context += f"\n【已存在的人物】{', '.join(existing_characters)}\n"
    if existing_landmarks:
        existing_context += f"\n【已存在的地点】{', '.join(existing_landmarks)}\n"

    if language == "zh":
        # 根据阈值动态生成描述
        if min_appearances <= 1:
            freq_desc = "在故事中出现过的"
            freq_rule = "在故事中至少被提及过"
        elif min_appearances == 2:
            freq_desc = "在故事中出现至少2次的"
            freq_rule = "至少出现2次"
        else:
            freq_desc = f"在故事中出现至少{min_appearances}次的"
            freq_rule = f"至少出现{min_appearances}次"

        return f"""请分析以下完整的故事历史，识别其中{freq_desc}重要实体（物品、人物、地点）。

**任务说明：**
你需要仔细阅读整个故事，找出{freq_desc}实体，并生成它们的详细描述。

**识别规则：**

1. **物品识别规则：**
   - {freq_rule}
   - 对剧情有影响、有特殊意义、或与角色有情感联系的物品
   - 排除完全没有剧情意义的日常用品
   - 包括：武器、工具、纪念品、宝物、文件、关键道具、有故事背景的物件等

2. **人物识别规则：**
   - {freq_rule}
   - 有名字或有明确身份的角色
   - 排除完全没有剧情作用的背景路人
   - 包括：朋友、家人、同事、对手、重要NPC等

3. **地点识别规则：**
   - {freq_rule}
   - 有明确名称或显著特征的场所
   - 排除完全没有辨识度的泛泛描述（如"路上"）
   - 包括：具体建筑、房间、自然景观、标志性地点、故事中反复提到的场所等

**已有实体（不要重复识别）：**
{existing_context}

**故事历史：**
{story_text}

**输出格式（JSON）：**
{{
  "items": [
    {{
      "name": "物品名称",
      "description": "详细描述（100-200字，包含外观、来源、意义）",
      "category": "weapon/tool/keepsake/treasure/document/other",
      "importance": "critical/important/normal",
      "appear_count": 5,
      "appear_contexts": ["第3周周一：在书房发现...", "第5周周末：用它来..."]
    }}
  ],
  "characters": [
    {{
      "name": "人物名称",
      "description": "详细描述（100-200字，包含外貌、性格、与主角关系）",
      "role": "角色定位（朋友/对手/导师等）",
      "importance": "critical/important/normal",
      "appear_count": 8,
      "appear_contexts": ["第2周：首次在...", "第4周：帮助主角..."]
    }}
  ],
  "landmarks": [
    {{
      "name": "地点名称",
      "description": "详细描述（100-200字，包含外观、氛围、意义）",
      "category": "building/nature/room/area/other",
      "importance": "critical/important/normal",
      "appear_count": 4,
      "appear_contexts": ["第1周：主角第一次来到...", "第6周：再次回到..."]
    }}
  ]
}}

**注意事项：**
1. 只返回{freq_desc}实体
2. 不要返回已存在的实体
3. description必须详细，便于后续生成图片
4. appear_contexts列出3-5个关键出现场景（包含周数和简要描述）
5. importance判断标准：
   - critical: 对剧情走向有重大影响的
   - important: 有重要情感或剧情价值的
   - normal: 值得记录但影响较小的
6. 如果没有符合条件的实体，返回对应类别的空数组
7. 确保输出是有效的JSON格式
"""
    else:
        # Dynamic frequency description for English
        if min_appearances <= 1:
            freq_desc = "that appear in the story"
            freq_rule = "Appears at least once in the story"
        elif min_appearances == 2:
            freq_desc = "that appear at least 2 times"
            freq_rule = "Must appear at least 2 times"
        else:
            freq_desc = f"that appear at least {min_appearances} times"
            freq_rule = f"Must appear at least {min_appearances} times"

        return f"""Please analyze the following complete story history and identify important entities (items, characters, locations) {freq_desc}.

**Task Description:**
Read the entire story carefully and find entities {freq_desc}, generating detailed descriptions for them.

**Recognition Rules:**

1. **Item Recognition Rules:**
   - {freq_rule}
   - Items that impact the plot, have special significance, or emotional connection with characters
   - Exclude items with absolutely no plot significance
   - Include: weapons, tools, keepsakes, treasures, documents, key props, story-relevant objects, etc.

2. **Character Recognition Rules:**
   - {freq_rule}
   - Named characters or those with clear identities
   - Exclude background extras with no plot relevance
   - Include: friends, family, colleagues, rivals, important NPCs, etc.

3. **Location Recognition Rules:**
   - {freq_rule}
   - Places with specific names or notable characteristics
   - Exclude completely generic descriptions with no identifiable features (e.g., "on the road")
   - Include: specific buildings, rooms, natural landscapes, iconic locations, recurring story locations, etc.

**Existing Entities (DO NOT duplicate):**
{existing_context}

**Story History:**
{story_text}

**Output Format (JSON):**
{{
  "items": [
    {{
      "name": "Item Name",
      "description": "Detailed description (100-200 words, including appearance, origin, significance)",
      "category": "weapon/tool/keepsake/treasure/document/other",
      "importance": "critical/important/normal",
      "appear_count": 5,
      "appear_contexts": ["Week 3 Monday: Found in the study...", "Week 5 Weekend: Used it to..."]
    }}
  ],
  "characters": [
    {{
      "name": "Character Name",
      "description": "Detailed description (100-200 words, including appearance, personality, relationship with protagonist)",
      "role": "Role (friend/rival/mentor/etc.)",
      "importance": "critical/important/normal",
      "appear_count": 8,
      "appear_contexts": ["Week 2: First appeared at...", "Week 4: Helped protagonist..."]
    }}
  ],
  "landmarks": [
    {{
      "name": "Location Name",
      "description": "Detailed description (100-200 words, including appearance, atmosphere, significance)",
      "category": "building/nature/room/area/other",
      "importance": "critical/important/normal",
      "appear_count": 4,
      "appear_contexts": ["Week 1: Protagonist first came to...", "Week 6: Returned again to..."]
    }}
  ]
}}

**Notes:**
1. Only return entities {freq_desc}
2. Do not return existing entities
3. Descriptions must be detailed enough for image generation
4. appear_contexts should list 3-5 key appearances (with week number and brief description)
5. Importance criteria:
   - critical: Major impact on plot direction
   - important: Significant emotional or plot value
   - normal: Worth recording but minor impact
6. If no qualifying entities, return empty array for that category
7. Ensure output is valid JSON format
"""


def get_item_description_extraction_prompt(
    item_name: str,
    story_text: str,
    language: str = "zh",
) -> str:
    """生成从历史中提取物品描述的提示词。

    Args:
        item_name: 物品名称
        story_text: 包含该物品的故事文本片段
        language: 语言代码

    Returns:
        提示词字符串
    """
    if language == "zh":
        return f"""请基于以下故事片段，为物品"{item_name}"生成详细的描述。

**故事片段：**
{story_text}

**要求：**
1. 描述应包含物品的外观特征（形状、颜色、材质、大小）
2. 描述物品在故事中的作用或意义
3. 描述物品的来源或与主角的关系
4. 描述应生动具体，便于读者想象物品的样子
5. 字数在100-200字之间

**输出格式（JSON）：**
{{
  "name": "{item_name}",
  "description": "详细描述...",
  "category": "weapon/tool/keepsake/treasure/document/other",
  "importance": "critical/important/normal",
  "appearance": "外观特征简述",
  "significance": "物品在故事中的意义"
}}
"""
    else:
        return f"""Please generate a detailed description for the item "{item_name}" based on the following story fragments.

**Story Fragments:**
{story_text}

**Requirements:**
1. Description should include appearance features (shape, color, material, size)
2. Describe the item's role or significance in the story
3. Describe the item's origin or relationship with the protagonist
4. Description should be vivid and specific, helping readers visualize the item
5. Word count between 100-200 words

**Output Format (JSON):**
{{
  "name": "{item_name}",
  "description": "Detailed description...",
  "category": "weapon/tool/keepsake/treasure/document/other",
  "importance": "critical/important/normal",
  "appearance": "Brief appearance description",
  "significance": "Item's significance in the story"
}}
"""
