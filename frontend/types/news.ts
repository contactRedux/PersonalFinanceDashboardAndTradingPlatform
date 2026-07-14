/**
 * News and sentiment TypeScript types.
 */

export type SentimentLabel = "bullish" | "bearish" | "neutral";
export type ImpactCategory = "earnings" | "macro" | "regulatory" | "ma" | "analyst" | "general";

export interface SentimentScore {
  label: SentimentLabel;
  score: number;           // -1 to +1
  confidence: number;      // 0 to 1
  impact_category: ImpactCategory;
}

export interface NewsArticle {
  id: string;
  source: string;
  headline: string;
  body?: string;
  url: string;
  published_at: string;
  tickers_mentioned: string[];
  sentiment: SentimentScore;
}

export interface TickerSentimentAggregate {
  symbol: string;
  score_1h: number | null;
  score_4h: number | null;
  score_1d: number | null;
  dominant_label: SentimentLabel;
  article_count_1h: number;
  article_count_1d: number;
  updated_at: string;
}
