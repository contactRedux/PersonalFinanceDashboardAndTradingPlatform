"use client";

/**
 * NewsFeedPanel — real-time news feed with AI sentiment scores.
 *
 * Displays articles with:
 *   - Sentiment badge: Bullish/Bearish/Neutral + confidence %
 *   - Impact category (earnings, macro, M&A, analyst, regulatory)
 *   - Ticker mentions
 *   - Publication time
 *
 * AI DISCLAIMER: Sentiment scores are not investment advice.
 */

import React, { useEffect, useState, useCallback } from "react";
import { Panel } from "@/components/layout/Panel";
import { apiRequest } from "@/lib/api/client";

interface Article {
  source: string;
  headline: string;
  url: string;
  published_at: string;
  tickers_mentioned: string[];
  sentiment?: {
    composite_score: number;
    label: "bullish" | "bearish" | "neutral";
    finbert_confidence: number;
    impact_category: string;
  } | null;
}

interface NewsFeedPanelProps {
  panelId?: string;
  symbols?: string[];
}

export function NewsFeedPanel({ panelId = "news", symbols }: NewsFeedPanelProps) {
  const [articles, setArticles] = useState<Article[]>([]);
  const [loading, setLoading] = useState(false);
  const [filter, setFilter] = useState<"all" | "bullish" | "bearish">("all");

  const loadArticles = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({ limit: "50", page: "1" });
      if (symbols?.length) params.set("symbols", symbols.join(","));
      const resp = await apiRequest<{ articles: Article[] }>(
        `/news/feed?${params}`
      );
      setArticles(resp.articles || []);
    } catch {
      /* silently ignore */
    } finally {
      setLoading(false);
    }
  }, [symbols]);

  useEffect(() => {
    loadArticles();
    const interval = setInterval(loadArticles, 60_000); // refresh every minute
    return () => clearInterval(interval);
  }, [loadArticles]);

  const filtered = articles.filter((a) => {
    if (filter === "all") return true;
    return a.sentiment?.label === filter;
  });

  const toolbar = (
    <div style={{ display: "flex", gap: 4 }}>
      {(["all", "bullish", "bearish"] as const).map((f) => (
        <button
          key={f}
          style={{
            padding: "1px 6px",
            background: filter === f ? "rgba(0,208,132,0.12)" : "transparent",
            border: `1px solid ${filter === f ? "rgba(0,208,132,0.3)" : "transparent"}`,
            borderRadius: 3,
            fontSize: 9,
            fontFamily: "var(--font-mono)",
            color: filter === f ? "var(--color-accent-green)" : "var(--color-text-muted)",
            cursor: "pointer",
            letterSpacing: "0.04em",
            textTransform: "uppercase",
          }}
          onClick={() => setFilter(f)}
        >
          {f}
        </button>
      ))}
    </div>
  );

  return (
    <Panel id={panelId} title="News & Sentiment" toolbar={toolbar}>
      {/* AI Disclaimer */}
      <div style={styles.disclaimer}>
        ⚠ AI sentiment scores are for informational purposes only and do not
        constitute investment advice.
      </div>

      {loading && articles.length === 0 && (
        <div style={styles.empty}>Loading news…</div>
      )}

      {!loading && articles.length === 0 && (
        <div style={styles.empty}>
          No articles. Configure NEWSAPI_KEY or BENZINGA_API_KEY to enable
          live news.
        </div>
      )}

      <div style={styles.feedList}>
        {filtered.map((article, i) => (
          <ArticleRow key={`${article.source}-${i}`} article={article} />
        ))}
      </div>
    </Panel>
  );
}

