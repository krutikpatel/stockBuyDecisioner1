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
  // Moving averages
  ma_10?: number;
  ma_20?: number;
  ma_50?: number;
  ma_100?: number;
  ma_200?: number;
  // EMA relatives (% deviation)
  ema8_relative?: number;
  ema21_relative?: number;
  // SMA relatives (% deviation)
  sma20_relative?: number;
  sma50_relative?: number;
  sma200_relative?: number;
  // SMA slopes (5-bar % change)
  sma20_slope?: number;
  sma50_slope?: number;
  sma200_slope?: number;
  // Momentum
  rsi_14?: number;
  macd?: number;
  macd_signal?: number;
  macd_histogram?: number;
  adx?: number;
  stochastic_rsi?: number;
  // Volatility
  atr?: number;
  atr_percent?: number;
  bollinger_band_position?: number;
  bollinger_band_width?: number;
  volatility_weekly?: number;
  volatility_monthly?: number;
  // Performance periods (% returns)
  perf_1w?: number;
  perf_1m?: number;
  perf_3m?: number;
  perf_6m?: number;
  perf_ytd?: number;
  perf_1y?: number;
  perf_3y?: number;
  perf_5y?: number;
  // Intraday
  gap_percent?: number;
  change_from_open_percent?: number;
  // Range distances
  dist_from_20d_high?: number;
  dist_from_20d_low?: number;
  dist_from_50d_high?: number;
  dist_from_50d_low?: number;
  dist_from_52w_high?: number;
  dist_from_52w_low?: number;
  dist_from_ath?: number;
  dist_from_atl?: number;
  // Volume trend
  volume_trend: string;
  // Volume / accumulation
  obv_trend: number;
  ad_trend: number;
  chaikin_money_flow?: number;
  vwap_deviation?: number;
  anchored_vwap_deviation?: number;
  volume_dryup_ratio?: number;
  breakout_volume_multiple?: number;
  updown_volume_ratio?: number;
  // Trend / extension
  trend: TrendClassification;
  is_extended: boolean;
  extension_pct_above_20ma?: number;
  extension_pct_above_50ma?: number;
  // Support / resistance
  support_resistance: SupportResistanceLevels;
  // Relative strength
  rs_vs_spy?: number;
  rs_vs_qqq?: number;
  rs_vs_sector?: number;
  // Return percentile ranks
  return_pct_rank_20d?: number;
  return_pct_rank_63d?: number;
  return_pct_rank_126d?: number;
  return_pct_rank_252d?: number;
  // Drawdown
  max_drawdown_3m?: number;
  max_drawdown_1y?: number;
  // Gap / post-earnings
  gap_filled: boolean;
  post_earnings_drift?: number;
  // Composite
  technical_score: number;
}

export interface FundamentalData {
  revenue_ttm?: number;
  revenue_growth_yoy?: number;
  revenue_growth_qoq?: number;
  eps_ttm?: number;
  eps_growth_yoy?: number;
  gross_margin?: number;
  operating_margin?: number;
  net_margin?: number;
  free_cash_flow?: number;
  free_cash_flow_margin?: number;
  cash?: number;
  total_debt?: number;
  net_debt?: number;
  current_ratio?: number;
  debt_to_equity?: number;
  shares_outstanding?: number;
  roe?: number;
  roic?: number;
  sector?: string;
  beta?: number;
  // Story 4: Enhanced growth
  eps_growth_next_year?: number;
  eps_growth_ttm?: number;
  eps_growth_3y?: number;
  eps_growth_5y?: number;
  eps_growth_next_5y?: number;
  sales_growth_ttm?: number;
  sales_growth_3y?: number;
  sales_growth_5y?: number;
  // Story 4: Quality
  roa?: number;
  quick_ratio?: number;
  long_term_debt_equity?: number;
  // Story 4: Ownership & sentiment
  insider_ownership?: number;
  insider_transactions?: number;
  institutional_ownership?: number;
  institutional_transactions?: number;
  short_float?: number;
  short_ratio?: number;
  analyst_recommendation?: number;
  analyst_target_price?: number;
  target_price_distance?: number;
  shares_float?: number;
  dividend_yield?: number;
  fundamental_score: number;
  archetype: string;
  archetype_confidence: number;
}

export interface ValuationData {
  trailing_pe?: number;
  forward_pe?: number;
  peg_ratio?: number;
  price_to_sales?: number;
  ev_to_ebitda?: number;
  price_to_fcf?: number;
  fcf_yield?: number;
  // Story 4: Additional metrics
  ev_sales?: number;
  price_to_book?: number;
  price_to_cash?: number;
  peer_comparison_available: boolean;
  valuation_score: number;
  archetype_adjusted_score?: number;
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
  confidence_score: number;
  data_completeness_score: number;
  summary: string;
  bullish_factors: string[];
  bearish_factors: string[];
  entry_plan: EntryPlan;
  exit_plan: ExitPlan;
  risk_reward: RiskReward;
  position_sizing: PositionSizing;
  data_warnings: string[];
  signal_cards_weights: Record<string, number>;
}

// Story 5: Signal Card types
export type SignalCardLabelValue =
  | 'VERY_BULLISH'
  | 'BULLISH'
  | 'NEUTRAL'
  | 'BEARISH'
  | 'VERY_BEARISH';

export interface SignalCard {
  name: string;
  score: number;
  label: SignalCardLabelValue;
  explanation: string;
  top_positives: string[];
  top_negatives: string[];
  missing_data_warnings: string[];
}

export interface SignalCards {
  momentum: SignalCard;
  trend: SignalCard;
  entry_timing: SignalCard;
  volume_accumulation: SignalCard;
  volatility_risk: SignalCard;
  relative_strength: SignalCard;
  growth: SignalCard;
  valuation: SignalCard;
  quality: SignalCard;
  ownership: SignalCard;
  catalyst: SignalCard;
}

export interface DataQualityReport {
  score: number;
  warnings: string[];
}

export interface SignalProfile {
  momentum: string;
  growth: string;
  valuation: string;
  entry_timing: string;
  sentiment: string;
  risk_reward: string;
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
  archetype: string;
  archetype_confidence: number;
  market_regime: string;
  regime_confidence: number;
  signal_profile?: SignalProfile;
  signal_cards?: SignalCards;
  disclaimer: string;
}

export interface AnalysisRequest {
  ticker: string;
  horizons?: string[];
  risk_profile?: string;
}
