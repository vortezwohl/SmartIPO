"""主脑模型集中配置。

该文件只负责维护 SmartIPO 本地 agent 主脑的可编辑配置表，不承担环境变量
读取、SDK 构造或运行时调度职责。第一版只配置一个本地会话主脑调用点，
避免为尚未存在的调用场景提前扩展抽象。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ChannelConfig:
    """描述一个模型渠道与其环境变量映射。"""

    provider: str
    api_key_env: str
    api_base_env: str
    default_api_base: str


@dataclass(frozen=True, slots=True)
class BrainModelConfig:
    """描述一个主脑调用点的集中配置。"""

    channel: str
    model: str
    temperature: float
    top_p: float
    seed: int | None = 42


AGENT_SESSION_ROUND = "agent_session_round"


CHANNEL_CONFIGS: dict[str, ChannelConfig] = {
    "deepseek": ChannelConfig(
        provider="openai",
        api_key_env="API_KEY",
        api_base_env="API_BASE",
        default_api_base="https://api.deepseek.com/v1",
    ),
}


BRAIN_MODEL_CONFIGS: dict[str, BrainModelConfig] = {
    AGENT_SESSION_ROUND: BrainModelConfig(
        channel="deepseek",
        model="deepseek-v4-pro",
        temperature=.01,
        top_p=.01,
        seed=None,
    ),
}
