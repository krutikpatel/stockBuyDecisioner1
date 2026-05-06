import type { SignalCards as SignalCardsType } from '../types/stock';
import { SignalCard } from './SignalCard';

interface Props {
  cards: SignalCardsType;
}

const CARD_ORDER: Array<{ key: keyof SignalCardsType; label: string }> = [
  { key: 'momentum', label: 'Momentum' },
  { key: 'trend', label: 'Trend' },
  { key: 'entry_timing', label: 'Entry Timing' },
  { key: 'volume_accumulation', label: 'Volume / Accumulation' },
  { key: 'volatility_risk', label: 'Volatility / Risk' },
  { key: 'relative_strength', label: 'Relative Strength' },
  { key: 'growth', label: 'Growth' },
  { key: 'valuation', label: 'Valuation' },
  { key: 'quality', label: 'Quality' },
  { key: 'ownership', label: 'Ownership' },
  { key: 'catalyst', label: 'Catalyst' },
];

export function SignalCardsGrid({ cards }: Props) {
  return (
    <div className="bg-slate-800/60 rounded-xl border border-slate-700 p-5">
      <h3 className="text-slate-200 font-semibold mb-4">Signal Cards</h3>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
        {CARD_ORDER.map(({ key }) => {
          const card = cards[key];
          // Override display name from name field for clarity
          return <SignalCard key={key} card={card} />;
        })}
      </div>
    </div>
  );
}
