---
name: trend-watch
description: Use when checking current trends, popularity, or momentum for a technology or market
allowed-tools: WebSearch, WebFetch, Read
tags:
  function: [research, engineering]
  scenario: [technology-evaluation, market-analysis]
  custom: [trends, popularity, adoption]
---

# Trend Watch

Quick trend check for a technology, library, or market segment. Returns a concise momentum assessment, not a full analysis.

## Input

```text
$ARGUMENTS
```

If no arguments provided, ask: "What technology or market would you like a trend check on?"

## Process

### Step 1: Parallel Search

Use `mcp__jina__parallel_search_web` with time-sensitive queries:

- "$ARGUMENTS adoption 2026"
- "$ARGUMENTS vs alternatives 2026"
- "$ARGUMENTS market share"
- "$ARGUMENTS trends"
- "$ARGUMENTS growth OR decline"

### Step 2: Extract Key Sources

Use `mcp__jina__read_url` on the top 3-5 most relevant results from Step 1. Prioritize:
- Industry reports and analyst commentary
- Developer surveys and usage statistics
- Community discussions with recent activity
- Blog posts from notable practitioners (not vendor marketing)

### Step 3: Relevance Ranking

Use `mcp__jina__sort_by_relevance` to rank extracted content against the query "$ARGUMENTS momentum and adoption trends".

### Step 4: Synthesize

Write a concise trend report (200-400 words max) with this structure:

**Momentum: [Rising / Stable / Declining]**

- **Key Signals**: 3-5 bullet points with evidence (each citing a source URL)
- **Notable Adopters or Defectors**: companies/projects recently adopting or moving away
- **Related Trends**: 2-3 adjacent technologies or market shifts to watch
- **Bottom Line**: one sentence assessment

## Constraints

- Keep it short. This is a quick pulse check, not a market scan or full evaluation.
- Every signal must cite a source URL.
- If the data is ambiguous or contradictory, say so. Do not force a directional call without evidence.
- Prefer recent data (last 6 months) over older reports.
