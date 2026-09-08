function escapeHtml(value: string): string {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

function renderInline(value: string): string {
  const code: string[] = []
  let html = escapeHtml(value).replace(/`([^`]+)`/g, (_, content: string) => {
    const token = `\u0000CODE${code.length}\u0000`
    code.push(`<code>${content}</code>`)
    return token
  })

  html = html
    .replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>')
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
    .replace(/__([^_]+)__/g, '<strong>$1</strong>')
    .replace(/~~([^~]+)~~/g, '<del>$1</del>')
    .replace(/(^|[^*])\*([^*\n]+)\*/g, '$1<em>$2</em>')

  return html.replace(/\u0000CODE(\d+)\u0000/g, (_, index: string) => code[Number(index)] ?? '')
}

function isTableSeparator(line: string): boolean {
  const cells = line.trim().replace(/^\||\|$/g, '').split('|')
  return cells.length > 0 && cells.every((cell) => /^\s*:?-{3,}:?\s*$/.test(cell))
}

function tableCells(line: string): string[] {
  return line.trim().replace(/^\||\|$/g, '').split('|').map((cell) => cell.trim())
}

function startsBlock(lines: string[], index: number): boolean {
  const line = lines[index] ?? ''
  return /^\s*```/.test(line)
    || /^#{1,6}\s+/.test(line)
    || /^\s*>\s?/.test(line)
    || /^\s*([-+*]|\d+\.)\s+/.test(line)
    || /^\s*((-{3,})|(\*{3,})|(_{3,}))\s*$/.test(line)
    || (line.includes('|') && isTableSeparator(lines[index + 1] ?? ''))
}

export function renderMarkdown(markdown: string): string {
  const lines = markdown.replace(/\r\n?/g, '\n').split('\n')
  const output: string[] = []
  let index = 0

  while (index < lines.length) {
    const line = lines[index] ?? ''
    if (!line.trim()) {
      index += 1
      continue
    }

    const fence = line.match(/^\s*```([\w-]*)\s*$/)
    if (fence) {
      const fenceLanguage = fence[1] ?? ''
      const language = fenceLanguage ? ` data-language="${escapeHtml(fenceLanguage)}"` : ''
      const body: string[] = []
      index += 1
      while (index < lines.length && !/^\s*```\s*$/.test(lines[index] ?? '')) {
        body.push(lines[index] ?? '')
        index += 1
      }
      if (index < lines.length) index += 1
      output.push(`<pre><code${language}>${escapeHtml(body.join('\n'))}</code></pre>`)
      continue
    }

    const heading = line.match(/^(#{1,6})\s+(.+)$/)
    if (heading) {
      const level = (heading[1] ?? '').length
      output.push(`<h${level}>${renderInline(heading[2] ?? '')}</h${level}>`)
      index += 1
      continue
    }

    if (line.includes('|') && isTableSeparator(lines[index + 1] ?? '')) {
      const headers = tableCells(line)
      const rows: string[][] = []
      index += 2
      while (index < lines.length && (lines[index] ?? '').includes('|') && (lines[index] ?? '').trim()) {
        rows.push(tableCells(lines[index] ?? ''))
        index += 1
      }
      output.push(`<div class="markdown-table-wrap"><table><thead><tr>${headers.map((cell) => `<th>${renderInline(cell)}</th>`).join('')}</tr></thead><tbody>${rows.map((row) => `<tr>${headers.map((_, cellIndex) => `<td>${renderInline(row[cellIndex] ?? '')}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`)
      continue
    }

    if (/^\s*>\s?/.test(line)) {
      const quote: string[] = []
      while (index < lines.length && /^\s*>\s?/.test(lines[index] ?? '')) {
        quote.push((lines[index] ?? '').replace(/^\s*>\s?/, ''))
        index += 1
      }
      output.push(`<blockquote>${quote.map(renderInline).join('<br>')}</blockquote>`)
      continue
    }

    const listItem = line.match(/^\s*([-+*]|\d+\.)\s+(.+)$/)
    if (listItem) {
      const ordered = /\d+\./.test(listItem[1] ?? '')
      const tag = ordered ? 'ol' : 'ul'
      const items: string[] = []
      while (index < lines.length) {
        const item = (lines[index] ?? '').match(/^\s*([-+*]|\d+\.)\s+(.+)$/)
        if (!item || /\d+\./.test(item[1] ?? '') !== ordered) break
        items.push(`<li>${renderInline(item[2] ?? '')}</li>`)
        index += 1
      }
      output.push(`<${tag}>${items.join('')}</${tag}>`)
      continue
    }

    if (/^\s*((-{3,})|(\*{3,})|(_{3,}))\s*$/.test(line)) {
      output.push('<hr>')
      index += 1
      continue
    }

    const paragraph: string[] = []
    while (index < lines.length && (lines[index] ?? '').trim() && !startsBlock(lines, index)) {
      paragraph.push(renderInline(lines[index] ?? ''))
      index += 1
    }
    if (!paragraph.length) {
      paragraph.push(renderInline(line))
      index += 1
    }
    output.push(`<p>${paragraph.join('<br>')}</p>`)
  }

  return output.join('')
}
