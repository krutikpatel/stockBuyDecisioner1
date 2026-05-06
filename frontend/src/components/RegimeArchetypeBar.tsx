const ARCHETYPE_STYLES: Record<string, { bg: string; text: string }> = {
  HYPER_GROWTH:       { bg: 'bg-violet-900/60',  text: 'text-violet-300' },
  PROFITABLE_GROWTH:  { bg: 'bg-blue-900/50',    text: 'text-blue-300' },
  CYCLICAL_GROWTH:    { bg: 'bg-amber-900/50',   text: 'text-amber-300' },
  MATURE_VALUE:       { bg: 'bg-slate-700/70',   text: 'text-slate-300' },
  TURNAROUND:         { bg: 'bg-orange-900/50',  text: 'text-orange-300' },
  SPECULATIVE_STORY:  { bg: 'bg-pink-900/50',    text: 'text-pink-300' },
  DEFENSIVE:          { bg: 'bg-teal-900/50',    text: 'text-teal-300' },
  COMMODITY_CYCLICAL: { bg: 'bg-yellow-900/50',  text: 'text-yellow-300' },
};

const REGIME_STYLES: Record<string, { bg: string; text: string; dot: string }> = {
  BULL_RISK_ON:          { bg: 'bg-green-900/50',  text: 'text-green-300',  dot: 'bg-green-400' },
  BULL_NARROW_LEADERSHIP:{ bg: 'bg-lime-900/40',   text: 'text-lime-300',   dot: 'bg-lime-400' },
  SIDEWAYS_CHOPPY:       { bg: 'bg-slate-700/60',  text: 'text-slate-300',  dot: 'bg-slate-400' },
  BEAR_RISK_OFF:         { bg: 'bg-red-900/50',    text: 'text-red-300',    dot: 'bg-red-400' },
  SECTOR_ROTATION:       { bg: 'bg-yellow-900/40', text: 'text-yellow-300', dot: 'bg-yellow-400' },
  LIQUIDITY_RALLY:       { bg: 'bg-cyan-900/40',   text: 'text-cyan-300',   dot: 'bg-cyan-400' },
};

interface Props {
  archetype: string;
  archetypeConfidence: number;
  marketRegime: string;
  regimeConfidence: number;
}

export function RegimeArchetypeBar({ archetype, archetypeConfidence, marketRegime, regimeConfidence }: Props) {
  const aStyle = ARCHETYPE_STYLES[archetype] ?? { bg: 'bg-slate-700', text: 'text-slate-300' };
  const rStyle = REGIME_STYLES[marketRegime] ?? { bg: 'bg-slate-700', text: 'text-slate-300', dot: 'bg-slate-400' };

  return (
    <div className="flex flex-wrap gap-3 items-center">
      {/* Archetype badge */}
      <div className={`flex items-center gap-2 rounded-full px-4 py-1.5 ${aStyle.bg} border border-white/10`}>
        <span className="text-xs text-slate-400 font-semibold">ARCHETYPE</span>
        <span className={`text-sm font-bold ${aStyle.text}`}>{archetype.replace(/_/g, ' ')}</span>
        <span className="text-xs text-slate-500">{archetypeConfidence.toFixed(0)}%</span>
      </div>

      {/* Regime badge */}
      <div className={`flex items-center gap-2 rounded-full px-4 py-1.5 ${rStyle.bg} border border-white/10`}>
        <span className={`w-2 h-2 rounded-full ${rStyle.dot} flex-shrink-0`} />
        <span className="text-xs text-slate-400 font-semibold">REGIME</span>
        <span className={`text-sm font-bold ${rStyle.text}`}>{marketRegime.replace(/_/g, ' ')}</span>
        <span className="text-xs text-slate-500">{regimeConfidence.toFixed(0)}%</span>
      </div>
    </div>
  );
}
