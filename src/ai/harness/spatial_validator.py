"""空间位移验证器 - 验证角色移动的空间合理性。

检查内容：
- 3级距离模型: 同城=0轮可达, 邻近=1轮, 远距离=2-3轮
- 瞬移检测：角色不应在一轮内跨越远距离
"""

import logging
import re
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# 默认距离等级（无location_graph时的fallback）
# 1=同城, 2=邻近, 3=远距离
DEFAULT_DISTANCE = 2

# 简单的区域距离映射 (用于无 location_graph 时的 fallback)
# 同区域=1, 相邻区域=2, 远距离=3
REGION_ADJACENCY = {
    "河南": ["山东", "河北", "山西", "陕西", "湖北", "安徽"],
    "云南": ["四川", "贵州", "广西", "西藏"],
    "四川": ["云南", "贵州", "重庆", "陕西", "甘肃", "青海", "西藏"],
    "浙江": ["江苏", "安徽", "江西", "福建"],
    "江苏": ["浙江", "安徽", "山东"],
}

# 距离等级与所需最少轮数的映射
DISTANCE_TRAVEL_ROUNDS = {
    1: 0,  # 同城: 0轮即可
    2: 1,  # 邻近: 至少1轮
    3: 2,  # 远距离: 至少2轮
}

# 位置变化关键词
LOCATION_CHANGE_PATTERNS = [
    r"来到了?(.{2,10})",
    r"到达了?(.{2,10})",
    r"抵达了?(.{2,10})",
    r"前往(.{2,10})",
    r"赶到了?(.{2,10})",
    r"回到了?(.{2,10})",
    r"踏入了?(.{2,10})",
    r"走进了?(.{2,10})",
    r"进入了?(.{2,10})",
    r"出现在(.{2,10})",
    r"站在(.{2,10})",
    r"已在(.{2,10})",
    r"身处(.{2,10})",
]

# 交通工具关键词（可加速旅行）
FAST_TRAVEL_KEYWORDS = [
    "骑马", "马车", "轿子", "快马", "驱车", "乘船", "飞", "传送",
    "日夜兼程", "快马加鞭", "星夜赶路", "连夜赶",
]


