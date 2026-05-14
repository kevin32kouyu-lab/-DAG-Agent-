import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';

interface Section {
  section: string;
  content: string;
  order: number;
}

export default function Report() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [sections, setSections] = useState<Section[]>([]);
  const [mdContent, setMdContent] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`/api/report/${id}`)
      .then(r => r.json())
      .then(data => {
        setSections(data.sections || []);
        setMdContent(data.content || '');
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) return <div className="max-w-4xl mx-auto p-6 text-gray-500 font-mono">加载中...</div>;

  return (
    <div className="max-w-5xl mx-auto p-6">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-bold text-gray-100">竞品分析报告</h1>
        <div className="flex gap-2">
          <button className="px-3 py-1.5 bg-gray-800 border border-gray-700 rounded text-sm text-gray-300 hover:bg-gray-700 font-mono">
            导出 Markdown
          </button>
          <button className="px-3 py-1.5 bg-gray-800 border border-gray-700 rounded text-sm text-gray-300 hover:bg-gray-700 font-mono">
            导出 JSON
          </button>
        </div>
      </div>

      <div className="bg-gray-900 border border-gray-800 rounded-lg p-8">
        {sections.length > 0 ? (
          <div className="prose prose-invert max-w-none">
            {sections.map((s, i) => (
              <div key={i} className="mb-8">
                <h2 className="text-lg font-bold text-gray-100 mb-3">{s.section}</h2>
                <div className="text-gray-300 text-sm leading-relaxed whitespace-pre-wrap">{s.content}</div>
                <button
                  onClick={() => navigate(`/task/${id}/trace`)}
                  className="mt-2 text-xs text-cyan-400 hover:text-cyan-300 font-mono"
                >
                  [溯源]
                </button>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-gray-600 font-mono text-sm text-center py-12">
            {mdContent ? (
              <div className="text-left text-gray-300 whitespace-pre-wrap">{mdContent}</div>
            ) : (
              '报告尚未生成'
            )}
          </div>
        )}
      </div>
    </div>
  );
}
