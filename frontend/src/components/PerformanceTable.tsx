import type { TechnicalIndicators } from '../types/stock';

interface Props {
  technicals: TechnicalIndicators;
}

function fmtPct(v?: number | null) {
  if (v == null) return 'N/A';
  const sign = v >= 0 ? '+' : '';
  return `${sign}${v.toFixed(2)}%`;
}

function perfClass(v?: number | null) {
  if (v == null) return 'text-slate-400';
  return v >= 0 ? 'text-green-400' : 'text-red-400';
}

const PERIODS: Array<{ key: keyof TechnicalIndicators; label: string }> = [
  { key: 'perf_1w', label: '1W' },
  { key: 'perf_1m', label: '1M' },
  { key: 'perf_3m', label: '3M' },
  { key: 'perf_6m', label: '6M' },
  { key: 'perf_ytd', label: 'YTD' },
  { key: 'perf_1y', label: '1Y' },
  { key: 'perf_3y', label: '3Y' },
  { key: 'perf_5y', label: '5Y' },
];

export function PerformanceTable({ technicals }: Props) {
  return (
    <div className="bg-slate-800/60 rounded-xl border border-slate-700 p-5">
      <h3 className="text-slate-200 font-semibold mb-3">Performance</h3>
      <div className="grid grid-cols-4 sm:grid-cols-8 gap-2 text-center">
        {PERIODS.map(({ key, label }) => {
          const val = technicals[key] as number | undefined;
          return (
            <div key={key} className="flex flex-col gap-0.5">
              <span className="text-xs text-slate-500 uppercase">{label}</span>
              <span className={`text-sm font-mono font-semibold ${perfClass(val)}`}>
                {fmtPct(val)}
              </span>
            </div>
          );
        })}
      </div>
      {(technicals.max_drawdown_3m != null || technicals.max_drawdown_1y != null) && (
        <div className="mt-3 pt-3 border-t border-slate-700 grid grid-cols-2 gap-x-6 gap-y-1 text-sm">
          {technicals.max_drawdown_3m != null && (
            <>
              <span className="text-slate-500">Max DD 3M</span>
              <span className="font-mono text-red-400">{fmtPct(technicals.max_drawdown_3m)}</span>
            </>
          )}
          {technicals.max_drawdown_1y != null && (
            <>
              <span className="text-slate-500">Max DD 1Y</span>
              <span className="font-mono text-red-400">{fmtPct(technicals.max_drawdown_1y)}</span>
            </>
          )}
        </div>
      )}
    </div>
  );
}
