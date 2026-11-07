// HTML from the site (comments, emails, Text Editor fields, report messages) made safe to show.
// It is parsed in an inert document (DOMParser: nothing loads, no handler runs, unlike a detached
// <div>), then rebuilt from an allowlist: formatting tags only, no attributes but a few harmless ones.
// Links become plain text with the address as a tooltip: following one would replace the app.
const TAGS = new Set(['p', 'br', 'b', 'strong', 'i', 'em', 'u', 's', 'strike', 'ul', 'ol', 'li', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'blockquote', 'pre', 'code', 'span', 'div', 'table', 'thead', 'tbody', 'tfoot', 'tr', 'th', 'td', 'hr', 'sub', 'sup', 'small', 'mark'])
const DROP = new Set(['script', 'style', 'iframe', 'object', 'embed', 'link', 'meta', 'base', 'form', 'input', 'button', 'textarea', 'select', 'svg', 'math', 'template', 'noscript', 'frame', 'frameset', 'audio', 'video', 'img', 'picture', 'source'])
const ATTRS = new Set(['colspan', 'rowspan'])

function copy(node, into, doc) {
  for (const child of node.childNodes) {
    if (child.nodeType === 3) {
      into.appendChild(doc.createTextNode(child.textContent))
      continue
    }
    if (child.nodeType !== 1) continue
    const tag = child.tagName.toLowerCase()
    if (DROP.has(tag)) continue
    if (tag === 'a') {
      const span = doc.createElement('span')
      span.className = 'underline decoration-dotted'
      const href = child.getAttribute('href') || ''
      if (/^(https?:|mailto:)/i.test(href.trim())) span.title = href.trim()
      copy(child, span, doc)
      into.appendChild(span)
      continue
    }
    if (!TAGS.has(tag)) {
      copy(child, into, doc) // unknown wrapper: keep its text
      continue
    }
    const el = doc.createElement(tag)
    for (const a of child.attributes) if (ATTRS.has(a.name) && /^\d{1,3}$/.test(a.value)) el.setAttribute(a.name, a.value)
    copy(child, el, doc)
    into.appendChild(el)
  }
}

export function sanitize(html) {
  const src = new DOMParser().parseFromString(String(html ?? ''), 'text/html')
  const out = document.implementation.createHTMLDocument('')
  const root = out.createElement('div')
  copy(src.body, root, out)
  return root.innerHTML
}

export const escapeHtml = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c])
