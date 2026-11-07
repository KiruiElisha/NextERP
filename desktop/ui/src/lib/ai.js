// The assistant (nexterp/api/ai.py): questions answered from the site's records as the signed-in user,
// and drafts handed to the normal form. The conversation lives in memory only: it is gone when the
// app closes, so nothing the assistant read is left on the computer.
import { reactive } from 'vue'
import { site } from './backend'
import { formRoute } from './forms'

export const chat = reactive({ messages: [], busy: false, error: '', context: null })

export function reset() {
  chat.messages = []
  chat.error = ''
  chat.context = null
}

export async function ask(text, context = chat.context) {
  const question = text.trim()
  if (!question || chat.busy) return
  chat.error = ''
  chat.messages.push({ role: 'user', content: question })
  chat.busy = true
  try {
    const history = chat.messages.map(({ role, content }) => ({ role, content }))
    const r = await site('nexterp.api.ai.ask', { messages: history, context }, true, false)
    chat.messages.push({ role: 'assistant', content: r.reply, drafts: r.drafts || [], records: r.records || [] })
  } catch (e) {
    chat.error = e.message
    // The question stays, so it can be sent again with Retry.
  } finally {
    chat.busy = false
  }
}

export function retry() {
  const last = chat.messages[chat.messages.length - 1]
  if (last?.role !== 'user') return
  chat.messages.pop()
  return ask(last.content)
}

// A draft waits here until its form opens it (FormPage takes it once, then it is gone).
const drafts = new Map()
export function openDraft(router, draft) {
  drafts.set(draft.doctype, JSON.parse(JSON.stringify(draft.doc)))
  router.push(formRoute(draft.doctype, 'new'))
}
export function takeDraft(doctype) {
  const d = drafts.get(doctype)
  drafts.delete(doctype)
  return d ? { ...d, __islocal: 1 } : null
}

// --- a small markdown renderer: HTML is escaped first, so a record's text can never become markup ---

const escape = (s) => s.replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c])

function inline(s) {
  return escape(s)
    .replace(/`([^`]+)`/g, '<code class="rounded bg-slate-100 px-1 text-[0.85em]">$1</code>')
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
    .replace(/(^|[^*])\*([^*\s][^*]*)\*/g, '$1<em>$2</em>')
    // Only links to records become links; any other address stays text (the app opens no web pages).
    .replace(/\[([^\]]+)\]\(record:([^)/]+)\/([^)]+)\)/g, (_m, label, dt, name) => {
      const to = formRoute(decode(dt), decode(name))
      return `<a href="#${escape(to)}" data-to="${escape(to)}" class="font-medium text-brand-600 hover:underline">${label}</a>`
    })
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '$1 ($2)')
}

function decode(s) {
  // the label and target were escaped above; undo that for the route, which escapes again
  return s.replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&quot;/g, '"').replace(/&#39;/g, "'").trim()
}

export function render(md = '') {
  const lines = md.replace(/\r/g, '').split('\n')
  const out = []
  let i = 0
  while (i < lines.length) {
    const line = lines[i]
    if (line.startsWith('```')) {
      const code = []
      for (i++; i < lines.length && !lines[i].startsWith('```'); i++) code.push(lines[i])
      i++
      out.push(`<pre class="overflow-x-auto rounded-lg bg-slate-900 p-3 text-xs text-slate-100">${escape(code.join('\n'))}</pre>`)
      continue
    }
    if (/^\s*\|.*\|\s*$/.test(line) && /^\s*\|[\s:|-]+\|\s*$/.test(lines[i + 1] || '')) {
      const cells = (l) => l.trim().replace(/^\||\|$/g, '').split('|').map((c) => inline(c.trim()))
      const head = cells(line)
      const body = []
      for (i += 2; i < lines.length && /^\s*\|.*\|\s*$/.test(lines[i]); i++) body.push(cells(lines[i]))
      const num = (c) => /^-?[\d,.\s]+%?$|^[A-Z]{3}\s?-?[\d,.]+$/.test(c.replace(/<[^>]+>/g, ''))
      out.push(
        `<div class="overflow-x-auto"><table class="w-full text-left text-[13px]"><thead><tr>${head.map((h) => `<th class="border-b border-slate-200 px-2 py-1 font-medium text-slate-500">${h}</th>`).join('')}</tr></thead><tbody>${body
          .map((r) => `<tr>${r.map((c) => `<td class="border-b border-slate-100 px-2 py-1 ${num(c) ? 'text-right tabular-nums' : ''}">${c}</td>`).join('')}</tr>`)
          .join('')}</tbody></table></div>`,
      )
      continue
    }
    const list = line.match(/^\s*([-*]|\d+\.)\s+(.*)/)
    if (list) {
      const ordered = /\d/.test(list[1])
      const items = []
      for (; i < lines.length; i++) {
        const m = lines[i].match(/^\s*([-*]|\d+\.)\s+(.*)/)
        if (!m) break
        items.push(`<li>${inline(m[2])}</li>`)
      }
      out.push(`<${ordered ? 'ol' : 'ul'} class="${ordered ? 'list-decimal' : 'list-disc'} space-y-0.5 pl-5">${items.join('')}</${ordered ? 'ol' : 'ul'}>`)
      continue
    }
    const heading = line.match(/^(#{1,4})\s+(.*)/)
    if (heading) out.push(`<p class="font-semibold text-slate-900">${inline(heading[2])}</p>`)
    else if (line.trim()) {
      const para = [line]
      for (i++; i < lines.length && lines[i].trim() && !/^(\s*([-*]|\d+\.)\s|#{1,4}\s|```|\s*\|)/.test(lines[i]); i++) para.push(lines[i])
      out.push(`<p>${para.map(inline).join('<br>')}</p>`)
      continue
    }
    i++
  }
  return out.join('')
}
