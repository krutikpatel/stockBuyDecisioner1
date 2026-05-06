import type { HorizonRecommendation } from '../types/stock';

const DECISION_STYLES: Record<string, { bg: string; text: string; border: string }> = {
  BUY_NOW:                   { bg: 'bg-green-900/60',   text: 'text-green-300',   border: 'border-green-600' },
  BUY_STARTER:               { bg: 'bg-emerald-900/40', text: 'text-emerald-300', border: 'border-emerald-600' },
  BUY_STARTER_EXTENDED:      { bg: 'bg-teal-900/40',    text: 'text-teal-300',    border: 'border-teal-600' },
  BUY_ON_PULLBACK:           { bg: 'bg-cyan-900/40',    text: 'text-cyan-300',    border: 'border-cyan-600' },
  BUY_ON_BREAKOUT:           { bg: 'bg-blue-900/40',    text: 'text-blue-300',    border: 'border-blue-600' },
  BUY_AFTER_EARNINGS:        { bg: 'bg-indigo-900/40',  text: 'text-indigo-300',  border: 'border-indigo-600' },
  WATCHLIST:                 { bg: 'bg-slate-800/60',   text: 'text-slate-300',   border: 'border-slate-500' },
  WATCHLIST_NEEDS_CATALYST:  { bg: 'bg-slate-800/40',   text: 'text-slate-400',   border: 'border-slate-600' },
  HOLD_EXISTING_DO_NOT_ADD:  { bg: 'bg-orange-900/30',  text: 'text-orange-300',  border: 'border-orange-700' },
  AVOID_BAD_BUSINESS:        { bg: 'bg-red-950/60',     text: 'text-red-400',     border: 'border-red-800' },
  AVOID_BAD_CHART:           { bg: 'bg-rose-900/50',    text: 'text-rose-300',    border: 'border-rose-700' },
  AVOID_BAD_RISK_REWARD:     { bg: 'bg-red-900/40',     text: 'text-red-300',     border: 'border-red-700' },
  AVOID_LOW_CONFIDENCE:      { bg: 'bg-neutral-800/60', text: 'text-neutral-400', border: 'border-neutral-600' },
  AVOID:                     { bg: 'bg-red-900/40',     text: 'text-red-300',     border: 'border-red-600' },
};

interface Props {
  rec: HorizonRecommendation;
}

function ScoreBar({ score, color }: { score: number; color: string }) {
  return (
    <div className="w-full bg-slate-700 rounded-full h-1.5 mt-1">
      <div className={`${color} h-1.5 rounded-full transition-all`} style={{ width: `${Math.min(100, score)}%` }} />
    </div>
  );
}

function scoreColor(score: number) {
  return score >= 80 ? 'bg-green-500' : score >= 65 ? 'bg-yellow-500' : score >= 50 ? 'bg-orange-500' : 'bg-red-500';
}

export function RecommendationCard({ rec }: Props) {
  const style = DECISION_STYLES[rec.decision] ?? DECISION_STYLES.WATCHLIST;
  const horizonLabel = rec.horizon.replace(/_/g, '-').replace(/\b\w/g, c => c.toUpperCase());

  return (
    <div className={`rounded-xl border ${style.border} ${style.bg} p-5 flex flex-col gap-3`}>
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">{horizonLabel}</span>
        <span className={`text-xs font-bold px-2 py-0.5 rounded-full border ${style.border} ${style.text}`}>
          {rec.confidence.replace(/_/g, ' ')}
        </span>
      </div>

      <div>
        <div className={`text-xl font-bold ${style.text}`}>{rec.decision.replace(/_/g, ' ')}</div>
        <div className="flex items-center gap-2 mt-1">
          <span className="text-slate-300 text-sm font-mono">{rec.score.toFixed(0)}/100</span>
          <div className="flex-1"><ScoreBar score={rec.score} color={scoreColor(rec.score)} /></div>
        </div>
      </div>

      <p className="text-slate-300 text-sm leading-relaxed">{rec.summary}</p>

      {rec.bullish_factors.length > 0 && (
        <div>
          <div className="text-xs text-green-400 font-semibold mb-1">BULLISH</div>
          <ul className="space-y-0.5">
            {rec.bullish_factors.slice(0, 3).map((f, i) => (
              <li key={i} className="text-xs text-slate-300 flex gap-1.5">
                <span className="text-green-500 mt-0.5 flex-shrink-0">↑</span>{f}
              </li>
            ))}
          </ul>
        </div>
      )}

      {rec.bearish_factors.length > 0 && (
        <div>
          <div className="text-xs text-red-400 font-semibold mb-1">BEARISH</div>
          <ul className="space-y-0.5">
            {rec.bearish_factors.slice(0, 3).map((f, i) => (
              <li key={i} className="text-xs text-slate-300 flex gap-1.5">
                <span className="text-red-500 mt-0.5 flex-shrink-0">↓</span>{f}
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="border-t border-slate-700 pt-3 grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
        <div><span className="text-slate-500">Entry:</span> <span className="text-slate-200 font-mono">${rec.entry_plan.preferred_entry?.toFixed(2) ?? '—'}</span></div>
        <div><span className="text-slate-500">Stop:</span> <span className="text-red-400 font-mono">${rec.exit_plan.stop_loss?.toFixed(2) ?? '—'}</span></div>
        <div><span className="text-slate-500">Target 1:</span> <span className="text-green-400 font-mono">${rec.exit_plan.first_target?.toFixed(2) ?? '—'}</span></div>
        <div><span className="text-slate-500">R/R:</span> <span className="text-slate-200 font-mono">{rec.risk_reward.ratio?.toFixed(2) ?? '—'}x</span></div>
        <div className="col-span-2"><span className="text-slate-500">Starter size:</span> <span className="text-slate-200">{rec.position_sizing.suggested_starter_pct_of_full}% of position · max {rec.position_sizing.max_portfolio_allocation_pct}% portfolio</span></div>
      </div>

      {/* Data completeness / confidence mini-bars */}
      <div className="border-t border-slate-700/50 pt-2 space-y-1.5">
        <div className="flex items-center gap-2 text-xs">
          <span className="text-slate-500 w-24 flex-shrink-0">Data quality</span>
          <div className="flex-1"><ScoreBar score={rec.data_completeness_score} color={scoreColor(rec.data_completeness_score)} /></div>
          <span className="text-slate-400 font-mono w-8 text-right">{rec.data_completeness_score?.toFixed(0) ?? '—'}</span>
        </div>
        <div className="flex items-center gap-2 text-xs">
          <span className="text-slate-500 w-24 flex-shrink-0">Confidence</span>
          <div className="flex-1"><ScoreBar score={rec.confidence_score} color="bg-blue-500" /></div>
          <span className="text-slate-400 font-mono w-8 text-right">{rec.confidence_score?.toFixed(0) ?? '—'}</span>
        </div>
        {rec.data_warnings.length > 0 && (
          <ul className="mt-1 space-y-0.5">
            {rec.data_warnings.map((w, i) => (
              <li key={i} className="text-xs text-yellow-500/80 flex gap-1.5">
                <span className="flex-shrink-0">⚠</span>{w}
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
