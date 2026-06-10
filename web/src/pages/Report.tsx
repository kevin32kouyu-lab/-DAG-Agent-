import { useState, useEffect, lazy, Suspense } from 'react';
import { useParams, useSearchParams } from 'react-router-dom';
import LoadingSkeleton from '../components/LoadingSkeleton';
import EmptyState from '../components/EmptyState';
import { renderMarkdown, stripFirstHeading } from '../utils/markdown';
import type { ReportSection } from '../types';

const AnalyticsDashboard = lazy(() => import('../components/charts/AnalyticsDashboard'));

export default function Report() {
  const { id } = useParams<{ id: string }>();
  const [searchParams] = useSearchParams();
  const isDemo = searchParams.get('demo') === 'true';
  const taskId = isDemo ? (searchParams.get('task') || id || '') : (id || '');

  const [sections, setSections] = useState<ReportSection[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [chartError, setChartError] = useState(false);

  useEffect(() => {
    if (!taskId) return;
    let ignore = false;
    setLoading(true);
    fetch(`/api/report/${taskId}?lang=zh`)
      .then(r => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); })
      .then(data => {
        if (ignore) return;
        setSections(data.sections || []);
        setError('');
      })
      .catch(err => { if (!ignore) setError(err.message); })
      .finally(() => { if (!ignore) setLoading(false); });
    return () => { ignore = true; };
  }, [taskId]);

  if (loading) return <div className="max-w-5xl mx-auto px-8 py-10"><LoadingSkeleton lines={10} /></div>;
  if (error) return <div className="max-w-5xl mx-auto px-8 py-10"><EmptyState icon="error" title="加载失败" description={error} /></div>;

  return (
    <div className="max-w-5xl mx-auto px-8 py-8 animate-pageEnter">
      {/* Hero */}
      <div className="mb-8">
        <p className="text-xs font-semibold uppercase tracking-widest text-primary/70 mb-2">竞品分析 · Competitive Analysis</p>
        <h1 className="font-headline text-3xl font-semibold tracking-tight text-on-surface">竞品分析报告</h1>
        <div className="flex items-center gap-3 mt-3 flex-wrap">
          <span className="rounded-md bg-surface-container px-2.5 py-1 text-xs font-medium text-on-surface-variant">{sections.length} 章节</span>
          <span className="rounded-md bg-surface-container px-2.5 py-1 text-xs font-mono text-on-surface-variant">{taskId}</span>
          {isDemo && <span className="rounded-full bg-gradient-to-r from-violet-500 to-blue-500 px-3 py-0.5 text-xs font-semibold text-white">Demo</span>}
        </div>
      </div>

      {/* Charts */}
      {!chartError && (
        <section className="mb-8">
          <div id="report-content" className="rounded-xl border border-border-subtle bg-surface shadow-sm overflow-hidden">
            <div className="px-6 py-4 border-b border-border-subtle flex items-center gap-2">
              <span className="material-symbols-outlined text-primary">monitoring</span>
              <h2 className="font-headline text-base font-semibold text-on-surface">分析仪表盘</h2>
            </div>
            <div className="p-4">
              <Suspense fallback={<LoadingSkeleton lines={6} />}>
                <ErrorBoundary onError={() => setChartError(true)}>
                  <AnalyticsDashboard taskId={taskId} />
                </ErrorBoundary>
              </Suspense>
            </div>
          </div>
        </section>
      )}

      {/* Report sections */}
      {sections.length > 0 && (
        <section className="rounded-xl border border-border-subtle bg-surface shadow-sm overflow-hidden">
          <div className="px-6 py-4 border-b border-border-subtle flex items-center gap-2">
            <span className="material-symbols-outlined text-primary">description</span>
            <h2 className="font-headline text-base font-semibold text-on-surface">详细报告</h2>
          </div>
          <div className="px-6 py-6">
            {sections.map((s, i) => (
              <div key={s.node_id || `${s.section}-${i}`} className="animate-slideUp" style={{ animationDelay: `${i * 60}ms` }}>
                <div className="flex items-center gap-3 pt-5 pb-2">
                  <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-primary/10 text-sm font-mono font-bold text-primary">
                    {String(i + 1).padStart(2, '0')}
                  </span>
                  <h3 className="font-headline text-base font-semibold text-on-surface">{s.section}</h3>
                  <div className="h-px flex-1 bg-border-subtle" />
                </div>
                <div className="pl-10">
                  <div className="md-content text-sm leading-relaxed text-on-surface-variant"
                    dangerouslySetInnerHTML={{ __html: renderMarkdown(stripFirstHeading(s.content)) }} />
                </div>
                {i < sections.length - 1 && <div className="pl-10 mt-2"><div className="border-b border-border-subtle/50" /></div>}
              </div>
            ))}
          </div>
          <div className="border-t border-border-subtle bg-surface-container/30 px-6 py-3 flex justify-between items-center">
            <p className="text-xs text-on-surface-variant/60">Generated by CompAgent</p>
            <div className="flex gap-1.5">
              {(['markdown','json'] as const).map(fmt => (
                <button key={fmt} onClick={() => {
                  const content = sections.map(s => `## ${s.section}\n\n${s.content}`).join('\n\n');
                  const blob = new Blob([fmt === 'json' ? JSON.stringify({ sections, content }, null, 2) : content], { type: 'text/plain' });
                  const a = document.createElement('a'); a.href = URL.createObjectURL(blob);
                  a.download = `report-${taskId}.${fmt === 'json' ? 'json' : 'md'}`; a.click();
                }} className="rounded-md border border-border-subtle bg-surface px-3 py-1.5 text-xs font-medium text-on-surface-variant hover:border-primary/30 hover:text-primary transition-colors">
                  {fmt === 'json' ? 'JSON' : 'Markdown'}
                </button>
              ))}
            </div>
          </div>
        </section>
      )}

      {sections.length === 0 && !error && (
        <EmptyState icon="article" title="暂无报告内容" description="分析已完成但未生成报告章节" />
      )}
    </div>
  );
}

/* Simple error boundary fallback for charts */
function ErrorBoundary({ children, onError }: { children: React.ReactNode; onError: () => void }) {
  try {
    return <>{children}</>;
  } catch {
    onError();
    return null;
  }
}
