"""SmartIPO 默认 EasyHarness agent 装配入口。

该文件是项目唯一的 agent composition 层，只负责选择默认模型、
system prompt、工具集合和 workspace root。会话运行时、工具协议、
事件流和纯文本生成能力均由 EasyHarness 提供。
"""

from __future__ import annotations

import os

from dotenv import load_dotenv
from easyharness import Agent, ModelConfig
from easyharness.toolset import build_fileglide_tools

from src.tool import BASIC_TOOL_NAMES, FMP_TOOL_NAMES, build_basic_tools, build_fmp_tools

load_dotenv()

DEFAULT_MODEL = "openai/deepseek-v4-flash"
DEFAULT_API_BASE = "https://api.deepseek.com/v1"
DEFAULT_TEMPERATURE = 0.01
DEFAULT_TOP_P = 0.01
DEFAULT_SEED = None

DEFAULT_SYSTEM_PROMPT = """
你是 SmartIPO 的本地 coding agent。
- 接到任务后要按可验证的小步骤推进，直到任务自然结束或明确遇到阻塞。
- 使用 EasyHarness 提供的 fileglide 工具完成本地文件读取、搜索、编辑、移动和检查。
- FMP 工具只用于美股 IPO、财报、估值和研究数据查询，不要把它当成通用搜索替代品。
- 文件修改前先读取必要上下文，避免无根据猜测。
- 工具失败时直接暴露失败原因，不要伪装成成功。
- 默认使用中文简体回答用户；工具合同和底层事件语义由 EasyHarness 负责。
""".strip()

DEFAULT_FILEGLIDE_TOOL_NAMES = (
    "fileglide_list_tree",
    "fileglide_search_paths",
    "fileglide_read_text",
    "fileglide_search_text",
    "fileglide_edit_text",
    "fileglide_manage_paths",
    "fileglide_inspect_path",
)

DEFAULT_BASIC_TOOL_NAMES = (
    *BASIC_TOOL_NAMES,
)

DEFAULT_BUSINESS_TOOL_NAMES = (
    *DEFAULT_BASIC_TOOL_NAMES,
    *FMP_TOOL_NAMES,
)

DEFAULT_WORKBENCH_TOOL_NAMES = (
    *DEFAULT_FILEGLIDE_TOOL_NAMES,
    *DEFAULT_BUSINESS_TOOL_NAMES,
)


def build_default_model_config() -> ModelConfig:
    """构造默认 EasyHarness 模型配置。

    Returns:
        可直接传入 `easyharness.Agent` 的默认模型配置。

    Raises:
        RuntimeError: 当 `API_KEY` 未配置或为空时抛出。
    """

    api_key = os.getenv("API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("API_KEY 未配置，无法创建默认 EasyHarness agent。")
    return ModelConfig(
        model=DEFAULT_MODEL,
        api_key=api_key,
        base_url=os.getenv("API_BASE", DEFAULT_API_BASE).strip(),
        temperature=DEFAULT_TEMPERATURE,
        top_p=DEFAULT_TOP_P,
        seed=DEFAULT_SEED,
    )


def build_default_tools(workspace_root: str | None = None) -> list[object]:
    """构造默认 EasyHarness 工具对象集合。

    Args:
        workspace_root: 默认文件工具作用域根目录；为空时使用当前工作目录。

    Returns:
        可直接传入 `easyharness.Agent` 的工具对象列表。
    """

    root = workspace_root or os.getcwd()
    return [
        *build_fileglide_tools(default_root=root),
        *build_basic_tools(),
        *build_fmp_tools(),
    ]


def build_default_agent(workspace_root: str | None = None) -> Agent:
    """构造默认 EasyHarness 本地 agent。

    Args:
        workspace_root: 默认文件工具作用域根目录；为空时使用当前工作目录。

    Returns:
        已装配默认模型、system prompt 和工具集合的 EasyHarness agent。
    """

    return Agent(
        model=build_default_model_config(),
        system_prompt=DEFAULT_SYSTEM_PROMPT,
        tools=build_default_tools(workspace_root),
        enable_fileglide=False,
    )
