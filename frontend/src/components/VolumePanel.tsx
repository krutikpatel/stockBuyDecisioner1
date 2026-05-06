import type { TechnicalIndicators } from '../types/stock';

interface Props {
  technicals: TechnicalIndicators;
}

function trendLabel(v: number) {
  if (v === 1) return 'Rising';
  if (v === -1) return 'Falling';
  return 'Flat';
}

function trendClass(v: number) {
  if (v === 1) return 'text-green-400';
  if (v === -1) return 'text-red-400';
  return 'text-slate-400';
}

function fmtPct(v?: number | null) {
  if (v == null) return 'N/A';
  const sign = v >= 0 ? '+' : '';
  return `${sign}${v.toFixed(2)}%`;
}

function fmtNum(v?: number | null, decimals = 2) {
  if (v == null) return 'N/A';
  return v.toFixed(decimals);
}

export function VolumePanel({ technicals: t }: Props) {
  return (
    <div className="bg-slate-800/60 rounded-xl border border-slate-700 p-5">
      <h3 className="text-slate-200 font-semibold mb-3">Volume & Accumulation</h3>
      <div className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm">
        <span className="text-slate-500">OBV Trend</span>
        <span className={`font-mono font-semibold ${trendClass(t.obv_trend)}`}>{trendLabel(t.obv_trend)}</span>

        <span className="text-slate-500">A/D Trend</span>
        <span className={`font-mono font-semibold ${trendClass(t.ad_trend)}`}>{trendLabel(t.ad_trend)}</span>

        <span className="text-slate-500">CMF (20D)</span>
        <span className={`font-mono ${t.chaikin_money_flow != null ? (t.chaikin_money_flow >= 0 ? 'text-green-400' : 'text-red-400') : 'text-slate-400'}`}>
          {fmtNum(t.chaikin_money_flow)}
        </span>

        <span className="text-slate-500">VWAP Dev.</span>
        <span className={`font-mono ${t.vwap_deviation != null ? (t.vwap_deviation >= 0 ? 'text-green-400' : 'text-red-400') : 'text-slate-400'}`}>
          {fmtPct(t.vwap_deviation)}
        </span>

        <span className="text-slate-500">Up/Down Vol</span>
        <span className="font-mono text-slate-200">{fmtNum(t.updown_volume_ratio)}</span>

        <span className="text-slate-500">Vol Dry-up</span>
        <span className="font-mono text-slate-200">{fmtNum(t.volume_dryup_ratio)}</span>

        <span className="text-slate-500">Breakout Vol</span>
        <span className="font-mono text-slate-200">
          {t.breakout_volume_multiple != null ? `${t.breakout_volume_multiple.toFixed(1)}x` : 'N/A'}
        </span>

        <span className="text-slate-500">Vol Trend</span>
        <span className="font-mono text-slate-200">{t.volume_trend}</span>
      </div>
    </div>
  );
}
