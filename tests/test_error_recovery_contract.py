"""错误恢复机制契约测试 (Layer 3)

验证前端在 502/网络错误时不应踢用户回首页，
而应提供重试/恢复 UI。

对应 Bug: #27 (整页跳回首页), #32 (502 后被登出踢回首页)
"""

import os
import re
import pytest

pytestmark = [pytest.mark.unit]



class TestHandle401RedirectContract:
    """验证 handle401Redirect 只在真正的 401 时触发。"""

    def _get_api_source(self):
        api_path = os.path.join(os.path.dirname(__file__), "..", "frontend", "src", "lib", "api.ts")
        with open(api_path, "r", encoding="utf-8") as f:
            return f.read()

    def test_handle401_redirect_only_on_401(self):
        """handle401Redirect 必须只在 response.status === 401 时调用。

        ★ Bug #27/#32: 502 错误后某些代码路径错误地触发了 401 处理，
        导致 localStorage 被清除、用户被登出、踢回首页。
        """
        source = self._get_api_source()

        # 找到 handle401Redirect 的调用位置
        redirect_calls = [m.start() for m in re.finditer(r"handle401Redirect\(\)", source)]

        # 检查每个调用前是否都有 401 判断
        for call_pos in redirect_calls:
            # 向前搜索最近的 if 条件（最多往前 500 字符）
            search_start = max(0, call_pos - 500)
            preceding = source[search_start:call_pos]

            # 必须包含 401 检查
            has_401_check = (
                "401" in preceding
                or "Unauthorized" in preceding
                or "unauthorized" in preceding.lower()
            )

            assert has_401_check, (
                "handle401Redirect() 调用前必须检查 401 状态码，"
                "否则 502/网络错误会错误地清除用户状态 (Bug #27/#32)"
            )

    def test_no_redirect_on_502_or_504(self):
        """502/504 错误处理分支中不得调用 handle401Redirect。

        这是防止 502 导致用户被登出的核心约束。
        """
        source = self._get_api_source()

        # 找到所有 502/504 处理代码块
        # 通常模式: if (response.status === 502/504) { ... }
        for status_code in ["502", "504"]:
            # 查找包含该状态码的 if 块
            pattern = rf"if\s*\(\s*response\.status\s*===?\s*{status_code}[^)]+\)\s*\{{"
            for match in re.finditer(pattern, source, re.DOTALL):
                block_start = match.end() - 1  # 指向 {
                # 提取块内容
                depth = 0
                block_end = block_start
                for i, c in enumerate(source[block_start:], block_start):
                    if c == "{":
                        depth += 1
                    elif c == "}":
                        depth -= 1
                        if depth == 0:
                            block_end = i
                            break
                block = source[block_start + 1 : block_end]

                assert "handle401Redirect" not in block, (
                    "502/504 错误处理中不得调用 handle401Redirect，"
                    "否则会把网络错误误判为认证过期 (Bug #27/#32)"
                )

    def test_redirect_clears_localstorage(self):
        """handle401Redirect 确实会清除 localStorage 中的游戏状态。"""
        source = self._get_api_source()

        # 找到 handle401Redirect 函数体
        func_match = re.search(
            r"function handle401Redirect\(\)\s*\{([^}]*(?:\{[^}]*\}[^}]*)*)",
            source,
            re.DOTALL,
        )
        assert func_match, "必须能找到 handle401Redirect 函数"
        func_body = func_match.group(1)

        assert (
            "localStorage.removeItem" in func_body
        ), "handle401Redirect 必须清除 localStorage，防止过期状态干扰"

        assert (
            "gameId" in func_body or "gameState" in func_body
        ), "handle401Redirect 必须清除游戏相关 localStorage 项"


