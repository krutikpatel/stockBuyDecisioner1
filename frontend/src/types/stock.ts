export interface MarketData {
  ticker: string;
  current_price: number;
  previous_close: number;
  open: number;
  day_high: number;
  day_low: number;
  volume: number;
  avg_volume_30d: number;
  market_cap?: number;
  week_52_high?: number;
  week_52_low?: number;
  beta?: number;
  return_1m?: number;
  return_3m?: number;
  return_6m?: number;
  return_1y?: number;
  return_ytd?: number;
}

export interface TrendClassification {
  label: string;
  description: string;
}

export interface SupportResistanceLevels {
  supports: number[];
  resistances: number[];
  nearest_support?: number;
  nearest_resistance?: number;
}

export interface TechnicalIndicators {
  ma_10?: number;
  ma_20?: number;
  ma_50?: number;
  ma_100?: number;
  ma_200?: number;
  rsi_14?: number;
  macd?: number;
  macd_signal?: number;
  macd_histogram?: number;
  atr?: number;
  volume_trend: string;
  trend: TrendClassification;
  is_extended: boolean;
  extension_pct_above_20ma?: number;
  extension_pct_above_50ma?: number;
  support_resistance: SupportResistanceLevels;
  rs_vs_spy?: number;
  rs_vs_sector?: number;
  technical_score: number;
}

export interface FundamentalData {
  revenue_ttm?: number;
  revenue_growth_yoy?: number;
  eps_ttm?: number;
  gross_margin?: number;
  operating_margin?: number;
  net_margin?: number;
  free_cash_flow?: number;
  cash?: number;
  total_debt?: number;
  net_debt?: number;
  debt_to_equity?: number;
  roe?: number;
  fundamental_score: number;
}

export interface ValuationData {
  trailing_pe?: number;
  forward_pe?: number;
  peg_ratio?: number;
  price_to_sales?: number;
  ev_to_ebitda?: number;
  price_to_fcf?: number;
  fcf_yield?: number;
  peer_comparison_available: boolean;
  valuation_score: number;
}

export interface EarningsRecord {
  date?: string;
  eps_estimate?: number;
  eps_actual?: number;
  eps_surprise_pct?: number;
}

export interface EarningsData {
  last_earnings_date?: string;
  next_earnings_date?: string;
  history: EarningsRecord[];
  avg_eps_surprise_pct?: number;
  beat_count: number;
  miss_count: number;
  beat_rate?: number;
  within_30_days: boolean;
  earnings_score: number;
}

export interface NewsItem {
  title: string;
  source?: string;
  published_at?: string;
  url?: string;
  summary?: string;
  sentiment: 'positive' | 'neutral' | 'negative';
  importance: 'low' | 'medium' | 'high';
  category: string;
}

export interface NewsSummary {
  items: NewsItem[];
  positive_count: number;
  negative_count: number;
  neutral_count: number;
  news_score: number;
  coverage_limited: boolean;
}

export interface EntryPlan {
  preferred_entry?: number;
  starter_entry?: number;
  breakout_entry?: number;
  avoid_above?: number;
}

export interface ExitPlan {
  stop_loss?: number;
  invalidation_level?: number;
  first_target?: number;
  second_target?: number;
}

export interface RiskReward {
  downside_percent?: number;
  upside_percent?: number;
  ratio?: number;
}

export interface PositionSizing {
  suggested_starter_pct_of_full: number;
  max_portfolio_allocation_pct: number;
}

export interface HorizonRecommendation {
  horizon: string;
  decision: string;
  score: number;
  confidence: string;
  summary: string;
  bullish_factors: string[];
  bearish_factors: string[];
  entry_plan: EntryPlan;
  exit_plan: ExitPlan;
  risk_reward: RiskReward;
  position_sizing: PositionSizing;
  data_warnings: string[];
}

export interface DataQualityReport {
  score: number;
  warnings: string[];
}

export interface StockAnalysisResult {
  ticker: string;
  generated_at: string;
  current_price: number;
  data_quality: DataQualityReport;
  market_data: MarketData;
  technicals: TechnicalIndicators;
  fundamentals: FundamentalData;
  valuation: ValuationData;
  earnings: EarningsData;
  news: NewsSummary;
  recommendations: HorizonRecommendation[];
  markdown_report: string;
  disclaimer: string;
}

export interface AnalysisRequest {
  ticker: string;
  horizons?: string[];
  risk_profile?: string;
}
