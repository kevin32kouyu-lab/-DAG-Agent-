// 这个文件提供报告导出能力，PDF 由后端生成，前端只负责触发下载。

// 下载 Markdown 文本文件。
export function downloadMarkdown(content: string, filename: string): void {
  downloadBlob(content, filename, 'text/markdown;charset=utf-8');
}

// 下载 JSON 数据文件。
export function downloadJSON(data: unknown, filename: string): void {
  downloadBlob(JSON.stringify(data, null, 2), filename, 'application/json;charset=utf-8');
}

// 通过后端接口下载 PDF 文件。
export async function downloadPDF(taskId: string, filename: string, lang: string = 'zh'): Promise<void> {
  const response = await fetch(`/api/report/${encodeURIComponent(taskId)}?format=pdf&lang=${encodeURIComponent(lang)}`);
  if (!response.ok) {
    throw new Error(`PDF download failed: ${response.status}`);
  }
  saveBlob(await response.blob(), filename);
}

// 把文本内容保存为浏览器下载文件。
function downloadBlob(content: string, filename: string, mimeType: string): void {
  const blob = new Blob([content], { type: mimeType });
  saveBlob(blob, filename);
}

// 触发浏览器保存 Blob。
function saveBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}
