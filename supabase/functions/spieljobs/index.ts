const backend = 'https://spieljobs-search.vercel.app'
const supported = new Set(['/search', '/search/stream', '/mcp', '/health'])
const maxBody = 64_000

Deno.serve(async request => {
  const path = new URL(request.url).pathname
    .replace(/^\/(?:functions\/v1\/)?spieljobs(?=\/|$)/, '').replace(/\/$/, '')
  if (!supported.has(path)) return Response.json({error:'Not found'}, {status:404})
  const validMethod = path === '/health' ? request.method === 'GET'
    : request.method === 'POST' || (path === '/mcp' && ['GET','DELETE'].includes(request.method))
  if (!validMethod) return Response.json({error:'Method not allowed'}, {status:405})
  let body: Uint8Array | undefined
  if (request.body) {
    const reader = request.body.getReader()
    const bytes = new Uint8Array(maxBody)
    let used = 0
    try {
      while (true) {
        const {done,value} = await reader.read()
        if (done) break
        if (used + value.byteLength > maxBody) return Response.json({error:'Request too large'}, {status:413})
        bytes.set(value, used)
        used += value.byteLength
      }
      body = bytes.subarray(0, used)
    } finally {
      await reader.cancel().catch(() => {})
    }
  }
  const headers = new Headers()
  for (const key of ['accept','content-type','mcp-protocol-version','mcp-session-id','origin']) {
    const value = request.headers.get(key)
    if (value) headers.set(key, value)
  }
  try {
    const upstream = await fetch(new URL(path, backend), {method:request.method, headers, body,
      signal:AbortSignal.any([request.signal, AbortSignal.timeout(110_000)]), redirect:'manual'})
    return upstream
  } catch {
    return Response.json({error:'Search temporarily unavailable'}, {status:502})
  }
})
