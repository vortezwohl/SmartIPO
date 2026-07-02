"""fileglide 工具注册与适配。

该文件把 fileglide Python facade 的常用本地文件系统能力映射为项目内
`ToolSpec`。第一版直接暴露完整最小能力集，避免再包一层 shell 适配。
"""

from __future__ import annotations

import base64
from typing import Any, Callable

from fileglide.facade import FileGlideFacade

from src.tool.contracts import ToolContext, ToolResult, ToolSpec


_FILEGLIDE_FACADE = FileGlideFacade()


def _default_root(context: ToolContext, root: str | None) -> str:
    """统一 fileglide 工具默认根目录。"""

    return root or context.workspace_root or "."


def _build_result(name: str, payload: dict[str, Any]) -> ToolResult:
    """把 fileglide 返回值整理为统一工具结果。"""

    entry = payload.get("entry", {})
    if isinstance(entry, dict) and entry.get("relative_path"):
        summary = str(entry["relative_path"])
    elif "query" in payload:
        summary = str(payload["query"])
    elif "pattern" in payload:
        summary = str(payload["pattern"])
    else:
        summary = name
    return ToolResult(
        content=payload,
        summary=summary,
        metadata={"tool_name": name},
    )


def _object_schema(
    properties: dict[str, Any],
    required: list[str] | None = None,
) -> dict[str, Any]:
    """生成统一的对象 schema。"""

    return {
        "type": "object",
        "properties": properties,
        "required": required or [],
    }


def _tool_spec(
    *,
    name: str,
    description: str,
    display_name: str,
    input_schema: dict[str, Any],
    handler: Callable[..., ToolResult],
) -> ToolSpec:
    """构造一个 fileglide 工具定义。"""

    return ToolSpec(
        name=name,
        description=description,
        display_name=display_name,
        input_schema=input_schema,
        handler=handler,
        tool_kind="fileglide",
    )


def _run_file_create(context: ToolContext, **kwargs) -> ToolResult:
    payload = _FILEGLIDE_FACADE.filesystem.create_file(
        _default_root(context, kwargs.get("root")),
        kwargs["target"],
        parents=kwargs.get("parents", False),
        exist_ok=kwargs.get("exist_ok", False),
    )
    return _build_result("file.create", payload)


def _run_file_delete(context: ToolContext, **kwargs) -> ToolResult:
    payload = _FILEGLIDE_FACADE.filesystem.delete_file(
        _default_root(context, kwargs.get("root")),
        kwargs["target"],
        dry_run=kwargs.get("dry_run", False),
        confirm=kwargs.get("confirm", False),
        missing_ok=kwargs.get("missing_ok", False),
    )
    return _build_result("file.delete", payload)


def _run_file_move(context: ToolContext, **kwargs) -> ToolResult:
    payload = _FILEGLIDE_FACADE.filesystem.move_file(
        _default_root(context, kwargs.get("root")),
        kwargs["source"],
        kwargs["destination"],
        destination_root=kwargs.get("destination_root"),
        dry_run=kwargs.get("dry_run", False),
        confirm=kwargs.get("confirm", False),
    )
    return _build_result("file.move", payload)


def _run_file_exists(context: ToolContext, **kwargs) -> ToolResult:
    payload = _FILEGLIDE_FACADE.filesystem.exists(
        _default_root(context, kwargs.get("root")),
        kwargs["target"],
    )
    return _build_result("file.exists", payload)


def _run_file_list(context: ToolContext, **kwargs) -> ToolResult:
    payload = _FILEGLIDE_FACADE.traversal.list_entries(
        _default_root(context, kwargs.get("root")),
        start=kwargs.get("start", "."),
        kind="file",
        recursive=kwargs.get("recursive", True),
        max_depth=kwargs.get("max_depth"),
        include=tuple(kwargs.get("include", [])),
        exclude=tuple(kwargs.get("exclude", [])),
    )
    return _build_result("file.list", payload)


