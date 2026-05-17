import { useState, useEffect, useRef, useCallback } from 'react';
import { useParams } from 'react-router-dom';
import TraceSidebar from '../components/TraceSidebar';
import LoadingSkeleton from '../components/LoadingSkeleton';
import EmptyState from '../components/EmptyState';
import Spinner from '../components/Spinner';
import { useToast } from '../components/Toast';
import { downloadMarkdown, downloadJSON, downloadPDF } from '../utils/export';
import { renderMarkdown, stripFirstHeading } from '../utils/markdown';
import AnalyticsDashboard from '../components/charts/AnalyticsDashboard';
import type { ReportSection } from '../types';

type ExportFormat = 'pdf' | 'markdown' | 'json';

interface ExportOption {
  key: ExportFormat;
  label: string;
  desc: string;
  icon: string;
}

const exportOptions: ExportOption[] = [
  { key: 'pdf', label: 'PDF 文档', desc: '适合分享与打印，保留完整排版', icon: '📑' },
  { key: 'markdown', label: 'Markdown', desc: '纯文本标记格式，适合技术文档', icon: '📝' },
  { key: 'json', label: 'JSON 数据', desc: '结构化原始数据，适合二次处理', icon: '📊' },
];

const exportLabels: Record<ExportFormat, Record<string, string>> = {
  pdf: { zh: 'PDF 文档', en: 'PDF Document' },
  markdown: { zh: 'Markdown', en: 'Markdown' },
  json: { zh: 'JSON 数据', en: 'JSON Data' },
};

const exportDescs: Record<ExportFormat, Record<string, string>> = {
  pdf: { zh: '适合分享与打印，保留完整排版', en: 'Ideal for sharing & printing, preserves layout' },
  markdown: { zh: '纯文本标记格式，适合技术文档', en: 'Plain text markup, great for technical docs' },
  json: { zh: '结构化原始数据，适合二次处理', en: 'Structured raw data for downstream processing' },
};

// map both English AND Chinese keywords to icons
const sectionIcons: [string[], string][] = [
  [['executive', '执行摘要', '概述', '总览'], '📋'],
  [['feature', '功能', '特性'], '⚡'],
  [['pricing', '定价', '价格', '费用'], '💰'],
  [['sentiment', '情感', '舆情', '口碑', '评价'], '💬'],
  [['technical', 'tech stack', '技术', '架构', 'techstack'], '🔧'],
  [['market', '市场', '定位', '竞争', 'position'], '📈'],
  [['swot', '优势', '劣势', '机会', '威胁'], '🎯'],
  [['strategic', '战略', '建议', '推荐', 'recommendation'], '🚀'],
  [['summary', '摘要', '总结', '结论'], '📊'],
  [['collection', '采集', '来源', 'source', 'discovery'], '🔍'],
];

function pickIcon(sectionName: string): string {
  const lower = sectionName.toLowerCase();
  for (const [keywords, icon] of sectionIcons) {
    for (const kw of keywords) {
      if (lower.includes(kw)) return icon;
    }
  }
  return '📄';
}

