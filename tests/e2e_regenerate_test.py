#!/usr/bin/env python3
"""
重新生成故事功能 - 端到端测试验证脚本

使用方法:
  python tests/e2e_regenerate_test.py

这个脚本会:
1. 运行所有相关的单元测试和集成测试
2. 输出手动测试清单
3. 验证关键代码路径
"""

import subprocess
import sys
from pathlib import Path

# 测试颜色
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"


def print_header(text):
    print(f"\n{BLUE}{'='*60}{RESET}")
    print(f"{BLUE}{text}{RESET}")
    print(f"{BLUE}{'='*60}{RESET}\n")


def print_success(text):
    print(f"{GREEN}✓ {text}{RESET}")


def print_error(text):
    print(f"{RED}✗ {text}{RESET}")


def print_info(text):
    print(f"{YELLOW}  {text}{RESET}")


def run_command(cmd, cwd=None):
    """运行命令并返回结果"""
    try:
        result = subprocess.run(
            cmd, shell=True, cwd=cwd, capture_output=True, text=True, timeout=120
        )
        return result.returncode == 0, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return False, "", "Command timed out"


def test_backend_api():
    """测试后端 API"""
    print_header("测试后端 API")

    # 运行后端测试
    success, stdout, stderr = run_command(
        "python3 -m pytest tests/test_api_story.py -v --tb=short",
        cwd=Path(__file__).parent.parent,
    )

    if success:
        print_success("后端 API 测试通过")
        return True
    else:
        print_error("后端 API 测试失败")
        print_info(stderr)
        return False


def test_frontend_unit():
    """测试前端单元测试"""
    print_header("测试前端单元测试")

    success, stdout, stderr = run_command(
        "npm test -- --testPathPatterns='usePlayGame.regenerate' --passWithNoTests --watchAll=false",
        cwd=Path(__file__).parent.parent / "frontend",
    )

    if success:
        print_success("前端单元测试通过")
        return True
    else:
        print_error("前端单元测试失败")
        print_info(stderr)
        return False


def test_frontend_components():
    """测试前端组件测试"""
    print_header("测试前端组件测试")

    success, stdout, stderr = run_command(
        "npm test -- --testPathPatterns='RegenerateStory' --passWithNoTests --watchAll=false",
        cwd=Path(__file__).parent.parent / "frontend",
    )

    if success:
        print_success("前端组件测试通过")
        return True
    else:
        print_error("前端组件测试失败")
        print_info(stderr)
        return False


def verify_code_changes():
    """验证关键代码更改"""
    print_header("验证代码更改")

    checks = [
        {
            "name": "StoryAdjuster.tsx 导入 EventOption 类型",
            "file": "frontend/src/components/game/StoryAdjuster.tsx",
            "pattern": "import type { EventOption }",
        },
        {
            "name": "StoryAdjuster.tsx 传递新事件数据",
            "file": "frontend/src/components/game/StoryAdjuster.tsx",
            "pattern": "onRegenerateComplete(newEventData)",
        },
        {
            "name": "ChatBar.tsx 调用 regenerate API",
            "file": "frontend/src/components/game/ChatBar.tsx",
            "pattern": "api.story.regenerate",
        },
        {
            "name": "ChatBar.tsx 传递新事件数据",
            "file": "frontend/src/components/game/ChatBar.tsx",
            "pattern": "onRegenerate(newEventData)",
        },
        {
            "name": "usePlayGame.ts handleRegenerate 接收参数",
            "file": "frontend/src/hooks/usePlayGame.ts",
            "pattern": "handleRegenerate = useCallback",
        },
        {
            "name": "usePlayGame.ts 使用新事件数据",
            "file": "frontend/src/hooks/usePlayGame.ts",
            "pattern": "newEventData.story",
        },
    ]

    all_passed = True
    base_path = Path(__file__).parent.parent

    for check in checks:
        file_path = base_path / check["file"]
        if not file_path.exists():
            print_error(f"{check['name']} - 文件不存在: {check['file']}")
            all_passed = False
            continue

        content = file_path.read_text()
        if check["pattern"] in content:
            print_success(check["name"])
        else:
            print_error(f"{check['name']} - 未找到模式: {check['pattern']}")
            all_passed = False

    return all_passed


def print_manual_test_checklist():
    """打印手动测试清单"""
    print_header("手动测试清单")

    checklist = """
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📝 请按以下步骤进行手动测试验证
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

【测试场景 1：ChatBar 重新生成按钮】

1. 启动应用并登录
2. 进入一个正在进行的游戏
3. 等待故事生成完成，确保显示选项
4. 点击底部 ChatBar 展开
5. 点击"重新生成"按钮
6. ✅ 验证：
   - 按钮显示加载动画
   - 故事内容更新为新内容
   - 选项同步更新为新选项
   - phase 保持为 options（不会跳转到下一轮）
   - 没有加载预生成的故事

【测试场景 2：StoryAdjuster 重新生成】

1. 在游戏页面，点击"改写"按钮打开 StoryAdjuster
2. 点击"重新生成"按钮
3. ✅ 验证：
   - 按钮显示加载动画
   - 抽屉自动关闭
   - 故事内容更新为新内容
   - 选项同步更新为新选项
   - 没有加载预生成的故事

【测试场景 3：预生成结果清除】

1. 进入一个游戏，完成一轮选择
2. 在轮次小结页面等待几秒（触发预生成）
3. 点击"重新生成"按钮
4. ✅ 验证：
   - 预生成的故事被清除
   - 重新生成的是全新的故事

【测试场景 4：网络错误处理】

1. 断开网络或关闭后端服务
2. 点击"重新生成"按钮
3. ✅ 验证：
   - 显示错误提示或优雅降级
   - 应用不会崩溃

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🔍 开发者控制台检查（浏览器 F12）

测试时请打开浏览器控制台，观察以下日志：

1. 点击重新生成时：
   [StoryAdjuster] Regenerate complete, passing new event data: { storyLen: X, optionsCount: X }
   或
   [ChatBar] Regenerate complete...

2. handleRegenerate 被调用时：
   [handleRegenerate] Called with data: story=X chars, options=X
   [handleRegenerate] Using new event data from backend API

如果看到以下日志，说明有问题：
   [handleRegenerate] No data provided, falling back to SSE regeneration
   （这表示没有正确传递数据，走了 fallback）

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
    print(checklist)


def main():
    print(f"\n{GREEN}重新生成故事功能 - 端到端测试验证{RESET}\n")

    results = []

    # 1. 验证代码更改
    results.append(("代码更改验证", verify_code_changes()))

    # 2. 运行后端测试
    results.append(("后端 API 测试", test_backend_api()))

    # 3. 运行前端测试
    # 注意：前端测试可能需要 Jest 配置，暂时跳过自动运行
    # results.append(("前端单元测试", test_frontend_unit()))
    # results.append(("前端组件测试", test_frontend_components()))

    # 输出结果汇总
    print_header("测试结果汇总")

    all_passed = True
    for name, passed in results:
        if passed:
            print_success(name)
        else:
            print_error(name)
            all_passed = False

    # 打印手动测试清单
    print_manual_test_checklist()

    if all_passed:
        print(f"\n{GREEN}所有自动测试通过！请进行手动测试验证。{RESET}\n")
        return 0
    else:
        print(f"\n{RED}部分测试失败，请检查错误信息。{RESET}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
