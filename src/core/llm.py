"""LLM 抽象基类。

该文件定义统一的模型提供方、模型名和接口调用约定，作为具体文本
生成实现的基础父类。凭据解析职责由上层配置模块负责，此处仅保存
已经解析完成的调用参数，避免执行阶段再回退到其他环境变量维度。
"""


class LLM:
    """封装语言模型调用所需的通用配置。"""

    def __init__(
        self,
        provider: str,
        model_name: str,
        api_key: str = "",
        api_base: str = "",
    ):
        """初始化模型提供方、模型名称和鉴权配置。"""
        self._provider = provider
        self._model = model_name
        self._api_key = api_key
        self._api_base = api_base

    @property
    def endpoint(self) -> str:
        """返回传给底层 SDK 的 `provider/model` 端点字符串。"""
        return f"{self._provider}/{self._model}"

    def __call__(
        self,
        user_message: str,
        system_message: str = "",
        temperature: float = 1.0,
        top_p: float = 1.0,
        seed: int | None = 42,
        **kwargs,
    ) -> str:
        """定义统一调用入口，交由子类实现。"""
        _ = (user_message, system_message, temperature, top_p, seed, kwargs)
        ...
