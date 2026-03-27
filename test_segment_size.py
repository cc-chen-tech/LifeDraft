#!/usr/bin/env python3
"""
测试实体识别分段大小，找到 DeepSeek API 不会超时的最佳阈值。

测试范围：2000 - 15000 字符
超时阈值：5 分钟（300秒）
"""

import time
import sys
from typing import List, Dict, Any

# 添加项目路径
sys.path.insert(0, '/Users/luicy/story2')

from src.ai.client import AIClient
from src.services.entity_recognition_service import EntityRecognitionService
from config.prompts.entity_recognition_prompt import get_segment_recognition_prompt


def generate_test_story(target_chars: int) -> str:
    """生成指定长度的测试故事文本。"""
    # 使用一个基础故事模板，重复直到达到目标长度
    base_story = """
=== 第1周 周一 ===

清晨的阳光透过落地窗洒进陈美美的办公室。她刚刚完成了体感服原型的最终测试，准备向董事会展示。

"系统，调出昨晚的测试数据。"陈美美对着空气说道。

全息投影在她面前展开，显示着昨晚在元宇宙接入舱的完整记录。数据很漂亮：延迟降低了40%，舒适度提升了35%。

手机突然震动。是父亲陈建国发来的消息："董事会提前到上午十点，王董和张董都会来。准备充分点。"

陈美美深吸一口气。这不仅是一次产品展示，更是她在父亲面前证明自己的机会。

她拿起桌上的生物监测环，这是体感服的核心组件之一。过去三个月，她和团队在这个小小的环上投入了无数心血。

"小美，"助理敲门进来，"林浩宇先生在会客室等您。他说有重要的事情。"

陈美美皱眉。林浩宇是她大学时的学长，现在是一家投资公司的合伙人。他这个时候来，肯定不是为了叙旧。

会客室里，林浩宇正站在窗前，看着楼下的车水马龙。听到脚步声，他转过身，脸上带着陈美美熟悉的温和笑容。

"好久不见，小美。"

"学长，你怎么来了？"

"听说你今天要去陈氏集团董事会？"林浩宇直截了当，"我代表星辰投资，对你的体感服项目很感兴趣。"

陈美美心中一动。星辰投资是业内顶尖的风投机构，如果能得到他们的支持...

"但有个条件，"林浩宇继续说，"我们要在董事会之前，看到完整的商业计划书和技术白皮书。"

"现在？"陈美美看了眼手表，"离董事会只有两个小时了。"

"所以我说这是重要的事情。"林浩宇递给她一份文件，"这是我们的意向书。如果你能在董事会前准备好材料，我们可以当场签约。"

陈美美接过文件，快速浏览了一遍。条件很优厚，但时间确实太紧了。

"我需要考虑一下。"

"当然，"林浩宇看了看表，"你有三十分钟。我在楼下咖啡厅等你。"

林浩宇离开后，陈美美陷入沉思。这是一个机会，但也是一个巨大的挑战。她必须在两小时内完成原本需要两天的工作。

她拿起手机，拨通了苏晓雅的电话。

"晓雅，紧急任务。我需要你在两小时内帮我完成商业计划书的技术部分..."

电话那头，苏晓雅沉默了几秒："你疯了？但...好吧，把资料发给我。"

陈美美露出笑容。这就是她的团队，永远在最需要的时候支持她。

她看向窗外的城市天际线，上海中心大厦在阳光下闪闪发光。那是陈氏集团的总部，也是她今天必须征服的战场。

"系统，启动紧急工作模式。所有通知静音，直到我手动解除。"

"已启动紧急工作模式。"

陈美美坐到电脑前，开始了一场与时间的赛跑。

=== 第1周 周中 ===

董事会会议室里，气氛凝重。

陈美美站在投影屏前，看着台下十二位董事。父亲陈建国坐在主位，表情严肃。王董和张董分列两侧，目光中带着审视。

"各位董事，"陈美美开口，声音平稳，"今天我要向大家展示的，不仅仅是一款新产品，而是陈氏集团未来的战略方向。"

她按下遥控器，全息投影展开，显示出体感服的完整设计图。

"我们的体感服采用了革命性的记忆纤维材料，配合生物监测环，可以实现真正的沉浸式元宇宙体验。"

王董举手打断她："陈小姐，我看过你们的技术报告。但我要问的是，市场在哪里？"

"游戏市场，"陈美美回答，"全球元宇宙游戏市场规模预计将在五年内达到5000亿美元。我们的体感服正是这个市场的核心入口。"

"竞争对手呢？"张董问道，"据我所知，至少有三家大公司正在开发类似产品。"

"是的，"陈美美点头，"但我们有三大优势。第一，技术领先..."

她详细解释了体感服的技术优势，包括延迟降低40%、舒适度提升35%等关键数据。

"第二，成本优势。我们的生产工艺可以将成本控制在竞争对手的60%。"

"第三，"陈美美停顿了一下，看向父亲，"我们有陈氏集团的品牌和渠道支持。"

会议室里一片寂静。陈建国面无表情，但陈美美注意到他微微点了点头。

"我还有一个消息要宣布，"陈美美继续说，"星辰投资已经向我们发出了投资意向书。他们愿意以5亿美元估值，投资1亿美元。"

这句话引起了轰动。星辰投资的名字在业界就是金字招牌。

"这是真的？"王董惊讶地问。

"意向书在这里，"陈美美举起手中的文件，"只要董事会批准，我们可以立即签约。"

陈建国终于开口了："各位，我们需要讨论一下。美美，你先出去等一下。"

陈美美退出会议室，靠在墙上，长出一口气。她已经做了所有能做的，现在只能等待。

十分钟后，门开了。陈建国走出来，脸上带着罕见的笑容。

"恭喜你，项目通过了。董事会全票同意。"

陈美美眼眶一热。三个月的努力，终于得到了回报。

"但有个条件，"陈建国继续说，"你要在三个月内完成量产准备。王董会负责监督。"

"我明白。"

"还有，"陈建国顿了顿，"林浩宇在楼下等你。他说要庆祝一下。"

陈美美笑了。这一天的挑战，终于画上了圆满的句号。

=== 第1周 周末 ===

周六晚上，陈美美站在周雨薇工作室的门口，手里提着一瓶红酒。

门开了，周雨薇穿着宽松的毛衣，头发随意地扎着，一副艺术家的慵懒模样。

"哟，大忙人终于来了，"周雨薇笑着接过红酒，"董事会怎么样？"

"通过了，"陈美美走进工作室，"全票。"

"我就知道你能行！"周雨薇拥抱了她，"来，看看我为你准备的惊喜。"

工作室中央，一个穿着体感服的人体模型静静地站立着。但与之前不同的是，这套体感服上多了许多精致的装饰——刺绣、珠片、还有流光溢彩的纤维。

"这是..."

"我设计的限量版，"周雨薇得意地说，"既然你要进军时尚圈，那就要有时尚的样子。"

陈美美走近细看。这些装饰不仅美观，还巧妙地隐藏了体感服的技术组件。生物监测环被设计成手镯的样子，连接线变成了装饰链条。

"太美了，"陈美美由衷地赞叹，"这完全改变了体感服的形象。"

"不只是形象，"周雨薇说，"我还重新设计了材料结构。现在的透气性提升了50%，重量减轻了30%。"

陈美美惊讶地看着她："你怎么做到的？"

"秘密，"周雨薇眨眨眼，"但我可以告诉你，这用了我最新研发的智能纤维。"

两人坐在工作室的沙发上，打开红酒，开始讨论合作细节。

"我需要一个完整的时尚系列，"陈美美说，"不只是体感服，还有配套的服饰、配饰。"

"没问题，"周雨薇说，"但我有个条件。"

"什么条件？"

"我要成为这个系列的联合设计师，名字要并排出现在所有产品上。"

陈美美想了想，点头同意："成交。"

她们举杯相庆。两个从小一起长大的女孩，终于要一起创造属于她们的时代了。

"对了，"周雨薇突然说，"我听说林浩宇投资了你们？"

陈美美点头："1亿美元。"

"他对你还是有意思啊，"周雨薇意味深长地笑了，"大学时他就追过你，现在又来这一套。"

"别瞎说，"陈美美脸微红，"这是纯粹的商业投资。"

"是吗？"周雨薇挑眉，"那他为什么特意在董事会前出现，还给你那么优厚的条件？"

陈美美没有回答。她知道周雨薇说得有道理，但现在她只想专注于事业。

"不管怎样，"她说，"这是我们新的开始。"

"对，"周雨薇举杯，"为了新的开始。"

窗外，上海的夜景璀璨如星。两个女孩的梦想，正在这片星空下慢慢绽放。
"""
    
    # 计算需要重复多少次
    repeat_count = max(1, target_chars // len(base_story))
    result = base_story * repeat_count
    
    # 如果还不够，再添加一些内容
    while len(result) < target_chars:
        result += "\n\n（故事继续...）\n\n" + base_story[:min(500, target_chars - len(result))]
    
    return result[:target_chars]


def test_segment_size(segment_size: int, ai_client: AIClient) -> Dict[str, Any]:
    """测试指定分段大小的处理时间。"""
    print(f"\n{'='*60}")
    print(f"测试分段大小: {segment_size} 字符")
    print(f"{'='*60}")
    
    # 生成测试故事
    story_text = generate_test_story(segment_size)
    print(f"实际生成文本: {len(story_text)} 字符")
    
    # 构建测试用的 round_history
    round_history = [
        {
            "week": 1,
            "round": 0,
            "event_description": story_text[:len(story_text)//3],
            "story_continuation": ""
        },
        {
            "week": 1, 
            "round": 1,
            "event_description": story_text[len(story_text)//3:2*len(story_text)//3],
            "story_continuation": ""
        },
        {
            "week": 1,
            "round": 2, 
            "event_description": story_text[2*len(story_text)//3:],
            "story_continuation": ""
        }
    ]
    
    # 创建识别服务
    service = EntityRecognitionService(ai_client)
    
    # 记录开始时间
    start_time = time.time()
    
    try:
        # 执行识别
        result = service.recognize_from_history(
            round_history=round_history,
            existing_items=[],
            existing_characters=[],
            existing_landmarks=[],
            min_appearances=2,
            language="zh"
        )
        
        elapsed_time = time.time() - start_time
        
        print(f"✅ 成功! 耗时: {elapsed_time:.2f} 秒")
        print(f"识别结果:")
        print(f"  - 物品: {len(result.get('items', []))} 个")
        print(f"  - 人物: {len(result.get('characters', []))} 个")
        print(f"  - 地点: {len(result.get('landmarks', []))} 个")
        
        return {
            "size": segment_size,
            "success": True,
            "time": elapsed_time,
            "items": len(result.get('items', [])),
            "characters": len(result.get('characters', [])),
            "landmarks": len(result.get('landmarks', []))
        }
        
    except Exception as e:
        elapsed_time = time.time() - start_time
        print(f"❌ 失败! 耗时: {elapsed_time:.2f} 秒")
        print(f"错误: {type(e).__name__}: {e}")
        
        return {
            "size": segment_size,
            "success": False,
            "time": elapsed_time,
            "error": str(e)
        }


def main():
    """主测试函数。"""
    print("="*60)
    print("实体识别分段大小测试")
    print("="*60)
    print("\n测试目标: 找到 DeepSeek API 不会超时的最佳分段大小")
    print("超时阈值: 300 秒 (5 分钟)")
    print("\n")
    
    # 创建 AI 客户端
    print("初始化 AI 客户端...")
    ai_client = AIClient()
    print("✅ 初始化完成\n")
    
    # 测试的分段大小（从大到小测试，避免小测试通过但大测试失败的情况）
    test_sizes = [15000, 12000, 10000, 8000, 6000, 5000, 4000, 3000, 2000]
    
    results = []
    
    for size in test_sizes:
        result = test_segment_size(size, ai_client)
        results.append(result)
        
        # 如果成功且时间小于 60 秒，记录为最佳候选
        if result["success"] and result["time"] < 60:
            print(f"\n🎯 找到合适的大小: {size} 字符 (耗时 {result['time']:.2f} 秒)")
            # 继续测试更小的，找到最佳平衡点
    
    # 输出总结
    print("\n" + "="*60)
    print("测试结果总结")
    print("="*60)
    
    print(f"\n{'大小':<10} {'状态':<10} {'耗时(秒)':<12} {'物品':<8} {'人物':<8} {'地点':<8}")
    print("-"*60)
    
    for r in results:
        status = "✅ 成功" if r["success"] else "❌ 失败"
        time_str = f"{r['time']:.2f}" if r["success"] else f"{r['time']:.2f}"
        items = str(r.get("items", "-"))
        chars = str(r.get("characters", "-"))
        lands = str(r.get("landmarks", "-"))
        print(f"{r['size']:<10} {status:<10} {time_str:<12} {items:<8} {chars:<8} {lands:<8}")
    
    # 推荐值
    successful = [r for r in results if r["success"]]
    if successful:
        # 找最大的成功值
        best = max(successful, key=lambda x: x["size"])
        print(f"\n✨ 推荐分段大小: {best['size']} 字符")
        print(f"   平均耗时: {best['time']:.2f} 秒")
        print(f"   识别质量: {best['items']} 物品, {best['characters']} 人物, {best['landmarks']} 地点")
    else:
        print("\n⚠️ 所有测试都失败了，建议检查 API 连接或降低分段大小到 2000 以下")
    
    print("\n" + "="*60)


if __name__ == "__main__":
    main()