export default function Report() {
  const { id } = useParams<{ id: string }>();
  const [sections, setSections] = useState<ReportSection[]>([]);
  const [mdContent, setMdContent] = useState('');
  const [loading, setLoading] = useState(true);
  const [exporting, setExporting] = useState<ExportFormat | null>(null);
  const [error, setError] = useState('');
  const [sidebar, setSidebar] = useState<{ insightId: string; sectionTitle: string } | null>(null);
  const [menuOpen, setMenuOpen] = useState(false);
  const [lang, setLang] = useState<'zh' | 'en'>('zh');
  const { toast } = useToast();

  const reportRef = useRef<HTMLDivElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false);
      }
    };
    if (menuOpen) document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [menuOpen]);

  useEffect(() => {
    setLoading(true);
    setError('');
    fetch(`/api/report/${id}?lang=${lang}`)
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
  }, [id, lang]);

  const handleExport = useCallback(async (format: ExportFormat) => {
    setExporting(format);
    setMenuOpen(false);
    const baseName = `competitive-analysis-${id}`;

    try {
      switch (format) {
        case 'pdf': {
          if (!reportRef.current) {
            toast(lang === 'zh' ? '报告内容未加载' : 'Report content not loaded', 'error');
            break;
          }
          await downloadPDF(reportRef.current, `${baseName}.pdf`);
          toast(lang === 'zh' ? 'PDF 已导出' : 'PDF exported', 'success');
          break;
        }
        case 'markdown': {
          const content = mdContent || sections.map(s => `## ${s.section}\n\n${s.content}`).join('\n\n');
          downloadMarkdown(content, `${baseName}.md`);
          toast(lang === 'zh' ? 'Markdown 已导出' : 'Markdown exported', 'success');
          break;
        }
        case 'json':
          downloadJSON({ task_id: id, sections, content: mdContent }, `${baseName}.json`);
          toast(lang === 'zh' ? 'JSON 已导出' : 'JSON exported', 'success');
          break;
      }
    } catch {
      toast(lang === 'zh' ? '导出失败，请重试' : 'Export failed, please retry', 'error');
    } finally {
      setTimeout(() => setExporting(null), 600);
    }
  }, [id, mdContent, sections, toast, lang]);

  const handlePrint = () => {
    window.print();
  };

  const getInsightId = (section: ReportSection): string => {
    return section.node_id || `insight_${encodeURIComponent(section.section)}`;
  };

  const isEmpty = !loading && !error && sections.length === 0 && !mdContent;

  return (
    <div className="min-h-screen bg-gray-950">
      {/* ── Sticky toolbar ── */}
      <div className="sticky top-0 z-20 bg-gray-950/85 backdrop-blur-md border-b border-gray-800/60">
        <div className="max-w-5xl mx-auto px-6 py-3 flex items-center justify-between gap-4">
          <div className="flex items-center gap-3 min-w-0">
            <a href="/" className="text-gray-500 hover:text-gray-300 text-sm transition-colors shrink-0">
              ← {lang === 'zh' ? '任务列表' : 'Tasks'}
            </a>
            <span className="text-gray-700 shrink-0">/</span>
            <h1 className="text-base font-semibold text-gray-100 truncate">
              {lang === 'zh' ? '竞品分析报告' : 'Analysis Report'}
            </h1>
            <span className="text-xs text-gray-600 font-mono truncate hidden sm:inline">#{id?.slice(0, 8)}</span>
          </div>

          <div className="flex items-center gap-2 shrink-0">
            {/* language toggle */}
            <div className="flex items-center bg-gray-800/50 rounded-lg p-0.5">
              <button
                onClick={() => setLang('zh')}
                className={`px-2.5 py-1 text-xs font-medium rounded-md transition-all ${
                  lang === 'zh'
                    ? 'bg-cyan-500/20 text-cyan-300 shadow-sm'
                    : 'text-gray-500 hover:text-gray-300'
                }`}
              >
                中
              </button>
              <button
                onClick={() => setLang('en')}
                className={`px-2.5 py-1 text-xs font-medium rounded-md transition-all ${
                  lang === 'en'
                    ? 'bg-cyan-500/20 text-cyan-300 shadow-sm'
                    : 'text-gray-500 hover:text-gray-300'
                }`}
              >
                EN
              </button>
            </div>

            <button
              onClick={handlePrint}
              disabled={loading || !!error || isEmpty}
              className="hidden sm:inline-flex items-center gap-1.5 px-3 py-1.5 text-sm text-gray-400 hover:text-gray-200 hover:bg-gray-800/50 rounded-lg transition-all disabled:opacity-40 disabled:cursor-not-allowed"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M6.72 13.829c-.24.03-.48.062-.72.096m.72-.096a42.415 42.415 0 0110.56 0m-10.56 0L6.34 18m10.94-4.171c.24.03.48.062.72.096m-.72-.096L17.66 18m0 0l.229 2.523a1.125 1.125 0 01-1.12 1.227H7.231c-.662 0-1.18-.568-1.12-1.227L6.34 18m11.318 0h1.091A2.25 2.25 0 0021 15.75V9.456c0-1.081-.768-2.015-1.837-2.175a48.055 48.055 0 00-1.913-.247M6.34 18H5.25A2.25 2.25 0 013 15.75V9.456c0-1.081.768-2.015 1.837-2.175a48.041 48.041 0 011.913-.247m10.5 0a48.536 48.536 0 00-10.5 0m10.5 0V3.375c0-.621-.504-1.125-1.125-1.125h-8.25c-.621 0-1.125.504-1.125 1.125v3.659M18 10.5h.008v.008H18V10.5zm-3 0h.008v.008H15V10.5z" />
              </svg>
              {lang === 'zh' ? '打印' : 'Print'}
            </button>

            <div className="relative" ref={menuRef}>
              <button
                onClick={() => setMenuOpen(v => !v)}
                disabled={loading || !!error || isEmpty}
                className="inline-flex items-center gap-2 px-4 py-1.5 bg-cyan-500/10 border border-cyan-500/30 text-cyan-300 text-sm font-medium rounded-lg hover:bg-cyan-500/20 hover:border-cyan-500/50 active:scale-[0.97] transition-all disabled:opacity-40 disabled:cursor-not-allowed"
              >
                {exporting ? (
                  <Spinner size="sm" />
                ) : (
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3" />
                  </svg>
                )}
                {exporting ? (lang === 'zh' ? '导出中...' : 'Exporting...') : (lang === 'zh' ? '导出报告' : 'Export')}
                <svg className={`w-3.5 h-3.5 transition-transform ${menuOpen ? 'rotate-180' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 8.25l-7.5 7.5-7.5-7.5" />
                </svg>
              </button>

              {menuOpen && (
                <div className="absolute right-0 mt-2 w-60 bg-gray-900 border border-gray-700/60 rounded-xl shadow-2xl shadow-black/40 overflow-hidden z-30 animate-slideUp">
                  <div className="px-3 pt-2 pb-1">
                    <p className="text-[10px] font-semibold uppercase tracking-wider text-gray-500 mb-1">
                      {lang === 'zh' ? '选择导出格式' : 'Export Format'}
                    </p>
                  </div>
                  {exportOptions.map(opt => (
                    <button
                      key={opt.key}
                      onClick={() => handleExport(opt.key)}
                      disabled={exporting !== null}
                      className="w-full flex items-start gap-3 px-3 py-2.5 text-left hover:bg-gray-800/60 transition-colors disabled:opacity-50"
                    >
                      <span className="text-lg shrink-0 mt-0.5">{opt.icon}</span>
                      <div>
                        <div className="text-sm font-medium text-gray-200">{exportLabels[opt.key][lang]}</div>
                        <div className="text-xs text-gray-500">{exportDescs[opt.key][lang]}</div>
                      </div>
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* ── Main content ── */}
      <div className="max-w-5xl mx-auto px-6 py-8">
        {loading && (
          <div className="bg-gray-900/50 border border-gray-800/50 rounded-2xl p-10">
            <LoadingSkeleton lines={8} />
          </div>
        )}

        {!loading && error && (
          <div className="bg-gray-900/50 border border-red-900/30 rounded-2xl p-10">
            <EmptyState icon="⚠" title={lang === 'zh' ? `加载失败: ${error}` : `Load Failed: ${error}`} description={lang === 'zh' ? '请确认后端服务已启动' : 'Please confirm the backend service is running'} />
          </div>
        )}

        {isEmpty && (
          <div className="bg-gray-900/50 border border-gray-800/50 rounded-2xl p-10">
            <EmptyState icon="📄" title={lang === 'zh' ? '报告尚未生成' : 'Report Not Ready'} description={lang === 'zh' ? '请等待 DAG 流水线完成分析任务' : 'Please wait for the DAG pipeline to complete'} />
          </div>
        )}

        {!loading && !error && !isEmpty && (
          <div ref={reportRef} id="report-content" className="bg-gray-900/80 border border-gray-800/60 rounded-2xl overflow-hidden shadow-xl shadow-black/20">
            {/* report header */}
            <div className="px-8 pt-8 pb-4 border-b border-gray-800/40">
              <div className="flex items-center gap-3 mb-2">
                <span className="text-2xl">📊</span>
                <div>
                  <h2 className="text-xl font-bold text-gray-100">
                    {lang === 'zh' ? '竞品分析报告' : 'Competitive Analysis Report'}
                  </h2>
                  <p className="text-xs text-gray-500 font-mono mt-0.5">Report ID: {id}</p>
                </div>
              </div>
              <div className="flex flex-wrap gap-3 mt-4 text-xs text-gray-500 font-mono">
                <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-gray-800/50 rounded">
                  <span className="w-1.5 h-1.5 rounded-full bg-green-400/60" />
                  {sections.length} {lang === 'zh' ? '个章节' : 'sections'}
                </span>
                <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-gray-800/50 rounded">
                  📅 {new Date().toLocaleDateString(lang === 'zh' ? 'zh-CN' : 'en-US', { year: 'numeric', month: 'long', day: 'numeric' })}
                </span>
              </div>
            </div>

            {/* ── Analytics Dashboard ── */}
            <div className="px-8 py-6 border-b border-gray-800/40">
              <AnalyticsDashboard taskId={id!} />
            </div>

            {/* sections */}
            <div className="px-8 py-6 space-y-1">
              {sections.map((s, i) => (
                <div
                  key={i}
                  id={`section-${i}`}
                  className="group animate-slideUp rounded-xl transition-colors"
                  style={{ animationDelay: `${i * 60}ms` }}
                >
                  {/* section header */}
                  <div className="flex items-center gap-3 pt-6 pb-2">
                    <span className="text-lg shrink-0">{pickIcon(s.section)}</span>
                    <h3 className="text-base font-semibold text-gray-100">{s.section}</h3>
                    <div className="h-px flex-1 bg-gray-800/40" />
                  </div>

                  {/* section body — rendered from markdown */}
                  <div className="pl-9">
                    <div
                      className="md-content text-sm leading-relaxed text-gray-300"
                      dangerouslySetInnerHTML={{ __html: renderMarkdown(stripFirstHeading(s.content)) }}
                    />

                    <button
                      onClick={() => setSidebar({ insightId: getInsightId(s), sectionTitle: s.section })}
                      className="mt-3 mb-4 inline-flex items-center gap-1.5 text-xs font-mono text-cyan-400/80 hover:text-cyan-300 bg-cyan-500/5 hover:bg-cyan-500/10 border border-cyan-500/20 hover:border-cyan-500/30 px-2.5 py-1 rounded-md transition-all opacity-0 group-hover:opacity-100"
                    >
                      <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M13.19 8.688a4.5 4.5 0 011.242 7.244l-4.5 4.5a4.5 4.5 0 01-6.364-6.364l1.757-1.757m13.35-.622l1.757-1.757a4.5 4.5 0 00-6.364-6.364l-4.5 4.5a4.5 4.5 0 001.242 7.244" />
                      </svg>
                      溯源 / Trace
                    </button>
                  </div>

                  {i < sections.length - 1 && (
                    <div className="pl-9">
                      <div className="border-b border-gray-800/30" />
                    </div>
                  )}
                </div>
              ))}
            </div>

            {/* report footer */}
            <div className="px-8 py-4 border-t border-gray-800/40 bg-gray-900/50">
              <p className="text-xs text-gray-600 text-center font-mono">
                Generated by CompAgent · {new Date().toISOString().slice(0, 10)}
              </p>
            </div>
          </div>
        )}
      </div>

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
