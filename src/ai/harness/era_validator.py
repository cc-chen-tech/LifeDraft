"""时代一致性验证器。

检测故事文本中是否包含与设定时代背景不符的元素，
防止古代背景出现现代物品/概念（如"星巴克"、"手机"等）。
"""

import logging
from typing import List, Tuple

logger = logging.getLogger(__name__)

# 古代背景中不应出现的现代元素关键词
_ANCIENT_FORBIDDEN_MODERN = [
    # 现代科技/物品
    "手机",
    "电脑",
    "笔记本",
    "平板",
    "互联网",
    "计算机",
    "电视",
    "冰箱",
    "空调",
    "电暖器",
    "洗衣机",
    "微波炉",
    "电梯",
    "汽车",
    "摩托车",
    "自行车",
    "火车",
    "飞机",
    "地铁",
    "公交",
    "出租车",
    "滴滴",
    "高铁",
    "相机",
    "照片",
    "录像",
    "视频",
    "直播",
    "短视频",
    "抖音",
    "快手",
    # 现代品牌/商业
    "星巴克",
    "麦当劳",
    "肯德基",
    "必胜客",
    "汉堡王",
    "可口可乐",
    "百事",
    "耐克",
    "阿迪达斯",
    "优衣库",
    "ZARA",
    "H&M",
    "苹果",
    "华为",
    "小米",
    "淘宝",
    "京东",
    "拼多多",
    "亚马逊",
    "外卖",
    "快递",
    "顺丰",
    "美团",
    "支付宝",
    "微信",
    "微博",
    "小红书",
    "知乎",
    "B站",
    "哔哩哔哩",
    # 现代概念
    "二维码",
    "扫码",
    "刷卡",
    "扫码支付",
    "移动支付",
    "数字货币",
    "比特币",
    "人工智能",
    "机器人",
    "无人机",
    "元宇宙",
    # 现代服饰
    "牛仔裤",
    "T恤",
    "卫衣",
    "西装",
    "领带",
    "皮鞋",
    "运动鞋",
    "帆布鞋",
    "毛呢大衣",
    "羽绒服",
    "风衣",
    "连衣裙",
    "丝袜",
    "高跟鞋",
    # 现代建筑/设施
    "摩天大楼",
    "玻璃幕墙",
    "中央空调",
    "LED",
    "霓虹灯",
    "高速公路",
    "公路",
    "立交桥",
    "停车场",
    "加油站",
    "收费站",
    # 西式现代元素（古代中国不应出现）
    "咖啡",
    "拿铁",
    "卡布奇诺",
    "摩卡",
    "espresso",
    "latte",
    "cappuccino",
    "披萨",
    "汉堡",
    "热狗",
    "三明治",
    "沙拉",
    "牛排",
    "意大利面",
    "巧克力",
    "冰淇淋",
    "小餐馆",
    "蛋糕",
    "面包",
    "吐司",
    "可颂",
    "威士忌",
    "伏特加",
    "红酒",
    "香槟",
    "鸡尾酒",
    # 其他
    "塑料",
    "塑料袋",
    "塑料瓶",
    "一次性",
    "GPS",
    "导航",
    "定位",
    "卫星",
]

# 现代背景中完全允许的关键词（用于避免误报）
_MODERN_ALLOWED = [
    "现代",
    "当代",
    "今天",
    "现在",
    "如今",
    "当下",
]

_MODERN_FORBIDDEN_HISTORICAL = [
    "长安",
    "洛阳",
    "汴京",
    "临安",
    "唐朝",
    "宋朝",
    "元朝",
    "明朝",
    "清朝",
    "大唐",
    "南宋",
    "北宋",
    "郎君",
    "娘子",
    "将作监",
    "科举",
    "客栈",
    "茶楼",
    "木坊",
    "银两",
    "铜钱",
    "三百文",
    "贯钱",
    "文钱",
    "绢帛",
    "胡商",
    "西市",
    "东市",
]


def validate_era_consistency(story_text: str, context: dict) -> Tuple[bool, str, dict]:
    """检查故事文本是否与设定的时代背景一致。

    Args:
        story_text: 生成的故事文本
        context: 包含 era（时代）和 era_type（类型）的上下文

    Returns:
        (是否通过, 失败证据, 详细信息)
    """
    era = context.get("era", "")
    era_type = context.get("era_type", "")

    # 现代/当代背景也需要反向校验，防止故事漂移成古代朝代、古风称谓或前现代货币。
    if era_type == "modern" or "现代" in era or "当代" in era or "未来" in era:
        found_historical: List[str] = []
        for keyword in _MODERN_FORBIDDEN_HISTORICAL:
            if keyword in story_text:
                found_historical.append(keyword)

        if found_historical:
            evidence = f"现代背景检测到古代/前现代漂移: {', '.join(found_historical[:5])}"
            return (
                False,
                evidence,
                {
                    "found_historical": found_historical,
                    "era": era,
                    "era_type": "modern",
                },
            )

        return True, "", {"era": era, "era_type": "modern", "checked_keywords": len(_MODERN_FORBIDDEN_HISTORICAL)}

    # 如果时代未明确指定为古代，检查 era 字符串是否包含古代关键词
    ancient_keywords = [
        "唐",
        "宋",
        "元",
        "明",
        "清",
        "汉",
        "秦",
        "周",
        "春秋",
        "战国",
        "三国",
        "晋",
        "隋",
        "五代",
        "十国",
        "南北朝",
        "上古",
        "远古",
        "古代",
        "medieval",
        "ancient",
        "historic",
    ]
    is_ancient = era_type == "ancient" or any(kw in era for kw in ancient_keywords)

    if not is_ancient:
        return (
            True,
            "",
            {"skipped": True, "reason": f"era '{era}' not recognized as ancient"},
        )

    # 检测故事中是否包含现代元素
    found_modern: List[str] = []
    for keyword in _ANCIENT_FORBIDDEN_MODERN:
        if keyword in story_text:
            found_modern.append(keyword)

    if found_modern:
        evidence = f"检测到现代元素: {', '.join(found_modern[:5])}"
        return (
            False,
            evidence,
            {
                "found_modern": found_modern,
                "era": era,
                "era_type": era_type,
            },
        )

    return True, "", {"era": era, "checked_keywords": len(_ANCIENT_FORBIDDEN_MODERN)}
