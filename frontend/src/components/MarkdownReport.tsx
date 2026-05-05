import ReactMarkdown from 'react-markdown';

interface Props {
  markdown: string;
}

export function MarkdownReport({ markdown }: Props) {
  return (
    <details className="bg-slate-800/60 rounded-xl border border-slate-700">
      <summary className="p-5 cursor-pointer text-slate-200 font-semibold select-none hover:text-white">
        Full Markdown Report ▾
      </summary>
      <div className="px-5 pb-5 prose prose-invert prose-sm max-w-none
        prose-headings:text-slate-200 prose-p:text-slate-300 prose-li:text-slate-300
        prose-table:text-slate-300 prose-th:text-slate-400 prose-td:text-slate-300
        prose-strong:text-slate-100 prose-a:text-blue-400">
        <ReactMarkdown>{markdown}</ReactMarkdown>
      </div>
    </details>
  );
}
