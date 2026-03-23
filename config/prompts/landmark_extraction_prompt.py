"""标志物提取Prompt。

用于从故事中提取重要地点/场景的AI提示词。
"""

from typing import Any, Dict, List


def get_landmark_extraction_prompt(
    story_text: str,
    existing_landmarks: List[Dict[str, Any]],
    character_settings: Dict[str, Any],
    current_week: int,
    language: str = "zh",
) -> str:
    """生成标志物提取的提示词。

    Args:
        story_text: 故事文本
        existing_landmarks: 已存在的标志物列表
        character_settings: 角色设定
        current_week: 当前周数
        language: 语言代码

    Returns:
        提示词字符串
    """
    # 构建已存在标志物的上下文
    existing_context = ""
    if existing_landmarks:
        if language == "zh":
            existing_context = "【已记录的重要地点】\n"
            for landmark in existing_landmarks:
                appear_count = landmark.get("appear_count", 1)
                existing_context += f"- {landmark.get('name', '未知')}: {landmark.get('description', '')[:50]}... (出现{appear_count}次)\n"
        else:
            existing_context = "[Recorded Important Locations]\n"
            for landmark in existing_landmarks:
                appear_count = landmark.get("appear_count", 1)
                existing_context += f"- {landmark.get('name', 'Unknown')}: {landmark.get('description', '')[:50]}... (appeared {appear_count} times)\n"

    # 获取主角名字
    player_name = character_settings.get("player_name", "主角")

    if language == "zh":
        return f"""请分析以下故事，提取其中的重要地点/场景（标志物）。

**标志物的定义：**
1. 反复出现的重要地点（主角的家、工作场所、常去的咖啡厅等）
2. 关键剧情发生的地点（重要事件发生地、秘密基地等）
3. 具有特殊意义或象征性的地点（故乡、母校、纪念碑等）
4. 对主角有情感价值的地点（初遇之地、成长之地等）

**不是标志物：**
- 仅作为过渡提及的普通地点
- 没有具体描述的泛泛之地（如"街道"、"商场"）
- 一次性路过且无特殊意义的地点

**主角：** {player_name}
**当前周数：** {current_week + 1}

{existing_context}

**故事文本：**
{story_text}

**输出格式（JSON）：**
{{
  "landmarks": [
    {{
      "action": "new" 或 "update",
      "name": "地点名称",
      "description": "地点描述（2-4句话，包含外观、氛围、特色）",
      "category": "building/nature/room/area/other",
      "importance": "critical/important/normal",
      "context": "当前场景描述",
      "is_key_location": true/false,
      "metadata": {{
        "atmosphere": "氛围描述",
        "features": "特色元素",
        "related_characters": ["关联人物"]
      }}
    }}
  ]
}}

**注意事项：**
1. description 必须详细，便于后续生成图片
2. importance 判断标准：
   - critical: 关键地点，故事核心场景
   - important: 重要地点，多次出现或有特殊意义
   - normal: 值得记录但非核心
3. category 分类说明：
   - building: 建筑物（房屋、办公楼、商店等）
   - nature: 自然景观（公园、山林、湖泊等）
   - room: 室内房间（卧室、办公室、教室等）
   - area: 区域范围（街区、城市、区域等）
   - other: 其他
4. action 字段：
   - "new": 新发现的地点
   - "update": 已存在的地点再次出现，需要更新出现次数
5. 如果没有发现重要地点，返回空数组 {{"landmarks": []}}
6. 对于已存在的地点，只需返回 {{"action": "update", "name": "地点名称"}}
"""
    else:
        return f"""Please analyze the following story and extract important locations/landmarks.

**Definition of Landmarks:**
1. Recurring important locations (protagonist's home, workplace, favorite cafe, etc.)
2. Locations where key plot events occur (important event sites, secret bases, etc.)
3. Locations with special meaning or symbolism (hometown, alma mater, monuments, etc.)
4. Locations with emotional value to the protagonist (first meeting place, growth place, etc.)

**NOT Landmarks:**
- Ordinary locations mentioned only in passing
- Generic places without specific description (like "street", "mall")
- One-time visited locations with no special significance

**Protagonist:** {player_name}
**Current Week:** {current_week + 1}

{existing_context}

**Story Text:**
{story_text}

**Output Format (JSON):**
{{
  "landmarks": [
    {{
      "action": "new" or "update",
      "name": "Location Name",
      "description": "Location description (2-4 sentences including appearance, atmosphere, features)",
      "category": "building/nature/room/area/other",
      "importance": "critical/important/normal",
      "context": "Current scene description",
      "is_key_location": true/false,
      "metadata": {{
        "atmosphere": "Atmosphere description",
        "features": "Notable features",
        "related_characters": ["Related characters"]
      }}
    }}
  ]
}}

**Notes:**
1. description must be detailed enough for image generation
2. importance criteria:
   - critical: Key locations, core story scenes
   - important: Important locations, recurring or with special meaning
   - normal: Worth recording but not core
3. category explanations:
   - building: Buildings (houses, offices, shops, etc.)
   - nature: Natural landscapes (parks, mountains, lakes, etc.)
   - room: Indoor rooms (bedrooms, offices, classrooms, etc.)
   - area: Area ranges (neighborhoods, cities, regions, etc.)
   - other: Other
4. action field:
   - "new": Newly discovered location
   - "update": Existing location appearing again, need to update appearance count
5. If no important locations found, return empty array {{"landmarks": []}}
6. For existing locations, only return {{"action": "update", "name": "Location Name"}}
"""


