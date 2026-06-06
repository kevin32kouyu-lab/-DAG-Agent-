/**
 * Lightweight Markdown → HTML renderer.
 * Handles the subset produced by LLM-generated reports:
 * headings, bold/italic, inline code, links, lists, blockquotes, tables, hr, paragraphs.
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

function isTableRow(line: string): boolean {
  return line.startsWith('|') && line.endsWith('|') && line.split('|').length >= 3;
}

function isTableSeparator(line: string): boolean {
  if (!isTableRow(line)) return false;
  const cells = splitTableRow(line);
  return cells.length > 0 && cells.every(cell => /^:?-{3,}:?$/.test(cell.trim()));
}

function splitTableRow(line: string): string[] {
  return line
    .trim()
    .replace(/^\|/, '')
    .replace(/\|$/, '')
    .split('|')
    .map(cell => cell.trim());
}

function renderTable(rows: string[]): string {
  const headers = splitTableRow(rows[0]);
  const bodyRows = rows.slice(2).map(splitTableRow);
  const thead = `<thead><tr>${headers
    .map(cell => `<th>${renderInline(escapeHtml(cell))}</th>`)
    .join('')}</tr></thead>`;
  const tbody = `<tbody>${bodyRows
    .map(row => `<tr>${headers
      .map((_, i) => `<td>${renderInline(escapeHtml(row[i] || ''))}</td>`)
      .join('')}</tr>`)
    .join('')}</tbody>`;
  return `<div class="md-table-wrap"><table class="md-table">${thead}${tbody}</table></div>`;
}

/**
 * 去掉 markdown 内容的首行 h1/h2 标题（避免与 section header 重复）。
 * 跳过前导空行，找到第一个非空行；如果是 h1/h2 标题则移除。
 * 不再在遇到普通文本时立即退出 — 某些 LLM 输出在标题前有空白行序列。
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
    // 第一个非空行不是标题 → 不删除任何内容
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

    // markdown table
    if (isTableRow(trimmed) && i + 1 < lines.length && isTableSeparator(lines[i + 1].trim())) {
      closeList();
      closeBlockquote();
      const tableRows = [trimmed, lines[i + 1].trim()];
      i += 2;
      while (i < lines.length && isTableRow(lines[i].trim())) {
        tableRows.push(lines[i].trim());
        i++;
      }
      i--;
      html.push(renderTable(tableRows));
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
