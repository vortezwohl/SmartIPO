"""运行时服务装配入口。

该包只放最小服务层薄封装，当前提供主脑模型配置解析与装配能力。
"""

from src.service.model_hub import ModelHub, create_default_brain_model, create_default_model_hub

__all__ = [
    "ModelHub",
    "create_default_model_hub",
    "create_default_brain_model",
]
