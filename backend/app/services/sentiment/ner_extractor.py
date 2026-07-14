"""
spaCy Named Entity Recognition — extract ticker symbols from news text.

Uses a combination of spaCy NER and a regex-based fallback for common
equity ticker patterns (1-5 uppercase letters).
"""

from __future__ import annotations

import re

import structlog

logger = structlog.get_logger(__name__)

_nlp = None
# Common words that look like tickers but are not
_TICKER_STOP_WORDS = frozenset(
    {
        "A",
        "I",
        "AND",
        "OR",
        "THE",
        "TO",
        "OF",
        "IN",
        "IS",
        "IT",
        "BE",
        "AS",
        "AT",
        "SO",
        "WE",
        "BY",
        "AN",
        "DO",
        "IF",
        "ON",
        "NO",
        "UP",
        "EX",
        "OK",
        "GO",
        "US",
        "UK",
        "EU",
        "FY",
        "Q1",
        "Q2",
        "Q3",
        "Q4",
        "YOY",
        "QOQ",
        "IPO",
        "M&A",
        "EPS",
        "TTM",
        "LTM",
        "CEO",
        "CFO",
        "COO",
        "CTO",
        "SEC",
        "NYSE",
        "NASDAQ",
        "ETF",
        "AI",
        "ML",
        "GDP",
        "CPI",
        "PPI",
        "PMI",
        "Fed",
        "FED",
        "FOMC",
    }
)

_TICKER_RE = re.compile(r"\b([A-Z]{1,5})\b")


def _get_nlp():
    global _nlp
    if _nlp is None:
        try:
            import spacy

            _nlp = spacy.load("en_core_web_sm")
        except Exception:
            logger.warning("spacy.load_failed", hint="run: python -m spacy download en_core_web_sm")
            _nlp = None
    return _nlp


def extract_tickers(text: str) -> list[str]:
    """
    Extract likely stock tickers from text.
    Returns a deduplicated list of uppercase ticker strings.
    """
    tickers: set[str] = set()

    # Method 1: spaCy ORG entities that look like tickers
    nlp = _get_nlp()
    if nlp:
        try:
            doc = nlp(text[:5000])  # limit for speed
            for ent in doc.ents:
                if ent.label_ == "ORG":
                    candidate = ent.text.upper().strip().replace("$", "")
                    if (
                        1 <= len(candidate) <= 5
                        and candidate.isalpha()
                        and candidate not in _TICKER_STOP_WORDS
                    ):
                        tickers.add(candidate)
        except Exception:
            logger.exception("spacy.ner_error")

    # Method 2: Regex for $TICKER and TICKER: patterns
    dollar_tickers = re.findall(r"\$([A-Z]{1,5})\b", text)
    for t in dollar_tickers:
        if t not in _TICKER_STOP_WORDS:
            tickers.add(t)

    return sorted(tickers)