// ─── ArticleRow ───────────────────────────────────────────────────────────────
function ArticleRow({ article }: { article: Article }) {
  const sentiment = article.sentiment;
  const label = sentiment?.label ?? "neutral";
  const confidence = sentiment?.finbert_confidence ?? 0;
  const score = sentiment?.composite_score ?? 0;

  const labelColor = {
    bullish: "#00d084",
    bearish: "#ef4444",
    neutral: "#f59e0b",
  }[label];

  return (
    <div style={styles.articleRow}>
      {/* Source + time */}
      <div style={styles.articleMeta}>
        <span style={styles.source}>{article.source.toUpperCase()}</span>
        <span style={styles.time}>{formatRelativeTime(article.published_at)}</span>
        {article.tickers_mentioned.slice(0, 3).map((t) => (
          <span key={t} style={styles.ticker}>{t}</span>
        ))}
      </div>

      {/* Headline */}
      <a
        href={article.url}
        target="_blank"
        rel="noopener noreferrer"
        style={styles.headline}
      >
        {article.headline}
      </a>

      {/* Sentiment badge */}
      {sentiment && (
        <div style={styles.sentimentRow}>
          <span
            style={{
              ...styles.sentimentBadge,
              color: labelColor,
              borderColor: `${labelColor}40`,
              background: `${labelColor}10`,
            }}
          >
            {label.toUpperCase()}
          </span>
          <span style={styles.confidence}>
            {Math.round(confidence * 100)}% conf
          </span>
          <span style={styles.scoreBar}>
            <span
              style={{
                ...styles.scoreBarFill,
                width: `${Math.abs(score) * 100}%`,
                background: score >= 0 ? "#00d084" : "#ef4444",
              }}
            />
          </span>
          {sentiment.impact_category && sentiment.impact_category !== "general" && (
            <span style={styles.impactCategory}>
              {sentiment.impact_category.toUpperCase()}
            </span>
          )}
        </div>
      )}
    </div>
  );
}

function formatRelativeTime(isoString: string): string {
  try {
    const dt = new Date(isoString);
    const diffMs = Date.now() - dt.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    if (diffMins < 60) return `${diffMins}m ago`;
    const diffHrs = Math.floor(diffMins / 60);
    if (diffHrs < 24) return `${diffHrs}h ago`;
    return `${Math.floor(diffHrs / 24)}d ago`;
  } catch {
    return "";
  }
}

// ─── Styles ───────────────────────────────────────────────────────────────────
const styles: Record<string, React.CSSProperties> = {
  disclaimer: {
    padding: "4px 10px",
    fontSize: 9,
    color: "var(--color-accent-amber)",
    background: "rgba(245,158,11,0.06)",
    borderBottom: "1px solid var(--color-bg-separator)",
    letterSpacing: "0.02em",
    fontFamily: "var(--font-sans)",
  },
  empty: {
    padding: "16px 10px",
    fontSize: 11,
    color: "var(--color-text-muted)",
    textAlign: "center",
    fontFamily: "var(--font-mono)",
  },
  feedList: {
    display: "flex",
    flexDirection: "column",
    overflow: "auto",
  },
  articleRow: {
    padding: "8px 10px",
    borderBottom: "1px solid rgba(255,255,255,0.04)",
    display: "flex",
    flexDirection: "column",
    gap: 3,
  },
  articleMeta: {
    display: "flex",
    alignItems: "center",
    gap: 6,
    flexWrap: "wrap",
  },
  source: {
    fontSize: 9,
    fontFamily: "var(--font-mono)",
    color: "var(--color-accent-blue)",
    letterSpacing: "0.06em",
    fontWeight: 600,
  },
  time: {
    fontSize: 9,
    color: "var(--color-text-muted)",
    fontFamily: "var(--font-mono)",
  },
  ticker: {
    fontSize: 9,
    fontFamily: "var(--font-mono)",
    fontWeight: 700,
    color: "var(--color-accent-green)",
    background: "rgba(0,208,132,0.08)",
    padding: "1px 4px",
    borderRadius: 2,
  },
  headline: {
    fontSize: 12,
    color: "var(--color-text-primary)",
    fontFamily: "var(--font-sans)",
    lineHeight: 1.4,
    textDecoration: "none",
    display: "block",
  },
  sentimentRow: {
    display: "flex",
    alignItems: "center",
    gap: 6,
  },
  sentimentBadge: {
    fontSize: 9,
    fontFamily: "var(--font-mono)",
    fontWeight: 700,
    letterSpacing: "0.06em",
    padding: "1px 5px",
    borderRadius: 2,
    border: "1px solid",
  },
  confidence: {
    fontSize: 9,
    color: "var(--color-text-muted)",
    fontFamily: "var(--font-mono)",
  },
  scoreBar: {
    width: 48,
    height: 4,
    background: "var(--color-bg-separator)",
    borderRadius: 2,
    overflow: "hidden",
    display: "inline-block",
  },
  scoreBarFill: {
    height: "100%",
    borderRadius: 2,
    display: "block",
    transition: "width 0.3s ease",
  },
  impactCategory: {
    fontSize: 8,
    fontFamily: "var(--font-mono)",
    color: "var(--color-accent-amber)",
    letterSpacing: "0.06em",
    padding: "1px 4px",
    background: "rgba(245,158,11,0.08)",
    borderRadius: 2,
  },
};
