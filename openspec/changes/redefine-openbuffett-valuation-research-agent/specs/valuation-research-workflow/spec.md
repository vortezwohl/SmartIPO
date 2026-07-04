## ADDED Requirements

### Requirement: Valuation analysis SHALL be the default research mainline
The system MUST treat professional valuation analysis as the default mainline for supported equity research requests. A complete analysis MUST be conclusion-first and MUST explicitly separate verified facts, fact-based inference, and unresolved uncertainty.

#### Scenario: User requests company valuation analysis
- **WHEN** the user asks for a research or valuation view on a supported equity
- **THEN** the system MUST answer through a valuation-first workflow rather than an IPO-first workflow

### Requirement: Valuation output SHALL include evidence-graded fundamentals and comparable analysis
The system MUST ground valuation analysis in business quality, financial quality, valuation level, and peer comparison. The analysis MUST use evidence grading that distinguishes primary disclosures from structured data sources and lower-confidence secondary materials.

#### Scenario: User receives a full valuation answer
- **WHEN** the system provides a full valuation analysis
- **THEN** it MUST include evidence-supported discussion of company quality, financial quality, and comparable companies from the same or closely related sector

### Requirement: Valuation output SHALL include multi-horizon judgment and current-market risk framing
For a complete valuation answer, the system MUST state whether the target appears cheap or expensive across five horizons: 1 month, 6 months, 1 year, 3 years, and 5 years. The answer MUST also warn about the risk of immediately going long or short under the current market regime and MUST anchor the conclusion to the current analysis date.

#### Scenario: User asks whether a stock is cheap or expensive
- **WHEN** the system provides a full valuation conclusion
- **THEN** it MUST include 1-month, 6-month, 1-year, 3-year, and 5-year valuation perspectives and explicit current long/short risk warnings with a date anchor

### Requirement: Short-horizon valuation framing SHALL include macro, geopolitics, market mood, and fund-flow context
For the 1-month and 6-month horizons, the system MUST explicitly analyze monetary/economic policy, geopolitical risk, broad market sentiment, and capital or fund-flow conditions. It MUST treat these as first-class inputs rather than optional commentary.

#### Scenario: System produces short-horizon valuation judgment
- **WHEN** the answer states a 1-month or 6-month valuation view
- **THEN** it MUST include explicit discussion of monetary/economic policy, geopolitics, broad market sentiment, and fund-flow context

### Requirement: Short-horizon macro commentary SHALL use observable proxies or admit confidence limits
When the system discusses short-horizon valuation or risk framing, it MUST ground that discussion in observable proxies where possible, such as rate-path expectations, Fed communication, inflation or labor data, yield curves, dollar strength, oil, VIX, credit spreads, ETF or sector flows, relative strength, or crowding. If reliable evidence is missing, the system MUST disclose that the short-horizon judgment has limited confidence instead of presenting a confident unsupported claim.

#### Scenario: Reliable short-horizon market proxies are unavailable
- **WHEN** the system cannot verify enough macro or flow evidence for a confident 1-month or 6-month judgment
- **THEN** it MUST explicitly say that short-horizon confidence is limited and avoid overstating certainty

### Requirement: Information-driven market framing SHALL use latest online evidence with source confidence grading
When the system discusses macro policy, geopolitics, market sentiment, fund flows, earnings updates, guidance changes, IPO status, or other information-driven market context, it MUST obtain the latest relevant information through online sources rather than relying only on static prior knowledge. It MUST grade source confidence and prefer official or structured sources for key conclusions.

#### Scenario: System discusses current information-driven market context
- **WHEN** the answer relies on current policy, geopolitical, sentiment, flow, news, or IPO-status context
- **THEN** the system MUST use latest online information and identify source confidence rather than presenting unsupported static knowledge as current fact

### Requirement: Emotional or weakly sourced narratives SHALL be explicitly downgraded
The system MUST distinguish verified facts, observable proxies, media narratives, and emotional or unverified claims. It MUST NOT treat emotionally loaded commentary, rumors, or social-media chatter as core evidence without explicit downgrading and caveats.

#### Scenario: A news source uses emotional or speculative language
- **WHEN** the system encounters a source with exaggerated, emotional, or speculative framing
- **THEN** it MUST identify the narrative as lower-confidence or emotional framing and avoid promoting it to a core factual conclusion

### Requirement: Research output SHALL include a minimal information-audit summary
For a full valuation or IPO-subscription analysis, the system MUST summarize the key online information sources, their timestamps, their confidence grades, and any unresolved conflicts or unverified items. The response tone MUST remain neutral, non-emotional, and audit-friendly.

#### Scenario: System produces a full research answer
- **WHEN** the system finishes a complete valuation or IPO-subscription analysis
- **THEN** it MUST include a minimal information-audit summary with source/timestamp/confidence notes and maintain a neutral tone

### Requirement: Unsupported market-data coverage SHALL be disclosed instead of fabricated
When a user asks for a non-core asset or a data view that is not reliably covered by the currently integrated tools, the system MUST state that the requested analysis cannot be verified with the current data surface. It MUST NOT overstate support or fabricate precise conclusions for unsupported instruments.

#### Scenario: User requests unsupported or weakly covered market analysis
- **WHEN** the current integrated data tools cannot rigorously support the requested asset or data view
- **THEN** the system MUST explicitly disclose the coverage limit instead of pretending that complete analysis is available
