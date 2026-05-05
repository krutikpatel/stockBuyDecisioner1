import type { TechnicalIndicators } from '../types/stock';

interface Props {
  technicals: TechnicalIndicators;
  currentPrice: number;
}

export function TechnicalChart({ technicals: ti }: Props) {

  const rows = [
    { label: 'Trend', value: ti.trend.label.replace(/_/g, ' '), color: ti.trend.label === 'strong_uptrend' ? 'text-green-400' : ti.trend.label === 'downtrend' ? 'text-red-400' : 'text-yellow-400' },
    { label: 'RSI (14)', value: ti.rsi_14?.toFixed(1) ?? 'N/A', color: (ti.rsi_14 ?? 50) > 75 ? 'text-red-400' : (ti.rsi_14 ?? 50) < 35 ? 'text-yellow-400' : 'text-green-400' },
    { label: 'MACD Hist.', value: ti.macd_histogram?.toFixed(4) ?? 'N/A', color: (ti.macd_histogram ?? 0) > 0 ? 'text-green-400' : 'text-red-400' },
    { label: 'Volume', value: ti.volume_trend.replace(/_/g, ' '), color: ti.volume_trend === 'above_average' ? 'text-green-400' : ti.volume_trend === 'below_average' ? 'text-red-400' : 'text-slate-300' },
    { label: 'Extended?', value: ti.is_extended ? 'Yes' : 'No', color: ti.is_extended ? 'text-red-400' : 'text-green-400' },
    { label: 'RS vs SPY', value: ti.rs_vs_spy?.toFixed(2) ?? 'N/A', color: (ti.rs_vs_spy ?? 1) >= 1 ? 'text-green-400' : 'text-red-400' },
  ];

  const maRows = [
    { label: 'MA(10)', value: ti.ma_10 },
    { label: 'MA(20)', value: ti.ma_20 },
    { label: 'MA(50)', value: ti.ma_50 },
    { label: 'MA(100)', value: ti.ma_100 },
    { label: 'MA(200)', value: ti.ma_200 },
  ];

  const sr = ti.support_resistance;

  return (
    <div className="bg-slate-800/60 rounded-xl border border-slate-700 p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-slate-200 font-semibold">Technical Analysis</h3>
        <span className="text-xs text-slate-400">Score: <span className="text-slate-200 font-mono">{ti.technical_score.toFixed(0)}/100</span></span>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 mb-5">
        {rows.map(r => (
          <div key={r.label} className="bg-slate-900/50 rounded-lg p-2.5">
            <div className="text-xs text-slate-500">{r.label}</div>
            <div className={`text-sm font-semibold capitalize ${r.color}`}>{r.value}</div>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-2 gap-4 mb-4">
        <div>
          <div className="text-xs text-slate-400 font-semibold mb-2">Moving Averages</div>
          <div className="space-y-1">
            {maRows.map(r => (
              <div key={r.label} className="flex justify-between text-xs">
                <span className="text-slate-500">{r.label}</span>
                <span className="text-slate-200 font-mono">{r.value != null ? `$${r.value.toFixed(2)}` : 'N/A'}</span>
              </div>
            ))}
          </div>
        </div>

        <div>
          <div className="text-xs text-slate-400 font-semibold mb-2">Support / Resistance</div>
          <div className="space-y-1">
            {sr.resistances.slice(0, 3).map((r, i) => (
              <div key={`r${i}`} className="flex justify-between text-xs">
                <span className="text-red-400">Resistance {i + 1}</span>
                <span className="text-red-300 font-mono">${r.toFixed(2)}</span>
              </div>
            ))}
            {sr.supports.slice(0, 3).map((s, i) => (
              <div key={`s${i}`} className="flex justify-between text-xs">
                <span className="text-green-400">Support {i + 1}</span>
                <span className="text-green-300 font-mono">${s.toFixed(2)}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
