#!/usr/bin/env python3
"""
测试 DeepSeek API 并发能力
测试不同并发数下的成功率和响应时间
"""

import time
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List
import statistics

sys.path.insert(0, '/Users/luicy/story2')

from src.ai.client import AIClient


def make_api_call(client: AIClient, call_id: int, prompt_length: int = 1000) -> Dict:
    """执行一次 API 调用。"""
    start_time = time.time()
    
    # 生成测试 prompt
    prompt = "请分析以下故事中的实体（人物、物品、地点）：\n\n"
    prompt += "这是一个测试故事。" * (prompt_length // 10)
    
    try:
        response = client.call(
            system_prompt="你是一个实体识别助手。请识别故事中的关键实体。",
            user_prompt=prompt[:prompt_length],
            temperature=0.5,
            max_tokens=500,
        )
        
        elapsed = time.time() - start_time
        return {
            "call_id": call_id,
            "success": True,
            "time": elapsed,
            "response_length": len(response),
        }
    except Exception as e:
        elapsed = time.time() - start_time
        return {
            "call_id": call_id,
            "success": False,
            "time": elapsed,
            "error": type(e).__name__,
            "error_msg": str(e)[:100],
        }


def test_concurrency(concurrent_calls: int, prompt_length: int = 1000) -> Dict:
    """测试指定并发数的 API 调用。"""
    print(f"\n{'='*60}")
    print(f"测试并发数: {concurrent_calls}")
    print(f"Prompt 长度: {prompt_length} 字符")
    print(f"{'='*60}")
    
    client = AIClient()
    results = []
    
    start_time = time.time()
    
    # 使用线程池执行并发调用
    with ThreadPoolExecutor(max_workers=concurrent_calls) as executor:
        futures = [
            executor.submit(make_api_call, client, i, prompt_length)
            for i in range(concurrent_calls)
        ]
        
        for future in as_completed(futures):
            result = future.result()
            results.append(result)
            status = "✅" if result["success"] else "❌"
            print(f"  {status} 调用 {result['call_id']}: {result['time']:.2f}s")
    
    total_time = time.time() - start_time
    
    # 统计结果
    success_results = [r for r in results if r["success"]]
    failed_results = [r for r in results if not r["success"]]
    
    success_times = [r["time"] for r in success_results]
    
    print(f"\n结果统计:")
    print(f"  总耗时: {total_time:.2f}s")
    print(f"  成功: {len(success_results)}/{concurrent_calls} ({len(success_results)*100//concurrent_calls}%)")
    print(f"  失败: {len(failed_results)}/{concurrent_calls}")
    
    if success_times:
        print(f"\n成功调用耗时统计:")
        print(f"  平均: {statistics.mean(success_times):.2f}s")
        print(f"  最小: {min(success_times):.2f}s")
        print(f"  最大: {max(success_times):.2f}s")
        if len(success_times) > 1:
            print(f"  标准差: {statistics.stdev(success_times):.2f}s")
    
    if failed_results:
        print(f"\n失败原因:")
        error_counts = {}
        for r in failed_results:
            error_type = r.get("error", "Unknown")
            error_counts[error_type] = error_counts.get(error_type, 0) + 1
        for error_type, count in error_counts.items():
            print(f"  - {error_type}: {count} 次")
    
    return {
        "concurrent": concurrent_calls,
        "success_rate": len(success_results) / concurrent_calls,
        "avg_time": statistics.mean(success_times) if success_times else 0,
        "total_time": total_time,
    }


def main():
    """主测试函数。"""
    print("="*60)
    print("DeepSeek API 并发测试")
    print("="*60)
    
    # 测试不同的并发数
    test_cases = [
        (1, 1000),    # 1个并发，短文本
        (2, 1000),    # 2个并发
        (3, 1000),    # 3个并发
        (5, 1000),    # 5个并发
        (1, 5000),    # 1个并发，中等文本
        (2, 5000),    # 2个并发，中等文本
        (1, 10000),   # 1个并发，长文本
    ]
    
    all_results = []
    
    for concurrent, prompt_len in test_cases:
        result = test_concurrency(concurrent, prompt_len)
        all_results.append(result)
        
        # 如果成功率低于 50%，停止测试
        if result["success_rate"] < 0.5:
            print(f"\n⚠️ 成功率低于 50%，停止测试")
            break
        
        # 间隔一段时间，避免触发速率限制
        time.sleep(5)
    
    # 输出总结
    print("\n" + "="*60)
    print("测试结果总结")
    print("="*60)
    print(f"{'并发数':<10} {'Prompt长度':<12} {'成功率':<10} {'平均耗时':<12} {'总耗时':<10}")
    print("-"*60)
    
    for r in all_results:
        print(f"{r['concurrent']:<10} {test_cases[all_results.index(r)][1]:<12} "
              f"{r['success_rate']*100:.0f}%{'':<6} {r['avg_time']:.2f}s{'':<6} {r['total_time']:.2f}s")
    
    print("\n" + "="*60)


if __name__ == "__main__":
    main()
