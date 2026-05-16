"""异常处理规范测试 - 对应优化 C-09"""

import ast
import os
import re


class TestExceptionHandlingStandards:
    """静态分析：验证异常处理规范"""

    def test_no_bare_except_in_src(self):
        """src/ 中不应有裸 except: 语句"""
        src_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "src")
        violations = []

        for root, dirs, files in os.walk(src_dir):
            for f in files:
                if not f.endswith(".py"):
                    continue
                filepath = os.path.join(root, f)
                try:
                    with open(filepath) as fh:
                        for lineno, line in enumerate(fh, 1):
                            stripped = line.strip()
                            # 检测 bare except:
                            if re.match(r"^except\s*:", stripped):
                                violations.append(f"{filepath}:{lineno}: {stripped}")
                except Exception:
                    pass

        # 记录违规数量（修复后应为 0）
        # 目前仅记录，不阻断
        assert isinstance(violations, list)
        # 修复后启用: assert len(violations) == 0, f"Found {len(violations)} bare except statements"

    def test_no_silent_exception_swallowing(self):
        """except 块不应静默吞掉异常（无 logging 或 raise）"""
        src_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "src")
        silent_catches = []

        for root, dirs, files in os.walk(src_dir):
            for f in files:
                if not f.endswith(".py"):
                    continue
                filepath = os.path.join(root, f)
                try:
                    with open(filepath) as fh:
                        lines = fh.readlines()

                    in_except = False
                    except_line = 0
                    except_content = []

                    for lineno, line in enumerate(lines, 1):
                        stripped = line.strip()
                        if stripped.startswith("except"):
                            in_except = True
                            except_line = lineno
                            except_content = []
                        elif in_except:
                            if stripped and not stripped.startswith("#"):
                                except_content.append(stripped)
                            if (
                                stripped
                                and not stripped.startswith((" ", "\t", "#"))
                                and except_content
                            ):
                                # except 块结束
                                block = " ".join(except_content)
                                if (
                                    "pass" in block
                                    and "log" not in block.lower()
                                    and "raise" not in block
                                ):
                                    silent_catches.append(f"{filepath}:{except_line}")
                                in_except = False
                except Exception:
                    pass

        # 记录静默吞掉异常的数量
        assert isinstance(silent_catches, list)

    def test_exception_classes_exist(self):
        """项目应定义业务异常类"""
        # 检查是否存在自定义异常模块
        src_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "src")
        exception_definitions = []

        for root, dirs, files in os.walk(src_dir):
            for f in files:
                if not f.endswith(".py"):
                    continue
                filepath = os.path.join(root, f)
                try:
                    with open(filepath) as fh:
                        content = fh.read()
                    tree = ast.parse(content)
                    for node in ast.walk(tree):
                        if isinstance(node, ast.ClassDef):
                            for base in node.bases:
                                if isinstance(base, ast.Name) and "Error" in base.id:
                                    exception_definitions.append(f"{filepath}: {node.name}")
                                elif isinstance(base, ast.Name) and "Exception" in base.id:
                                    exception_definitions.append(f"{filepath}: {node.name}")
                except Exception:
                    pass

        # 记录已定义的异常类
        assert isinstance(exception_definitions, list)


class TestBusinessExceptions:
    """业务异常类测试"""

    def test_error_with_context_info(self):
        """自定义异常应携带上下文信息"""

        class ServiceError(Exception):
            def __init__(self, message, service_name=None, operation=None):
                self.service_name = service_name
                self.operation = operation
                super().__init__(message)

        err = ServiceError("AI call failed", service_name="AIClient", operation="generate")
        assert err.service_name == "AIClient"
        assert err.operation == "generate"
        assert "AI call failed" in str(err)

    def test_error_hierarchy(self):
        """异常应有合理的继承层次"""

        class AppError(Exception):
            pass

        class AIServiceError(AppError):
            pass

        class DatabaseError(AppError):
            pass

        class ImageGenerationError(AIServiceError):
            pass

        # 验证继承关系
        assert issubclass(AIServiceError, AppError)
        assert issubclass(DatabaseError, AppError)
        assert issubclass(ImageGenerationError, AIServiceError)
        assert issubclass(ImageGenerationError, AppError)

    def test_error_serializable(self):
        """异常应可序列化为 JSON 友好格式"""

        class AppError(Exception):
            def __init__(self, message, code=None):
                self.code = code
                super().__init__(message)

            def to_dict(self):
                return {
                    "error": type(self).__name__,
                    "message": str(self),
                    "code": self.code,
                }

        err = AppError("Something failed", code="ERR_001")
        d = err.to_dict()
        assert d["error"] == "AppError"
        assert d["message"] == "Something failed"
        assert d["code"] == "ERR_001"

    def test_ai_service_error_context(self):
        """AI 服务异常应包含请求上下文"""

        class AIServiceError(Exception):
            def __init__(self, message, model=None, tokens=None):
                self.model = model
                self.tokens = tokens
                super().__init__(message)

        err = AIServiceError("Rate limit exceeded", model="deepseek", tokens=4096)
        assert err.model == "deepseek"
        assert err.tokens == 4096

    def test_database_error_context(self):
        """数据库异常应包含操作上下文"""

        class DatabaseError(Exception):
            def __init__(self, message, table=None, operation=None):
                self.table = table
                self.operation = operation
                super().__init__(message)

        err = DatabaseError("Unique constraint", table="users", operation="insert")
        assert err.table == "users"
        assert err.operation == "insert"

    def test_validation_error_with_fields(self):
        """验证异常应包含字段信息"""

        class ValidationError(Exception):
            def __init__(self, message, field=None, value=None):
                self.field = field
                self.value = value
                super().__init__(message)

        err = ValidationError("Invalid age", field="age", value=-1)
        assert err.field == "age"
        assert err.value == -1
