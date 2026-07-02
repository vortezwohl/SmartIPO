"""fileglide 工具注册与适配。

该文件把 fileglide Python facade 的常用本地文件系统能力映射为项目内
`ToolSpec`。第一版直接暴露完整最小能力集，避免再包一层 shell 适配。
"""

from __future__ import annotations

import base64
from typing import Any, Callable

from fileglide.facade import FileGlideFacade

from src.tool.contracts import ToolContext, ToolDoc, ToolPolicies, ToolResult, ToolSpec
from src.tool.framework.policies import (
    FileglideReadonlyErrorMapper,
    FileglideResultFormatter,
    ReadonlyTraversalPolicy,
    ScopedPathPolicy,
    run_with_error_mapper,
)


_FILEGLIDE_FACADE = FileGlideFacade()
_MODEL_ENTRY_LIMIT = 80
_MODEL_LINE_LIMIT = 120
_SCOPED_PATH_POLICY = ScopedPathPolicy()
_READONLY_TRAVERSAL_POLICY = ReadonlyTraversalPolicy(default_recursive=False)
_FILEGLIDE_RESULT_FORMATTER = FileglideResultFormatter(
    model_entry_limit=_MODEL_ENTRY_LIMIT,
    model_line_limit=_MODEL_LINE_LIMIT,
)
_FILEGLIDE_ERROR_MAPPER = FileglideReadonlyErrorMapper()
_FILEGLIDE_POLICIES = ToolPolicies(
    path_policy=_SCOPED_PATH_POLICY,
    traversal_policy=_READONLY_TRAVERSAL_POLICY,
    result_formatter=_FILEGLIDE_RESULT_FORMATTER,
    error_mapper=_FILEGLIDE_ERROR_MAPPER,
)


def _default_root(context: ToolContext, root: str | None) -> str:
    """统一 fileglide 工具默认根目录。"""

    return root or context.workspace_root or "."


def _build_result(name: str, payload: dict[str, Any]) -> ToolResult:
    """把 fileglide 返回值整理为统一工具结果。"""

    return _FILEGLIDE_RESULT_FORMATTER.build_result(name, payload)


def _normalize_readonly_scope(
    context: ToolContext,
    kwargs: dict[str, Any],
    *,
    path_key: str,
) -> tuple[str, str]:
    """把只读工具的绝对路径参数规范化为 root + 相对路径。"""

    return _SCOPED_PATH_POLICY.normalize(
        workspace_root=_default_root(context, kwargs.get("root")),
        explicit_root=kwargs.get("root"),
        raw_value=str(kwargs.get(path_key, ".")).strip() or ".",
        path_key=path_key,
    )


def _run_readonly_operation(
    *,
    tool_name: str,
    root: str,
    path_key: str,
    path_value: str,
    runner: Callable[[], dict[str, Any]],
) -> ToolResult:
    """执行只读 fileglide 调用，并通过公共策略映射结果和错误。"""

    return run_with_error_mapper(
        mapper=_FILEGLIDE_ERROR_MAPPER.map,
        tool_name=tool_name,
        root=root,
        path_key=path_key,
        path_value=path_value,
        runner=runner,
        formatter=_FILEGLIDE_RESULT_FORMATTER,
    )


def _readonly_recursive(kwargs: dict[str, Any], *, default: bool) -> bool:
    """读取只读探索工具的统一递归默认值。"""

    explicit = kwargs.get("recursive")
    if explicit is not None:
        return _READONLY_TRAVERSAL_POLICY.recursive(
            explicit=bool(explicit),
            default=default,
        )
    return _READONLY_TRAVERSAL_POLICY.recursive(
        explicit=None,
        default=default,
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
    description: ToolDoc | str,
    display_name: str,
    input_schema: dict[str, Any],
    handler: Callable[..., ToolResult],
) -> ToolSpec:
    """构造一个 fileglide 工具定义。"""

    normalized_doc = description
    if isinstance(description, ToolDoc):
        normalized_doc = _merge_schema_parameter_docs(description, input_schema)
    return ToolSpec(
        name=name,
        description=description if isinstance(description, str) else "",
        display_name=display_name,
        input_schema=input_schema,
        handler=handler,
        tool_kind="fileglide",
        doc=normalized_doc if isinstance(normalized_doc, ToolDoc) else None,
        policies=_FILEGLIDE_POLICIES,
    )


