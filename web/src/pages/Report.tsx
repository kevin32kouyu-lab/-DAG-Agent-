// 这个页面展示最终竞品分析报告，并提供图表、导出和证据链入口。

import { useState, useEffect, useRef, useCallback, lazy, Suspense } from 'react';
import { useParams } from 'react-router-dom';
import TraceSidebar from '../components/TraceSidebar';
import LoadingSkeleton from '../components/LoadingSkeleton';
import EmptyState from '../components/EmptyState';
import Spinner from '../components/Spinner';
import { useToast } from '../hooks/useToast';
import { downloadMarkdown, downloadJSON, downloadPDF } from '../utils/export';
import { renderMarkdown, stripFirstHeading } from '../utils/markdown';
import type { ReportSection } from '../types';

type ExportFormat = 'pdf' | 'markdown' | 'json';

interface ExportOption {
  key: ExportFormat;
  label: string;
  desc: string;
}

const exportOptions: ExportOption[] = [
  { key: 'pdf', label: 'PDF 文档', desc: '适合分享与打印，保留完整排版' },
  { key: 'markdown', label: 'Markdown', desc: '纯文本标记格式，适合技术文档' },
  { key: 'json', label: 'JSON 数据', desc: '结构化原始数据，适合二次处理' },
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

const AnalyticsDashboard = lazy(() => import('../components/charts/AnalyticsDashboard'));

const sectionIcons: [string[], string][] = [
  [['executive', '执行摘要', '概述', '总览'], '01'],
  [['feature', '功能', '特性'], '02'],
  [['pricing', '定价', '价格', '费用'], '03'],
  [['sentiment', '情感', '舆情', '口碑', '评价'], '04'],
  [['technical', 'tech stack', '技术', '架构', 'techstack'], '05'],
  [['market', '市场', '定位', '竞争', 'position'], '06'],
  [['swot', '优势', '劣势', '机会', '威胁'], '07'],
  [['strategic', '战略', '建议', '推荐', 'recommendation'], '08'],
  [['summary', '摘要', '总结', '结论'], '09'],
  [['collection', '采集', '来源', 'source', 'discovery'], '10'],
];

function pickSectionNumber(sectionName: string, fallback: number): string {
  const lower = sectionName.toLowerCase();
  for (const [keywords, label] of sectionIcons) {
    if (keywords.some(kw => lower.includes(kw))) return label;
  }
  return String(fallback + 1).padStart(2, '0');
}

function DashboardLoading() {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-8">
      <LoadingSkeleton lines={6} />
    </div>
  );
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
    let ignore = false;
    fetch(`/api/report/${id}?lang=${lang}`)
      .then(r => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then(data => {
        if (ignore) return;
        setSections(data.sections || []);
        setMdContent(data.content || '');
        setError('');
      })
      .catch(err => {
        if (!ignore) setError(err.message);
      })
      .finally(() => {
        if (!ignore) setLoading(false);
      });
    return () => { ignore = true; };
  }, [id, lang]);

  const handleExport = useCallback(async (format: ExportFormat) => {
    setExporting(format);
    setMenuOpen(false);
    const baseName = `competitive-analysis-${id}`;

    try {
      switch (format) {
        case 'pdf': {
          await downloadPDF(id!, `${baseName}.pdf`, lang);
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

  const getInsightId = (section: ReportSection): string => {
    return section.node_id || `insight_${encodeURIComponent(section.section)}`;
  };

  const isEmpty = !loading && !error && sections.length === 0 && !mdContent;

  return (
    <div className="min-h-screen bg-slate-100">
      <div className="sticky top-0 z-20 border-b border-slate-200 bg-white/90 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-6 py-3">
          <div className="flex min-w-0 items-center gap-3">
            <a href="/" className="shrink-0 text-sm text-slate-500 transition-colors hover:text-slate-900">
              ← {lang === 'zh' ? '任务列表' : 'Tasks'}
            </a>
            <span className="shrink-0 text-slate-300">/</span>
            <h1 className="truncate text-base font-semibold text-slate-950">
              {lang === 'zh' ? '分析报告' : 'Analysis Report'}
            </h1>
            <span className="hidden truncate font-mono text-xs text-slate-500 sm:inline">#{id?.slice(0, 8)}</span>
          </div>

          <div className="flex shrink-0 items-center gap-2">
            <div className="flex items-center rounded-md bg-slate-100 p-0.5">
              <button
                onClick={() => setLang('zh')}
                className={`rounded px-2.5 py-1 text-xs font-medium transition-all ${
                  lang === 'zh'
                    ? 'bg-white text-teal-800 shadow-sm'
                    : 'text-slate-500 hover:text-slate-900'
                }`}
              >
                中
              </button>
              <button
                onClick={() => setLang('en')}
                className={`rounded px-2.5 py-1 text-xs font-medium transition-all ${
                  lang === 'en'
                    ? 'bg-white text-teal-800 shadow-sm'
                    : 'text-slate-500 hover:text-slate-900'
                }`}
              >
                EN
              </button>
            </div>

            <button
              onClick={() => window.print()}
              disabled={loading || !!error || isEmpty}
              className="hidden items-center rounded-md px-3 py-1.5 text-sm text-slate-600 transition-all hover:bg-slate-100 hover:text-slate-900 disabled:cursor-not-allowed disabled:opacity-40 sm:inline-flex"
            >
              {lang === 'zh' ? '打印' : 'Print'}
            </button>

            <div className="relative" ref={menuRef}>
              <button
                onClick={() => setMenuOpen(v => !v)}
                disabled={loading || !!error || isEmpty}
                className="inline-flex items-center gap-2 rounded-md border border-teal-200 bg-teal-50 px-4 py-1.5 text-sm font-medium text-teal-800 transition-all hover:border-teal-300 hover:bg-teal-100 active:scale-[0.97] disabled:cursor-not-allowed disabled:opacity-40"
              >
                {exporting && <Spinner size="sm" />}
                {exporting ? (lang === 'zh' ? '导出中...' : 'Exporting...') : (lang === 'zh' ? '导出报告' : 'Export')}
              </button>

              {menuOpen && (
                <div className="absolute right-0 z-30 mt-2 w-60 overflow-hidden rounded-lg border border-slate-200 bg-white shadow-xl animate-slideUp">
                  <div className="px-3 pt-2 pb-1">
                    <p className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-slate-500">
                      {lang === 'zh' ? '选择导出格式' : 'Export Format'}
                    </p>
                  </div>
                  {exportOptions.map(opt => (
                    <button
                      key={opt.key}
                      onClick={() => handleExport(opt.key)}
                      disabled={exporting !== null}
                      className="w-full px-3 py-2.5 text-left transition-colors hover:bg-slate-50 disabled:opacity-50"
                    >
                      <div className="text-sm font-medium text-slate-800">{exportLabels[opt.key][lang]}</div>
                      <div className="text-xs text-slate-500">{exportDescs[opt.key][lang] || opt.desc}</div>
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      <div className="mx-auto max-w-6xl px-6 py-8">
        {loading && (
          <div className="rounded-lg border border-slate-200 bg-white p-10">
            <LoadingSkeleton lines={8} />
          </div>
        )}

        {!loading && error && (
          <div className="rounded-lg border border-red-200 bg-white p-10">
            <EmptyState icon="⚠" title={lang === 'zh' ? `加载失败: ${error}` : `Load Failed: ${error}`} description={lang === 'zh' ? '请确认后端服务已启动' : 'Please confirm the backend service is running'} />
          </div>
        )}

        {isEmpty && (
          <div className="rounded-lg border border-slate-200 bg-white p-10">
            <EmptyState icon="📄" title={lang === 'zh' ? '报告尚未生成' : 'Report Not Ready'} description={lang === 'zh' ? '请等待分析流程完成' : 'Please wait for the analysis pipeline to complete'} />
          </div>
        )}

        {!loading && !error && !isEmpty && (
          <div id="report-content" className="overflow-hidden rounded-lg border border-slate-200 bg-white shadow-sm">
            <div className="border-b border-slate-200 px-8 py-7">
              <p className="text-sm font-semibold text-teal-700">
                {lang === 'zh' ? '竞品分析报告' : 'Competitive Analysis Report'}
              </p>
              <h2 className="mt-2 text-2xl font-semibold tracking-normal text-slate-950">
                {lang === 'zh' ? '面向决策的竞品分析' : 'Decision-ready Competitive Analysis'}
              </h2>
              <div className="mt-4 flex flex-wrap gap-3 text-sm text-slate-500">
                <span className="rounded-md bg-slate-100 px-2.5 py-1">{sections.length} {lang === 'zh' ? '个章节' : 'sections'}</span>
                <span className="rounded-md bg-slate-100 px-2.5 py-1">Report ID: {id}</span>
                <span className="rounded-md bg-slate-100 px-2.5 py-1">
                  {new Date().toLocaleDateString(lang === 'zh' ? 'zh-CN' : 'en-US', { year: 'numeric', month: 'long', day: 'numeric' })}
                </span>
              </div>
            </div>

            <div className="border-b border-slate-200 bg-slate-50 px-8 py-6">
              <Suspense fallback={<DashboardLoading />}>
                <AnalyticsDashboard taskId={id!} />
              </Suspense>
            </div>

            <div className="px-8 py-6">
              {sections.map((s, i) => (
                <section
                  key={s.node_id || `${s.section}-${i}`}
                  id={`section-${i}`}
                  className="animate-slideUp"
                  style={{ animationDelay: `${i * 60}ms` }}
                >
                  <div className="flex items-center gap-3 pt-7 pb-2">
                    <span className="flex h-7 w-7 items-center justify-center rounded-md bg-slate-100 text-sm text-slate-600">
                      {pickSectionNumber(s.section, i)}
                    </span>
                    <h3 className="text-base font-semibold text-slate-950">{s.section}</h3>
                    <div className="h-px flex-1 bg-slate-200" />
                  </div>

                  <div className="pl-10">
                    <div
                      className="md-content text-sm leading-relaxed text-slate-700"
                      dangerouslySetInnerHTML={{ __html: renderMarkdown(stripFirstHeading(s.content)) }}
                    />

                    <button
                      onClick={() => setSidebar({ insightId: getInsightId(s), sectionTitle: s.section })}
                      className="mt-3 mb-5 inline-flex items-center gap-1.5 rounded-md border border-slate-200 bg-white px-2.5 py-1 text-xs font-medium text-slate-600 transition-colors hover:border-teal-700 hover:text-teal-800"
                    >
                      查看证据链
                    </button>
                  </div>

                  {i < sections.length - 1 && (
                    <div className="pl-10">
                      <div className="border-b border-slate-100" />
                    </div>
                  )}
                </section>
              ))}
            </div>

            <div className="border-t border-slate-200 bg-slate-50 px-8 py-4">
              <p className="text-center text-xs text-slate-500">
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
