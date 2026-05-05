import type { HorizonRecommendation } from '../types/stock';

const DECISION_STYLES: Record<string, { bg: string; text: string; border: string }> = {
  BUY_NOW:           { bg: 'bg-green-900/60',  text: 'text-green-300',  border: 'border-green-600' },
  BUY_STARTER:       { bg: 'bg-emerald-900/40', text: 'text-emerald-300', border: 'border-emerald-600' },
  WAIT_FOR_PULLBACK: { bg: 'bg-yellow-900/40', text: 'text-yellow-300', border: 'border-yellow-600' },
  BUY_ON_BREAKOUT:   { bg: 'bg-blue-900/40',   text: 'text-blue-300',   border: 'border-blue-600' },
  WATCHLIST:         { bg: 'bg-slate-800/60',  text: 'text-slate-300',  border: 'border-slate-500' },
  AVOID:             { bg: 'bg-red-900/40',    text: 'text-red-300',    border: 'border-red-600' },
};

interface Props {
  rec: HorizonRecommendation;
}

function ScoreBar({ score }: { score: number }) {
  const color = score >= 80 ? 'bg-green-500' : score >= 65 ? 'bg-yellow-500' : score >= 50 ? 'bg-orange-500' : 'bg-red-500';
  return (
    <div className="w-full bg-slate-700 rounded-full h-2 mt-1">
      <div className={`${color} h-2 rounded-full transition-all`} style={{ width: `${score}%` }} />
    </div>
  );
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
          <div className="flex-1"><ScoreBar score={rec.score} /></div>
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
    </div>
  );
}
