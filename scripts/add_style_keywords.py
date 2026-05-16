#!/usr/bin/env python3
"""Batch add tags and matching_keywords to all style JSON files."""
import json
import os
import collections

STYLES_DIR = "/Users/luicy/AI/story2/config/styles"

# fmt: off
KEYWORDS_MAP = {
    "absurdist_theatre_novel": {
        "tags": ["荒诞", "戏剧", "存在主义", "西方", "现代", "实验文学"],
        "matching_keywords": {
            "era_hints": ["现代", "当代", "20世纪", "战后", "1950", "1960"],
            "theme_hints": ["荒诞", "存在", "虚无", "循环", "异化", "等待", "无意义", "孤独"],
            "personality_hints": ["迷茫", "荒诞", "冷漠", "疏离", "执拗"],
            "technology_hints": ["现代工业", "城市", "机械"]
        }
    },
    "african_oral_epic": {
        "tags": ["非洲", "口传", "史诗", "部族", "说唱", "神话"],
        "matching_keywords": {
            "era_hints": ["古代", "部族时代", "中世纪", "原始", "远古", "传说时代"],
            "theme_hints": ["祖先", "部族", "英雄", "传承", "自然", "团结", "命运", "勇气"],
            "personality_hints": ["勇敢", "忠诚", "智慧", "坚韧", "虔诚"],
            "technology_hints": ["原始", "手工", "农牧", "铁器"]
        }
    },
    "arabian_nights_frame": {
        "tags": ["阿拉伯", "东方奇幻", "框架叙事", "冒险", "寓言", "中东"],
        "matching_keywords": {
            "era_hints": ["中世纪", "古代", "阿巴斯", "波斯", "阿拉伯", "伊斯兰黄金时代", "古代中东"],
            "theme_hints": ["命运", "智慧", "奇迹", "冒险", "宝藏", "忠诚", "背叛", "寓言"],
            "personality_hints": ["机智", "聪慧", "贪婪", "虔诚", "勇敢", "狡黠"],
            "technology_hints": ["航海", "手工", "商贸", "魔法"]
        }
    },
    "black_humor": {
        "tags": ["黑色幽默", "讽刺", "反战", "荒诞", "西方", "现代"],
        "matching_keywords": {
            "era_hints": ["现代", "当代", "20世纪", "战后", "冷战", "1960"],
            "theme_hints": ["荒诞", "讽刺", "战争", "官僚", "反抗", "死亡", "制度", "疯狂"],
            "personality_hints": ["愤世嫉俗", "叛逆", "幽默", "冷嘲", "清醒", "疯狂"],
            "technology_hints": ["现代工业", "军事", "官僚体制", "城市"]
        }
    },
    "childrens_literature": {
        "tags": ["儿童", "童话", "成长", "奇幻", "温暖", "教育"],
        "matching_keywords": {
            "era_hints": ["任意时代", "现代", "当代", "幻想世界", "童话时代"],
            "theme_hints": ["勇气", "善良", "友谊", "成长", "想象", "冒险", "奇迹"],
            "personality_hints": ["天真", "善良", "勇敢", "好奇", "纯真", "乐观"],
            "technology_hints": ["魔法", "日常", "手工", "简单"]
        }
    },
    "chinese_classic_saga": {
        "tags": ["古代", "中国", "演义", "帝制", "战争", "章回体"],
        "matching_keywords": {
            "era_hints": ["唐", "宋", "明", "清", "古代", "春秋", "战国", "帝制", "王朝", "封建"],
            "theme_hints": ["忠义", "权谋", "战争", "家国", "江山", "天命", "朝廷", "兄弟"],
            "personality_hints": ["忠勇", "豪迈", "义气", "刚正", "智谋", "仁义"],
            "technology_hints": ["冷兵器", "农业", "手工", "骑射"]
        }
    },
    "chinese_domestic_realism": {
        "tags": ["中国", "世情", "家族", "古代", "现实主义", "人情世故"],
        "matching_keywords": {
            "era_hints": ["明", "清", "古代", "封建", "帝制", "王朝", "近代"],
            "theme_hints": ["家族", "人情", "礼教", "兴衰", "婚姻", "权力", "世态炎凉", "女性命运"],
            "personality_hints": ["圆滑", "隐忍", "敏感", "算计", "温婉", "世故"],
            "technology_hints": ["手工", "农业", "纺织", "传统工艺"]
        }
    },
    "chinese_mythic_journey": {
        "tags": ["中国", "神魔", "修仙", "佛道", "降妖", "神话"],
        "matching_keywords": {
            "era_hints": ["远古", "神话时代", "唐", "古代", "三界", "上古", "封神"],
            "theme_hints": ["修行", "降妖", "因果", "天命", "师徒", "轮回", "悟道", "正邪"],
            "personality_hints": ["坚毅", "慈悲", "桀骜", "智慧", "执着", "赤诚"],
            "technology_hints": ["法术", "炼丹", "法器", "阵法"]
        }
    },
    "chinese_wuxia": {
        "tags": ["中国", "武侠", "江湖", "古代", "侠义", "功夫"],
        "matching_keywords": {
            "era_hints": ["唐", "宋", "明", "清", "古代", "江湖", "武林"],
            "theme_hints": ["侠义", "恩仇", "江湖", "门派", "武功", "正邪", "爱情", "家国"],
            "personality_hints": ["侠义", "豪迈", "正义", "洒脱", "仗义", "痴情"],
            "technology_hints": ["冷兵器", "轻功", "内功", "暗器"]
        }
    },
    "classic_whodunit": {
        "tags": ["推理", "古典", "本格", "英国", "逻辑", "密室"],
        "matching_keywords": {
            "era_hints": ["近代", "20世纪初", "维多利亚", "爱德华", "1920", "1930", "英国"],
            "theme_hints": ["谋杀", "推理", "逻辑", "线索", "嫌疑人", "密室", "真相", "正义"],
            "personality_hints": ["理性", "冷静", "观察力", "优雅", "精明", "自负"],
            "technology_hints": ["工业时代", "火车", "电报", "手工"]
        }
    },
    "confessional_novel": {
        "tags": ["自白", "内省", "心理", "现代", "日本", "暗黑"],
        "matching_keywords": {
            "era_hints": ["现代", "当代", "20世纪", "战后", "昭和", "平成"],
            "theme_hints": ["自毁", "羞耻", "孤独", "疯狂", "爱", "痛苦", "面具", "真实"],
            "personality_hints": ["敏感", "自卑", "颓废", "偏执", "脆弱", "真诚"],
            "technology_hints": ["现代都市", "日常", "工业"]
        }
    },
    "cosmic_horror": {
        "tags": ["克苏鲁", "恐怖", "宇宙", "未知", "疯狂", "洛夫克拉夫特"],
        "matching_keywords": {
            "era_hints": ["近代", "1920", "1930", "20世纪", "远古", "史前"],
            "theme_hints": ["未知", "恐惧", "疯狂", "深渊", "远古", "不可名状", "禁忌知识", "宇宙"],
            "personality_hints": ["好奇", "理性", "恐惧", "偏执", "学者", "疯狂"],
            "technology_hints": ["工业时代", "航海", "考古", "科学仪器"]
        }
    },
    "courtroom_drama": {
        "tags": ["法庭", "推理", "法律", "现代", "正义", "辩论"],
        "matching_keywords": {
            "era_hints": ["现代", "当代", "近代", "20世纪", "21世纪"],
            "theme_hints": ["正义", "法律", "辩护", "真相", "证据", "审判", "道德", "权力"],
            "personality_hints": ["雄辩", "理性", "正义", "冷静", "机敏", "执着"],
            "technology_hints": ["现代法律", "取证", "通讯", "城市"]
        }
    },
    "cyberpunk": {
        "tags": ["赛博朋克", "科幻", "未来", "黑客", "反乌托邦", "高科技"],
        "matching_keywords": {
            "era_hints": ["未来", "2050", "2077", "近未来", "赛博", "数字时代"],
            "theme_hints": ["人机融合", "黑客", "企业", "虚拟", "反抗", "身份", "控制", "自由"],
            "personality_hints": ["叛逆", "冷酷", "机敏", "孤僻", "愤世嫉俗", "极客"],
            "technology_hints": ["人工智能", "网络", "机械", "芯片", "虚拟现实", "义体"]
        }
    },
    "epistolary_novel": {
        "tags": ["书信体", "多声部", "浪漫", "欧洲", "私密", "情感"],
        "matching_keywords": {
            "era_hints": ["18世纪", "19世纪", "近代", "维多利亚", "现代", "任意时代"],
            "theme_hints": ["书信", "思念", "误解", "秘密", "等待", "爱情", "真相", "欺骗"],
            "personality_hints": ["深情", "敏感", "多疑", "浪漫", "矛盾", "真诚"],
            "technology_hints": ["书信", "邮政", "手写", "印刷"]
        }
    },
    "everyday_mystery": {
        "tags": ["日常", "推理", "青春", "日本", "温柔", "校园"],
        "matching_keywords": {
            "era_hints": ["现代", "当代", "平成", "令和", "校园", "21世纪"],
            "theme_hints": ["日常", "青春", "友情", "成长", "好奇", "温柔", "秘密", "理解"],
            "personality_hints": ["内敛", "温和", "好奇", "敏感", "善良", "聪慧"],
            "technology_hints": ["现代日常", "校园", "手机", "网络"]
        }
    },
    "existential_absurdist": {
        "tags": ["存在主义", "荒诞", "哲学", "西方", "现代", "冷峻"],
        "matching_keywords": {
            "era_hints": ["现代", "当代", "20世纪", "战后", "1940", "1950", "1960"],
            "theme_hints": ["荒诞", "自由", "虚无", "存在", "反抗", "孤独", "焦虑", "异化"],
            "personality_hints": ["疏离", "冷漠", "理性", "叛逆", "孤独", "清醒"],
            "technology_hints": ["现代工业", "城市", "日常", "机械"]
        }
    },
    "folktale_fairytale": {
        "tags": ["童话", "民间故事", "欧洲", "寓言", "善恶", "魔法"],
        "matching_keywords": {
            "era_hints": ["远古", "中世纪", "传说时代", "不确定", "古代", "童话时代"],
            "theme_hints": ["善恶", "勇气", "魔法", "惩罚", "奖赏", "成长", "智慧", "冒险"],
            "personality_hints": ["善良", "勇敢", "贪婪", "天真", "狡猾", "纯真"],
            "technology_hints": ["魔法", "手工", "农业", "原始"]
        }
    },
    "gothic_horror": {
        "tags": ["哥特", "恐怖", "黑暗", "古堡", "心理", "超自然"],
        "matching_keywords": {
            "era_hints": ["18世纪", "19世纪", "维多利亚", "近代", "中世纪", "爱德华"],
            "theme_hints": ["恐怖", "黑暗", "诅咒", "古堡", "幽灵", "秘密", "疯狂", "罪恶"],
            "personality_hints": ["神经质", "多疑", "敏感", "恐惧", "阴郁", "偏执"],
            "technology_hints": ["蜡烛", "马车", "手工", "煤油灯"]
        }
    },
    "gothic_romance": {
        "tags": ["哥特", "罗曼史", "庄园", "爱情", "悬疑", "女性"],
        "matching_keywords": {
            "era_hints": ["19世纪", "维多利亚", "爱德华", "近代", "18世纪", "摄政时代"],
            "theme_hints": ["爱情", "秘密", "庄园", "危险", "激情", "荒野", "幽灵", "觉醒"],
            "personality_hints": ["敏感", "勇敢", "深情", "神秘", "独立", "执着"],
            "technology_hints": ["马车", "庄园", "手工", "煤油灯"]
        }
    },
    "greek_tragedy": {
        "tags": ["希腊", "悲剧", "命运", "古典", "神话", "英雄"],
        "matching_keywords": {
            "era_hints": ["古希腊", "古代", "雅典", "城邦", "神话时代", "英雄时代"],
            "theme_hints": ["命运", "悲剧", "傲慢", "净化", "神谕", "复仇", "正义", "牺牲"],
            "personality_hints": ["高傲", "刚愎", "英勇", "悲壮", "执拗", "崇高"],
            "technology_hints": ["冷兵器", "航海", "农业", "城邦"]
        }
    },
    "hardboiled_detective": {
        "tags": ["硬汉", "侦探", "犯罪", "美国", "黑色", "城市"],
        "matching_keywords": {
            "era_hints": ["1930", "1940", "1950", "近代", "20世纪", "美国", "禁酒令"],
            "theme_hints": ["犯罪", "腐败", "正义", "城市", "孤独", "真相", "暴力", "道德"],
            "personality_hints": ["冷峻", "愤世嫉俗", "坚韧", "孤独", "正义", "硬汉"],
            "technology_hints": ["手枪", "汽车", "电话", "城市工业"]
        }
    },
    "historical_romance": {
        "tags": ["历史", "演义", "宫廷", "权谋", "中国", "帝王"],
        "matching_keywords": {
            "era_hints": ["秦", "汉", "唐", "宋", "明", "清", "古代", "帝制", "王朝", "近代"],
            "theme_hints": ["权力", "忠诚", "背叛", "战争", "变革", "宫廷", "英雄", "文明"],
            "personality_hints": ["雄才", "隐忍", "果断", "智谋", "忠义", "孤独"],
            "technology_hints": ["冷兵器", "农业", "手工", "水利", "印刷"]
        }
    },
    "indian_epic_myth": {
        "tags": ["印度", "史诗", "神话", "哲学", "轮回", "宗教"],
        "matching_keywords": {
            "era_hints": ["远古", "印度古代", "吠陀时代", "神话时代", "古代"],
            "theme_hints": ["法", "业", "轮回", "神性", "战争", "命运", "道德", "宇宙"],
            "personality_hints": ["虔诚", "刚毅", "智慧", "慈悲", "矛盾", "英勇"],
            "technology_hints": ["冷兵器", "战车", "农业", "手工"]
        }
    },
    "inverted_detective": {
        "tags": ["倒叙", "推理", "心理", "犯罪", "猫鼠游戏", "悬疑"],
        "matching_keywords": {
            "era_hints": ["现代", "当代", "20世纪", "近代", "21世纪"],
            "theme_hints": ["犯罪", "完美计划", "破绽", "心理", "博弈", "正义", "傲慢", "细节"],
            "personality_hints": ["冷静", "自负", "耐心", "精明", "执着", "观察力"],
            "technology_hints": ["现代", "取证", "通讯", "城市"]
        }
    },
    "japanese_honkaku": {
        "tags": ["日本", "本格", "推理", "密室", "诡计", "和风"],
        "matching_keywords": {
            "era_hints": ["大正", "昭和", "近代", "20世纪", "日本", "战前"],
            "theme_hints": ["密室", "诡计", "逻辑", "不可能犯罪", "名侦探", "怪奇", "推理"],
            "personality_hints": ["理性", "怪癖", "执着", "天才", "冷静", "孤僻"],
            "technology_hints": ["机关", "建筑", "铁路", "手工"]
        }
    },
    "japanese_monogatari": {
        "tags": ["日本", "物语", "平安", "古典", "物哀", "雅致"],
        "matching_keywords": {
            "era_hints": ["平安", "奈良", "古代日本", "源氏", "王朝", "中古"],
            "theme_hints": ["物哀", "无常", "爱情", "季节", "别离", "礼仪", "幽玄", "美"],
            "personality_hints": ["温柔", "哀婉", "含蓄", "多情", "优雅", "敏感"],
            "technology_hints": ["和纸", "手工", "宫廷", "书法"]
        }
    },
    "japanese_shakaiha": {
        "tags": ["日本", "社会派", "推理", "现实", "批判", "纪实"],
        "matching_keywords": {
            "era_hints": ["昭和", "平成", "战后", "现代", "20世纪", "当代日本"],
            "theme_hints": ["社会", "不公", "腐败", "底层", "犯罪", "制度", "权力", "绝望"],
            "personality_hints": ["隐忍", "绝望", "正直", "同情", "执着", "愤怒"],
            "technology_hints": ["现代工业", "铁路", "城市", "通讯"]
        }
    },
    "low_fantasy_grimdark": {
        "tags": ["低魔", "黑暗", "奇幻", "反英雄", "战争", "残酷"],
        "matching_keywords": {
            "era_hints": ["中世纪", "封建", "古代", "黑暗时代", "虚构世界"],
            "theme_hints": ["战争", "道德灰色", "权力", "生存", "暴力", "背叛", "讽刺"],
            "personality_hints": ["玩世不恭", "冷酷", "坚韧", "自私", "矛盾", "务实"],
            "technology_hints": ["冷兵器", "攻城", "低魔法", "手工"]
        }
    },
    "magical_realism": {
        "tags": ["魔幻现实", "拉美", "家族", "循环", "文学", "超自然"],
        "matching_keywords": {
            "era_hints": ["近代", "19世纪", "20世纪", "拉美", "殖民", "独立", "百年"],
            "theme_hints": ["家族", "孤独", "循环", "记忆", "遗忘", "魔幻", "历史", "命运"],
            "personality_hints": ["孤独", "执念", "热情", "宿命", "疯狂", "深沉"],
            "technology_hints": ["农业", "手工", "殖民工业", "铁路"]
        }
    },
    "minimalist_fiction": {
        "tags": ["极简", "现实主义", "美国", "留白", "冰山", "日常"],
        "matching_keywords": {
            "era_hints": ["现代", "当代", "20世纪", "美国", "战后", "1970", "1980"],
            "theme_hints": ["孤独", "沉默", "日常", "绝望", "沟通", "平凡", "隐忍", "爱"],
            "personality_hints": ["沉默", "内敛", "笨拙", "隐忍", "孤独", "朴实"],
            "technology_hints": ["日常", "汽车", "工厂", "城镇"]
        }
    },
    "murakami_magical_daily": {
        "tags": ["村上春树", "日本", "超现实", "孤独", "都市", "爵士"],
        "matching_keywords": {
            "era_hints": ["昭和", "平成", "现代", "当代", "1980", "1990", "日本"],
            "theme_hints": ["孤独", "失去", "寻找", "异界", "日常", "记忆", "音乐", "猫"],
            "personality_hints": ["疏离", "温和", "孤独", "内省", "慵懒", "敏感"],
            "technology_hints": ["现代都市", "唱片", "家电", "日常"]
        }
    },
    "naturalism": {
        "tags": ["自然主义", "现实", "底层", "西方", "社会", "科学"],
        "matching_keywords": {
            "era_hints": ["19世纪", "工业革命", "近代", "维多利亚", "镀金时代", "20世纪初"],
            "theme_hints": ["环境", "遗传", "贫穷", "堕落", "社会", "生存", "资本", "命运"],
            "personality_hints": ["卑微", "挣扎", "欲望", "绝望", "麻木", "顽强"],
            "technology_hints": ["工厂", "矿山", "蒸汽机", "铁路", "工业"]
        }
    },
    "neo_honkaku": {
        "tags": ["日本", "新本格", "推理", "叙述诡计", "后现代", "实验"],
        "matching_keywords": {
            "era_hints": ["平成", "令和", "现代", "当代", "1980", "1990", "2000"],
            "theme_hints": ["诡计", "叙述", "元推理", "建筑", "虚构", "逻辑", "文本", "谜题"],
            "personality_hints": ["理性", "偏执", "天才", "怪癖", "多疑", "敏锐"],
            "technology_hints": ["现代建筑", "通讯", "日常", "城市"]
        }
    },
    "new_wave_scifi": {
        "tags": ["新浪潮", "科幻", "内空间", "文学", "心理", "实验"],
        "matching_keywords": {
            "era_hints": ["近未来", "未来", "20世纪", "当代", "1960", "1970"],
            "theme_hints": ["内空间", "心理", "社会", "性别", "权力", "语言", "熵", "认知"],
            "personality_hints": ["内省", "理性", "敏感", "叛逆", "思辨", "孤独"],
            "technology_hints": ["生物技术", "心理学", "社会工程", "信息"]
        }
    },
    "nonfiction_novel": {
        "tags": ["非虚构", "纪实", "文学", "新闻", "现代", "真实"],
        "matching_keywords": {
            "era_hints": ["现代", "当代", "20世纪", "21世纪", "近代"],
            "theme_hints": ["真实", "正义", "暴力", "社会", "制度", "人性", "历史", "真相"],
            "personality_hints": ["冷静", "正直", "勇敢", "执着", "理性", "同情"],
            "technology_hints": ["现代", "新闻", "通讯", "交通"]
        }
    },
    "norse_saga": {
        "tags": ["北欧", "萨迦", "维京", "命运", "史诗", "神话"],
        "matching_keywords": {
            "era_hints": ["维京时代", "中世纪", "北欧", "冰岛", "古代", "黑暗时代"],
            "theme_hints": ["命运", "荣誉", "血仇", "勇气", "诸神黄昏", "英雄", "毁灭", "轮回"],
            "personality_hints": ["刚毅", "冷峻", "勇猛", "忠诚", "悲壮", "坚韧"],
            "technology_hints": ["冷兵器", "航海", "长船", "铁匠"]
        }
    },
    "police_procedural": {
        "tags": ["警察", "程序", "推理", "现代", "团队", "纪实"],
        "matching_keywords": {
            "era_hints": ["现代", "当代", "20世纪", "21世纪", "美国", "都市"],
            "theme_hints": ["正义", "程序", "团队", "犯罪", "调查", "制度", "社会", "坚守"],
            "personality_hints": ["务实", "坚韧", "正直", "合作", "耐心", "执着"],
            "technology_hints": ["现代取证", "枪械", "通讯", "数据库", "监控"]
        }
    },
    "postmodern_metafiction": {
        "tags": ["后现代", "元小说", "实验", "解构", "文本游戏", "西方"],
        "matching_keywords": {
            "era_hints": ["现代", "当代", "20世纪", "1960", "1970", "1980", "后现代"],
            "theme_hints": ["自我指涉", "解构", "符号", "虚构", "文本", "身份", "碎片", "游戏"],
            "personality_hints": ["智性", "叛逆", "自觉", "矛盾", "幽默", "怀疑"],
            "technology_hints": ["印刷", "媒体", "城市", "信息"]
        }
    },
    "psychological_suspense": {
        "tags": ["心理", "悬疑", "暗黑", "女性", "现代", "不可靠叙述"],
        "matching_keywords": {
            "era_hints": ["现代", "当代", "21世纪", "都市", "郊区"],
            "theme_hints": ["操控", "谎言", "亲密关系", "背叛", "记忆", "愤怒", "秘密", "真相"],
            "personality_hints": ["多疑", "敏感", "内向", "焦虑", "偏执", "控制欲"],
            "technology_hints": ["现代都市", "手机", "社交媒体", "监控"]
        }
    },
    "romantic_legend": {
        "tags": ["浪漫主义", "传奇", "冒险", "欧洲", "理想", "激情"],
        "matching_keywords": {
            "era_hints": ["18世纪", "19世纪", "法国大革命", "拿破仑", "近代", "浪漫主义时代"],
            "theme_hints": ["爱情", "自由", "复仇", "正义", "冒险", "牺牲", "荣誉", "激情"],
            "personality_hints": ["热情", "勇敢", "浪漫", "正义", "深情", "豪迈"],
            "technology_hints": ["剑术", "航海", "马车", "火药", "城堡"]
        }
    },
    "russian_psychological_realism": {
        "tags": ["俄国", "心理", "现实主义", "灵魂", "哲学", "厚重"],
        "matching_keywords": {
            "era_hints": ["19世纪", "沙俄", "帝俄", "农奴制", "1860", "1880", "近代俄国"],
            "theme_hints": ["灵魂", "善恶", "苦难", "救赎", "罪", "信仰", "社会", "道德"],
            "personality_hints": ["矛盾", "痛苦", "深沉", "偏执", "悲悯", "极端"],
            "technology_hints": ["马车", "铁路", "农业", "手工"]
        }
    },
    "scifi_space_opera": {
        "tags": ["科幻", "太空歌剧", "星际", "帝国", "宏大", "未来"],
        "matching_keywords": {
            "era_hints": ["未来", "远未来", "星际时代", "银河纪元", "数千年后"],
            "theme_hints": ["星际", "宇宙", "外星", "银河", "太空", "星球", "文明", "帝国"],
            "personality_hints": ["理性", "果断", "远见", "孤独", "坚韧", "智慧"],
            "technology_hints": ["跃迁引擎", "激光", "人工智能", "量子", "太空站", "能量盾"]
        }
    },
    "southern_gothic": {
        "tags": ["南方哥特", "美国", "怪诞", "种族", "衰败", "宗教"],
        "matching_keywords": {
            "era_hints": ["美国南方", "内战后", "19世纪", "20世纪", "种植园", "近代美国"],
            "theme_hints": ["种族", "创伤", "衰败", "怪诞", "暴力", "恩典", "历史", "罪恶"],
            "personality_hints": ["怪异", "偏执", "虔诚", "疯狂", "固执", "扭曲"],
            "technology_hints": ["农业", "种植园", "马车", "手工"]
        }
    },
    "special_setting_mystery": {
        "tags": ["设定系", "推理", "超现实", "日本", "规则", "实验"],
        "matching_keywords": {
            "era_hints": ["任意时代", "虚构世界", "平行世界", "现代", "未来"],
            "theme_hints": ["规则", "逻辑", "超能力", "设定", "谜题", "人性", "实验", "推理"],
            "personality_hints": ["理性", "冷静", "好奇", "果断", "适应力", "聪慧"],
            "technology_hints": ["超自然", "特殊规则", "现代", "虚构科技"]
        }
    },
    "steampunk_romance": {
        "tags": ["蒸汽朋克", "维多利亚", "冒险", "发明", "复古未来", "齿轮"],
        "matching_keywords": {
            "era_hints": ["维多利亚", "19世纪", "工业革命", "蒸汽时代", "爱德华"],
            "theme_hints": ["发明", "冒险", "阶级", "自由", "帝国", "科技", "齿轮", "飞艇"],
            "personality_hints": ["冒险", "创造力", "绅士", "叛逆", "浪漫", "好奇"],
            "technology_hints": ["蒸汽", "齿轮", "发条", "维多利亚", "飞艇", "机械"]
        }
    },
    "stream_of_consciousness": {
        "tags": ["意识流", "现代主义", "心理", "文学", "实验", "内省"],
        "matching_keywords": {
            "era_hints": ["现代", "20世纪", "1920", "1930", "战间期", "现代主义"],
            "theme_hints": ["意识", "时间", "记忆", "瞬间", "自我", "感官", "联想", "永恒"],
            "personality_hints": ["敏感", "内省", "多情", "孤独", "细腻", "流动"],
            "technology_hints": ["现代都市", "日常", "工业", "城市"]
        }
    },
    "surrealist_novel": {
        "tags": ["超现实", "梦境", "无意识", "前卫", "西方", "实验"],
        "matching_keywords": {
            "era_hints": ["现代", "20世纪", "1920", "1930", "战间期", "超现实主义"],
            "theme_hints": ["梦境", "无意识", "欲望", "现实", "理性", "偶然", "颠覆", "幻觉"],
            "personality_hints": ["疯狂", "直觉", "反叛", "自由", "敏感", "幻想"],
            "technology_hints": ["现代", "艺术", "城市", "工业"]
        }
    },
    "western_epic_fantasy": {
        "tags": ["西方", "史诗奇幻", "中世纪", "魔法", "善恶", "英雄"],
        "matching_keywords": {
            "era_hints": ["中世纪", "封建", "虚构世界", "古代", "第二世界", "奇幻纪元"],
            "theme_hints": ["善恶", "魔法", "英雄", "牺牲", "权力", "命运", "冒险", "救赎"],
            "personality_hints": ["勇敢", "正义", "忠诚", "坚韧", "智慧", "善良"],
            "technology_hints": ["冷兵器", "魔法", "手工", "城堡", "铁匠"]
        }
    },
    "zhang_ailing_urban_desolation": {
        "tags": ["张爱玲", "都市", "苍凉", "民国", "女性", "上海"],
        "matching_keywords": {
            "era_hints": ["民国", "上海", "1930", "1940", "近代", "租界", "沦陷"],
            "theme_hints": ["苍凉", "爱情", "幻灭", "世俗", "女性", "算计", "繁华", "孤独"],
            "personality_hints": ["敏感", "世故", "苍凉", "精明", "矛盾", "清醒"],
            "technology_hints": ["旗袍", "电车", "洋房", "广播"]
        }
    },
}
# fmt: on


