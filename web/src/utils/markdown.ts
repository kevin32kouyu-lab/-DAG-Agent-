/**
 * Lightweight Markdown → HTML renderer.
 * Handles the subset produced by LLM-generated reports:
 * headings, bold/italic, inline code, links, lists, blockquotes, hr, paragraphs.
 */

function escapeHtml(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function renderInline(text: string): string {
  // order matters: code before bold/italic, links before everything
  return text
    // inline code
    .replace(/`([^`]+)`/g, '<code class="md-inline-code">$1</code>')
    // bold+italic
    .replace(/\*\*\*(.+?)\*\*\*/g, '<strong><em>$1</em></strong>')
    // bold
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    // italic
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    // links
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" class="md-link" target="_blank" rel="noopener">$1</a>');
}

/**
 * 去掉 markdown 内容的首行 h1/h2 标题（避免与 section header 重复）
 */
export function stripFirstHeading(md: string): string {
  if (!md) return '';
  const lines = md.split('\n');
  for (let i = 0; i < lines.length; i++) {
    const trimmed = lines[i].trim();
    if (!trimmed) continue;
    if (/^#{1,2}\s+/.test(trimmed)) {
      lines.splice(i, 1);
      if (i < lines.length && !lines[i].trim()) {
        lines.splice(i, 1);
      }
      break;
    }
    break;
  }
  return lines.join('\n');
}

export function renderMarkdown(md: string): string {
  if (!md) return '';

  const lines = md.split('\n');
  const html: string[] = [];
  let inList: 'ul' | 'ol' | null = null;
  let inBlockquote = false;

  function closeList() {
    if (inList === 'ul') { html.push('</ul>'); }
    if (inList === 'ol') { html.push('</ol>'); }
    inList = null;
  }

  function closeBlockquote() {
    if (inBlockquote) { html.push('</blockquote>'); inBlockquote = false; }
  }

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    const trimmed = line.trim();

    // blank line — close open blocks
    if (!trimmed) {
      closeList();
      closeBlockquote();
      html.push('<div class="md-spacer"></div>');
      continue;
    }

    // horizontal rule
    if (/^(-{3,}|\*{3,}|_{3,})\s*$/.test(trimmed)) {
      closeList();
      closeBlockquote();
      html.push('<hr class="md-hr">');
      continue;
    }

    // headings
    const hMatch = trimmed.match(/^(#{1,6})\s+(.+)/);
    if (hMatch && !inList && !inBlockquote) {
      closeList();
      closeBlockquote();
      const level = hMatch[1].length;
      const text = renderInline(escapeHtml(hMatch[2]));
      html.push(`<h${level} class="md-h${level}">${text}</h${level}>`);
      continue;
    }

    // blockquote
    const bqMatch = trimmed.match(/^>\s?(.*)/);
    if (bqMatch) {
      closeList();
      if (!inBlockquote) { html.push('<blockquote class="md-blockquote">'); inBlockquote = true; }
      html.push(`<p>${renderInline(escapeHtml(bqMatch[1]))}</p>`);
      continue;
    } else {
      closeBlockquote();
    }

    // unordered list
    const ulMatch = trimmed.match(/^[-*]\s+(.+)/);
    if (ulMatch) {
      closeBlockquote();
      if (inList !== 'ul') { closeList(); html.push('<ul class="md-ul">'); inList = 'ul'; }
      html.push(`<li>${renderInline(escapeHtml(ulMatch[1]))}</li>`);
      continue;
    }

    // ordered list
    const olMatch = trimmed.match(/^\d+[.)]\s+(.+)/);
    if (olMatch) {
      closeBlockquote();
      if (inList !== 'ol') { closeList(); html.push('<ol class="md-ol">'); inList = 'ol'; }
      html.push(`<li>${renderInline(escapeHtml(olMatch[1]))}</li>`);
      continue;
    }

    // not a list item — close lists
    closeList();
    closeBlockquote();

    // paragraph
    html.push(`<p class="md-p">${renderInline(escapeHtml(trimmed))}</p>`);
  }

  closeList();
  closeBlockquote();

  return html.join('\n');
}
