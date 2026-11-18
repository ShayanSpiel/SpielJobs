import { McpServer } from 'npm:@modelcontextprotocol/sdk@1.32.2/server/mcp.js'
import { WebStandardStreamableHTTPServerTransport } from 'npm:@modelcontextprotocol/sdk@1.32.2/server/webStandardStreamableHttp.js'
import { z } from 'npm:zod@3.25.76'
import { pendingSources, searchJobs } from './search.ts'

const endpoint = Deno.env.get('SUPABASE_URL')
const serviceKey = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')
const json = (message: unknown, status = 200) => Response.json(message, {status, headers:{'Cache-Control':'no-store'}})

const input = z.object({query:z.string().trim().min(1).max(2000), resume:z.string().max(30000).optional()})
type Admission = 'allowed' | 'full' | 'unavailable'
async function admit(signal: AbortSignal): Promise<Admission> {
  if (!endpoint || !serviceKey) return 'unavailable'
  try {
    const response = await fetch(endpoint + '/rest/v1/rpc/spieljobs_edge_take_slot', {
      method:'POST', headers:{apikey:serviceKey, Authorization:'Bearer ' + serviceKey, 'Content-Type':'application/json'},
      body:'{}', signal:AbortSignal.any([signal, AbortSignal.timeout(2500)]),
    })
    if (!response.ok) return 'unavailable'
    const admitted = await response.json()
    return admitted === true ? 'allowed' : admitted === false ? 'full' : 'unavailable'
  } catch { return 'unavailable' }
}

class InvalidRequest extends Error {}
async function body(request: Request) {
  const reader = request.body?.getReader()
  if (!reader) throw new InvalidRequest()
  const decoder = new TextDecoder()
  let text = ''
  let bytes = 0
  try {
    while (true) {
      const {done, value} = await reader.read()
      if (done) return JSON.parse(text + decoder.decode())
      bytes += value.length
      if (bytes > 64_000) throw new InvalidRequest()
      text += decoder.decode(value, {stream:true})
    }
  } finally {
    await reader.cancel().catch(() => {})
  }
}

async function mcp(request: Request) {
  const origin = request.headers.get('origin')
  if (origin && origin !== 'https://job.spielos.xyz') return json({error:'Origin not allowed'}, 403)
  const server = new McpServer({name:'SpielJobs', version:'0.1.0'})
  server.registerTool('search_live_jobs', {
    description:'Search the first page of Jobinja and Jobvision using a keyword phrase.',
    inputSchema:{query:input.shape.query}, annotations:{readOnlyHint:true, openWorldHint:true},
  }, async ({query}) => {
    const access = await admit(request.signal)
    if (access !== 'allowed') {
      return {isError:true, content:[{type:'text', text:access === 'full' ? 'Search limit reached. Try again in a minute.' : 'Search is temporarily unavailable.'}]}
    }
    const result = await searchJobs(query, request.signal)
    return {content:[{type:'text', text:JSON.stringify(result)}], structuredContent:result}
  })
  const transport = new WebStandardStreamableHTTPServerTransport({enableJsonResponse:true})
  try {
    const parsedBody = request.method === 'POST' ? await body(request) : undefined
    await server.connect(transport)
    return await transport.handleRequest(request, {parsedBody})
  } catch (error) {
    if (error instanceof InvalidRequest || error instanceof SyntaxError) return json({error:'Invalid MCP request'}, 400)
    return json({error:'MCP temporarily unavailable'}, 503)
  } finally {
    await server.close()
  }
}

Deno.serve(async request => {
  const path = new URL(request.url).pathname.replace(/^\/(?:functions\/v1\/)?spieljobs(?=\/|$)/, '').replace(/\/$/, '')
  if (request.method === 'GET' && path === '/health') {
    return json({ok:true, runtime:'supabase-edge', quota_configured:Boolean(endpoint && serviceKey)})
  }
  if (path === '/mcp') return mcp(request)
  if (request.method !== 'POST' || !['/search','/search/stream','/resume'].includes(path)) return json({error:'Not found'}, 404)
  if (path === '/resume') return json({error:'Résumé upload is not available in the Supabase pilot.'}, 501)
  let parsed: z.infer<typeof input>
  try { parsed = input.parse(await body(request)) } catch { return json({error:'Invalid search request'}, 400) }
  if (parsed.resume) return json({error:'Résumé matching is not available in the Supabase pilot.'}, 501)
  const access = await admit(request.signal)
  if (access === 'unavailable') return json({error:'Search is temporarily unavailable'}, 503)
  if (access === 'full') return json({error:'Search limit reached'}, 429)
  if (path === '/search') return json(await searchJobs(parsed.query, request.signal))
  const stream = new ReadableStream<Uint8Array>({
    async start(controller) {
      const encoder = new TextEncoder()
      const send = (name: string, data: unknown) => controller.enqueue(encoder.encode('event: ' + name + '\ndata: ' + JSON.stringify(data) + '\n\n'))
      send('status', {phase:'search', group:'job_boards', sources:pendingSources()})
      try {
        const result = await searchJobs(parsed.query, request.signal, source => {
          if (!request.signal.aborted) send('source_progress', {group:'job_boards', sources:[source]})
        })
        send('result', result)
      }
      catch { if (!request.signal.aborted) send('error', {message:'جست‌وجو متوقف شد.'}) }
      finally { controller.close() }
    },
  })
  return new Response(stream, {headers:{'Content-Type':'text/event-stream; charset=utf-8','Cache-Control':'no-store'}})
})
