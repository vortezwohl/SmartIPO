"""主脑模型配置解析与装配入口。

该文件把 `src/model_config.py` 中的静态配置解析为 strands 可直接使用的
`LiteLLMModel`，并集中处理环境变量读取与采样参数覆写保护。
"""

from __future__ import annotations

import os
from typing import Any

from dotenv import load_dotenv
from strands.models.litellm import LiteLLMModel

from src.model_config import (
    AGENT_SESSION_ROUND,
    BRAIN_MODEL_CONFIGS,
    CHANNEL_CONFIGS,
    BrainModelConfig,
    ChannelConfig,
)

load_dotenv()


class ModelHub:
    """按调用点名称装配主脑模型。"""

    def get_brain_model(
        self,
        call_name: str = AGENT_SESSION_ROUND,
        **overrides: Any,
    ) -> LiteLLMModel:
        """返回一个绑定了集中采样参数的主脑模型。

        Args:
            call_name: 主脑调用点名称。
            **overrides: 预留给未来非采样类扩展；采样参数覆写会被拒绝。

        Returns:
            strands 可直接使用的 `LiteLLMModel`。
        """

        _reject_sampling_overrides(overrides)
        config = _get_brain_model_config(call_name)
        channel = _get_channel_config(config.channel)
        params: dict[str, Any] = {
            "temperature": config.temperature,
            "top_p": config.top_p,
        }
        if config.seed is not None:
            params["seed"] = config.seed
        return LiteLLMModel(
            model_id=f"{channel.provider}/{config.model}",
            client_args={
                "api_key": _resolve_api_key(channel, call_name),
                "api_base": _resolve_api_base(channel),
            },
            params=params,
        )


def create_default_model_hub() -> ModelHub:
    """创建默认模型装配入口。"""

    return ModelHub()


def create_default_brain_model(
    call_name: str = AGENT_SESSION_ROUND,
    **overrides: Any,
) -> LiteLLMModel:
    """创建默认主脑模型。"""

    return create_default_model_hub().get_brain_model(
        call_name=call_name,
        **overrides,
    )


def validate_model_config(call_names: tuple[str, ...] = (AGENT_SESSION_ROUND,)) -> None:
    """校验当前主脑模型配置表完整且可用。"""

    if not CHANNEL_CONFIGS:
        raise RuntimeError("src/model_config.py 中没有可用的渠道配置。")
    for channel_name, channel in CHANNEL_CONFIGS.items():
        if not channel.provider.strip():
            raise RuntimeError(f"渠道 '{channel_name}' 缺少 provider。")
        if not channel.api_key_env.strip():
            raise RuntimeError(f"渠道 '{channel_name}' 缺少 api_key_env。")
        if not channel.api_base_env.strip():
            raise RuntimeError(f"渠道 '{channel_name}' 缺少 api_base_env。")
        if not channel.default_api_base.strip():
            raise RuntimeError(f"渠道 '{channel_name}' 缺少 default_api_base。")
    for call_name in call_names:
        config = _get_brain_model_config(call_name)
        if not config.model.strip():
            raise RuntimeError(f"主脑调用点 '{call_name}' 缺少模型名。")
        if config.temperature < 0:
            raise RuntimeError(f"主脑调用点 '{call_name}' 的 temperature 必须 >= 0。")
        if not 0 < config.top_p <= 1:
            raise RuntimeError(f"主脑调用点 '{call_name}' 的 top_p 必须满足 0 < top_p <= 1。")
        if config.seed is not None and not isinstance(config.seed, int):
            raise RuntimeError(f"主脑调用点 '{call_name}' 的 seed 必须是整数或 None。")


def _reject_sampling_overrides(overrides: dict[str, Any]) -> None:
    """拒绝调用点直接覆写集中采样参数。"""

    forbidden = {"temperature", "top_p", "seed"} & set(overrides)
    if forbidden:
        joined = ", ".join(sorted(forbidden))
        raise RuntimeError(
            "主脑采样参数必须来自 src/model_config.py，"
            f"当前覆写字段: {joined}。"
        )


def _get_brain_model_config(call_name: str) -> BrainModelConfig:
    """读取一个主脑调用点配置。"""

    if call_name not in BRAIN_MODEL_CONFIGS:
        raise RuntimeError(f"src/model_config.py 中缺少主脑调用点配置: {call_name}。")
    return BRAIN_MODEL_CONFIGS[call_name]


def _get_channel_config(channel_name: str) -> ChannelConfig:
    """读取一个渠道配置。"""

    if channel_name not in CHANNEL_CONFIGS:
        raise RuntimeError(f"src/model_config.py 中存在未知渠道: {channel_name}。")
    return CHANNEL_CONFIGS[channel_name]


def _resolve_api_key(channel: ChannelConfig, call_name: str) -> str:
    """按渠道约定解析 API Key。"""

    api_key = os.getenv(channel.api_key_env, "").strip()
    if not api_key:
        raise RuntimeError(
            f"{channel.api_key_env} 未配置，无法创建主脑模型 '{call_name}'。"
        )
    return api_key


def _resolve_api_base(channel: ChannelConfig) -> str:
    """按渠道约定解析 API Base。"""

    return os.getenv(channel.api_base_env, channel.default_api_base).strip()
