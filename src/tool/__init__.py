"""主脑可调用工具集合。

该包负责定义项目内业务能力的统一 tool 契约与注册入口。当前默认接入
完整 fileglide 本地文件系统工具集，以及现有 Seedream 生图能力。
"""

from src.tool.fileglide_tools import build_fileglide_tool_specs
from src.tool.seedream_image import TOOL_SPEC as SEEDREAM_IMAGE_TOOL_SPEC

__all__ = [
    "build_fileglide_tool_specs",
    "SEEDREAM_IMAGE_TOOL_SPEC",
]