def _run_file_search(context: ToolContext, **kwargs) -> ToolResult:
    payload = _FILEGLIDE_FACADE.search.search_names(
        _default_root(context, kwargs.get("root")),
        query=kwargs["query"],
        mode=kwargs.get("mode", "contains"),
        start=kwargs.get("start", "."),
        kind="file",
        recursive=kwargs.get("recursive", True),
        max_depth=kwargs.get("max_depth"),
        include=tuple(kwargs.get("include", [])),
        exclude=tuple(kwargs.get("exclude", [])),
        limit=kwargs.get("limit", 50),
    )
    return _build_result("file.search", payload)


def _run_path_create(context: ToolContext, **kwargs) -> ToolResult:
    payload = _FILEGLIDE_FACADE.filesystem.create_path(
        _default_root(context, kwargs.get("root")),
        kwargs["target"],
        parents=kwargs.get("parents", True),
        exist_ok=kwargs.get("exist_ok", True),
    )
    return _build_result("path.create", payload)


def _run_path_delete(context: ToolContext, **kwargs) -> ToolResult:
    payload = _FILEGLIDE_FACADE.filesystem.delete_path(
        _default_root(context, kwargs.get("root")),
        kwargs["target"],
        recursive=kwargs.get("recursive", False),
        dry_run=kwargs.get("dry_run", False),
        confirm=kwargs.get("confirm", False),
        missing_ok=kwargs.get("missing_ok", False),
    )
    return _build_result("path.delete", payload)


def _run_path_move(context: ToolContext, **kwargs) -> ToolResult:
    payload = _FILEGLIDE_FACADE.filesystem.move_path(
        _default_root(context, kwargs.get("root")),
        kwargs["source"],
        kwargs["destination"],
        destination_root=kwargs.get("destination_root"),
        dry_run=kwargs.get("dry_run", False),
        confirm=kwargs.get("confirm", False),
    )
    return _build_result("path.move", payload)


def _run_path_exists(context: ToolContext, **kwargs) -> ToolResult:
    payload = _FILEGLIDE_FACADE.filesystem.exists(
        _default_root(context, kwargs.get("root")),
        kwargs["target"],
    )
    return _build_result("path.exists", payload)


def _run_path_list(context: ToolContext, **kwargs) -> ToolResult:
    payload = _FILEGLIDE_FACADE.traversal.list_entries(
        _default_root(context, kwargs.get("root")),
        start=kwargs.get("start", "."),
        kind=kwargs.get("kind", "directory"),
        recursive=kwargs.get("recursive", True),
        max_depth=kwargs.get("max_depth"),
        include=tuple(kwargs.get("include", [])),
        exclude=tuple(kwargs.get("exclude", [])),
    )
    return _build_result("path.list", payload)


def _run_path_search(context: ToolContext, **kwargs) -> ToolResult:
    payload = _FILEGLIDE_FACADE.search.search_names(
        _default_root(context, kwargs.get("root")),
        query=kwargs["query"],
        mode=kwargs.get("mode", "contains"),
        start=kwargs.get("start", "."),
        kind=kwargs.get("kind", "all"),
        recursive=kwargs.get("recursive", True),
        max_depth=kwargs.get("max_depth"),
        include=tuple(kwargs.get("include", [])),
        exclude=tuple(kwargs.get("exclude", [])),
        limit=kwargs.get("limit", 50),
    )
    return _build_result("path.search", payload)


def _run_tree_list(context: ToolContext, **kwargs) -> ToolResult:
    payload = _FILEGLIDE_FACADE.traversal.list_entries(
        _default_root(context, kwargs.get("root")),
        start=kwargs.get("start", "."),
        kind=kwargs.get("kind", "all"),
        recursive=kwargs.get("recursive", True),
        max_depth=kwargs.get("max_depth"),
        include=tuple(kwargs.get("include", [])),
        exclude=tuple(kwargs.get("exclude", [])),
    )
    return _build_result("tree.list", payload)


