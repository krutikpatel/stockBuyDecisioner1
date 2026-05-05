import type { DataQualityReport } from '../types/stock';

interface Props {
  quality: DataQualityReport;
}

export function DataWarnings({ quality }: Props) {
  if (quality.warnings.length === 0) return null;
  return (
    <div className="bg-yellow-900/20 border border-yellow-800 rounded-xl p-4">
      <div className="flex items-center gap-2 mb-2">
        <span className="text-yellow-400 font-semibold text-sm">Data Quality Warnings</span>
        <span className="text-xs text-yellow-600">({quality.score.toFixed(0)}/100)</span>
      </div>
      <ul className="space-y-1">
        {quality.warnings.map((w, i) => (
          <li key={i} className="text-xs text-yellow-300 flex gap-2">
            <span>⚠</span>{w}
          </li>
        ))}
      </ul>
    </div>
  );
}
