# Nokku

> Before you decide... Nokku.

Nokku is a conversational decision-support companion.

It helps users examine real-world choices by combining personal context, domain-specific knowledge, and reusable capabilities without pretending to guarantee outcomes.

Nokku is designed to grow through living applications and real use rather than speculative architecture.

## Installation

Nokku consumes established Banyan ecosystem capabilities as independent packages rather than embedding their source inside the Nokku repository.

The current runtime dependencies are declared in `pyproject.toml` and pinned to verified Git commits:

- **Banyan** — shared reusable capabilities;
- **Collector** — external data collection;
- **COSsse** — Flow and durable Memory capabilities.

A fresh environment should therefore require no manual sibling-repository installation or `PYTHONPATH` adjustment.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install ".[dev]"
```

The repository includes a fresh-install regression workflow at `.github/workflows/fresh-install.yml`. It creates a new virtual environment, installs Nokku using only its declared dependencies, verifies that `banyan`, `collector`, `cossse`, and `nokku` import correctly, and runs the full Nokku test suite.

## First Living Habitat

The first living use case is Kerala Lottery weekly participation support.

This began historically as Project Lakshmi and now serves as the first real habitat for Nokku to exercise existing COSsse capabilities such as Flow, Memory, and Collector.

The current living loop:

1. accepts a conversational weekly decision request;
2. resolves the Friday-to-Thursday decision week, using a saved preference when present;
3. recalls verified official Kerala Lottery facts from durable COSsse Memory;
4. refreshes only the small current numeric source frontier when Memory is stale;
5. applies Kerala-Lottery-specific participation logic;
6. returns BUY or SKIP, an operational preferred/backup date, evidence and uncertainty;
7. preserves the decision experience in Memory so later runs can compare recommendation and outcome.

Run it with:

```bash
python -m nokku "Should I buy a Kerala lottery this week?"
```

To explicitly override the neutral conservative default:

```bash
python -m nokku "I want to buy this week"
python -m nokku "Skip the lottery this week"
```

To save a different decision-week start:

```bash
python -m nokku "Should I buy this week?" --week-start monday --remember-week-start
```

Historical result patterns are not presented as a proven predictive edge. The first living policy defaults a neutral request to SKIP; an explicit user BUY/SKIP choice is respected and preserved.

`KeralaLotteryStore` remains only as an early experiment kept for compatibility. It is not the living source of truth. Accumulated experience lives in durable COSsse Memory.

## Current Principle

Build only what the living use case proves necessary.

Anything that appears reusable remains a candidate until evidence from multiple real applications justifies promotion.
