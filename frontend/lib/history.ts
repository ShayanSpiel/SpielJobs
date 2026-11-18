import type { Message } from './search-types.ts'

export type Conversation = { id: string; title: string; updatedAt: string; messages: Message[] }
export const HISTORY_KEY = 'spieljobs-history-v1'
const maxAge = 7 * 24 * 60 * 60 * 1000

/** Search history stays on this device for seven days. Resume text is never saved. */
export function historySnapshot(chats: Conversation[], now = Date.now()): Conversation[] {
  return chats.filter(chat => Number.isFinite(Date.parse(chat.updatedAt)) && now - Date.parse(chat.updatedAt) < maxAge)
    .slice(0, 20).map(chat => ({
      id: chat.id, title: chat.title.slice(0, 80), updatedAt: chat.updatedAt,
      messages: chat.messages.slice(-30).map(message => {
        // Whitelist persisted fields. Uploaded file contents and filename are excluded.
        const saved: Message = { id: message.id, role: message.role, text: message.text?.slice(0, 2000), stopped: message.stopped, error: message.error, usedResume: message.usedResume === true || undefined }
        if (message.result) saved.result = { jobs: message.result.jobs.slice(0, 50), sources: message.result.sources, warnings: message.result.warnings, model_used: message.result.model_used }
        else if (message.role === 'assistant' && !message.error) saved.stopped = true
        return saved
      }),
    }))
}

export function readHistory(raw: string | null): Conversation[] {
  if (!raw || raw.length > 4_000_000) return []
  try {
    const data: unknown = JSON.parse(raw)
    if (!Array.isArray(data)) return []
    const chats = data.filter((chat): chat is Conversation => !!chat && typeof chat === 'object' && typeof chat.id === 'string' && typeof chat.title === 'string' && typeof chat.updatedAt === 'string' && Array.isArray(chat.messages) && chat.messages.every((m: Message) => m && typeof m.id === 'string' && ['user', 'assistant'].includes(m.role) && (!m.result || (Array.isArray(m.result.jobs) && Array.isArray(m.result.sources)))))
    return historySnapshot(chats)
  } catch { return [] }
}

export function writeHistory(storage: Pick<Storage, 'setItem'>, chats: Conversation[]) {
  const snapshot = historySnapshot(chats)
  if (!snapshot.length) {
    try { storage.setItem(HISTORY_KEY, '[]'); return true } catch { return false }
  }
  while (snapshot.length) {
    const value = JSON.stringify(snapshot)
    if (value.length <= 3_500_000) {
      try { storage.setItem(HISTORY_KEY, value); return true } catch {}
    }
    snapshot.pop()
  }
  try { storage.setItem(HISTORY_KEY, '[]') } catch {}
  return false
}
