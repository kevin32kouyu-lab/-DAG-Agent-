import { useState, useEffect } from 'react';

const ROWS = [
  { label: '编排', width: '60%' },
  { label: '源发现', width: '40%' },
  { label: '采集', width: '75%' },
  { label: '富化', width: '35%' },
  { label: '分析', width: '80%' },
  { label: '互审', width: '30%' },
  { label: '综合', width: '25%' },
  { label: '撰写 + QA', width: '50%' },
];

const MESSAGES = [
  '正在分析目标产品...',
  '正在规划 Agent 协作流程...',
  'DeepSeek 正在生成执行方案...',
];

export default function PipelineSkeleton() {
  const [msgIdx, setMsgIdx] = useState(0);

  useEffect(() => {
    const timer = setInterval(() => {
      setMsgIdx(prev => (prev + 1) % MESSAGES.length);
    }, 3000);
    return () => clearInterval(timer);
  }, []);

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg p-8 space-y-5">
      {/* header */}
      <div className="flex items-center gap-3">
        <div className="w-4 h-4 rounded-full border-2 border-cyan-500 border-t-transparent animate-spin" />
        <span className="text-gray-300 text-sm font-medium">正在规划分析流程...</span>
      </div>

      {/* skeleton rows */}
      <div className="space-y-2.5">
        {ROWS.map((row, i) => (
          <div key={i} className="flex items-center gap-3">
            <span className="text-xs text-gray-600 font-mono w-16 text-right shrink-0">
              {row.label}
            </span>
            <div
              className="h-5 rounded animate-shimmer"
              style={{ width: row.width }}
            />
          </div>
        ))}
      </div>

      {/* rotating status */}
      <p
        key={msgIdx}
        className="text-xs text-gray-500 font-mono text-center animate-fadeIn"
      >
        {MESSAGES[msgIdx]}
      </p>
    </div>
  );
}
