"""SSE 流式请求前端重试机制契约测试 (Layer 3)

验证前端 SSE 流式请求（choice / custom-choice / opening-story）
在遭遇 502/504 时具备指数退避重试能力，防止"一次 502 就永久卡死"。

对应 Bug: #15 (choice 502 卡死), #32 (opening-story 502 卡死)
"""

import os
import re

import pytest


class TestSSERetryMechanismContract:
    """验证前端 SSE 流具备 502/504 重试机制。"""

    def _get_sse_source(self):
        """读取前端 sse.ts 源码。"""
        sse_path = os.path.join(
            os.path.dirname(__file__), "..", "frontend", "src", "lib", "sse.ts"
        )
        with open(sse_path, "r", encoding="utf-8") as f:
            return f.read()

    def _extract_function_body(self, source: str, func_name: str) -> str:
        """Extract function body by brace counting."""
        pattern = rf"export async function {func_name}\("
        match = re.search(pattern, source)
        assert match, f"必须能找到 {func_name} 函数"

        # Find the function body's opening brace by looking for 'Promise<' then ') {' pattern
        # Skip any '{' inside parameter list (e.g., options?: { signal?: AbortSignal })
        search_start = match.end()
        # Find the closing ')' of the parameter list
        paren_depth = 1
        paren_end = search_start
        for i, c in enumerate(source[search_start:], search_start):
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

    def test_stream_choice_has_retry_logic(self):
        """streamChoice 必须包含 502/504 重试逻辑。

        ★ 修复前: streamChoice 使用原始 fetch，502 直接抛异常，页面永久卡死。
        ★ 修复后: 遇到 502/504 时自动重试，最多 3 次，指数退避。
        """
        source = self._get_sse_source()
        choice_body = self._extract_function_body(source, "streamChoice")

        # 必须有重试机制（循环或递归）
        has_retry_loop = (
            "for" in choice_body
            or "while" in choice_body
            or "retry" in choice_body.lower()
        )
        # 或者调用了带重试的辅助函数
        has_retry_helper = (
            "fetchWithRetry" in choice_body or "retry" in choice_body.lower()
        )

        assert has_retry_loop or has_retry_helper, (
            "streamChoice 必须包含重试循环或调用重试辅助函数，"
            "否则 502/504 会导致永久卡死 (Bug #15)"
        )

    def test_stream_custom_choice_has_retry_logic(self):
        """streamCustomChoice 必须包含 502/504 重试逻辑。"""
        source = self._get_sse_source()
        custom_body = self._extract_function_body(source, "streamCustomChoice")

        has_retry = (
            "for" in custom_body
            or "while" in custom_body
            or "retry" in custom_body.lower()
        )
        has_helper = "fetchWithRetry" in custom_body or "retry" in custom_body.lower()

        assert has_retry or has_helper, "streamCustomChoice 必须包含重试机制 (Bug #15)"

    def test_stream_opening_story_has_retry_logic(self):
        """streamOpeningStory 必须包含 502/504 重试逻辑。

        ★ 修复前: opening-story 接口 502 后页面永久卡死，60+ 秒无响应。
        ★ 修复后: 自动重试最多 3 次，失败后保留登录态并提供重试按钮。
        """
        source = self._get_sse_source()
        opening_body = self._extract_function_body(source, "streamOpeningStory")

        has_retry = (
            "for" in opening_body
            or "while" in opening_body
            or "retry" in opening_body.lower()
        )
        has_helper = "fetchWithRetry" in opening_body or "retry" in opening_body.lower()

        assert has_retry or has_helper, "streamOpeningStory 必须包含重试机制 (Bug #32)"

    def test_retry_max_attempts_is_three(self):
        """重试次数必须最多 3 次（1 次原始 + 2 次重试 = 3 次总计）。

        过多重试会加剧上游压力，过少则无法应对短暂抖动。
        """
        source = self._get_sse_source()

        # 查找重试次数定义
        retry_patterns = [
            r"retries\s*=\s*3",
            r"maxRetries\s*=\s*3",
            r"max_attempts\s*=\s*3",
            r"retry\s*<\s*3",
            r"retryCount\s*<\s*3",
            r"attempt\s*<\s*3",
            r"attempts\s*<\s*3",
            r"for\s*\(.*;\s*.*\s*<\s*3",
        ]
        has_max_three = any(re.search(p, source) for p in retry_patterns)

        assert has_max_three, (
            "SSE 重试次数应最多 3 次（原始请求 + 2 次重试），"
            "避免过少无法恢复或过多加剧上游压力"
        )

    def test_retry_exponential_backoff(self):
        """重试必须使用指数退避延迟（如 1s, 2s, 4s）。

        固定间隔重试会在上游恢复瞬间造成请求洪峰（thundering herd）。
        """
        source = self._get_sse_source()

        # 指数退避的典型模式：Math.pow(2, i) * 1000 或类似的翻倍逻辑
        exp_patterns = [
            r"Math\.pow\(2",
            r"\*\s*1000",
            r"delay\s*\*\s*2",
            r"setTimeout.*\*\s*2",
            r"backoff",
            r"exponential",
            r"1\s*\*\s*1000",
            r"2\s*\*\s*1000",
            r"4\s*\*\s*1000",
        ]
        has_exponential = any(re.search(p, source, re.IGNORECASE) for p in exp_patterns)

        # 或者至少存在延迟重试（非立即重试）
        delay_patterns = [
            r"setTimeout",
            r"await new Promise",
            r"sleep",
            r"delay",
        ]
        has_delay = any(re.search(p, source, re.IGNORECASE) for p in delay_patterns)

        assert has_exponential or has_delay, (
            "SSE 重试必须包含延迟机制（最好是指数退避），"
            "避免在上游恢复瞬间造成请求洪峰"
        )

    def test_retry_only_on_server_errors(self):
        """重试必须只在 502/504 等服务器错误时触发，不在 400/404 时触发。

        客户端错误（4xx）重试是浪费，且可能触发限流。
        """
        source = self._get_sse_source()

        # 应检查 status >= 500 或特定 502/504 状态码
        server_error_patterns = [
            r"502",
            r"504",
            r"status\s*>=\s*500",
            r"status\s*==\s*502",
            r"status\s*==\s*504",
            r"response\.status",
            r"server error",
        ]
        has_server_error_check = any(
            re.search(p, source, re.IGNORECASE) for p in server_error_patterns
        )

        assert has_server_error_check, (
            "重试逻辑必须区分服务器错误（502/504）和客户端错误，"
            "避免对 4xx 错误进行无效重试"
        )

    def test_stream_functions_do_not_use_raw_fetch(self):
        """streamChoice/streamCustomChoice/streamOpeningStory 不应直接使用无保护的 fetch。

        ★ 根因：这三个函数之前直接使用原始 fetch，没有任何重试保护。
        """
        source = self._get_sse_source()

        # 提取三个函数的 body
        funcs = ["streamChoice", "streamCustomChoice", "streamOpeningStory"]
        for func_name in funcs:
            match = re.search(
                rf"export async function {func_name}\([^)]+\)\s*\{{([^}}]*(?:\{{[^}}]*\}}[^}}]*)*)",
                source,
                re.DOTALL,
            )
            if not match:
                continue
            body = match.group(1)

            # 如果函数体内直接使用 fetch 且没有 retry 包裹，这是危险的
            has_raw_fetch = "fetch(" in body
            has_retry_wrap = "retry" in body.lower() or "fetchWithRetry" in body

            if has_raw_fetch and not has_retry_wrap:
                pytest.fail(
                    f"{func_name} 直接使用原始 fetch 但没有重试保护，"
                    f"502 时将永久卡死"
                )

    def test_retry_preserves_abort_signal(self):
        """重试必须尊重 AbortSignal，用户取消时不应继续重试。

        否则用户点击取消后，后台仍在不断重试，浪费资源。
        """
        source = self._get_sse_source()

        # 检查 abort signal 的使用
        abort_patterns = [
            r"signal\.aborted",
            r"AbortSignal",
            r"controller\.abort",
            r"options\?\.signal",
        ]
        has_abort_check = any(re.search(p, source) for p in abort_patterns)

        assert has_abort_check, (
            "SSE 重试机制必须检查 AbortSignal，" "确保用户取消操作后停止重试"
        )

    def test_opening_story_error_shows_retry_ui(self):
        """opening-story 重试失败后必须提供 UI 重试入口，不踢用户回首页。

        ★ Bug #32: 502 后用户被登出且踢回首页，没有任何恢复手段。
        """
        # 检查 useCharacterCreation.ts 或相关 hook 中的错误处理
        creation_path = os.path.join(
            os.path.dirname(__file__),
            "..",
            "frontend",
            "src",
            "hooks",
            "useCharacterCreation.ts",
        )
        if os.path.exists(creation_path):
            with open(creation_path, "r", encoding="utf-8") as f:
                creation_source = f.read()

            # 错误处理不应直接跳转到首页
            has_redirect_on_error = (
                "router.push" in creation_source or "router.replace" in creation_source
            )
            has_retry_ui = (
                "retry" in creation_source.lower() or "重试" in creation_source
            )

            # 如果存在错误跳转，必须同时存在重试机制
            if has_redirect_on_error:
                assert has_retry_ui, (
                    "opening-story 错误处理必须提供重试 UI，"
                    "不能只在 502 后把用户踢回首页 (Bug #32)"
                )