class TestAttemptRecoveryContract:
    """验证 usePlayGame.ts 的 attemptRecovery 在失败时不直接跳转首页。"""

    def _get_play_source(self):
        play_path = os.path.join(
            os.path.dirname(__file__),
            "..",
            "frontend",
            "src",
            "hooks",
            "usePlayGame.ts",
        )
        with open(play_path, "r", encoding="utf-8") as f:
            return f.read()

    def test_attempt_recovery_has_error_handling(self):
        """attemptRecovery 必须有错误处理分支，不直接 router.replace('/')"。

        ★ Bug #27: 长任务失败后 attemptRecovery 直接 router.replace('/') 踢用户回首页。
        """
        source = self._get_play_source()

        # 找到 attemptRecovery 函数
        # 在 usePlayGame.ts 中它是一个内联 async 函数
        recovery_match = re.search(
            r"const attemptRecovery\s*=\s*async\s*\(\)\s*=\>\s*\{([^}]*(?:\{[^}]*\}[^}]*)*)",
            source,
            re.DOTALL,
        )
        if not recovery_match:
            # 可能是函数声明形式
            recovery_match = re.search(
                r"async function attemptRecovery\([^)]*\)\s*\{([^}]*(?:\{[^}]*\}[^}]*)*)",
                source,
                re.DOTALL,
            )

        assert recovery_match, "必须能找到 attemptRecovery 函数"
        recovery_body = recovery_match.group(1)

        # 错误处理中不应该直接跳转首页（至少在第一次错误时不应该）
        # 应该提供恢复 UI 或重试机制
        has_router_replace = "router.replace" in recovery_body or "router.push" in recovery_body

        if has_router_replace:
            # 如果存在跳转，必须也有恢复/重试机制
            has_recovery_ui = (
                "recover" in recovery_body.lower()
                or "retry" in recovery_body.lower()
                or "重试" in recovery_body
                or "恢复" in recovery_body
                or "error" in recovery_body.lower()
            )
            assert has_recovery_ui, (
                "attemptRecovery 在 router.replace('/') 前必须有恢复/重试机制，"
                "不能直接将用户踢回首页 (Bug #27)"
            )

    def test_no_hard_redirect_in_error_phase(self):
        """错误阶段不应有硬跳转，应留在 /play 页面。"""
        source = self._get_play_source()

        # 检查整体错误处理模式
        # 不应在 catch 块中直接 window.location.href = '/' 或 router.replace('/')
        catch_blocks = []
        depth = 0
        in_catch = False
        catch_start = 0

        for i, c in enumerate(source):
            if source[i : i + 5] == "catch":
                in_catch = True
                catch_start = i
            elif in_catch and c == "{":
                depth += 1
            elif in_catch and c == "}":
                depth -= 1
                if depth == 0:
                    catch_blocks.append(source[catch_start : i + 1])
                    in_catch = False

        for block in catch_blocks:
            # catch 块中如果包含跳转，必须有恢复逻辑
            if "router.replace" in block or "window.location" in block:
                assert "recover" in block.lower() or "retry" in block.lower(), (
                    "catch 块中的页面跳转必须与恢复机制共存，" "不能只有跳转 (Bug #27)"
                )


class TestChoiceErrorHandlerContract:
    """验证 choiceUtils.ts 的错误处理提供重试而非跳转。"""

    def _get_choice_utils_source(self):
        utils_path = os.path.join(
            os.path.dirname(__file__),
            "..",
            "frontend",
            "src",
            "hooks",
            "game",
            "choiceUtils.ts",
        )
        with open(utils_path, "r", encoding="utf-8") as f:
            return f.read()

    def _extract_function_body(self, source: str, func_name: str) -> str:
        """Extract function body by brace counting."""
        pattern = rf"export async function {func_name}\("
        match = re.search(pattern, source)
        assert match, f"必须能找到 {func_name} 函数"

        # Find the closing ')' of the parameter list
        paren_depth = 1
        paren_end = match.end()
        for i, c in enumerate(source[match.end() :], match.end()):
            if c == "(":
                paren_depth += 1
            elif c == ")":
                paren_depth -= 1
                if paren_depth == 0:
                    paren_end = i
                    break

        # Find opening brace after parameter list
        brace_start = source.find("{", paren_end)
        assert brace_start != -1, f"必须能找到 {func_name} 的函数体起始位置"

        # Count braces to find matching close
        depth = 0
        brace_end = brace_start
        for i, c in enumerate(source[brace_start:], brace_start):
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    brace_end = i
                    break

        return source[brace_start + 1 : brace_end]

    def test_handle_choice_error_provides_retry(self):
        """handleChoiceError 最终必须提供重试入口或恢复手段。

        ★ Bug #15: 502 后 setPhase('error') 但没有重试按钮，用户只能刷新页面。
        """
        source = self._get_choice_utils_source()
        func_body = self._extract_function_body(source, "handleChoiceError")

        # 错误处理应提供重试或恢复
        has_retry = (
            "retry" in func_body.lower()
            or "fallback" in func_body.lower()
            or "recover" in func_body.lower()
            or "重试" in func_body
            or "恢复" in func_body
        )

        assert has_retry, (
            "handleChoiceError 必须提供重试或恢复机制，"
            "不能只是 setPhase('error') 让用户无路可走 (Bug #15)"
        )

    def test_handle_choice_error_sets_error_phase(self):
        """handleChoiceError 确实会设置 error phase 作为兜底。"""
        source = self._get_choice_utils_source()
        func_body = self._extract_function_body(source, "handleChoiceError")

        assert "error" in func_body.lower(), "handleChoiceError 必须在无法恢复时设置 error phase"


class TestErrorRecoverySSEContract:
    """验证 SSE 错误处理与恢复机制的契约。"""

    def test_sse_callbacks_include_on_error(self):
        """StreamCallbacks 必须包含 onError 回调。"""
        sse_path = os.path.join(os.path.dirname(__file__), "..", "frontend", "src", "lib", "sse.ts")
        with open(sse_path, "r", encoding="utf-8") as f:
            source = f.read()

        assert "onError?:" in source, "StreamCallbacks 必须包含 onError 回调"
        assert "onConnectionStatus?:" in source, "StreamCallbacks 应包含连接状态回调"

    def test_sse_parser_emits_error_on_disconnect(self):
        """parseSSEStream 必须在流异常断开时触发 onError。"""
        sse_path = os.path.join(os.path.dirname(__file__), "..", "frontend", "src", "lib", "sse.ts")
        with open(sse_path, "r", encoding="utf-8") as f:
            source = f.read()

        # 检查流断开时的错误处理
        assert "onError" in source, "parseSSEStream 必须在错误时触发 onError"
        assert (
            "Stream ended without complete event" in source
        ), "SSE 流在未收到 complete 时断开必须触发错误，不能静默失败"
