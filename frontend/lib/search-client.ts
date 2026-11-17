/** Streaming transport shared by the chat UI and protocol tests. */
export type SearchEvent = { type: string; data: Record<string, unknown> }

export async function* readSearchEvents(body: ReadableStream<Uint8Array>): AsyncGenerator<SearchEvent> {
  const reader = body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  function parse(frame: string): SearchEvent | null {
    const lines = frame.split(/\r?\n/)
    const type = lines.find(line => line.startsWith('event:'))?.slice(6).trim()
    const raw = lines.filter(line => line.startsWith('data:')).map(line => line.slice(5).trimStart()).join('\n')
    if (!type || !raw) return null
    const data: unknown = JSON.parse(raw)
    if (!data || typeof data !== 'object' || Array.isArray(data)) throw Error('پاسخ سرور قابل خواندن نبود.')
    return { type, data: data as Record<string, unknown> }
  }
  try {
    while (true) {
      const { done, value } = await reader.read()
      buffer += decoder.decode(value, { stream: !done })
      if (buffer.length > 4_000_000) throw Error('پاسخ سرور بیش از اندازه بزرگ بود.')
      const frames = buffer.split(/\r?\n\r?\n/)
      buffer = frames.pop() || ''
      for (const frame of frames) {
        const event = parse(frame)
        if (event) yield event
      }
      if (done) {
        const event = parse(buffer)
        if (event) yield event
        break
      }
    }
  } finally {
    await reader.cancel().catch(() => {})
    reader.releaseLock()
  }
}

export async function searchStream(api: string, query: string, resume: string, signal: AbortSignal, sessionId?: string, analyticsHeaders:Record<string,string>={}) {
  if (!api) throw Error('سرور جست‌وجو برای این نسخه تنظیم نشده است.')
  const response = await fetch(`${api}/search/stream`, {
    method: 'POST',
    headers: { ...analyticsHeaders, 'Content-Type': 'application/json' },
    body: JSON.stringify({ query, resume, ...(sessionId ? {session_id:sessionId} : {}) }),
    signal: AbortSignal.any([signal, AbortSignal.timeout(115_000)]),
    cache: 'no-store',
  })
  if (response.status === 429) throw Error('تعداد درخواست‌ها زیاد است. یک دقیقه دیگر تلاش کنید.')
  if (response.status === 503) throw Error('سرویس مشغول است. کمی بعد تلاش کنید.')
  if (!response.ok || !response.body) throw Error('ارتباط با سرور جست‌وجو برقرار نشد.')
  return readSearchEvents(response.body)
}