class SpatialMovementValidator:
    """空间位移验证器。"""

    def validate(self, story_text: str, context: dict) -> Tuple[bool, str, dict]:
        """验证角色移动的空间合理性。"""
        try:
            world_model = context.get("world_model")
            if not world_model:
                return True, "", {"skipped": True, "reason": "no world_model"}

            character_locations = getattr(world_model, "character_locations", {})
            location_graph = getattr(world_model, "location_graph", {})

            if not character_locations:
                return True, "", {"skipped": True, "reason": "no character_locations"}

            player_state = context.get("player_state", {})

            violations = []
            details: Dict = {
                "characters_checked": 0,
                "movement_issues": [],
                "has_fast_travel": False,
            }

            # 检查是否有快速旅行描写
            has_fast_travel = any(kw in story_text for kw in FAST_TRAVEL_KEYWORDS)
            details["has_fast_travel"] = has_fast_travel

            # 对每个有位置记录的角色进行检查
            for char_name, loc_info in character_locations.items():
                if len(char_name) < 2 or char_name not in story_text:
                    continue

                details["characters_checked"] += 1

                prev_location = ""
                if hasattr(loc_info, "location"):
                    prev_location = loc_info.location
                elif isinstance(loc_info, dict):
                    prev_location = loc_info.get("location", "")

                if not prev_location:
                    continue

                # 提取文本中该角色的位置变化
                new_locations = self._extract_character_locations(
                    story_text, char_name
                )

                # 获取角色的当前region
                prev_region = ""
                if isinstance(loc_info, dict):
                    prev_region = loc_info.get("region", "")
                elif hasattr(loc_info, "region"):
                    prev_region = getattr(loc_info, "region", "")

                for new_loc in new_locations:
                    if not new_loc or new_loc == prev_location:
                        continue

                    # 计算距离
                    distance = self.get_location_distance(
                        prev_location, new_loc, location_graph
                    )

                    # 使用region信息增强距离计算
                    if prev_region and distance == DEFAULT_DISTANCE:
                        distance = self._estimate_region_distance(
                            prev_region, new_loc, character_locations
                        )

                    # 检查旅行可行性（假设每轮1回合）
                    required_rounds = DISTANCE_TRAVEL_ROUNDS.get(distance, 2)
                    feasible = (1 >= required_rounds)  # elapsed_rounds=1

                    if not feasible and not has_fast_travel:
                        violations.append({
                            "character": char_name,
                            "from": prev_location,
                            "to": new_loc,
                            "distance": distance,
                            "message": f"角色'{char_name}'从'{prev_location}'到'{new_loc}'"
                            f"距离等级{distance}，一轮内无法到达",
                        })
                        details["movement_issues"].append({
                            "character": char_name,
                            "from": prev_location,
                            "to": new_loc,
                            "distance": distance,
                        })

            if violations:
                return (
                    False,
                    f"空间位移违规: {'; '.join(v['message'] for v in violations[:3])}",
                    {
                        **details,
                        "violations": violations,
                        "correction_hint": "角色不应在一轮内跨越远距离，"
                        "同城(距离1)可即时到达，邻近(距离2)需至少1轮，"
                        "远距离(距离3)需2-3轮",
                    },
                )

            return True, "", details

        except Exception as e:
            logger.warning(f"空间位移验证异常: {e}")
            return True, "", {}

    def get_location_distance(
        self, loc_a: str, loc_b: str, location_graph: Dict[str, Dict[str, int]]
    ) -> int:
        """获取两地距离等级: 1=同城, 2=邻近, 3=远距离。"""
        if not location_graph:
            return DEFAULT_DISTANCE

        # 查找直接距离
        neighbors_a = location_graph.get(loc_a, {})
        if loc_b in neighbors_a:
            return neighbors_a[loc_b]

        # 反向查找
        neighbors_b = location_graph.get(loc_b, {})
        if loc_a in neighbors_b:
            return neighbors_b[loc_a]

        # 模糊匹配：检查是否部分包含
        for graph_loc, neighbors in location_graph.items():
            if loc_a in graph_loc or graph_loc in loc_a:
                for neighbor, dist in neighbors.items():
                    if loc_b in neighbor or neighbor in loc_b:
                        return dist

        # 未找到连接，假设远距离
        return 3

    def check_travel_feasibility(
        self, prev_location: str, curr_location: str, elapsed_rounds: int
    ) -> bool:
        """检查旅行是否可行。"""
        distance = self.get_location_distance(prev_location, curr_location, {})
        required_rounds = DISTANCE_TRAVEL_ROUNDS.get(distance, 2)
        return elapsed_rounds >= required_rounds

    def _extract_character_locations(
        self, text: str, character_name: str
    ) -> List[str]:
        """提取文本中角色的位置变化。"""
        locations = []

        # 查找 "角色名 + 位置动词 + 地点" 模式
        for pattern in LOCATION_CHANGE_PATTERNS:
            full_pattern = re.escape(character_name) + r".{0,20}" + pattern
            for match in re.finditer(full_pattern, text):
                loc = match.group(1).strip() if match.lastindex else ""
                # 清理提取的地点（去掉标点等）
                loc = re.sub(r"[，。！？、；：\"\"''（）\s].*", "", loc)
                if len(loc) >= 2:
                    locations.append(loc)

        return locations

    def _estimate_region_distance(
        self, prev_region: str, new_loc: str, character_locations: dict
    ) -> int:
        """利用region信息估算距离。"""
        # 在 character_locations 中查找目标地点所属的 region
        target_region = ""
        for char, loc_info in character_locations.items():
            loc = ""
            region = ""
            if isinstance(loc_info, dict):
                loc = loc_info.get("location", "")
                region = loc_info.get("region", "")
            elif hasattr(loc_info, "location"):
                loc = getattr(loc_info, "location", "")
                region = getattr(loc_info, "region", "")

            if new_loc in loc or loc in new_loc or new_loc in region:
                target_region = region
                break

        # 直接检查新位置名与已知region的匹配
        if not target_region:
            for region_name in REGION_ADJACENCY:
                if region_name in new_loc or new_loc in region_name:
                    target_region = region_name
                    break

        if not target_region:
            return DEFAULT_DISTANCE

        if target_region == prev_region:
            return 1  # 同区域

        # 检查是否相邻
        adjacent = REGION_ADJACENCY.get(prev_region, [])
        if target_region in adjacent:
            return 2  # 邻近

        return 3  # 远距离


def validate_spatial_movement(
    story_text: str, context: dict
) -> Tuple[bool, str, dict]:
    """模块级验证函数。"""
    return SpatialMovementValidator().validate(story_text, context)
