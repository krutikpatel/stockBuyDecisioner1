import { useState } from 'react';
import { analyzeStock } from '../api/stockApi';
import type { StockAnalysisResult } from '../types/stock';
import { RecommendationCard } from '../components/RecommendationCard';
import { TechnicalChart } from '../components/TechnicalChart';
import { ScoreBreakdown } from '../components/ScoreBreakdown';
import { NewsSection } from '../components/NewsSection';
import { DataWarnings } from '../components/DataWarnings';
import { MarkdownReport } from '../components/MarkdownReport';
import { SignalProfileCard } from '../components/SignalProfileCard';
import { RegimeArchetypeBar } from '../components/RegimeArchetypeBar';
import { SignalCardsGrid } from '../components/SignalCardsGrid';
import { PerformanceTable } from '../components/PerformanceTable';
import { OwnershipPanel } from '../components/OwnershipPanel';
import { VolumePanel } from '../components/VolumePanel';

const RISK_PROFILES = ['conservative', 'moderate', 'aggressive'];

function fmt(v?: number) { return v != null ? `${v.toFixed(2)}%` : 'N/A'; }
function fmtB(v?: number) {
  if (v == null) return 'N/A';
  const b = v / 1e9;
  return b >= 1 ? `$${b.toFixed(2)}B` : `$${(v / 1e6).toFixed(0)}M`;
}