def get_landmark_description_generation_prompt(
    landmark_name: str,
    landmark_category: str,
    context: str,
    story_context: str,
    language: str = "zh",
) -> str:
    """生成标志物描述生成的提示词。

    Args:
        landmark_name: 地点名称
        landmark_category: 地点类别
        context: 场景描述
        story_context: 相关故事上下文
        language: 语言代码

    Returns:
        提示词字符串
    """
    category_names = {
        "building": {"zh": "建筑", "en": "Building"},
        "nature": {"zh": "自然景观", "en": "Nature"},
        "room": {"zh": "房间", "en": "Room"},
        "area": {"zh": "区域", "en": "Area"},
        "other": {"zh": "其他", "en": "Other"},
    }

    category_name = category_names.get(
        landmark_category, {"zh": "其他", "en": "Other"}
    )[language]

    if language == "zh":
        return f"""请为以下地点生成详细的描述。

**地点名称：** {landmark_name}
**地点类别：** {category_name}
**场景描述：** {context}

**相关故事片段：**
{story_context}

**要求：**
1. 描述应包含地点的外观特征（建筑风格、布局、色调等）
2. 描述地点的氛围和感觉（温馨、庄严、神秘等）
3. 描述地点的特色元素或标志性特征
4. 描述应生动具体，便于读者想象地点的样子
5. 字数在100-200字之间

**输出格式（JSON）：**
{{
  "name": "{landmark_name}",
  "description": "详细描述...",
  "atmosphere": "氛围描述",
  "features": "特色元素"
}}
"""
    else:
        return f"""Please generate a detailed description for the following location.

**Location Name:** {landmark_name}
**Location Category:** {category_name}
**Scene Description:** {context}

**Related Story Fragment:**
{story_context}

**Requirements:**
1. Description should include appearance features (architectural style, layout, color scheme, etc.)
2. Describe the atmosphere and feeling of the location (cozy, solemn, mysterious, etc.)
3. Describe notable features or iconic characteristics
4. Description should be vivid and specific, helping readers visualize the location
5. Word count between 100-200 words

**Output Format (JSON):**
{{
  "name": "{landmark_name}",
  "description": "Detailed description...",
  "atmosphere": "Atmosphere description",
  "features": "Notable features"
}}
"""
