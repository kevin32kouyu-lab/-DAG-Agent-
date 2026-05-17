import html2pdf from 'html2pdf.js';

export function downloadMarkdown(content: string, filename: string): void {
  downloadBlob(content, filename, 'text/markdown;charset=utf-8');
}

export function downloadJSON(data: unknown, filename: string): void {
  downloadBlob(JSON.stringify(data, null, 2), filename, 'application/json;charset=utf-8');
}

export async function downloadPDF(element: HTMLElement, filename: string): Promise<void> {
  const opt = {
    margin: [10, 12, 10, 12] as [number, number, number, number],
    filename,
    image: { type: 'jpeg' as const, quality: 0.98 },
    html2canvas: {
      scale: 2,
      backgroundColor: '#0f172a',
      logging: false,
      useCORS: true,
    },
    jsPDF: {
      unit: 'mm' as const,
      format: 'a4' as const,
      orientation: 'portrait' as const,
    },
    pagebreak: { mode: ['avoid-all', 'css', 'legacy'] as const },
  };
  await html2pdf().set(opt).from(element).save();
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