def _run_text_read(context: ToolContext, **kwargs) -> ToolResult:
    payload = _FILEGLIDE_FACADE.text.read_text(
        _default_root(context, kwargs.get("root")),
        kwargs["target"],
        encoding=kwargs.get("encoding"),
        start_line=kwargs.get("start_line"),
        end_line=kwargs.get("end_line"),
    )
    return _build_result("text.read", payload)


def _run_text_write(context: ToolContext, **kwargs) -> ToolResult:
    payload = _FILEGLIDE_FACADE.text.write_text(
        _default_root(context, kwargs.get("root")),
        kwargs["target"],
        content=kwargs["content"],
        content_source={"source": "tool"},
        mode=kwargs.get("mode", "overwrite"),
        encoding=kwargs.get("encoding"),
        position=kwargs.get("position"),
    )
    return _build_result("text.write", payload)


def _run_text_replace_lines(context: ToolContext, **kwargs) -> ToolResult:
    payload = _FILEGLIDE_FACADE.text.replace_lines(
        _default_root(context, kwargs.get("root")),
        kwargs["target"],
        start_line=kwargs["start_line"],
        end_line=kwargs["end_line"],
        content=kwargs["content"],
        content_source={"source": "tool"},
        encoding=kwargs.get("encoding"),
    )
    return _build_result("text.replace-lines", payload)


def _run_text_insert_anchor(context: ToolContext, **kwargs) -> ToolResult:
    payload = _FILEGLIDE_FACADE.text.insert_by_anchor(
        _default_root(context, kwargs.get("root")),
        kwargs["target"],
        anchor=kwargs["anchor"],
        content=kwargs["content"],
        content_source={"source": "tool"},
        before=kwargs.get("before", False),
        encoding=kwargs.get("encoding"),
    )
    return _build_result("text.insert-anchor", payload)


def _run_text_grep(context: ToolContext, **kwargs) -> ToolResult:
    payload = _FILEGLIDE_FACADE.search.regex_search(
        _default_root(context, kwargs.get("root")),
        pattern=kwargs["pattern"],
        start=kwargs.get("start", "."),
        recursive=kwargs.get("recursive", True),
        max_depth=kwargs.get("max_depth"),
        include=tuple(kwargs.get("include", [])),
        exclude=tuple(kwargs.get("exclude", [])),
        encoding=kwargs.get("encoding"),
    )
    return _build_result("text.grep", payload)


def _run_text_binary_write(context: ToolContext, **kwargs) -> ToolResult:
    payload = _FILEGLIDE_FACADE.binary.write_bytes(
        _default_root(context, kwargs.get("root")),
        kwargs["target"],
        data=base64.b64decode(kwargs["data_base64"]),
        data_source={"source": "tool", "encoding": "base64"},
        mode=kwargs.get("mode", "overwrite"),
        offset=kwargs.get("offset"),
    )
    return _build_result("text.binary-write", payload)


def _run_text_binary_copy(context: ToolContext, **kwargs) -> ToolResult:
    payload = _FILEGLIDE_FACADE.binary.copy_binary(
        _default_root(context, kwargs.get("root")),
        kwargs["source"],
        kwargs["destination"],
    )
    return _build_result("text.binary-copy", payload)


def _run_inspect_size(context: ToolContext, **kwargs) -> ToolResult:
    payload = _FILEGLIDE_FACADE.sizing.stat_size(
        _default_root(context, kwargs.get("root")),
        kwargs["target"],
    )
    return _build_result("inspect.size", payload)


def _run_inspect_bytes(context: ToolContext, **kwargs) -> ToolResult:
    payload = _FILEGLIDE_FACADE.binary.read_bytes(
        _default_root(context, kwargs.get("root")),
        kwargs["target"],
        offset=kwargs.get("offset", 0),
        length=kwargs.get("length"),
    )
    return _build_result("inspect.bytes", payload)


