import { useState } from 'react';
import type { SignalCard as SignalCardType, SignalCardLabelValue } from '../types/stock';

const LABEL_COLORS: Record<SignalCardLabelValue, string> = {
  VERY_BULLISH: 'text-green-400',
  BULLISH: 'text-emerald-400',
  NEUTRAL: 'text-slate-400',
  BEARISH: 'text-orange-400',
  VERY_BEARISH: 'text-red-400',
};

const LABEL_BG: Record<SignalCardLabelValue, string> = {
  VERY_BULLISH: 'bg-green-900/30 border-green-700',
  BULLISH: 'bg-emerald-900/20 border-emerald-700',
  NEUTRAL: 'bg-slate-800/40 border-slate-600',
  BEARISH: 'bg-orange-900/20 border-orange-700',
  VERY_BEARISH: 'bg-red-900/30 border-red-700',
};

const GAUGE_COLORS: Record<SignalCardLabelValue, string> = {
  VERY_BULLISH: 'bg-green-500',
  BULLISH: 'bg-emerald-500',
  NEUTRAL: 'bg-slate-500',
  BEARISH: 'bg-orange-500',
  VERY_BEARISH: 'bg-red-500',
};

interface Props {
  card: SignalCardType;
}

export function SignalCard({ card }: Props) {
  const [expanded, setExpanded] = useState(false);
  const labelValue = card.label as SignalCardLabelValue;
  const hasDetails =
    card.top_positives.length > 0 ||
    card.top_negatives.length > 0 ||
    card.missing_data_warnings.length > 0;

  return (
    <div className={`rounded-lg border ${LABEL_BG[labelValue] ?? 'bg-slate-800/40 border-slate-600'} p-4 flex flex-col gap-2`}>
      {/* Header */}
      <div className="flex items-center justify-between">
        <span className="text-xs text-slate-400 uppercase tracking-wider font-semibold">
          {card.name.replace(/_/g, ' ')}
        </span>
        <span className={`text-xs font-bold px-1.5 py-0.5 rounded ${LABEL_COLORS[labelValue] ?? 'text-slate-300'}`}>
          {card.label.replace(/_/g, ' ')}
        </span>
      </div>

      {/* Score gauge */}
      <div className="flex items-center gap-2">
        <div className="flex-1 bg-slate-700 rounded-full h-1.5 overflow-hidden">
          <div
            className={`h-full rounded-full transition-all ${GAUGE_COLORS[labelValue] ?? 'bg-slate-500'}`}
            style={{ width: `${card.score}%` }}
          />
        </div>
        <span className="text-sm font-bold text-slate-200 w-10 text-right">
          {card.score.toFixed(0)}
        </span>
      </div>

      {/* Explanation (truncated) */}
      <p className="text-xs text-slate-400 leading-relaxed line-clamp-2">{card.explanation}</p>

      {/* Expand toggle */}
      {hasDetails && (
        <button
          onClick={() => setExpanded(e => !e)}
          className="text-xs text-slate-500 hover:text-slate-300 text-left transition-colors"
        >
          {expanded ? '▲ Hide factors' : '▼ Show factors'}
        </button>
      )}

      {/* Expanded details */}
      {expanded && (
        <div className="flex flex-col gap-2 mt-1">
          {card.top_positives.length > 0 && (
            <div>
              <span className="text-xs text-green-400 font-semibold">Positives</span>
              <ul className="mt-0.5 space-y-0.5">
                {card.top_positives.map((p, i) => (
                  <li key={i} className="text-xs text-slate-300">✓ {p}</li>
                ))}
              </ul>
            </div>
          )}
          {card.top_negatives.length > 0 && (
            <div>
              <span className="text-xs text-red-400 font-semibold">Negatives</span>
              <ul className="mt-0.5 space-y-0.5">
                {card.top_negatives.map((n, i) => (
                  <li key={i} className="text-xs text-slate-300">✗ {n}</li>
                ))}
              </ul>
            </div>
          )}
          {card.missing_data_warnings.length > 0 && (
            <div>
              <span className="text-xs text-yellow-400 font-semibold">Missing Data</span>
              <ul className="mt-0.5 space-y-0.5">
                {card.missing_data_warnings.map((w, i) => (
                  <li key={i} className="text-xs text-slate-400">⚠ {w}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