export function Dashboard() {
  const [ticker, setTicker] = useState('');
  const [riskProfile, setRiskProfile] = useState('moderate');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<StockAnalysisResult | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!ticker.trim()) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const data = await analyzeStock({ ticker: ticker.trim(), risk_profile: riskProfile });
      setResult(data);
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
        ?? (err as Error)?.message
        ?? 'Analysis failed';
      setError(msg);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-slate-900 text-slate-100">
      {/* Header */}
      <div className="bg-slate-800 border-b border-slate-700 px-6 py-4">
        <h1 className="text-2xl font-bold text-white">Stock Decision Tool</h1>
        <p className="text-sm text-slate-400 mt-0.5">Decision-support analysis across short, medium, and long-term horizons</p>
      </div>

      <div className="max-w-7xl mx-auto px-4 py-6">
        {/* Search form */}
        <form onSubmit={handleSubmit} className="flex gap-3 mb-8 flex-wrap">
          <input
            type="text"
            value={ticker}
            onChange={e => setTicker(e.target.value.toUpperCase())}
            placeholder="Enter ticker (e.g. AAPL)"
            className="flex-1 min-w-48 bg-slate-800 border border-slate-600 rounded-lg px-4 py-2.5 text-slate-100 placeholder-slate-500 focus:outline-none focus:border-blue-500 font-mono text-lg uppercase"
          />
          <select
            value={riskProfile}
            onChange={e => setRiskProfile(e.target.value)}
            className="bg-slate-800 border border-slate-600 rounded-lg px-3 py-2.5 text-slate-200 focus:outline-none focus:border-blue-500"
          >
            {RISK_PROFILES.map(p => (
              <option key={p} value={p}>{p.charAt(0).toUpperCase() + p.slice(1)}</option>
            ))}
          </select>
          <button
            type="submit"
            disabled={loading || !ticker.trim()}
            className="bg-blue-600 hover:bg-blue-500 disabled:bg-slate-700 disabled:text-slate-500 text-white font-semibold px-6 py-2.5 rounded-lg transition-colors"
          >
            {loading ? 'Analyzing…' : 'Analyze'}
          </button>
        </form>

        {/* Error */}
        {error && (
          <div className="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 mb-6">
            {error}
          </div>
        )}

        {/* Loading */}
        {loading && (
          <div className="text-center py-16">
            <div className="inline-block w-8 h-8 border-4 border-blue-500 border-t-transparent rounded-full animate-spin mb-4" />
            <p className="text-slate-400">Fetching market data and running analysis…</p>
            <p className="text-xs text-slate-600 mt-1">This can take 10–30 seconds</p>
          </div>
        )}

        {/* Results */}
        {result && !loading && (
          <div className="space-y-6">
            {/* Price header */}
            <div className="bg-slate-800 rounded-xl border border-slate-700 p-5">
              <div className="flex items-center justify-between flex-wrap gap-4">
                <div>
                  <h2 className="text-3xl font-bold text-white">{result.ticker}</h2>
                  <p className="text-slate-400 text-sm mt-0.5">Generated {new Date(result.generated_at).toLocaleString()}</p>
                  <div className="mt-2">
                    <RegimeArchetypeBar
                      archetype={result.archetype}
                      archetypeConfidence={result.archetype_confidence}
                      marketRegime={result.market_regime}
                      regimeConfidence={result.regime_confidence}
                    />
                  </div>
                </div>
                <div className="text-right">
                  <div className="text-4xl font-bold font-mono text-white">${result.current_price.toFixed(2)}</div>
                  <div className="text-sm text-slate-400 mt-0.5">
                    52W: ${result.market_data.week_52_low?.toFixed(2) ?? '—'} — ${result.market_data.week_52_high?.toFixed(2) ?? '—'}
                  </div>
                </div>
                <div className="grid grid-cols-4 gap-x-6 gap-y-1 text-sm">
                  <span className="text-slate-500">1M:</span><span className={`font-mono ${(result.market_data.return_1m ?? 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>{fmt(result.market_data.return_1m)}</span>
                  <span className="text-slate-500">3M:</span><span className={`font-mono ${(result.market_data.return_3m ?? 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>{fmt(result.market_data.return_3m)}</span>
                  <span className="text-slate-500">6M:</span><span className={`font-mono ${(result.market_data.return_6m ?? 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>{fmt(result.market_data.return_6m)}</span>
                  <span className="text-slate-500">1Y:</span><span className={`font-mono ${(result.market_data.return_1y ?? 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>{fmt(result.market_data.return_1y)}</span>
                  <span className="text-slate-500">Beta:</span><span className="font-mono text-slate-200">{result.market_data.beta?.toFixed(2) ?? 'N/A'}</span>
                  <span className="text-slate-500">Mkt Cap:</span><span className="font-mono text-slate-200">{fmtB(result.market_data.market_cap)}</span>
                </div>
              </div>
            </div>

            {/* Data warnings */}
            <DataWarnings quality={result.data_quality} />

            {/* Signal profile */}
            {result.signal_profile && (
              <SignalProfileCard profile={result.signal_profile} />
            )}

            {/* Signal cards grid */}
            {result.signal_cards && (
              <SignalCardsGrid cards={result.signal_cards} />
            )}

            {/* Recommendation cards */}
            <div>
              <h3 className="text-slate-300 font-semibold mb-3">Recommendations</h3>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {result.recommendations.map(rec => (
                  <RecommendationCard key={rec.horizon} rec={rec} />
                ))}
              </div>
            </div>

            {/* Performance table */}
            <PerformanceTable technicals={result.technicals} />

            {/* Score breakdown + Technical */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              <ScoreBreakdown
                technicals={result.technicals}
                fundamentals={result.fundamentals}
                valuation={result.valuation}
                earnings={result.earnings}
                news={result.news}
              />
              <TechnicalChart technicals={result.technicals} currentPrice={result.current_price} />
            </div>

            {/* Fundamentals + Valuation */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              <div className="bg-slate-800/60 rounded-xl border border-slate-700 p-5">
                <h3 className="text-slate-200 font-semibold mb-3">Fundamental Quality</h3>
                <div className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm">
                  {[
                    ['Revenue TTM', fmtB(result.fundamentals.revenue_ttm)],
                    ['Rev. Growth YoY', result.fundamentals.revenue_growth_yoy != null ? `${(result.fundamentals.revenue_growth_yoy * 100).toFixed(1)}%` : 'N/A'],
                    ['Rev. Growth QoQ', result.fundamentals.revenue_growth_qoq != null ? `${(result.fundamentals.revenue_growth_qoq * 100).toFixed(1)}%` : 'N/A'],
                    ['Gross Margin', result.fundamentals.gross_margin != null ? `${(result.fundamentals.gross_margin * 100).toFixed(1)}%` : 'N/A'],
                    ['Op. Margin', result.fundamentals.operating_margin != null ? `${(result.fundamentals.operating_margin * 100).toFixed(1)}%` : 'N/A'],
                    ['Net Margin', result.fundamentals.net_margin != null ? `${(result.fundamentals.net_margin * 100).toFixed(1)}%` : 'N/A'],
                    ['Free Cash Flow', fmtB(result.fundamentals.free_cash_flow)],
                    ['Net Debt', fmtB(result.fundamentals.net_debt)],
                    ['D/E Ratio', result.fundamentals.debt_to_equity?.toFixed(2) ?? 'N/A'],
                    ['LT D/E', result.fundamentals.long_term_debt_equity?.toFixed(2) ?? 'N/A'],
                    ['Current Ratio', result.fundamentals.current_ratio?.toFixed(2) ?? 'N/A'],
                    ['Quick Ratio', result.fundamentals.quick_ratio?.toFixed(2) ?? 'N/A'],
                    ['ROE', result.fundamentals.roe != null ? `${(result.fundamentals.roe * 100).toFixed(1)}%` : 'N/A'],
                    ['ROIC', result.fundamentals.roic != null ? `${(result.fundamentals.roic * 100).toFixed(1)}%` : 'N/A'],
                    ['ROA', result.fundamentals.roa != null ? `${(result.fundamentals.roa * 100).toFixed(1)}%` : 'N/A'],
                    ['Div. Yield', result.fundamentals.dividend_yield != null ? `${result.fundamentals.dividend_yield.toFixed(2)}%` : 'N/A'],
                  ].map(([label, val]) => (
                    <>
                      <span key={`l-${label}`} className="text-slate-500">{label}</span>
                      <span key={`v-${label}`} className="text-slate-200 font-mono">{val}</span>
                    </>
                  ))}
                </div>
              </div>

              <div className="bg-slate-800/60 rounded-xl border border-slate-700 p-5">
                <h3 className="text-slate-200 font-semibold mb-3">Valuation</h3>
                <div className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm">
                  {[
                    ['Trailing P/E', result.valuation.trailing_pe?.toFixed(1) ?? 'N/A'],
                    ['Forward P/E', result.valuation.forward_pe?.toFixed(1) ?? 'N/A'],
                    ['PEG Ratio', result.valuation.peg_ratio?.toFixed(2) ?? 'N/A'],
                    ['Price/Sales', result.valuation.price_to_sales?.toFixed(2) ?? 'N/A'],
                    ['EV/EBITDA', result.valuation.ev_to_ebitda?.toFixed(1) ?? 'N/A'],
                    ['EV/Sales', result.valuation.ev_sales?.toFixed(2) ?? 'N/A'],
                    ['P/Book', result.valuation.price_to_book?.toFixed(2) ?? 'N/A'],
                    ['P/Cash', result.valuation.price_to_cash?.toFixed(2) ?? 'N/A'],
                    ['P/FCF', result.valuation.price_to_fcf?.toFixed(1) ?? 'N/A'],
                    ['FCF Yield', result.valuation.fcf_yield != null ? `${result.valuation.fcf_yield.toFixed(2)}%` : 'N/A'],
                    ['Target Dist.', result.fundamentals.target_price_distance != null ? `${result.fundamentals.target_price_distance.toFixed(1)}%` : 'N/A'],
                    ['Peer Comparison', result.valuation.peer_comparison_available ? 'Available' : 'N/A'],
                  ].map(([label, val]) => (
                    <>
                      <span key={`l-${label}`} className="text-slate-500">{label}</span>
                      <span key={`v-${label}`} className="text-slate-200 font-mono">{val}</span>
                    </>
                  ))}
                </div>
              </div>
            </div>

            {/* Ownership + Volume */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              <OwnershipPanel fundamentals={result.fundamentals} />
              <VolumePanel technicals={result.technicals} />
            </div>

            {/* News */}
            <NewsSection news={result.news} />

            {/* Earnings */}
            <div className="bg-slate-800/60 rounded-xl border border-slate-700 p-5">
              <h3 className="text-slate-200 font-semibold mb-3">Earnings</h3>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-x-6 gap-y-2 text-sm">
                {[
                  ['Last Earnings', result.earnings.last_earnings_date?.slice(0, 10) ?? 'N/A'],
                  ['Next Earnings', result.earnings.next_earnings_date?.slice(0, 10) ?? 'N/A'],
                  ['Beat Rate', result.earnings.beat_rate != null ? `${(result.earnings.beat_rate * 100).toFixed(0)}%` : 'N/A'],
                  ['Avg EPS Surprise', result.earnings.avg_eps_surprise_pct != null ? `${result.earnings.avg_eps_surprise_pct.toFixed(1)}%` : 'N/A'],
                  ['Earnings < 30d?', result.earnings.within_30_days ? '⚠ Yes' : 'No'],
                  ['Score', `${result.earnings.earnings_score.toFixed(0)}/100`],
                ].map(([label, val]) => (
                  <>
                    <span key={`l-${label}`} className="text-slate-500">{label}</span>
                    <span key={`v-${label}`} className={`font-mono ${label === 'Earnings < 30d?' && val !== 'No' ? 'text-yellow-400' : 'text-slate-200'}`}>{val}</span>
                  </>
                ))}
              </div>
            </div>

            {/* Markdown report */}
            <MarkdownReport markdown={result.markdown_report} />

            {/* Disclaimer */}
            <p className="text-xs text-slate-600 text-center pb-6">{result.disclaimer}</p>
          </div>
        )}
      </div>
    </div>
  );
}
