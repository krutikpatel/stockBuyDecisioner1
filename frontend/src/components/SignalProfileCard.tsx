import type { SignalProfile } from '../types/stock';

const SIGNAL_COLORS: Record<string, string> = {
  VERY_BULLISH: 'text-green-400',
  BULLISH:      'text-emerald-400',
  NEUTRAL:      'text-slate-400',
  BEARISH:      'text-orange-400',
  VERY_BEARISH: 'text-red-400',
  ATTRACTIVE:   'text-green-400',
  FAIR:         'text-slate-300',
  ELEVATED:     'text-yellow-400',
  RISKY:        'text-red-400',
  IDEAL:        'text-green-400',
  ACCEPTABLE:   'text-slate-300',
  EXTENDED:     'text-yellow-400',
  VERY_EXTENDED:'text-orange-400',
  EXCELLENT:    'text-green-400',
  GOOD:         'text-emerald-400',
  POOR:         'text-red-400',
};

const BG_COLORS: Record<string, string> = {
  VERY_BULLISH: 'bg-green-900/30 border-green-700',
  BULLISH:      'bg-emerald-900/20 border-emerald-700',
  NEUTRAL:      'bg-slate-800/40 border-slate-600',
  BEARISH:      'bg-orange-900/20 border-orange-700',
  VERY_BEARISH: 'bg-red-900/30 border-red-700',
  ATTRACTIVE:   'bg-green-900/30 border-green-700',
  FAIR:         'bg-slate-800/40 border-slate-600',
  ELEVATED:     'bg-yellow-900/20 border-yellow-700',
  RISKY:        'bg-red-900/30 border-red-700',
  IDEAL:        'bg-green-900/30 border-green-700',
  ACCEPTABLE:   'bg-slate-800/40 border-slate-600',
  EXTENDED:     'bg-yellow-900/20 border-yellow-700',
  VERY_EXTENDED:'bg-orange-900/20 border-orange-700',
  EXCELLENT:    'bg-green-900/30 border-green-700',
  GOOD:         'bg-emerald-900/20 border-emerald-700',
  POOR:         'bg-red-900/30 border-red-700',
};

function defaultBg(label: string) {
  return BG_COLORS[label] ?? 'bg-slate-800/40 border-slate-600';
}
function labelColor(label: string) {
  return SIGNAL_COLORS[label] ?? 'text-slate-300';
}

function SignalCell({ title, label }: { title: string; label: string }) {
  return (
    <div className={`rounded-lg border ${defaultBg(label)} p-3 flex flex-col gap-1`}>
      <span className="text-xs text-slate-500 uppercase tracking-wider font-semibold">{title}</span>
      <span className={`text-sm font-bold ${labelColor(label)}`}>{label.replace(/_/g, ' ')}</span>
    </div>
  );
}

interface Props {
  profile: SignalProfile;
}

export function SignalProfileCard({ profile }: Props) {
  return (
    <div className="bg-slate-800/60 rounded-xl border border-slate-700 p-5">
      <h3 className="text-slate-200 font-semibold mb-3">Signal Profile</h3>
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
        <SignalCell title="Momentum"     label={profile.momentum} />
        <SignalCell title="Growth"       label={profile.growth} />
        <SignalCell title="Valuation"    label={profile.valuation} />
        <SignalCell title="Entry Timing" label={profile.entry_timing} />
        <SignalCell title="Sentiment"    label={profile.sentiment} />
        <SignalCell title="Risk / Reward" label={profile.risk_reward} />
      </div>
    </div>
  );
}
