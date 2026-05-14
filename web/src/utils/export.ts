export function downloadMarkdown(content: string, filename: string): void {
  downloadBlob(content, filename, 'text/markdown;charset=utf-8');
}

export function downloadJSON(data: unknown, filename: string): void {
  downloadBlob(JSON.stringify(data, null, 2), filename, 'application/json;charset=utf-8');
}

function downloadBlob(content: string, filename: string, mimeType: string): void {
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}
