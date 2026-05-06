import type { FundamentalData } from '../types/stock';

interface Props {
  fundamentals: FundamentalData;
}

function fmtPct(v?: number | null) {
  if (v == null) return 'N/A';
  return `${v.toFixed(2)}%`;
}

function fmtRec(v?: number | null) {
  if (v == null) return 'N/A';
  const labels: Record<number, string> = { 1: 'Strong Buy', 2: 'Buy', 3: 'Hold', 4: 'Sell', 5: 'Strong Sell' };
  const rounded = Math.round(v);
  return labels[rounded] ?? v.toFixed(1);
}

function fmtTxn(v?: number | null) {
  if (v == null) return 'N/A';
  return v >= 0 ? 'Buying' : 'Selling';
}

export function OwnershipPanel({ fundamentals: f }: Props) {
  return (
    <div className="bg-slate-800/60 rounded-xl border border-slate-700 p-5">
      <h3 className="text-slate-200 font-semibold mb-3">Ownership</h3>
      <div className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm">
        {[
          ['Insider Ownership', fmtPct(f.insider_ownership)],
          ['Insider Activity', fmtTxn(f.insider_transactions)],
          ['Inst. Ownership', fmtPct(f.institutional_ownership)],
          ['Inst. Activity', fmtTxn(f.institutional_transactions)],
          ['Short Float', fmtPct(f.short_float)],
          ['Short Ratio', f.short_ratio != null ? f.short_ratio.toFixed(1) : 'N/A'],
          ['Analyst Rec.', fmtRec(f.analyst_recommendation)],
          ['Target Distance', fmtPct(f.target_price_distance)],
        ].map(([label, val]) => (
          <>
            <span key={`l-${label}`} className="text-slate-500">{label}</span>
            <span key={`v-${label}`} className="text-slate-200 font-mono">{val}</span>
          </>
        ))}
      </div>
    </div>
  );
}