def process_file(filepath: str, style_id: str, kw_data: dict):
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f, object_pairs_hook=collections.OrderedDict)

    # Already has tags? Skip
    if "tags" in data and "matching_keywords" in data:
        print(f"  SKIP (already has tags): {os.path.basename(filepath)}")
        return

    # Build new ordered dict with tags inserted after style_name
    new_data = collections.OrderedDict()
    for key, value in data.items():
        new_data[key] = value
        if key == "style_name":
            new_data["tags"] = kw_data["tags"]
            new_data["matching_keywords"] = kw_data["matching_keywords"]

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(new_data, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print(f"  OK: {os.path.basename(filepath)}")


def main():
    files = sorted(f for f in os.listdir(STYLES_DIR) if f.endswith(".style.json"))
    print(f"Found {len(files)} style files\n")

    processed = 0
    missing = []
    for fname in files:
        style_id = fname.replace(".style.json", "")
        filepath = os.path.join(STYLES_DIR, fname)
        if style_id in KEYWORDS_MAP:
            process_file(filepath, style_id, KEYWORDS_MAP[style_id])
            processed += 1
        else:
            missing.append(style_id)
            print(f"  MISSING mapping: {style_id}")

    print(f"\nProcessed: {processed}/{len(files)}")
    if missing:
        print(f"Missing mappings: {missing}")


if __name__ == "__main__":
    main()
