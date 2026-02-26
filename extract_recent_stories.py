#!/usr/bin/env python3
"""从数据库提取最近生成的故事文本，写入txt文件"""
import sys
sys.path.insert(0, '/Users/luicy/story2')

from datetime import datetime
from src.database.models import SessionLocal, Decision, Game

def extract_recent_stories(output_file: str = "recent_stories.txt", limit: int = 50):
    """
    提取最近生成的故事文本
    
    Args:
        output_file: 输出文件名
        limit: 最大提取数量
    """
    db = SessionLocal()
    try:
        # 查询最近的决策记录，按创建时间倒序
        decisions = db.query(Decision).order_by(Decision.created_at.desc()).limit(limit).all()
        
        if not decisions:
            print("数据库中没有找到任何故事记录")
            return
        
        # 按游戏ID分组，获取每个游戏的基本信息
        game_ids = list(set(d.game_id for d in decisions))
        games = db.query(Game).filter(Game.game_id.in_(game_ids)).all()
        game_map = {g.game_id: g for g in games}
        
        # 按周数正序排列（时间顺序）
        decisions_sorted = sorted(decisions, key=lambda d: (d.game_id, d.week))
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write("=" * 80 + "\n")
            f.write("最近生成的故事文本\n")
            f.write(f"提取时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"总计: {len(decisions)} 条记录\n")
            f.write("=" * 80 + "\n\n")
            
            current_game_id = None
            for d in decisions_sorted:
                # 游戏分隔
                if d.game_id != current_game_id:
                    if current_game_id is not None:
                        f.write("\n" + "=" * 80 + "\n\n")
                    current_game_id = d.game_id
                    game = game_map.get(d.game_id)
                    if game:
                        f.write(f"【游戏 ID: {d.game_id}】\n")
                        f.write(f"创建时间: {game.created_at}\n")
                        f.write(f"最后更新: {game.updated_at}\n")
                        f.write("-" * 40 + "\n\n")
                
                # 写入故事内容
                f.write(f"【第 {d.week} 周】\n")
                f.write(f"时间: {d.created_at}\n\n")
                
                # 故事文本
                story_text = d.event_description or "(无故事内容)"
                f.write(f"{story_text}\n\n")
                
                # 玩家选择
                if d.choice_text:
                    f.write(f"→ 玩家选择: {d.choice_text}\n")
                
                # 效果（如果有）
                if d.effects:
                    f.write(f"→ 效果: {d.effects}\n")
                
                f.write("\n" + "-" * 40 + "\n\n")
        
        print(f"✅ 成功提取 {len(decisions)} 条故事记录到: {output_file}")
        
    finally:
        db.close()

if __name__ == "__main__":
    extract_recent_stories()
