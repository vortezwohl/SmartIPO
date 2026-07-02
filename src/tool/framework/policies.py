"""工具框架可复用策略接口与文件系统策略实现。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Protocol

from fileglide.exceptions import FileGlideError, NotFoundError, ScopeError

from src.tool.framework.contracts import ToolError, ToolExecutionError, ToolResult
from src.tool.framework.execution import build_tool_result


class PathPolicy(Protocol):
    """描述路径归一化策略接口。"""

    def normalize(
        self,
        *,
        workspace_root: str,
        explicit_root: str | None,
        raw_value: str,
        path_key: str,
    ) -> tuple[str, str]:
        """返回规范化后的 root 与相对路径。"""


class TraversalPolicy(Protocol):
    """描述遍历策略接口。"""

    def recursive(self, *, explicit: bool | None, default: bool = False) -> bool:
        """返回最终递归标记。"""


@dataclass(frozen=True, slots=True)
class ScopedPathPolicy:
    """把绝对路径折叠为 scope root + root-relative path。"""

    def normalize(
        self,
        *,
        workspace_root: str,
        explicit_root: str | None,
        raw_value: str,
        path_key: str,
    ) -> tuple[str, str]:
        value = raw_value.strip() or "."
        normalized_root = explicit_root or workspace_root or "."
        target_path = Path(value)
        if not target_path.is_absolute():
            return normalized_root, value
        resolved_target = target_path.expanduser().resolve(strict=False)
        if explicit_root is not None:
            resolved_root = Path(explicit_root).expanduser().resolve(strict=False)
            try:
                relative_target = resolved_target.relative_to(resolved_root)
            except ValueError as error:
                raise self.build_conflicting_root_error(
                    path_key=path_key,
                    resolved_root=resolved_root,
                    resolved_target=resolved_target,
                ) from error
            return str(resolved_root), _normalize_relative_text(str(relative_target))
        anchor = resolved_target.anchor or str(Path("/"))
        anchor_root = Path(anchor).expanduser().resolve(strict=False)
        relative_target = resolved_target.relative_to(anchor_root)
        return str(anchor_root), _normalize_relative_text(str(relative_target))

    def build_conflicting_root_error(
        self,
        *,
        path_key: str,
        resolved_root: Path,
        resolved_target: Path,
    ) -> ToolExecutionError:
        anchor = Path(resolved_target.anchor or str(Path("/"))).expanduser().resolve(
            strict=False
        )
        relative_target = _normalize_relative_text(
            str(resolved_target.relative_to(anchor))
        )
        suggestion = (
            f"For example, use root=\"{anchor}\" and {path_key}=\"{relative_target}\"."
        )
        raw_error = (
            f"absolute {path_key} '{resolved_target}' escapes explicit root "
            f"'{resolved_root}'"
        )
        return ToolExecutionError(
            ToolError(
                code="root_path_conflict",
                model_message=(
                    "This call violates the root-relative path contract: "
                    f'explicit root "{resolved_root}" does not contain absolute '
                    f'{path_key} "{resolved_target}". {suggestion}'
                ),
                raw_error=raw_error,
                retry_hint=suggestion,
                retryable=True,
            )
        )


@dataclass(frozen=True, slots=True)
class ReadonlyTraversalPolicy:
    """统一只读探索的默认递归策略。"""

    default_recursive: bool = False

    def recursive(self, *, explicit: bool | None, default: bool | None = None) -> bool:
        if explicit is not None:
            return explicit
        if default is not None:
            return default
        return self.default_recursive


@dataclass(frozen=True, slots=True)
class FileglideResultFormatter:
    """统一 fileglide 结果格式化。"""

    model_entry_limit: int = 80
    model_line_limit: int = 120

    def build_result(self, name: str, payload: dict[str, Any]) -> ToolResult:
        preview = self._build_preview(name, payload)
        model_text = self._build_model_text(payload)
        return build_tool_result(
            content=payload,
            summary=preview,
            preview_text=preview,
            model_text=model_text,
            detail_text=model_text,
            metadata={"tool_name": name},
        )

    def _build_preview(self, name: str, payload: dict[str, Any]) -> str:
        entry = payload.get("entry", {})
        if isinstance(entry, dict) and entry.get("relative_path"):
            return str(entry["relative_path"])
        entries = payload.get("entries")
        if isinstance(entries, list):
            return f"{len(entries)} entries"
        if "query" in payload:
            return str(payload["query"])
        if "pattern" in payload:
            return str(payload["pattern"])
        return name

    def _build_model_text(self, payload: dict[str, Any]) -> str:
        lines = payload.get("lines")
        if isinstance(lines, list) and "entry" in payload and "content" in payload:
            return self._render_text_read_payload(payload)
        entries = payload.get("entries")
        if isinstance(entries, list) and "scope" in payload:
            return self._render_entries_payload(payload)
        return ""

    def _render_entries_payload(self, payload: dict[str, Any]) -> str:
        scope = payload.get("scope", {})
        entries = payload.get("entries", [])
        root = str(scope.get("root", "")).strip()
        start = str(scope.get("start", "")).strip()
        lines = [
            f"Scope root: {root or '.'}",
            f"Start: {_render_scope_start(root, start)}",
            f"Entry count: {int(payload.get('count', len(entries)) or 0)}",
            "Entries:",
        ]
        if not entries:
            lines.append("- [empty]")
            return "\n".join(lines)
        for entry in entries[: self.model_entry_limit]:
            relative_path = _normalize_relative_text(
                str(entry.get("relative_path", "")).strip()
            )
            kind = str(entry.get("kind", "path")).strip() or "path"
            lines.append(f"- {relative_path} [{kind}]")
        if len(entries) > self.model_entry_limit:
            lines.append(
                f"- ... {len(entries) - self.model_entry_limit} more entries omitted"
            )
        return "\n".join(lines)

    def _render_text_read_payload(self, payload: dict[str, Any]) -> str:
        entry = payload.get("entry", {})
        relative_path = _normalize_relative_text(
            str(entry.get("relative_path") or entry.get("path") or "").strip()
        )
        lines_payload = payload.get("lines", [])
        rendered = [
            f"File: {relative_path}",
            f"Line count: {int(payload.get('line_count', len(lines_payload)) or 0)}",
            "Content:",
        ]
        if not lines_payload:
            text = str(payload.get("content", "")).rstrip()
            rendered.append(text or "[empty]")
            return "\n".join(rendered)
        for item in lines_payload[: self.model_line_limit]:
            line_number = int(item.get("line_number", 0) or 0)
            line_text = str(item.get("text", ""))
            rendered.append(f"{line_number}: {line_text}")
        if len(lines_payload) > self.model_line_limit:
            rendered.append(
                f"... {len(lines_payload) - self.model_line_limit} more lines omitted"
            )
        return "\n".join(rendered)


@dataclass(frozen=True, slots=True)
class FileglideReadonlyErrorMapper:
    """把底层 fileglide 只读异常映射为统一结构化错误。"""

    def map(
        self,
        *,
        tool_name: str,
        root: str,
        path_key: str,
        path_value: str,
        error: Exception,
    ) -> Exception:
        if isinstance(error, ToolExecutionError):
            return error
        raw_error = str(error).strip() or error.__class__.__name__
        if isinstance(error, ScopeError):
            return ToolExecutionError(
                ToolError(
                    code="scope_violation",
                    model_message=(
                        f"{tool_name} failed because the call violates the root-relative "
                        f'path contract. Set root to the intended scope root and pass '
                        f'{path_key} as a path relative to that root. Current root="{root}", '
                        f'{path_key}="{path_value}".'
                    ),
                    raw_error=raw_error,
                    retry_hint=(
                        f'Retry with root="{root}" and a {path_key} value relative to that root.'
                    ),
                    retryable=True,
                )
            )
        if isinstance(error, NotFoundError):
            return ToolExecutionError(
                ToolError(
                    code="not_found",
                    model_message=(
                        f"{tool_name} failed because the requested target does not exist. "
                        f'Confirm that {path_key} exists inside the current root before '
                        f'retrying. Current root="{root}", {path_key}="{path_value}".'
                    ),
                    raw_error=raw_error,
                    retry_hint=(
                        f'Confirm that {path_key} exists under root="{root}" before retrying.'
                    ),
                    retryable=True,
                )
            )
        if isinstance(error, PermissionError):
            return ToolExecutionError(
                ToolError(
                    code="permission_denied",
                    model_message=(
                        f"{tool_name} failed because traversal hit a protected location. "
                        f"Retry with a narrower root or {path_key}, or set recursive=false "
                        f"for a shallow exploration pass."
                    ),
                    raw_error=raw_error,
                    retry_hint=(
                        f"Retry with a narrower {path_key} or recursive=false."
                    ),
                    retryable=True,
                )
            )
        if isinstance(error, FileGlideError):
            return ToolExecutionError(
                ToolError(
                    code=str(getattr(error, "code", "fileglide_error")),
                    model_message=f"{tool_name} failed: {raw_error}",
                    raw_error=raw_error,
                )
            )
        return error


def run_with_error_mapper(
    *,
    mapper: Callable[..., Exception],
    tool_name: str,
    root: str,
    path_key: str,
    path_value: str,
    runner: Callable[[], dict[str, Any]],
    formatter: FileglideResultFormatter,
) -> ToolResult:
    """执行一个只读 fileglide 操作，并通过公共 mapper/formatter 收口。"""

    try:
        payload = runner()
    except Exception as error:
        raise mapper(
            tool_name=tool_name,
            root=root,
            path_key=path_key,
            path_value=path_value,
            error=error,
        ) from error
    return formatter.build_result(tool_name, payload)


def _normalize_relative_text(value: str) -> str:
    normalized = value.replace("\\", "/").strip()
    if normalized in {"", "."}:
        return "."
    return normalized


def _render_scope_start(root: str, start: str) -> str:
    if not root or not start:
        return _normalize_relative_text(start)
    try:
        relative = Path(start).resolve(strict=False).relative_to(
            Path(root).resolve(strict=False)
        )
    except ValueError:
        return _normalize_relative_text(start)
    return _normalize_relative_text(str(relative))
