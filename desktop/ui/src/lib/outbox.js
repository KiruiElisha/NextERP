// Drafts kept on this computer while the site can't be reached (desktop/src-tauri commands outbox_*):
// only new documents, only as drafts. They're sent after the next successful sync, saved by the site
// with the user's own permissions, and never submitted; each keeps its id, so a send retried after a
// lost answer doesn't make it twice.
import { reactive } from 'vue'
import { call, on } from './backend'
import { __ } from './i18n'

export const outbox = reactive({ items: [], loaded: false })

export async function refresh() {
  try {
    outbox.items = await call('outbox_list')
  } catch {
    outbox.items = []
  }
  outbox.loaded = true
  return outbox.items
}

// The title a person recognises the draft by: its customer, supplier or title field.
function titleOf(doc) {
  return doc.customer_name || doc.customer || doc.party_name || doc.supplier_name || doc.supplier || doc.company_name || doc.lead_name || doc.first_name || doc.title || doc.description || ''
}

export async function keep(doctype, doc, id = null) {
  const draftId = id || crypto.randomUUID()
  const clean = JSON.parse(JSON.stringify(doc))
  for (const k of Object.keys(clean)) if (k.startsWith('__') && k !== '__islocal') delete clean[k]
  await call('outbox_add', { id: draftId, doctype, doc: clean, title: String(titleOf(clean)).slice(0, 140) })
  await refresh()
  return draftId
}

export async function remove(id) {
  await call('outbox_delete', { id })
  await refresh()
}

export const sendNow = (retry = null) => call('outbox_send', { retry })

// A kept draft opened again for editing: the form keeps its id, so saving it (online) or keeping it
// again (still offline) replaces the same draft instead of adding a second.
let reopened = null
export async function reopen(router, item, formRoute) {
  await call('outbox_mark', { id: item.id, status: 'editing' }) // the sender leaves it alone meanwhile
  reopened = { id: item.id, doctype: item.doctype, doc: { ...item.doc, __islocal: 1 } }
  router.push(formRoute(item.doctype, 'new'))
}
export function takeReopened(doctype) {
  const r = reopened?.doctype === doctype ? reopened : null
  reopened = null
  return r
}

let watching = false
export function watchOutbox(toast) {
  if (watching) return
  watching = true
  refresh()
  on('outbox', (e) => {
    refresh()
    if (e?.saved?.name && !e.saved.already) toast(__('{0} {1} saved on the site', [__(e.saved.doctype), e.saved.name]))
    if (e?.failed) toast(__('A kept draft was refused: {0}', [e.error]), true)
  })
}

export const release = (id) => call('outbox_mark', { id, status: 'pending' }).then(refresh).catch(() => {})

// Save a reopened draft now the site answers: through the same push as the sender (by its id), so if
// it was sent meanwhile, the site gives back that document instead of saving a second one.
export async function pushNow(doctype, doc, id) {
  const { site } = await import('./backend')
  const r = await site('nexterp.api.outbox.push', { doctype, doc: JSON.parse(JSON.stringify(doc)), client_id: id }, true)
  await call('outbox_delete', { id }).catch(() => {})
  await refresh()
  return r
}
