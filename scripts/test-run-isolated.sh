#!/usr/bin/env bash
set -euo pipefail

# 使用独立运行目录与可复用命令模板，避免 .test-runs 与 worktree 互相污染。
# - 默认运行目录：/tmp/story2-test-runs 或 $TMPDIR
# - 默认命名空间：story2-<user>-<YYYYMMDDTHHMMSS>-<随机数>
# - 支持一键清理旧运行目录

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
DEFAULT_TEST_RUN_ROOT="${TMPDIR:-/tmp}/story2-test-runs"
DEFAULT_TEST_RUN_KEEP_DAYS=7

usage() {
    cat <<'USAGE'
用法:
  ./scripts/test-run-isolated.sh [选项] <test.sh 命令>

默认运行: ./scripts/test-run-isolated.sh all

选项:
  --root <dir>         覆盖 TEST_RUN_ROOT（默认: $DEFAULT_TEST_RUN_ROOT）
  --namespace <name>    覆盖 TEST_NAMESPACE（默认: story2-<user>-<timestamp>-<rand>）
  --keep-days <n>      清理旧测试目录保留天数（默认: 7）
  clean                 执行清理旧运行目录后退出
  -h, --help           显示帮助

示例:
  ./scripts/test-run-isolated.sh preflight
  ./scripts/test-run-isolated.sh --namespace contract_fix_20260610 contract
  TEST_RUN_ROOT=/tmp/story2-codex ./scripts/test-run-isolated.sh all
  ./scripts/test-run-isolated.sh clean
USAGE
}

clean_runs() {
    local root="$1"
    local keep_days="$2"

    if [ ! -d "$root" ]; then
        echo "[info] no runtime root to clean: $root"
        return 0
    fi

    echo "[info] cleaning old test runtimes under $root (older than ${keep_days} days)"
    find "$root" -mindepth 1 -type d -mtime "+$keep_days" -exec rm -rf {} +
}

run_cmd="all"
root="$DEFAULT_TEST_RUN_ROOT"
namespace=""
keep_days="$DEFAULT_TEST_RUN_KEEP_DAYS"

if [ "$#" -gt 0 ]; then
    while [[ "$#" -gt 0 ]]; do
        case "$1" in
            --root)
                shift
                root="$1"
                ;;
            --namespace)
                shift
                namespace="$1"
                ;;
            --keep-days)
                shift
                keep_days="$1"
                ;;
            clean)
                shift
                clean_runs "$root" "$keep_days"
                exit 0
                ;;
            -h|--help)
                usage
                exit 0
                ;;
            *)
                run_cmd="$1"
                shift
                break
                ;;
        esac
        shift
    done
fi

if [ -z "$namespace" ]; then
    namespace="story2-${USER:-ci}-$(date +%Y%m%dT%H%M%S)-${RANDOM}"
fi

mkdir -p "$root"
clean_runs "$root" "$keep_days"

export TEST_RUN_ROOT="$root"
export TEST_NAMESPACE="$namespace"

cd "$PROJECT_DIR"
./test.sh "$run_cmd" "$@"
