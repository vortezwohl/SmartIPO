<div align="center">
  <h1>OpenBuffett</h1>
  <p>
    <strong>
      一个以巴菲特式方法研究公司的自主智能体。<br>提供专业级公司研究、可比分析与严谨的价格发现能力。
    </strong>
  </p>
  <p>
    <a href="https://github.com/vortezwohl/EasyHarness">EasyHarness</a>
    ·
    <a href="https://github.com/Textualize/textual">Textual</a>
    ·
    <a href="https://site.financialmodelingprep.com/">FMP</a>
  </p>
  <p>
    <img src="https://img.shields.io/badge/python-3.10%2B-3776AB?logo=python&amp;logoColor=white" alt="Python 3.10+" />
    <a href="https://github.com/vortezwohl/EasyHarness">
      <img src="https://img.shields.io/badge/EasyHarness-agent%20loop-2563EB?logo=github&amp;logoColor=white" alt="EasyHarness" />
    </a>
    <a href="https://github.com/Textualize/textual">
      <img src="https://img.shields.io/badge/Textual-TUI-1F6FEB?logo=github&amp;logoColor=white" alt="Textual" />
    </a>
    <a href="https://site.financialmodelingprep.com/">
      <img src="https://img.shields.io/badge/FMP-financial%20data-0F766E?logoColor=white" alt="FMP" />
    </a>
  </p>
  <p>
    <sub>
      致力于缩小散户与机构之间的投研能力鸿沟。
    </sub>
  </p>
</div>

<h4 align="center">
  <p>
    <a href="../README.md">English</a> |
    <b>简体中文</b>
  </p>
</h4>

## 项目简介

OpenBuffett 是一个以美股估值研究为主轴的本地投研 workbench，目标是帮助投资者用更接近机构的方法论来做公司研究。

它把 AI 的大规模信息处理能力，与结构化的金融研究工作流结合起来，让用户可以更系统地研究企业、对照可比公司，并更严谨地理解估值。其核心目标，是尽可能缩小专业研究员能处理的信息量，与普通投资者现实中能完成的研究深度之间的差距。

落到实践层面，OpenBuffett 想做的是：让更多投资者也能以长期基本面投资者常见的深度、结构和怀疑精神去研究公司。

## 痛点与应用场景

大多数散户并不是因为没有兴趣而做不好投研，而是因为严肃的估值研究需要阅读大量一手资料、理解较深的会计与财务语境，并在时间压力下完成高强度的信息综合。

OpenBuffett 面向的是专业级公司研究与估值分析，目标是在投资研究领域推动散户与机构之间的**平权**。它尤其适合以下场景：

- 判断一家企业在当前市场价格下究竟偏贵还是偏便宜
- 将公司放进合适的可比公司框架中研究，而不是孤立地看单一估值倍数
- 在一条研究链路中同时梳理财报、披露文件与市场叙事
- 在美股新股尚未上市、且处于可申购或即将申购阶段时做打新研究
- 拉取市场数据、历史价格轨迹与历史市值变化，作为研究输入

## 核心创新点

OpenBuffett 不是一个外面套了一层金融话术的通用聊天 Agent，而是一个专门为深度投资研究，尤其是估值研究而设计的专用 Agent。

它的设计目标很直接：通过弥补知识广度、一手资料阅读能力和大规模信息处理能力上的不足，让每个人的电脑里都住着一个更接近巴菲特式研究流程的本地研究助手。

这能帮助用户尽量避免在泡沫高位买入优秀公司，也尽量减少因为研究不足而错过仍被低估或尚未被充分理解的好公司。

## 核心功能说明

当前能力合同以 `src/agent.py` 中的默认 agent 组装与 system prompt 为准。在当前产品表面上，OpenBuffett 主要聚焦五类核心行为：

1. 当用户输入公司名、别名、简称或含糊标识时，先做 ticker 候选推断与确认，再进入正式分析。
2. 以估值为主链做研究，围绕商业质量、财务质量、市场隐含预期与深度可比公司对照展开分析。
3. 对 1 个月、6 个月、1 年、3 年、5 年五个周期分别给出判断，并把短周期观点明确锚定到宏观政策、利率、情绪与资金流。
4. 只有在目标属于尚未上市、且当前正在申购或即将申购的美股新股时，才进入打新分析流程。
5. 以来源分级、最新信息校验、审计式输出边界为基础，显式区分已核事实、基于事实的推断，以及尚未证实的内容。

在当前数据面支持下，Agent 还可以完成市场数据辅助研究，包括历史 OHLC、历史市值、SEC 披露、财务报表、关键指标、财务比率、一致预期、纪要、内部人交易，以及 FMP 当前可覆盖的相关宏观输入。

## 技术栈

OpenBuffett 当前主要建立在三层技术栈之上：

- **EasyHarness**：我的自研 agent-loop 框架，负责默认 agent 的运行时基础、流式事件模型、工具合同，以及本地 workbench 的作用域集成。
- **Textual**：TUI 界面层，让 Agent 成为一个可交互的本地研究工作台，而不只是一次性脚本。
- **Financial Modeling Prep (FMP)**：结构化美股金融数据层，提供市场数据、公司画像、SEC 披露、财务报表、估值输入、一致预期、可比公司、电话会纪要、内部人交易、宏观背景与 IPO 相关数据集。

在仓库层面，默认产品边界是刻意收窄的：OpenBuffett 先专注于美股估值研究，其次是打新研究，最后才是市场数据辅助。

## 启动方式

```bash
git clone https://github.com/vortezwohl/SmartIPO.git
cd SmartIPO
uv sync
python -m src.tui
```

第一次真实运行前，请先配置默认 agent runtime 所需的环境变量：

- `API_KEY`：必需，模型 API key。
- `API_BASE`：可选，模型 base URL 覆盖项。OpenBuffett 默认通过 `https://api.deepseek.com/v1` 使用 DeepSeek，且 `src/agent.py` 中的默认模型是 `openai/deepseek-v4-pro`。只要目标供应商兼容 OpenAI 接口规范，也都可以通过替换 `API_BASE` 与对应 `API_KEY` 接入。
- `FMP_API_KEY`：必需。OpenBuffett 的核心研究链路依赖 FMP 提供的市场与公司数据，因此没有这个 key 的真实运行场景不受支持。
- `FMP_API_BASE`：可选，FMP base URL 覆盖项。

## 学术引用

如果你在学术研究、行业研究或其他正式工作中使用 OpenBuffett，建议按软件形式引用本仓库：

```bibtex
@software{Wu_OpenBuffett_2026,
  author = {Wu, Zihao},
  title = {{OpenBuffett}},
  url = {https://github.com/vortezwohl/OpenBuffett},
  version = {0.1.0},
  year = {2026}
}
```