def _tool_description(
    *,
    purpose: str,
    when_to_use: tuple[str, ...],
    parameters: tuple[str, ...],
    returns: tuple[str, ...],
    common_failures: tuple[str, ...],
) -> ToolDoc:
    """构造结构化英文工具文档。"""

    return ToolDoc(
        purpose=purpose,
        when_to_use=when_to_use,
        parameters=parameters,
        returns=returns,
        common_failures=common_failures,
    )


def _merge_schema_parameter_docs(doc: ToolDoc, input_schema: dict[str, Any]) -> ToolDoc:
    """用 schema 字段补齐 fileglide 的参数文档，避免重复手写样板。"""

    properties = input_schema.get("properties", {})
    if not isinstance(properties, dict):
        return doc
    documented_names = {
        item.split("`")[1]
        for item in doc.parameters
        if item.count("`") >= 2
    }
    merged_parameters = list(doc.parameters)
    for field_name in properties:
        if field_name in documented_names:
            continue
        merged_parameters.append(
            f"`{field_name}`: Additional structured input field supported by this tool."
        )
    return ToolDoc(
        purpose=doc.purpose,
        when_to_use=doc.when_to_use,
        parameters=tuple(merged_parameters),
        returns=doc.returns,
        common_failures=doc.common_failures,
        notes=doc.notes,
    )


