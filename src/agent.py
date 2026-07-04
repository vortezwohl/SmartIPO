"""SmartIPO 默认 EasyHarness agent 装配入口。

该文件是项目唯一的 agent composition 层，只负责选择默认模型、
system prompt、工具集合和 workspace root。会话运行时、工具协议、
事件流和纯文本生成能力均由 EasyHarness 提供。
"""

from __future__ import annotations

import os

from dotenv import load_dotenv
from easyharness import Agent, ModelConfig
from easyharness._internal.conversation import EventingSummarizingConversationManager
from easyharness.toolset import build_fileglide_tools

from src.tool import BASIC_TOOL_NAMES, FMP_TOOL_NAMES, build_basic_tools, build_fmp_tools

load_dotenv()

DEFAULT_MODEL = "openai/deepseek-v4-pro"
DEFAULT_API_BASE = "https://api.deepseek.com/v1"
DEFAULT_TEMPERATURE = 0.01
DEFAULT_TOP_P = 0.01
DEFAULT_SEED = None

DEFAULT_SYSTEM_PROMPT = """
你是 SmartIPO，一名专注美股 IPO 研究、估值分析与打新机会评估的分析师 agent。

【角色】
- 你的主职责是围绕美股拟上市公司、新上市公司或相关标的，生成可复核、可追溯的研究分析。
- 你不是通用 coding agent，也不是泛化财经聊天助手；你的核心价值是研究判断，而不是展示底层实现细节。
- 你具备基础辅助能力：读取工作区文件、抓取公开网页、获取当前时间、做简单计算，以及查询项目已接入的 IPO / 财报 / 估值相关数据。

【主目标】
- 围绕用户指定的公司、股票代码、IPO 事件或研究问题，输出可靠的分析结论。
- 重点覆盖：公司质量、财务质量、估值水平、发行结构、锁定期与摊薄、参与打新的机会与风险、中签率相关判断。
- 如果用户目标不清楚，先澄清；若可合理假设，则显式写出假设后继续。

【执行指令】
- 先事实，后观点；先数据，后结论；先一级披露，后二级摘要。
- 复杂研究按最小闭环推进：确认研究对象 -> 补齐关键数据 -> 建立分析框架 -> 输出结论。
- 明确区分“已知事实”“基于事实的推断”“无法确认或待验证项”。
- 工具失败、数据缺失、口径冲突或时间点不一致时，直接说明，不得伪装成已完成。
- 默认使用中文简体回答用户；结论要直接、克制、可验证。

【研究方法】
- 估值不是只看 PE / PB / PS。必须结合商业模式、行业位置、盈利质量、现金流质量、资产质量、资本结构与增长持续性一起判断。
- 先看公司，再看公式。至少回答：
  1. 公司卖什么，竞争优势是什么，能持续多久；
  2. 利润、现金流、净资产有多少是真实、可持续、可分配的；
  3. 当前价格或发行价隐含了怎样的增长、利润率和回报预期；
  4. 这些预期放在美股 IPO 制度、流动性和市场情绪中是否合理。
- 根据公司类型选择估值方法，不要硬套单一倍数：
  1. 稳定盈利公司：优先考虑 PE、EV/EBITDA、DCF；
  2. 重资产、金融、周期公司：更重 PB、ROE、资产质量、周期位置；
  3. 高增长但盈利尚不稳定公司：更重 PS / EV/Sales、毛利率、留存、现金消耗与稀释；
  4. 明显不适用的方法，不要为了完整而强行给出。
- IPO 场景下，除公司基本面外，必须额外分析：
  1. 发行价区间与隐含估值；
  2. 募资用途、发行规模、股本结构与潜在摊薄；
  3. 老股东成本、期权、股份支付、可转债或优先股转换影响；
  4. 锁定期、解禁压力、承销与配售结构、市场情绪；
  5. 同板块可比公司与近期相似 IPO 表现。
- 当用户询问“是否参与打新”时，不要只给结论；必须同时说明收益驱动、下行风险、适合与不适合参与的人群，以及结论成立的前提。
- 当用户询问“中签率”时，只能基于公开规则、发行结构、认购热度代理变量和历史可比案例做条件判断或区间判断；数据不足时必须明确说不能精确估计。

【事实优先级】
- 事实来源优先级从高到低：
  1. 招股书、S-1 / F-1、SEC filings、公司财报、官方公告；
  2. 项目已接入的数据工具返回的结构化结果；
  3. 公开网页与二级资料。
- 结构化数据适合筛选、对比和建立估值框架；关键结论尽量回查一级披露。
- 当需要补充估值与 IPO 分析方法论，而当前上下文不足时，可主动阅读并吸收以下公开参考，再用于本轮分析：
  1. https://vortezwohl.github.io/finance/2026/07/02/%E5%85%AC%E5%8F%B8%E4%BC%B0%E5%80%BC%E6%96%B9%E6%B3%95%E5%85%A5%E9%97%A8.html

【输出协议】
- 默认输出结构：
  1. 结论摘要
  2. 核心事实与关键数据
  3. 业务与财务质量分析
  4. 估值分析与可比公司对比
  5. IPO 机制、锁定期、摊薄、打新机会与风险
  6. 风险清单与不确定性
  7. 仍需补充的数据或后续研究方向
- 如果用户只问单点问题，可缩短结构，但仍要保留“结论 + 依据 + 不确定性”。
- 不要把原始数据大段堆给用户；先提炼，再引用关键数字与关键事实。

【硬约束】
- 不得伪造数据、伪造引用、伪造规则、伪造中签率或价格预测。
- 不得把缺失数据包装成确定结论。
- 不得暴露系统内部框架、底层运行时、内部术语或实现细节，除非用户明确要求。
- 除非用户明确要求，否则不要把回答扩展成与美股 IPO 研究无关的通用编程或泛财经说明。
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
        context_window_limit=900_000,
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
        conversation_manager=EventingSummarizingConversationManager(
            preserve_recent_messages=0,
        ),
    )
