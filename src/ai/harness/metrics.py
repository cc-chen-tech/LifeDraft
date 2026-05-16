"""
约束 Harness 指标收集与存储模块。

使用 SQLite 记录每次故事生成的约束遵守情况，
提供查询接口用于统计分析和趋势观察。
"""

import json
import logging
import os
import sqlite3
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class HarnessMetrics:
    """约束 Harness 指标收集器"""

    def __init__(self, db_path: str = "data/harness_metrics.db"):
        """
        初始化指标存储。

        Args:
            db_path: SQLite 数据库文件路径
        """
        self.db_path = db_path
        self._ensure_db()

    def _ensure_db(self) -> None:
        """确保数据库和表结构存在"""
        # 确保目录存在
        db_dir = os.path.dirname(self.db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)

        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()

            # 生成运行记录表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS generation_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    game_id TEXT,
                    week INTEGER,
                    timestamp TEXT NOT NULL,
                    attempts INTEGER DEFAULT 1,
                    final_score REAL,
                    passed INTEGER DEFAULT 1,
                    prompt_token_estimate INTEGER,
                    latency_ms REAL,
                    preflight_passed INTEGER,
                    preflight_missing TEXT,
                    error_message TEXT
                )
            """)  # nosec B608

            # 约束检查记录表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS constraint_checks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id INTEGER NOT NULL,
                    constraint_type TEXT NOT NULL,
                    priority TEXT NOT NULL,
                    passed INTEGER NOT NULL,
                    evidence TEXT,
                    details TEXT,
                    FOREIGN KEY (run_id) REFERENCES generation_runs(id)
                )
            """)  # nosec B608

            # 创建索引提高查询性能
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_runs_timestamp
                ON generation_runs(timestamp)
            """)  # nosec B608
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_runs_game_id
                ON generation_runs(game_id)
            """)  # nosec B608
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_checks_run_id
                ON constraint_checks(run_id)
            """)  # nosec B608
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_checks_constraint_type
                ON constraint_checks(constraint_type)
            """)  # nosec B608

            conn.commit()
        finally:
            conn.close()

    def record_generation(
        self,
        game_id: Optional[str] = None,
        week: Optional[int] = None,
        attempts: int = 1,
        preflight_result: Optional[Dict] = None,
        validation_result: Optional[Dict] = None,
        token_usage: Optional[int] = None,
        latency_ms: Optional[float] = None,
        error_message: Optional[str] = None,
    ) -> Optional[int]:
        """
        记录一次完整的故事生成周期。

        Args:
            game_id: 游戏ID
            week: 当前周数
            attempts: 尝试次数（包括重试）
            preflight_result: 预检查结果 dict
            validation_result: 验证结果 dict
            token_usage: 估计的 token 使用量
            latency_ms: 总延迟（毫秒）
            error_message: 错误信息（如果有）

        Returns:
            生成的 run_id，失败返回 None
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # 解析 preflight 结果
            preflight_passed = 1
            preflight_missing = None
            if preflight_result:
                preflight_passed = 1 if preflight_result.get("all_present", True) else 0
                missing = preflight_result.get("missing_constraints", [])
                if missing:
                    preflight_missing = json.dumps(missing, ensure_ascii=False)

            # 解析 validation 结果
            final_score = 100.0
            passed = 1
            if validation_result:
                final_score = validation_result.get("score", 100.0)
                passed = 1 if validation_result.get("passed", True) else 0

            # 插入生成运行记录
            cursor.execute(  # nosec B608
                """
                INSERT INTO generation_runs
                (game_id, week, timestamp, attempts, final_score, passed,
                 prompt_token_estimate, latency_ms, preflight_passed,
                 preflight_missing, error_message)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    game_id,
                    week,
                    datetime.now().isoformat(),
                    attempts,
                    final_score,
                    passed,
                    token_usage,
                    latency_ms,
                    preflight_passed,
                    preflight_missing,
                    error_message,
                ),
            )

            run_id = cursor.lastrowid

            # 插入每个约束的检查记录
            if validation_result and "detailed_checks" in validation_result:
                for ctype, check in validation_result["detailed_checks"].items():
                    cursor.execute(  # nosec B608
                        """
                        INSERT INTO constraint_checks
                        (run_id, constraint_type, priority, passed, evidence, details)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """,
                        (
                            run_id,
                            ctype,
                            check.get("priority", "UNKNOWN"),
                            1 if check.get("passed", True) else 0,
                            check.get("evidence", ""),
                            json.dumps(check.get("details", {}), ensure_ascii=False),
                        ),
                    )

            conn.commit()
            logger.debug(f"Recorded generation run #{run_id}: score={final_score}, passed={passed}")
            return run_id

        except Exception as e:
            logger.error(f"Failed to record harness metrics: {e}")
            return None
        finally:
            conn.close()

    def get_constraint_pass_rates(self, last_n: int = 100) -> Dict[str, float]:
        """
        获取每种约束的通过率。

        Args:
            last_n: 最近 N 次生成

        Returns:
            约束类型 -> 通过率(0.0~1.0) 的映射
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # 获取最近N次run的ID
            cursor.execute(  # nosec B608
                """
                SELECT id FROM generation_runs
                ORDER BY timestamp DESC LIMIT ?
            """,
                (last_n,),
            )
            run_ids = [row[0] for row in cursor.fetchall()]

            if not run_ids:
                return {}

            placeholders = ",".join(["?"] * len(run_ids))
            cursor.execute(  # nosec B608 - placeholders are safe ? parameters
                f"""
                SELECT constraint_type,
                       COUNT(*) as total,
                       SUM(passed) as passed_count
                FROM constraint_checks
                WHERE run_id IN ({placeholders})
                GROUP BY constraint_type
            """,
                run_ids,
            )

            rates = {}
            for row in cursor.fetchall():
                ctype, total, passed_count = row
                rates[ctype] = round(passed_count / total, 4) if total > 0 else 1.0

            return rates

        except Exception as e:
            logger.error(f"Failed to get constraint pass rates: {e}")
            return {}
        finally:
            conn.close()

    def get_retry_distribution(self, last_n: int = 100) -> Dict[int, int]:
        """
        获取重试次数分布。

        Args:
            last_n: 最近 N 次生成

        Returns:
            重试次数 -> 出现次数 的映射
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute(  # nosec B608
                """
                SELECT attempts, COUNT(*) as count
                FROM (
                    SELECT attempts FROM generation_runs
                    ORDER BY timestamp DESC LIMIT ?
                )
                GROUP BY attempts
                ORDER BY attempts
            """,
                (last_n,),
            )

            return {row[0]: row[1] for row in cursor.fetchall()}

        except Exception as e:
            logger.error(f"Failed to get retry distribution: {e}")
            return {}
        finally:
            conn.close()

    def get_failure_patterns(self, last_n: int = 50) -> List[Dict[str, Any]]:
        """
        获取最近的失败模式。

        Args:
            last_n: 最近 N 次失败

        Returns:
            失败模式列表，每项包含 constraint_type, count, recent_evidence
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute(  # nosec B608
                """
                SELECT cc.constraint_type,
                       COUNT(*) as failure_count,
                       GROUP_CONCAT(cc.evidence, ' | ') as recent_evidence
                FROM constraint_checks cc
                JOIN generation_runs gr ON cc.run_id = gr.id
                WHERE cc.passed = 0
                GROUP BY cc.constraint_type
                ORDER BY failure_count DESC
                LIMIT ?
            """,
                (last_n,),
            )

            patterns = []
            for row in cursor.fetchall():
                evidence_list = row[2].split(" | ") if row[2] else []
                patterns.append(
                    {
                        "constraint_type": row[0],
                        "failure_count": row[1],
                        "recent_evidence": evidence_list[:3],  # 只保留最近3条证据
                    }
                )

            return patterns

        except Exception as e:
            logger.error(f"Failed to get failure patterns: {e}")
            return []
        finally:
            conn.close()

    def get_summary_report(self, last_n: int = 50) -> str:
        """
        生成可读的摘要报告（用于日志输出）。

        Args:
            last_n: 统计范围

        Returns:
            格式化的报告字符串
        """
        pass_rates = self.get_constraint_pass_rates(last_n)
        retry_dist = self.get_retry_distribution(last_n)
        failures = self.get_failure_patterns(last_n)

        lines = [
            f"=== 约束 Harness 报告 (最近 {last_n} 次生成) ===",
            "",
            "【约束通过率】",
        ]

        if pass_rates:
            for ctype, rate in sorted(pass_rates.items(), key=lambda x: x[1]):
                status = "OK" if rate >= 0.9 else ("WARN" if rate >= 0.7 else "FAIL")
                lines.append(f"  {ctype}: {rate*100:.1f}% [{status}]")
        else:
            lines.append("  暂无数据")

        lines.append("")
        lines.append("【重试分布】")
        if retry_dist:
            for attempts, count in sorted(retry_dist.items()):
                lines.append(f"  {attempts}次尝试: {count}次")
        else:
            lines.append("  暂无数据")

        lines.append("")
        lines.append("【高频失败模式】")
        if failures:
            for pattern in failures[:5]:
                lines.append(f"  {pattern['constraint_type']}: {pattern['failure_count']}次失败")
                for ev in pattern["recent_evidence"][:1]:
                    lines.append(f"    证据: {ev[:80]}...")
        else:
            lines.append("  暂无数据")

        lines.append("=" * 50)
        return "\n".join(lines)