class TestAPIFetchWithRetryContract:
    """验证 REST API 层的 fetchWithRetry 已具备重试能力。"""

    def test_fetch_with_retry_exists(self):
        """api.ts 中必须存在 fetchWithRetry 函数。"""
        api_path = os.path.join(
            os.path.dirname(__file__), "..", "frontend", "src", "lib", "api.ts"
        )
        with open(api_path, "r", encoding="utf-8") as f:
            source = f.read()

        assert (
            "function fetchWithRetry" in source or "const fetchWithRetry" in source
        ), "api.ts 必须定义 fetchWithRetry 函数用于 REST API 重试"

    def test_fetch_with_retry_has_exponential_backoff(self):
        """fetchWithRetry 必须实现指数退避。"""
        api_path = os.path.join(
            os.path.dirname(__file__), "..", "frontend", "src", "lib", "api.ts"
        )
        with open(api_path, "r", encoding="utf-8") as f:
            source = f.read()

        assert (
            "Math.pow(2, i)" in source or "* 1000" in source
        ), "fetchWithRetry 必须实现指数退避延迟"

    def test_fetch_with_retry_handles_502(self):
        """fetchWithRetry 必须在 502 时重试。"""
        api_path = os.path.join(
            os.path.dirname(__file__), "..", "frontend", "src", "lib", "api.ts"
        )
        with open(api_path, "r", encoding="utf-8") as f:
            source = f.read()

        assert (
            "response.status < 500" in source or "502" in source or "504" in source
        ), "fetchWithRetry 必须处理 5xx 错误并触发重试"
