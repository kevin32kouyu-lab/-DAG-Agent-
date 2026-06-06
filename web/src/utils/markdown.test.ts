import { describe, expect, it } from 'vitest';
import { renderMarkdown } from './markdown';

describe('renderMarkdown', () => {
  it('renders markdown tables as html tables', () => {
    const html = renderMarkdown([
      '| Feature | Notion | Figma |',
      '|---------|--------|-------|',
      '| Docs | **Advantage** | Disadvantage |',
    ].join('\n'));

    expect(html).toContain('<div class="md-table-wrap">');
    expect(html).toContain('<table class="md-table">');
    expect(html).toContain('<th>Feature</th>');
    expect(html).toContain('<td><strong>Advantage</strong></td>');
    expect(html).not.toContain('|---------|');
  });

  it('keeps headings lists and paragraphs working', () => {
    const html = renderMarkdown([
      '## Summary',
      '',
      '- First point',
      '- Second point',
      '',
      'Plain text.',
    ].join('\n'));

    expect(html).toContain('<h2 class="md-h2">Summary</h2>');
    expect(html).toContain('<ul class="md-ul">');
    expect(html).toContain('<li>First point</li>');
    expect(html).toContain('<p class="md-p">Plain text.</p>');
  });
});
