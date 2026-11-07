// The inbox, workflow actions and list tools (nexterp/api/work.py).
import { reactive } from 'vue'
import { call, site } from './backend'

const M = 'nexterp.api.work.'
export const badge = reactive({ assigned: 0, unread: 0, approvals: 0 })
const keep = (c) => (c && Object.assign(badge, c), c)

export const inbox = () => site(`${M}inbox`).then((r) => (keep(r.counts), r))
export const refreshCounts = () => site(`${M}counts`).then(keep).catch(() => null)
export const closeTodo = (name) => site(`${M}close_todo`, { name }, true, false).then(keep)
export const markRead = (name = null) => site(`${M}mark_read`, { name }, true, false).then(keep)

export const workflowOf = (doctype, name) => site(`${M}workflow`, { doctype, name })
export const applyAction = (doctype, name, action) => site(`${M}apply_action`, { doctype, name, action }, true)

export const bulkFields = (doctype) => site(`${M}bulk_fields`, { doctype })
export const bulkSet = (doctype, names, fieldname, value) => site(`${M}bulk_set`, { doctype, names, fieldname, value }, true)
export const views = (doctype) => site(`${M}views`, { doctype })
export const saveViews = (doctype, list) => site(`${M}save_views`, { doctype, views: list }, true, false)
export const exportList = (doctype, args) =>
  call('save_file', { method: `${M}export`, args: { doctype, ...args }, filename: `${doctype}.xlsx` })

export const repeatInfo = (doctype, name) => site(`${M}repeat_info`, { doctype, name })
export const repeat = (doctype, name, frequency, start_date, end_date) => site(`${M}repeat`, { doctype, name, frequency, start_date, end_date }, true, false)
export const stopRepeat = (doctype, name) => site(`${M}stop_repeat`, { doctype, name }, true, false)