def _run_batch(context: ToolContext, **kwargs) -> ToolResult:
    _ = context

    def _operation_runner(action: str, arguments: dict[str, Any]) -> dict[str, Any]:
        return _FILEGLIDE_FACADE.run_batch_step(action, arguments)

    def _preview_runner(action: str, arguments: dict[str, Any]) -> dict[str, Any]:
        return _FILEGLIDE_FACADE.preview_batch_step(action, arguments)

    payload = _FILEGLIDE_FACADE.batch.execute_plan(
        kwargs["plan"],
        operation_runner=_operation_runner,
        preview_runner=_preview_runner,
        dry_run=kwargs.get("dry_run", True),
    )
    return _build_result("batch.run", payload)


def build_fileglide_tool_specs() -> tuple[ToolSpec, ...]:
    """返回完整 fileglide 工具集合。"""

    return (
        _tool_spec(
            name="file.create",
            description="Create an empty file inside the local workspace.",
            display_name="File create",
            input_schema=_object_schema(
                {
                    "root": {"type": "string"},
                    "target": {"type": "string"},
                    "parents": {"type": "boolean"},
                    "exist_ok": {"type": "boolean"},
                },
                ["target"],
            ),
            handler=_run_file_create,
        ),
        _tool_spec(
            name="file.delete",
            description="Delete a file with optional dry-run and confirmation.",
            display_name="File delete",
            input_schema=_object_schema(
                {
                    "root": {"type": "string"},
                    "target": {"type": "string"},
                    "dry_run": {"type": "boolean"},
                    "confirm": {"type": "boolean"},
                    "missing_ok": {"type": "boolean"},
                },
                ["target"],
            ),
            handler=_run_file_delete,
        ),
        _tool_spec(
            name="file.move",
            description="Move a file within the local workspace.",
            display_name="File move",
            input_schema=_object_schema(
                {
                    "root": {"type": "string"},
                    "source": {"type": "string"},
                    "destination": {"type": "string"},
                    "destination_root": {"type": "string"},
                    "dry_run": {"type": "boolean"},
                    "confirm": {"type": "boolean"},
                },
                ["source", "destination"],
            ),
            handler=_run_file_move,
        ),
        _tool_spec(
            name="file.exists",
            description="Check whether a file exists in the local workspace.",
            display_name="File exists",
            input_schema=_object_schema(
                {
                    "root": {"type": "string"},
                    "target": {"type": "string"},
                },
                ["target"],
            ),
            handler=_run_file_exists,
        ),
        _tool_spec(
            name="file.list",
            description="List files under a root or subdirectory.",
            display_name="File list",
            input_schema=_object_schema(
                {
                    "root": {"type": "string"},
                    "start": {"type": "string"},
                    "recursive": {"type": "boolean"},
                    "max_depth": {"type": "integer"},
                    "include": {"type": "array", "items": {"type": "string"}},
                    "exclude": {"type": "array", "items": {"type": "string"}},
                }
            ),
            handler=_run_file_list,
        ),
        _tool_spec(
            name="file.search",
            description="Search file names under a root or subdirectory.",
            display_name="File search",
            input_schema=_object_schema(
                {
                    "root": {"type": "string"},
                    "query": {"type": "string"},
                    "mode": {"type": "string", "enum": ["exact", "contains", "fuzzy"]},
                    "start": {"type": "string"},
                    "recursive": {"type": "boolean"},
                    "max_depth": {"type": "integer"},
                    "include": {"type": "array", "items": {"type": "string"}},
                    "exclude": {"type": "array", "items": {"type": "string"}},
                    "limit": {"type": "integer"},
                },
                ["query"],
            ),
            handler=_run_file_search,
        ),
        _tool_spec(
            name="path.create",
            description="Create a directory inside the local workspace.",
            display_name="Path create",
            input_schema=_object_schema(
                {
                    "root": {"type": "string"},
                    "target": {"type": "string"},
                    "parents": {"type": "boolean"},
                    "exist_ok": {"type": "boolean"},
                },
                ["target"],
            ),
            handler=_run_path_create,
        ),
        _tool_spec(
            name="path.delete",
            description="Delete a directory with optional recursion.",
            display_name="Path delete",
            input_schema=_object_schema(
                {
                    "root": {"type": "string"},
                    "target": {"type": "string"},
                    "recursive": {"type": "boolean"},
                    "dry_run": {"type": "boolean"},
                    "confirm": {"type": "boolean"},
                    "missing_ok": {"type": "boolean"},
                },
                ["target"],
            ),
            handler=_run_path_delete,
        ),
        _tool_spec(
            name="path.move",
            description="Move a directory within the local workspace.",
            display_name="Path move",
            input_schema=_object_schema(
                {
                    "root": {"type": "string"},
                    "source": {"type": "string"},
                    "destination": {"type": "string"},
                    "destination_root": {"type": "string"},
                    "dry_run": {"type": "boolean"},
                    "confirm": {"type": "boolean"},
                },
                ["source", "destination"],
            ),
            handler=_run_path_move,
        ),
        _tool_spec(
            name="path.exists",
            description="Check whether a path exists in the local workspace.",
            display_name="Path exists",
            input_schema=_object_schema(
                {
                    "root": {"type": "string"},
                    "target": {"type": "string"},
                },
                ["target"],
            ),
            handler=_run_path_exists,
        ),
        _tool_spec(
            name="path.list",
            description="List directories or mixed paths under a root.",
            display_name="Path list",
            input_schema=_object_schema(
                {
                    "root": {"type": "string"},
                    "start": {"type": "string"},
                    "kind": {"type": "string", "enum": ["all", "directory"]},
                    "recursive": {"type": "boolean"},
                    "max_depth": {"type": "integer"},
                    "include": {"type": "array", "items": {"type": "string"}},
                    "exclude": {"type": "array", "items": {"type": "string"}},
                }
            ),
            handler=_run_path_list,
        ),
        _tool_spec(
            name="path.search",
            description="Search file or directory names under a root.",
            display_name="Path search",
            input_schema=_object_schema(
                {
                    "root": {"type": "string"},
                    "query": {"type": "string"},
                    "mode": {"type": "string", "enum": ["exact", "contains", "fuzzy"]},
                    "kind": {"type": "string", "enum": ["all", "directory"]},
                    "start": {"type": "string"},
                    "recursive": {"type": "boolean"},
                    "max_depth": {"type": "integer"},
                    "include": {"type": "array", "items": {"type": "string"}},
                    "exclude": {"type": "array", "items": {"type": "string"}},
                    "limit": {"type": "integer"},
                },
                ["query"],
            ),
            handler=_run_path_search,
        ),
        _tool_spec(
            name="tree.list",
            description="Traverse mixed files and directories under a root.",
            display_name="Tree list",
            input_schema=_object_schema(
                {
                    "root": {"type": "string"},
                    "start": {"type": "string"},
                    "kind": {"type": "string", "enum": ["all", "file", "directory"]},
                    "recursive": {"type": "boolean"},
                    "max_depth": {"type": "integer"},
                    "include": {"type": "array", "items": {"type": "string"}},
                    "exclude": {"type": "array", "items": {"type": "string"}},
                }
            ),
            handler=_run_tree_list,
        ),
        _tool_spec(
            name="text.read",
            description="Read a text file or a selected line range.",
            display_name="Text read",
            input_schema=_object_schema(
                {
                    "root": {"type": "string"},
                    "target": {"type": "string"},
                    "encoding": {"type": "string"},
                    "start_line": {"type": "integer"},
                    "end_line": {"type": "integer"},
                },
                ["target"],
            ),
            handler=_run_text_read,
        ),
        _tool_spec(
            name="text.write",
            description="Write text by overwrite, append, or insert mode.",
            display_name="Text write",
            input_schema=_object_schema(
                {
                    "root": {"type": "string"},
                    "target": {"type": "string"},
                    "content": {"type": "string"},
                    "mode": {"type": "string", "enum": ["overwrite", "append", "insert"]},
                    "encoding": {"type": "string"},
                    "position": {"type": "integer"},
                },
                ["target", "content"],
            ),
            handler=_run_text_write,
        ),
        _tool_spec(
            name="text.replace-lines",
            description="Replace a logical line range in a text file.",
            display_name="Text replace lines",
            input_schema=_object_schema(
                {
                    "root": {"type": "string"},
                    "target": {"type": "string"},
                    "start_line": {"type": "integer"},
                    "end_line": {"type": "integer"},
                    "content": {"type": "string"},
                    "encoding": {"type": "string"},
                },
                ["target", "start_line", "end_line", "content"],
            ),
            handler=_run_text_replace_lines,
        ),
        _tool_spec(
            name="text.insert-anchor",
            description="Insert text before or after a unique anchor.",
            display_name="Text insert anchor",
            input_schema=_object_schema(
                {
                    "root": {"type": "string"},
                    "target": {"type": "string"},
                    "anchor": {"type": "string"},
                    "content": {"type": "string"},
                    "before": {"type": "boolean"},
                    "encoding": {"type": "string"},
                },
                ["target", "anchor", "content"],
            ),
            handler=_run_text_insert_anchor,
        ),
        _tool_spec(
            name="text.grep",
            description="Search text content with a regular expression.",
            display_name="Text grep",
            input_schema=_object_schema(
                {
                    "root": {"type": "string"},
                    "pattern": {"type": "string"},
                    "start": {"type": "string"},
                    "recursive": {"type": "boolean"},
                    "max_depth": {"type": "integer"},
                    "include": {"type": "array", "items": {"type": "string"}},
                    "exclude": {"type": "array", "items": {"type": "string"}},
                    "encoding": {"type": "string"},
                },
                ["pattern"],
            ),
            handler=_run_text_grep,
        ),
        _tool_spec(
            name="text.binary-write",
            description="Write binary bytes from a base64 payload.",
            display_name="Binary write",
            input_schema=_object_schema(
                {
                    "root": {"type": "string"},
                    "target": {"type": "string"},
                    "data_base64": {"type": "string"},
                    "mode": {"type": "string", "enum": ["overwrite", "append", "insert"]},
                    "offset": {"type": "integer"},
                },
                ["target", "data_base64"],
            ),
            handler=_run_text_binary_write,
        ),
        _tool_spec(
            name="text.binary-copy",
            description="Copy a binary file without text decoding.",
            display_name="Binary copy",
            input_schema=_object_schema(
                {
                    "root": {"type": "string"},
                    "source": {"type": "string"},
                    "destination": {"type": "string"},
                },
                ["source", "destination"],
            ),
            handler=_run_text_binary_copy,
        ),
        _tool_spec(
            name="inspect.size",
            description="Inspect file size or aggregated directory size.",
            display_name="Inspect size",
            input_schema=_object_schema(
                {
                    "root": {"type": "string"},
                    "target": {"type": "string"},
                },
                ["target"],
            ),
            handler=_run_inspect_size,
        ),
        _tool_spec(
            name="inspect.bytes",
            description="Inspect binary bytes as hexadecimal content.",
            display_name="Inspect bytes",
            input_schema=_object_schema(
                {
                    "root": {"type": "string"},
                    "target": {"type": "string"},
                    "offset": {"type": "integer"},
                    "length": {"type": "integer"},
                },
                ["target"],
            ),
            handler=_run_inspect_bytes,
        ),
        _tool_spec(
            name="batch.run",
            description="Execute or preview a fileglide batch plan.",
            display_name="Batch run",
            input_schema=_object_schema(
                {
                    "plan": {
                        "type": "object",
                        "properties": {
                            "steps": {"type": "array", "items": {"type": "object"}},
                        },
                        "required": ["steps"],
                    },
                    "dry_run": {"type": "boolean"},
                },
                ["plan"],
            ),
            handler=_run_batch,
        ),
    )
