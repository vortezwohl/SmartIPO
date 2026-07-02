"""文本到文本模型封装。

该文件基于 `litellm` 实现统一的文本生成调用、重试、重复模式检测
和日志记录逻辑。
"""

import logging
import time
import json

import litellm
from overrides import override
from vortezwohl.func import Retry
from requests.exceptions import (
    ConnectTimeout,
    ConnectionError,
    HTTPError,
    ReadTimeout,
    SSLError,
    Timeout,
)

from src import NEW_LINE, BLANK
from src.core.llm import LLM

logger = logging.getLogger('resume-maker.llm')
litellm.drop_params = True
retry = Retry(max_retries=5, delay=True)
RETRYABLE_EXCEPTIONS = (
    ValueError,
    litellm.RateLimitError,
    litellm.Timeout,
    litellm.APIConnectionError,
    litellm.ServiceUnavailableError,
    litellm.InternalServerError,
    litellm.APIError,
    HTTPError,
    ConnectionError,
    SSLError,
    Timeout,
    ConnectTimeout,
    ReadTimeout,
)


class Text2Text(LLM):
    """提供同步与流式文本生成能力的具体实现。"""

    def __init__(
        self,
        provider: str,
        model_name: str,
        api_key: str = '',
        api_base: str = '',
    ):
        """初始化文本生成模型客户端。"""
        super().__init__(
            provider=provider,
            model_name=model_name,
            api_key=api_key,
            api_base=api_base,
        )

    @staticmethod
    def build_message(user_message: str, system_message: str = '') -> list[dict]:
        """把系统提示词与用户提示词整理为消息列表。"""
        messages = []
        if len(system_message):
            messages.append({
                'role': 'system',
                'content': system_message
            })
        messages.append({
            'role': 'user',
            'content': user_message
        })
        return messages

    @override
    def __call__(
        self,
        user_message: str,
        system_message: str = '',
        temperature: float = 1.,
        top_p: float = 1.,
        seed: int | None = 42,
        **kwargs,
    ) -> str:
        """根据 `stream` 参数分派到同步或流式调用。"""
        if not kwargs.get('stream', False):
            return self.completion(
                user_message=user_message,
                system_message=system_message,
                temperature=temperature,
                top_p=top_p,
                seed=seed,
                **kwargs,
            )
        return self.stream_completion(
            user_message=user_message,
            system_message=system_message,
            temperature=temperature,
            top_p=top_p,
            seed=seed,
            **kwargs,
        )

    @retry.on_exceptions(*RETRYABLE_EXCEPTIONS)
    def completion(
        self,
        user_message: str,
        system_message: str = '',
        temperature: float = 1.,
        top_p: float = 1.,
        seed: int | None = 42,
        **kwargs,
    ) -> str:
        """执行一次带重试保护的同步文本生成请求。"""
        if 'stream' in kwargs.keys():
            del kwargs['stream']
        kwargs['temperature'] = temperature
        kwargs['top_p'] = top_p
        kwargs['seed'] = seed
        messages = self.build_message(
            user_message=user_message,
            system_message=system_message,
        )
        logger.debug('\\'
                     f'\n- STAGE: <REQUEST>'
                     f'\n- ENDPOINT: {self.endpoint}'
                     f'\n- PARAMS: {kwargs if kwargs else None}'
                     f'\n- PROMPT: {json.dumps(messages, ensure_ascii=False)}')
        __start_time = time.perf_counter()
        response = litellm.completion(
            model=self.endpoint,
            messages=messages,
            api_key=self._api_key,
            api_base=self._api_base,
            stream=False,
            **kwargs
        )
        llm_completion = response.choices[0].message.content
        if len(str(llm_completion).strip()) < 1:
            raise ValueError('Empty response received.')
        __time_used = time.perf_counter() - __start_time
        logger.debug('\\'
                     f'\n- STAGE: <RESPONSE>'
                     f'\n- ENDPOINT: {self.endpoint}'
                     f'\n- PARAMS: {kwargs if kwargs else None}'
                     f'\n- PROMPT: {json.dumps(messages, ensure_ascii=False)}'
                     f'\n- COMPLETION: {llm_completion.replace(NEW_LINE, BLANK)}'
                     f'\n- TIME_USED: {__time_used} seconds')
        return llm_completion

    def _create_stream(self, messages: list[dict], **kwargs):
        """创建底层流式响应对象。"""
        return litellm.completion(
            model=self.endpoint,
            messages=messages,
            api_key=self._api_key,
            api_base=self._api_base,
            stream=True,
            **kwargs,
        )

    def stream_completion(
        self,
        user_message: str,
        system_message: str = '',
        temperature: float = 1.,
        top_p: float = 1.,
        seed: int | None = 42,
        **kwargs,
    ) -> str:
        """以生成器方式逐块返回流式模型输出。"""
        if 'stream' in kwargs.keys():
            del kwargs['stream']
        kwargs['temperature'] = temperature
        kwargs['top_p'] = top_p
        kwargs['seed'] = seed
        messages = self.build_message(
            user_message=user_message,
            system_message=system_message,
        )
        for chunk in self._create_stream(messages=messages, **kwargs):
            if not chunk.choices[0].finish_reason:
                yield chunk.choices[0].delta.content