_ROOT_SCOPE_PARAMETER = (
    "`root`: Scope root used to resolve every relative path. Omit it to use "
    "the current agent workspace root."
)
_TARGET_PATH_PARAMETER = (
    "`target`: Path relative to `root`. Use an absolute path only when you "
    "intend the wrapper to normalize it into a scope root plus a root-relative "
    "target."
)
_START_PATH_PARAMETER = (
    "`start`: Traversal start path relative to `root`. Use `.` to start at the "
    "scope root itself."
)
_RECURSIVE_PARAMETER = (
    "`recursive`: Whether traversal should descend into subdirectories. Omit it "
    "to keep exploration shallow for safer recovery."
)
_MAX_DEPTH_PARAMETER = (
    "`max_depth`: Optional recursion depth cap. Omit it when you want the tool "
    "to use its natural depth behavior."
)
_INCLUDE_PARAMETER = (
    "`include`: Optional glob filters that must match for an entry to be "
    "returned."
)
_EXCLUDE_PARAMETER = (
    "`exclude`: Optional glob filters that suppress matching entries."
)
_COMMON_SCOPE_FAILURES = (
    "Scope violation: the requested path escapes the current root. Retry with "
    "the correct root anchor and a root-relative path.",
    "Target missing: the requested start path or file does not exist inside "
    "the current root.",
)
_COMMON_LIST_FAILURES = _COMMON_SCOPE_FAILURES + (
    "Permission denied: traversal reached a protected location. Retry with a "
    "narrower `root`, a narrower `start`, or `recursive=false`.",
)
_ENTRY_RETURN = (
    "`entry`: Metadata for the target path. Expected fields include `path`, "
    "`relative_path`, `name`, `kind`, and `exists`."
)
_LIST_RETURNS = (
    "`entries`: Listed entries. Each entry includes `path`, `relative_path`, "
    "`name`, `kind`, `exists`, `depth`, and `size_bytes`.",
    "`scope`: Effective traversal scope, including `root`, `start`, "
    "`recursive`, `max_depth`, `include`, `exclude`, and `kind`.",
    "`count`: Number of returned entries.",
)
_SEARCH_RETURNS = (
    "`matches`: Matching entries returned by the search operation.",
    "`scope`: Effective traversal scope used during the search.",
    "`query` or `pattern`: The search expression that was executed.",
    "`count`: Number of returned matches.",
)
_WRITE_RETURNS = (
    _ENTRY_RETURN,
    "`encoding`: Encoding that was used or detected for the write operation.",
    "`verification`: Post-write verification metadata from fileglide.",
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
    root, start = _normalize_readonly_scope(
        context,
        kwargs,
        path_key="start",
    )
    return _run_readonly_operation(
        tool_name="file.list",
        root=root,
        path_key="start",
        path_value=start,
        runner=lambda: _FILEGLIDE_FACADE.traversal.list_entries(
            root,
            start=start,
            kind="file",
            recursive=_readonly_recursive(kwargs, default=False),
            max_depth=kwargs.get("max_depth"),
            include=tuple(kwargs.get("include", [])),
            exclude=tuple(kwargs.get("exclude", [])),
        ),
    )


def _run_file_search(context: ToolContext, **kwargs) -> ToolResult:
    root, start = _normalize_readonly_scope(
        context,
        kwargs,
        path_key="start",
    )
    return _run_readonly_operation(
        tool_name="file.search",
        root=root,
        path_key="start",
        path_value=start,
        runner=lambda: _FILEGLIDE_FACADE.search.search_names(
            root,
            query=kwargs["query"],
            mode=kwargs.get("mode", "contains"),
            start=start,
            kind="file",
            recursive=_readonly_recursive(kwargs, default=True),
            max_depth=kwargs.get("max_depth"),
            include=tuple(kwargs.get("include", [])),
            exclude=tuple(kwargs.get("exclude", [])),
            limit=kwargs.get("limit", 50),
        ),
    )


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
    root, start = _normalize_readonly_scope(
        context,
        kwargs,
        path_key="start",
    )
    return _run_readonly_operation(
        tool_name="path.list",
        root=root,
        path_key="start",
        path_value=start,
        runner=lambda: _FILEGLIDE_FACADE.traversal.list_entries(
            root,
            start=start,
            kind=kwargs.get("kind", "directory"),
            recursive=_readonly_recursive(kwargs, default=False),
            max_depth=kwargs.get("max_depth"),
            include=tuple(kwargs.get("include", [])),
            exclude=tuple(kwargs.get("exclude", [])),
        ),
    )


def _run_path_search(context: ToolContext, **kwargs) -> ToolResult:
    root, start = _normalize_readonly_scope(
        context,
        kwargs,
        path_key="start",
    )
    return _run_readonly_operation(
        tool_name="path.search",
        root=root,
        path_key="start",
        path_value=start,
        runner=lambda: _FILEGLIDE_FACADE.search.search_names(
            root,
            query=kwargs["query"],
            mode=kwargs.get("mode", "contains"),
            start=start,
            kind=kwargs.get("kind", "all"),
            recursive=_readonly_recursive(kwargs, default=True),
            max_depth=kwargs.get("max_depth"),
            include=tuple(kwargs.get("include", [])),
            exclude=tuple(kwargs.get("exclude", [])),
            limit=kwargs.get("limit", 50),
        ),
    )


def _run_tree_list(context: ToolContext, **kwargs) -> ToolResult:
    root, start = _normalize_readonly_scope(
        context,
        kwargs,
        path_key="start",
    )
    return _run_readonly_operation(
        tool_name="tree.list",
        root=root,
        path_key="start",
        path_value=start,
        runner=lambda: _FILEGLIDE_FACADE.traversal.list_entries(
            root,
            start=start,
            kind=kwargs.get("kind", "all"),
            recursive=_readonly_recursive(kwargs, default=True),
            max_depth=kwargs.get("max_depth"),
            include=tuple(kwargs.get("include", [])),
            exclude=tuple(kwargs.get("exclude", [])),
        ),
    )


def _run_text_read(context: ToolContext, **kwargs) -> ToolResult:
    root, target = _normalize_readonly_scope(
        context,
        kwargs,
        path_key="target",
    )
    return _run_readonly_operation(
        tool_name="text.read",
        root=root,
        path_key="target",
        path_value=target,
        runner=lambda: _FILEGLIDE_FACADE.text.read_text(
            root,
            target,
            encoding=kwargs.get("encoding"),
            start_line=kwargs.get("start_line"),
            end_line=kwargs.get("end_line"),
        ),
    )


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
    root, start = _normalize_readonly_scope(
        context,
        kwargs,
        path_key="start",
    )
    return _run_readonly_operation(
        tool_name="text.grep",
        root=root,
        path_key="start",
        path_value=start,
        runner=lambda: _FILEGLIDE_FACADE.search.regex_search(
            root,
            pattern=kwargs["pattern"],
            start=start,
            recursive=_readonly_recursive(kwargs, default=True),
            max_depth=kwargs.get("max_depth"),
            include=tuple(kwargs.get("include", [])),
            exclude=tuple(kwargs.get("exclude", [])),
            encoding=kwargs.get("encoding"),
        ),
    )


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
            description=_tool_description(
                purpose="Create an empty file inside a scoped root.",
                when_to_use=(
                    "You need a file to exist before another step writes or moves content.",
                    "You want a filesystem-safe alternative to shell redirection for bootstrapping a file path.",
                ),
                parameters=(
                    _ROOT_SCOPE_PARAMETER,
                    _TARGET_PATH_PARAMETER,
                    "`parents`: Create missing parent directories before creating the file.",
                    "`exist_ok`: Allow the operation to succeed when the file already exists.",
                ),
                returns=(
                    _ENTRY_RETURN,
                    "`created`: Whether this call created a new file.",
                ),
                common_failures=(
                    "Target already exists and `exist_ok` is false.",
                    "Parent directories are missing and `parents` is false.",
                    *_COMMON_SCOPE_FAILURES,
                ),
            ),
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
            description=_tool_description(
                purpose="Delete a file inside a scoped root with explicit safety controls.",
                when_to_use=(
                    "You want to remove one file without invoking shell commands.",
                    "You need a dry-run or explicit confirmation step before destructive file removal.",
                ),
                parameters=(
                    _ROOT_SCOPE_PARAMETER,
                    _TARGET_PATH_PARAMETER,
                    "`dry_run`: Preview the deletion without mutating the filesystem.",
                    "`confirm`: Required confirmation flag for destructive execution.",
                    "`missing_ok`: Treat a missing target as a successful no-op.",
                ),
                returns=(
                    _ENTRY_RETURN,
                    "`preview` or equivalent delete metadata describing the removal plan or result.",
                ),
                common_failures=(
                    "Deletion requires confirmation and `confirm` is false.",
                    "Target is missing and `missing_ok` is false.",
                    *_COMMON_SCOPE_FAILURES,
                ),
            ),
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
            description=_tool_description(
                purpose="Move or rename a file between scoped locations.",
                when_to_use=(
                    "You need to rename a file or move it to another directory.",
                    "You want an explicit, scope-aware move operation instead of shell-level path manipulation.",
                ),
                parameters=(
                    _ROOT_SCOPE_PARAMETER,
                    "`source`: Source path relative to `root`.",
                    "`destination`: Destination path relative to `destination_root` when provided, otherwise relative to `root`.",
                    "`destination_root`: Optional alternate scope root for the destination side of the move.",
                    "`dry_run`: Preview the move without mutating the filesystem.",
                    "`confirm`: Required confirmation flag when the underlying operation demands it.",
                ),
                returns=(
                    "`source_entry` or equivalent source metadata describing what moved.",
                    "`destination_entry` or equivalent destination metadata describing the final path.",
                    "Additional move metadata from fileglide, such as preview or confirmation state.",
                ),
                common_failures=(
                    "Source is missing inside the current root.",
                    "Destination escapes the allowed root or destination root.",
                    "A destructive move requires confirmation and `confirm` is false.",
                ),
            ),
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
            description=_tool_description(
                purpose="Check whether a file exists inside a scoped root.",
                when_to_use=(
                    "You need a cheap existence check before reading, writing, moving, or deleting.",
                    "You want the tool to resolve a root-relative file path and report canonical metadata.",
                ),
                parameters=(
                    _ROOT_SCOPE_PARAMETER,
                    _TARGET_PATH_PARAMETER,
                ),
                returns=(
                    _ENTRY_RETURN,
                    "The `exists` field inside `entry`, which tells you whether the target currently exists.",
                ),
                common_failures=_COMMON_SCOPE_FAILURES,
            ),
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
            description=_tool_description(
                purpose="List files inside a scoped root without opening file contents.",
                when_to_use=(
                    "You need to inspect which files exist before reading, editing, or moving them.",
                    "You want a narrow exploration step near a drive root or large directory tree.",
                ),
                parameters=(
                    _ROOT_SCOPE_PARAMETER,
                    _START_PATH_PARAMETER,
                    _RECURSIVE_PARAMETER,
                    _MAX_DEPTH_PARAMETER,
                    _INCLUDE_PARAMETER,
                    _EXCLUDE_PARAMETER,
                ),
                returns=_LIST_RETURNS,
                common_failures=_COMMON_LIST_FAILURES,
            ),
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
            description=_tool_description(
                purpose="Search file names inside a scoped root.",
                when_to_use=(
                    "You know part of a file name but not its exact location.",
                    "You want a search-oriented alternative to listing every file manually.",
                ),
                parameters=(
                    _ROOT_SCOPE_PARAMETER,
                    "`query`: Search text to match against file names.",
                    "`mode`: Matching mode. Use `exact`, `contains`, or `fuzzy` depending on how precise the name is.",
                    _START_PATH_PARAMETER,
                    _RECURSIVE_PARAMETER,
                    _MAX_DEPTH_PARAMETER,
                    _INCLUDE_PARAMETER,
                    _EXCLUDE_PARAMETER,
                    "`limit`: Maximum number of matches to return.",
                ),
                returns=_SEARCH_RETURNS,
                common_failures=_COMMON_LIST_FAILURES,
            ),
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
            description=_tool_description(
                purpose="Create a directory inside a scoped root.",
                when_to_use=(
                    "You need a destination directory before writing files or moving content.",
                    "You want a scope-aware directory creation step instead of shell commands.",
                ),
                parameters=(
                    _ROOT_SCOPE_PARAMETER,
                    _TARGET_PATH_PARAMETER,
                    "`parents`: Create missing parent directories as needed.",
                    "`exist_ok`: Allow the operation to succeed if the directory already exists.",
                ),
                returns=(
                    _ENTRY_RETURN,
                    "`created`: Whether this call created a new directory.",
                ),
                common_failures=(
                    "Target already exists and `exist_ok` is false.",
                    "Parent directories are missing and `parents` is false.",
                    *_COMMON_SCOPE_FAILURES,
                ),
            ),
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
            description=_tool_description(
                purpose="Delete a directory inside a scoped root with explicit safety controls.",
                when_to_use=(
                    "You need to remove a directory tree through a guarded API.",
                    "You want dry-run, confirmation, or missing-target behavior instead of ad hoc shell deletion.",
                ),
                parameters=(
                    _ROOT_SCOPE_PARAMETER,
                    _TARGET_PATH_PARAMETER,
                    "`recursive`: Delete nested content instead of only an empty directory.",
                    "`dry_run`: Preview the deletion without mutating the filesystem.",
                    "`confirm`: Required confirmation flag for destructive execution.",
                    "`missing_ok`: Treat a missing target as a successful no-op.",
                ),
                returns=(
                    _ENTRY_RETURN,
                    "`preview` or equivalent delete metadata describing the removal plan or result.",
                ),
                common_failures=(
                    "Deletion requires confirmation and `confirm` is false.",
                    "Target is missing and `missing_ok` is false.",
                    "A non-empty directory requires `recursive=true`.",
                    *_COMMON_SCOPE_FAILURES,
                ),
            ),
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
            description=_tool_description(
                purpose="Move or rename a directory between scoped locations.",
                when_to_use=(
                    "You need to rename a directory or relocate it under another parent path.",
                    "You want a root-aware directory move instead of manual shell path handling.",
                ),
                parameters=(
                    _ROOT_SCOPE_PARAMETER,
                    "`source`: Source path relative to `root`.",
                    "`destination`: Destination path relative to `destination_root` when provided, otherwise relative to `root`.",
                    "`destination_root`: Optional alternate scope root for the destination side of the move.",
                    "`dry_run`: Preview the move without mutating the filesystem.",
                    "`confirm`: Required confirmation flag when the underlying operation demands it.",
                ),
                returns=(
                    "`source_entry` or equivalent source metadata describing what moved.",
                    "`destination_entry` or equivalent destination metadata describing the final path.",
                    "Additional move metadata from fileglide, such as preview or confirmation state.",
                ),
                common_failures=(
                    "Source is missing inside the current root.",
                    "Destination escapes the allowed root or destination root.",
                    "A destructive move requires confirmation and `confirm` is false.",
                ),
            ),
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
            description=_tool_description(
                purpose="Check whether any filesystem path exists inside a scoped root.",
                when_to_use=(
                    "You need a quick existence check before creating, moving, reading, or deleting a path.",
                    "You want normalized metadata for a path that might be either a file or a directory.",
                ),
                parameters=(
                    _ROOT_SCOPE_PARAMETER,
                    _TARGET_PATH_PARAMETER,
                ),
                returns=(
                    _ENTRY_RETURN,
                    "The `exists` field inside `entry`, which tells you whether the target currently exists.",
                ),
                common_failures=_COMMON_SCOPE_FAILURES,
            ),
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
            description=_tool_description(
                purpose="List directories or mixed paths inside a scoped root.",
                when_to_use=(
                    "You need the high-level shape of a directory tree before reading files.",
                    "You want the safest first exploration step near a drive root, repository root, or large directory.",
                ),
                parameters=(
                    _ROOT_SCOPE_PARAMETER,
                    _START_PATH_PARAMETER,
                    "`kind`: Entry kind filter. Use `directory` for folder-only exploration or `all` for mixed entries.",
                    _RECURSIVE_PARAMETER,
                    _MAX_DEPTH_PARAMETER,
                    _INCLUDE_PARAMETER,
                    _EXCLUDE_PARAMETER,
                ),
                returns=_LIST_RETURNS,
                common_failures=_COMMON_LIST_FAILURES,
            ),
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
            description=_tool_description(
                purpose="Search file or directory names inside a scoped root.",
                when_to_use=(
                    "You know part of a path name but not where it lives.",
                    "You want to search both files and directories before deciding which one to inspect next.",
                ),
                parameters=(
                    _ROOT_SCOPE_PARAMETER,
                    "`query`: Search text to match against path names.",
                    "`mode`: Matching mode. Use `exact`, `contains`, or `fuzzy`.",
                    "`kind`: Whether to search `all` entries or only `directory` entries.",
                    _START_PATH_PARAMETER,
                    _RECURSIVE_PARAMETER,
                    _MAX_DEPTH_PARAMETER,
                    _INCLUDE_PARAMETER,
                    _EXCLUDE_PARAMETER,
                    "`limit`: Maximum number of matches to return.",
                ),
                returns=_SEARCH_RETURNS,
                common_failures=_COMMON_LIST_FAILURES,
            ),
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
            description=_tool_description(
                purpose="Traverse mixed files and directories inside a scoped root.",
                when_to_use=(
                    "You need a combined view of files and directories in one traversal step.",
                    "You want a tree-like inventory before choosing narrower list or read operations.",
                ),
                parameters=(
                    _ROOT_SCOPE_PARAMETER,
                    _START_PATH_PARAMETER,
                    "`kind`: Entry kind filter. Use `all`, `file`, or `directory`.",
                    _RECURSIVE_PARAMETER,
                    _MAX_DEPTH_PARAMETER,
                    _INCLUDE_PARAMETER,
                    _EXCLUDE_PARAMETER,
                ),
                returns=_LIST_RETURNS,
                common_failures=_COMMON_LIST_FAILURES,
            ),
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
            description=_tool_description(
                purpose="Read text content from a file inside a scoped root.",
                when_to_use=(
                    "You need file contents to understand or edit code, config, or documentation.",
                    "You want a line-aware read step instead of dumping an entire file blindly.",
                ),
                parameters=(
                    _ROOT_SCOPE_PARAMETER,
                    _TARGET_PATH_PARAMETER,
                    "`encoding`: Optional override for the expected text encoding.",
                    "`start_line`: First 1-based line number to include when you need a partial read.",
                    "`end_line`: Last 1-based line number to include when you need a partial read.",
                ),
                returns=(
                    _ENTRY_RETURN,
                    "`content`: The selected text body.",
                    "`lines`: Line-aware representation of the selected content, with `line_number` and `text` fields.",
                    "`line_count`: Number of lines in the returned selection.",
                    "`selection`: Selection metadata when a partial line range is used.",
                    "`encoding`: Encoding details used for decoding the file.",
                ),
                common_failures=(
                    *_COMMON_SCOPE_FAILURES,
                    "Target is binary or cannot be decoded with the effective encoding.",
                    "The requested line range is invalid for the current file.",
                ),
            ),
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
            description=_tool_description(
                purpose="Write text content to a file inside a scoped root.",
                when_to_use=(
                    "You need to create, replace, append, or insert text without leaving the fileglide tool chain.",
                    "You want fileglide verification metadata after a text write.",
                ),
                parameters=(
                    _ROOT_SCOPE_PARAMETER,
                    _TARGET_PATH_PARAMETER,
                    "`content`: Text to write into the target file.",
                    "`mode`: Write mode. Use `overwrite`, `append`, or `insert`.",
                    "`encoding`: Optional output encoding override.",
                    "`position`: Byte or character insertion position used when `mode` is `insert`.",
                ),
                returns=(
                    *_WRITE_RETURNS,
                    "`write_mode`: Effective write mode used by the operation.",
                    "`before_size_bytes` and `after_size_bytes`: File sizes before and after the write.",
                    "`insert_position`: Final insertion position when insert mode is used.",
                    "`content_source`: Metadata describing where the written content came from.",
                ),
                common_failures=(
                    *_COMMON_SCOPE_FAILURES,
                    "Encoding risk: the write cannot be completed safely with the requested encoding.",
                    "Insert mode requires a valid insertion position inside the target file.",
                ),
            ),
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
            description=_tool_description(
                purpose="Replace a logical line range inside a text file.",
                when_to_use=(
                    "You know the exact line span to rewrite and want a deterministic edit.",
                    "You want a safer alternative to ad hoc regex replacement for line-bounded changes.",
                ),
                parameters=(
                    _ROOT_SCOPE_PARAMETER,
                    _TARGET_PATH_PARAMETER,
                    "`start_line`: First 1-based line number to replace.",
                    "`end_line`: Last 1-based line number to replace.",
                    "`content`: Replacement text for the selected line range.",
                    "`encoding`: Optional encoding override for the edit.",
                ),
                returns=(
                    *_WRITE_RETURNS,
                    "`changed_range`: The final line range that was replaced.",
                    "`replacement_line_count`: Number of logical lines inserted by the replacement content.",
                    "`after_size_bytes`: File size after the replacement.",
                    "`content_source`: Metadata describing where the replacement content came from.",
                ),
                common_failures=(
                    *_COMMON_SCOPE_FAILURES,
                    "The requested line range is invalid for the current file.",
                    "Encoding risk: the replacement cannot be completed safely with the requested encoding.",
                ),
            ),
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
            description=_tool_description(
                purpose="Insert text before or after a unique anchor inside a text file.",
                when_to_use=(
                    "You know a stable anchor string but not an exact line number.",
                    "You want deterministic insertion semantics around a unique marker.",
                ),
                parameters=(
                    _ROOT_SCOPE_PARAMETER,
                    _TARGET_PATH_PARAMETER,
                    "`anchor`: Unique anchor text that identifies the insertion point.",
                    "`content`: Text to insert around the anchor.",
                    "`before`: Insert before the anchor when true; otherwise insert after it.",
                    "`encoding`: Optional encoding override for the edit.",
                ),
                returns=(
                    *_WRITE_RETURNS,
                    "`anchor`: The anchor text used for the insertion.",
                    "`insert_position`: Final insertion position resolved from the anchor.",
                    "`write_mode`: Effective insertion mode used by fileglide.",
                    "`after_size_bytes`: File size after the insertion.",
                    "`content_source`: Metadata describing where the inserted content came from.",
                ),
                common_failures=(
                    *_COMMON_SCOPE_FAILURES,
                    "The anchor is missing or not unique enough for a deterministic insertion.",
                    "Encoding risk: the insertion cannot be completed safely with the requested encoding.",
                ),
            ),
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
            description=_tool_description(
                purpose="Search text content with a regular expression inside a scoped root.",
                when_to_use=(
                    "You need to find matching text before deciding which file or line range to read next.",
                    "You want content-aware discovery instead of file-name-only search.",
                ),
                parameters=(
                    _ROOT_SCOPE_PARAMETER,
                    "`pattern`: Regular expression used to match text content.",
                    _START_PATH_PARAMETER,
                    _RECURSIVE_PARAMETER,
                    _MAX_DEPTH_PARAMETER,
                    _INCLUDE_PARAMETER,
                    _EXCLUDE_PARAMETER,
                    "`encoding`: Optional encoding override for text decoding during search.",
                ),
                returns=(
                    "`matches`: Matching text hits returned by the search operation.",
                    "`scope`: Effective traversal scope used during the search.",
                    "`pattern`: The regular expression that was executed.",
                    "`count`: Number of returned matches.",
                ),
                common_failures=(
                    *_COMMON_LIST_FAILURES,
                    "The regular expression is invalid.",
                    "A matching file cannot be decoded with the effective encoding.",
                ),
            ),
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
            description=_tool_description(
                purpose="Write binary bytes to a file from a base64 payload.",
                when_to_use=(
                    "You need to create or replace binary content without text decoding.",
                    "You already have bytes encoded as base64 and want a filesystem-safe write step.",
                ),
                parameters=(
                    _ROOT_SCOPE_PARAMETER,
                    _TARGET_PATH_PARAMETER,
                    "`data_base64`: Base64-encoded bytes to write.",
                    "`mode`: Write mode. Use `overwrite`, `append`, or `insert`.",
                    "`offset`: Optional byte offset for insert or partial-write flows.",
                ),
                returns=(
                    _ENTRY_RETURN,
                    "`write_mode`: Effective binary write mode used by the operation.",
                    "`content_source`: Metadata describing the base64 input source.",
                    "`before_size_bytes` and `after_size_bytes`: File sizes before and after the write.",
                ),
                common_failures=(
                    *_COMMON_SCOPE_FAILURES,
                    "The base64 payload is invalid or cannot be decoded.",
                    "Insert mode or offset usage is invalid for the current target.",
                ),
            ),
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
            description=_tool_description(
                purpose="Copy a binary file without text decoding.",
                when_to_use=(
                    "You need an exact byte-for-byte copy of a binary asset.",
                    "You want to avoid accidental text decoding or newline normalization.",
                ),
                parameters=(
                    _ROOT_SCOPE_PARAMETER,
                    "`source`: Source path relative to `root`.",
                    "`destination`: Destination path relative to `root`.",
                ),
                returns=(
                    "`source_entry` or equivalent source metadata describing what was copied.",
                    "`destination_entry` or equivalent destination metadata describing the copied target.",
                    "Binary copy metadata from fileglide, including resulting size information when available.",
                ),
                common_failures=(
                    *_COMMON_SCOPE_FAILURES,
                    "The source file is missing.",
                    "The destination path is invalid or blocked by filesystem permissions.",
                ),
            ),
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
            description=_tool_description(
                purpose="Inspect the size of a file or the aggregated size of a directory.",
                when_to_use=(
                    "You need byte-size information before reading, copying, or editing content.",
                    "You want a structured size inspection instead of a shell-specific stat command.",
                ),
                parameters=(
                    _ROOT_SCOPE_PARAMETER,
                    _TARGET_PATH_PARAMETER,
                ),
                returns=(
                    _ENTRY_RETURN,
                    "`size_bytes`: Size of the target in bytes.",
                    "`aggregate`: Aggregated sizing metadata when the target is a directory.",
                ),
                common_failures=_COMMON_SCOPE_FAILURES,
            ),
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
            description=_tool_description(
                purpose="Inspect a binary slice and return it as hexadecimal content.",
                when_to_use=(
                    "You need to inspect raw bytes without decoding them as text.",
                    "You want a bounded binary preview before modifying or copying a file.",
                ),
                parameters=(
                    _ROOT_SCOPE_PARAMETER,
                    _TARGET_PATH_PARAMETER,
                    "`offset`: Byte offset where the binary read should begin.",
                    "`length`: Optional number of bytes to read from the offset.",
                ),
                returns=(
                    _ENTRY_RETURN,
                    "`content_hex`: Hexadecimal representation of the selected byte slice.",
                    "`offset`: Effective read offset.",
                    "`length`: Number of bytes that were read.",
                    "`size_bytes`: Total size of the underlying file.",
                ),
                common_failures=(
                    *_COMMON_SCOPE_FAILURES,
                    "The target is missing or is not readable as a binary source.",
                    "The requested offset or length falls outside the valid byte range.",
                ),
            ),
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
            description=_tool_description(
                purpose="Execute or preview a multi-step fileglide batch plan.",
                when_to_use=(
                    "You need to coordinate several fileglide actions as one structured plan.",
                    "You want to inspect destructive steps in dry-run mode before execution.",
                ),
                parameters=(
                    "`plan`: Batch plan object. The `steps` array describes each action and its arguments.",
                    "`dry_run`: Preview the plan without mutating the filesystem when true.",
                ),
                returns=(
                    "`steps`: Per-step execution or preview results from the batch engine.",
                    "`summary` or equivalent batch metadata describing the overall outcome.",
                    "`preview`: Dry-run details when the plan is executed in preview mode.",
                ),
                common_failures=(
                    "A step action is unsupported by the batch adapter.",
                    "A step argument set does not match the target fileglide action.",
                    "An executed step fails with the underlying fileglide error for that action.",
                ),
            ),
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
