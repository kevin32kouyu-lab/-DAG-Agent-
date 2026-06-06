// 这个测试确认浏览器导出工具会通过后端接口下载 PDF。

import { afterEach, describe, expect, it, vi } from 'vitest';
import { downloadPDF } from './export';

describe('export utils', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it('downloads PDF from backend report endpoint', async () => {
    const pdfBlob = new Blob(['pdf'], { type: 'application/pdf' });
    const fetchMock = vi.fn(async () => new Response(pdfBlob, { status: 200 }));
    const createObjectURL = vi.fn(() => 'blob:report-pdf');
    const revokeObjectURL = vi.fn();
    const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});

    vi.stubGlobal('fetch', fetchMock);
    vi.stubGlobal('URL', {
      ...URL,
      createObjectURL,
      revokeObjectURL,
    });

    await downloadPDF('task demo', 'competitive-analysis-task-demo.pdf', 'en');

    expect(fetchMock).toHaveBeenCalledWith('/api/report/task%20demo?format=pdf&lang=en');
    expect(createObjectURL).toHaveBeenCalledWith(expect.any(Blob));
    expect(click).toHaveBeenCalledOnce();
    expect(revokeObjectURL).toHaveBeenCalledWith('blob:report-pdf');
  });
});
