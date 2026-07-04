<div align="center">
  <h1>OpenBuffett</h1>
  <p>
    <strong>
      An autonomous agent that study companies the way Buffett does.<br>For professional-grade company study, comparables analysis, and disciplined price discovery.
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
      Built to narrow the research gap between retail investors and institutions.
    </sub>
  </p>
</div>

<h4 align="center">
  <p>
    <b>English</b> |
    <a href="./i18n/README_zh-hans.md">简体中文</a>
  </p>
</h4>

## Project Overview

OpenBuffett is a valuation-first US equity research workbench built to help investors conduct company research with institutional discipline.

It combines large-scale AI information processing with structured financial workflows so users can study businesses, compare peers, and reason about valuation more rigorously. The core objective is to reduce the gap between what professional researchers can process and what most individual investors can realistically analyze on their own.

In practical terms, OpenBuffett is designed to help more investors research companies with the depth, structure, and skepticism usually associated with long-horizon fundamental investors.

## Pain Points and Use Cases

Most retail investors do not fail because they lack interest. They fail because serious valuation work requires too much primary-source reading, too much accounting context, and too much information synthesis under time pressure.

OpenBuffett is designed for professional-grade company research and valuation analysis, pushing toward research **parity** between retail investors and institutions. It is especially useful when a user needs to:

- understand whether a business is expensive or cheap at the current market price
- compare a company against relevant peers instead of relying on isolated multiples
- review financial statements, filings, and market narratives in one research flow
- study a not-yet-listed US IPO before subscription opens or closes
- pull market data, historical price paths, and market capitalization history as research inputs

## Core Innovations

OpenBuffett is purpose-built for deep investment research, especially valuation work, rather than being a generic chat agent with a finance wrapper.

Its design goal is simple: put a Buffett-like research process on every investor's desktop by compensating for limits in knowledge breadth, primary-source reading capacity, and large-scale information processing.

That makes it easier to avoid buying great companies at bubble valuations, or missing strong businesses when they are still misunderstood or underpriced.

## Core Capabilities

The current capability contract is defined by the default agent composition and system prompt in `src/agent.py`. In its current product surface, OpenBuffett focuses on five core behaviors:

1. Ticker disambiguation before formal analysis when the user provides a company name, alias, shorthand, or ambiguous identifier.
2. Valuation-first research centered on business quality, financial quality, implied expectations, and deep comparable-company analysis.
3. Multi-horizon judgment across 1 month, 6 months, 1 year, 3 years, and 5 years, with short-horizon views explicitly tied to macro policy, rates, sentiment, and capital flows.
4. IPO analysis only when the target is a not-yet-listed US offering that is currently open or about to open for subscription.
5. Source-aware research with explicit evidence grading, latest-information checks, audit-style output boundaries, and a clear distinction between verified facts, inferences, and unverified items.

The agent also supports market-data-assisted research for the current data surface, including historical OHLC, market capitalization history, SEC filings, financial statements, key metrics, ratios, estimates, transcripts, insider activity, and related macro inputs supported by FMP.

## Technology Stack

OpenBuffett is built on three primary layers:

- **EasyHarness**: my self-developed agent-loop framework. It provides the runtime foundation, streaming event model, tool contracts, and scoped local-workbench integration used by the default agent.
- **Textual**: the TUI layer that turns the agent into an interactive local research workbench instead of a one-shot script.
- **Financial Modeling Prep (FMP)**: the structured US equity data layer used for market data, company profiles, SEC filings, financial statements, valuation inputs, estimates, comparables, transcripts, insider activity, macro context, and IPO-related datasets.

At the repository level, the default product surface is intentionally narrow: OpenBuffett stays focused on US-equity valuation research first, then IPO research, then market-data assistance.

## Quick Start

```bash
git clone https://github.com/vortezwohl/SmartIPO.git
cd SmartIPO
uv sync
python -m src.tui
```

Before the first real run, configure the environment variables required by the default agent runtime:

- `API_KEY`: required model API key.
- `API_BASE`: optional model base URL override. By default, OpenBuffett uses DeepSeek through `https://api.deepseek.com/v1`, and the default model in `src/agent.py` is `openai/deepseek-v4-pro`. Any OpenAI-compatible model provider can be used as long as `API_BASE` points to that provider's compatible endpoint and `API_KEY` matches it.
- `FMP_API_KEY`: required FMP API key. OpenBuffett's core research flow depends on FMP-backed market and company data, so real runs without this key are not supported.
- `FMP_API_BASE`: optional FMP base URL override.

## Citation

If you use OpenBuffett in academic, research, or industry work, cite the repository as software:

```bibtex
@software{Wu_OpenBuffett_2026,
  author = {Wu, Zihao},
  title = {{OpenBuffett}},
  url = {https://github.com/vortezwohl/OpenBuffett},
  version = {0.1.0},
  year = {2026}
}
```
