---
name: market-scan
description: Use when analyzing a market segment, identifying competitors, or evaluating business opportunities
tags:
  function: [research, executive]
  scenario: [market-analysis, business-planning]
  custom: [competitors, market-size, opportunities]
---

# Market Scan

Structured market analysis for a product category or business domain. Produces a comprehensive market map with competitive positioning and entry strategy.

## Iron Law

**Every factual claim must cite a source URL.** No exceptions. Unsourced claims get deleted.

## Input

Describe the market segment, product category, or business domain to analyze. Include any known players, target audience, or specific angles to investigate.

## Process

### Phase 1: Market Definition

Define the boundaries of the analysis:
1. State the market segment in one sentence
2. Identify the target audience (who buys/uses products in this space)
3. List 3-5 known players as starting points (ask the user if none are obvious)
4. Define 2-3 adjacent markets that overlap or compete for the same buyers

### Phase 2: Landscape Mapping

Use `mcp__jina__parallel_search_web` with diverse queries to find ALL players, not just the obvious ones. Run at least three rounds of parallel searches:

**Round 1 -- Direct discovery:**
- "[category] companies"
- "[category] tools"
- "[category] platforms"
- "[category] open source"
- "[category] startups"

**Round 2 -- Alternative angles:**
- "[category] alternatives to [known player]"
- "[category] market report 2026"
- "[category] comparison"
- "best [category] for [target audience]"

**Round 3 -- Community signals:**
- "[category] reddit recommendations"
- "[category] hacker news"
- "[category] product hunt"
- "[category] G2 reviews"

Use `mcp__jina__deduplicate_strings` to collapse duplicate company mentions across all search results.

### Phase 3: Deep Analysis

For the top 5-10 players identified in Phase 2, conduct deep analysis on each:

1. Use `mcp__jina__read_url` on their homepage, pricing page, and about page
2. Use `mcp__jina__capture_screenshot_url` on landing pages for visual positioning analysis
3. Use `mcp__jina__search_web` for "[company] funding", "[company] revenue", "[company] customers"
4. Catalog: positioning, pricing model, target segment, key differentiators

For companies with open source products, also check GitHub for stars, contributor count, and release activity.

### Phase 4: Opportunity Identification

Synthesize findings to identify:
- **White spaces**: needs that no current player addresses well
- **Underserved niches**: segments that existing players ignore or deprioritize
- **Pricing gaps**: price points with no strong offering (too cheap for enterprise tools, too expensive for indie tools)
- **Technical gaps**: capabilities that are missing or poorly implemented across the market
- **Trend alignment**: where the market is heading vs. where current players are positioned

### Phase 5: Synthesis

Produce the final market scan report with the structure below. Save to: `research/YYYY-MM-DD-market-scan-{topic}.md` (create the `research/` directory if it does not exist).

## Output Structure

```markdown
# Market Scan: {Market Segment}
Date: YYYY-MM-DD

## Market Definition
- Segment: {one sentence}
- Target Audience: {who buys/uses}
- Market Size Signals: {any available data on TAM/SAM/SOM, with source URLs}
- Adjacent Markets: {overlapping or competing spaces}

## Competitive Landscape

### Market Map
{Position each player on two axes relevant to the market, e.g., price vs. feature depth, or enterprise vs. individual focus. Use a text-based visualization.}

### Player Profiles
{For each of the top 5-10 players:}
#### {Company Name}
- **URL**: {website}
- **Founded**: {year, if known}
- **Funding**: {amount and stage, if known}
- **Positioning**: {one sentence on their market position}
- **Pricing**: {model and tiers}
- **Strengths**: {2-3 bullet points}
- **Weaknesses**: {2-3 bullet points}
- **Sources**: {list of URLs used}

## Opportunity Analysis
- **White Spaces**: {unaddressed needs}
- **Underserved Niches**: {ignored segments}
- **Pricing Gaps**: {unoccupied price points}
- **Technical Gaps**: {missing capabilities}

## Recommended Entry Strategy
{Based on the analysis, where should we position? What niche to target first? What differentiator to lead with?}

## Sources
{Complete list of all URLs cited in this report}
```

## Anti-Patterns

- Do NOT produce a report with unsourced claims. If you cannot find a source, state that the data is unavailable.
- Do NOT limit discovery to the first page of search results. Run multiple query rounds to surface less obvious players.
- Do NOT confuse marketing positioning with actual market position. Cross-reference claims against community sentiment and real usage signals.
- Do NOT skip the opportunity analysis. The whole point of a market scan is to find where to play, not just to list who is playing.
