import { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import TraceSidebar from '../components/TraceSidebar';
import LoadingSkeleton from '../components/LoadingSkeleton';
import EmptyState from '../components/EmptyState';
import Spinner from '../components/Spinner';
import { useToast } from '../components/Toast';
import { downloadMarkdown, downloadJSON } from '../utils/export';
import type { ReportSection } from '../types';

export default function Report() {
  const { id } = useParams<{ id: string }>();
  const [sections, setSections] = useState<ReportSection[]>([]);
  const [mdContent, setMdContent] = useState('');
  const [loading, setLoading] = useState(true);
  const [exporting, setExporting] = useState<string | null>(null);
  const [error, setError] = useState('');
  const [sidebar, setSidebar] = useState<{ insightId: string; sectionTitle: string } | null>(null);
  const { toast } = useToast();

  useEffect(() => {
    setLoading(true);
    fetch(`/api/report/${id}`)
      .then(r => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then(data => {
        setSections(data.sections || []);
        setMdContent(data.content || '');
      })
      .catch(err => { setError(err.message); })
      .finally(() => setLoading(false));
  }, [id]);

  /* export handlers */
  const handleExportMD = () => {
    setExporting('md');
    const content = mdContent || sections.map(s => `## ${s.section}\n\n${s.content}`).join('\n\n');
    downloadMarkdown(content, `competitive-analysis-${id}.md`);
    setTimeout(() => setExporting(null), 500);
    toast('Markdown 已导出', 'success');
  };

  const handleExportJSON = () => {
    setExporting('json');
    downloadJSON({ task_id: id, sections, content: mdContent }, `competitive-analysis-${id}.json`);
    setTimeout(() => setExporting(null), 500);
    toast('JSON 已导出', 'success');
  };

  /* derive an insight ID from a section's node_id or section name */
  const getInsightId = (section: ReportSection): string => {
    return section.node_id || `insight_${encodeURIComponent(section.section)}`;
  };

  return (
    <div className="max-w-5xl mx-auto p-6 animate-pageEnter">
      {/* Header */}
      <div className="flex items-center justify-between mb-6 flex-wrap gap-2">
        <h1 className="text-xl font-bold text-gray-100">竞品分析报告</h1>
        <div className="flex gap-2">
          <button
            onClick={handleExportMD}
            disabled={exporting !== null}
            className="px-3 py-1.5 bg-gray-800 border border-gray-700 rounded text-sm text-gray-300 hover:bg-gray-700 font-mono transition-all active:scale-95 disabled:opacity-60 inline-flex items-center gap-1.5"
          >
            {exporting === 'md' && <Spinner size="sm" />}
            导出 Markdown
          </button>
          <button
            onClick={handleExportJSON}
            disabled={exporting !== null}
            className="px-3 py-1.5 bg-gray-800 border border-gray-700 rounded text-sm text-gray-300 hover:bg-gray-700 font-mono transition-all active:scale-95 disabled:opacity-60 inline-flex items-center gap-1.5"
          >
            {exporting === 'json' && <Spinner size="sm" />}
            导出 JSON
          </button>
        </div>
      </div>

      {/* Content */}
      <div className="bg-gray-900 border border-gray-800 rounded-lg p-8">
        {loading && <LoadingSkeleton lines={8} />}

        {!loading && error && (
          <EmptyState icon="⚠" title={`加载失败: ${error}`} description="请确认后端服务已启动" />
        )}

        {!loading && !error && sections.length > 0 && (
          <div className="prose prose-invert max-w-none">
            {sections.map((s, i) => (
              <div key={i} className="mb-8 pb-6 border-b border-gray-800/50 last:border-b-0 animate-slideUp stagger-item">
                <h2 className="text-lg font-bold text-gray-100 mb-3">{s.section}</h2>
                <div className="text-gray-300 text-sm leading-relaxed whitespace-pre-wrap">{s.content}</div>
                <button
                  onClick={() => setSidebar({ insightId: getInsightId(s), sectionTitle: s.section })}
                  className="mt-2 text-xs text-cyan-400 hover:text-cyan-300 font-mono inline-flex items-center gap-1"
                >
                  <span>📎</span> 溯源
                </button>
              </div>
            ))}
          </div>
        )}

        {!loading && !error && sections.length === 0 && mdContent && (
          <div className="text-left text-gray-300 whitespace-pre-wrap text-sm leading-relaxed">{mdContent}</div>
        )}

        {!loading && !error && sections.length === 0 && !mdContent && (
          <EmptyState icon="📄" title="报告尚未生成" description="请等待 DAG 流水线完成" />
        )}
      </div>

      {/* Traceability Sidebar */}
      {sidebar && (
        <TraceSidebar
          isOpen={true}
          onClose={() => setSidebar(null)}
          insightId={sidebar.insightId}
          taskId={id!}
          sectionTitle={sidebar.sectionTitle}
        />
      )}
    </div>
  );
}
