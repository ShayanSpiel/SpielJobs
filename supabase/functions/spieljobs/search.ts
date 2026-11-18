import { parse, type DefaultTreeAdapterTypes } from 'npm:parse5@7.3.0'

const boards = [
  {id:'jobinja', name:'Jobinja', label:'جابینجا', site_url:'https://jobinja.ir'},
  {id:'jobvision', name:'Jobvision', label:'جاب‌ویژن', site_url:'https://jobvision.ir'},
] as const

type Board = typeof boards[number]
type SourceReport = Board & {
  checked_at: string
  state: 'partial' | 'success' | 'unavailable' | 'unverified'
  matched_count: number
  failure_kind?: string
  http_status?: number
  searches?: {term: string; url: string}[]
}

export const pendingSources = () => boards.map(board => ({...board, state:'searching', checked_at:null}))

class SourceHttpError extends Error {
  constructor(readonly status: number) {
    super('Source HTTP ' + status)
  }
}
type Job = {
  title: string
  url: string
  company?: string
  location?: string
  posted_date?: string
  source: Board['id']
  status: 'listed'
  checked_at: string
}

function clean(value: unknown, max = 200) {
  return typeof value === 'string' ? value.replace(/\s+/g, ' ').trim().slice(0, max) : ''
}

async function readSource(url: URL, signal: AbortSignal, init: RequestInit = {}) {
  const response = await fetch(url, {...init, signal: AbortSignal.any([signal, AbortSignal.timeout(8000)])})
  if (!response.ok) throw new SourceHttpError(response.status)
  if (!response.body) throw new Error('Missing source body')
  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let text = ''
  let size = 0
  try {
    while (true) {
      const {done, value} = await reader.read()
      if (done) return text + decoder.decode()
      size += value.byteLength
      if (size > 1_500_000) throw new Error('Source response exceeds limit')
      text += decoder.decode(value, {stream:true})
    }
  } finally {
    await reader.cancel().catch(() => {})
  }
}

type HtmlNode = DefaultTreeAdapterTypes.Node

function* walk(root: HtmlNode): Generator<HtmlNode> {
  const stack = [root]
  while (stack.length) {
    const node = stack.pop()!
    yield node
    if ('childNodes' in node) {
      for (let i = node.childNodes.length - 1; i >= 0; i--) stack.push(node.childNodes[i])
    }
  }
}

function nodeText(node?: HtmlNode) {
  if (!node) return ''
  return clean(Array.from(walk(node), child => 'value' in child ? child.value : '').join(' '))
}

export function parseJobinja(html: string, checked_at: string): Job[] {
  const jobs: Job[] = []
  for (const heading of walk(parse(html))) {
    if (heading.nodeName !== 'h2') continue
    const link = Array.from(walk(heading)).find(node => node.nodeName === 'a')
    const href = link && 'attrs' in link ? link.attrs.find(attr => attr.name === 'href')?.value : ''
    let url: URL
    try { url = new URL(href ?? '', 'https://jobinja.ir') } catch { continue }
    if (url.origin !== 'https://jobinja.ir' || !url.pathname.includes('/jobs/') || url.username || url.password) continue
    const title = nodeText(link)
    if (title.length < 2) continue
    let card = 'parentNode' in heading ? heading.parentNode : null
    while (card && card.nodeName !== 'li') card = 'parentNode' in card ? card.parentNode : null
    const fields = card ? Array.from(walk(card)).filter(node => node !== card && node.nodeName === 'li') : []
    jobs.push({title, url:url.origin + url.pathname, company:nodeText(fields[0]),
      location:nodeText(fields[1]), source:'jobinja', status:'listed', checked_at})
    if (jobs.length >= 50) break
  }
  return jobs
}

type NamedField = {titleFa?: unknown; title?: unknown; titleEn?: unknown}
function placeName(field?: NamedField) {
  return clean(field?.titleFa || field?.title || field?.titleEn)
}

export function parseJobvision(value: unknown, checked_at: string): Job[] {
  const envelope = value as {isSuccess?: boolean; data?: {jobPosts?: unknown[]}} | null
  if (envelope?.isSuccess === false || !Array.isArray(envelope?.data?.jobPosts)) throw new Error('Unrecognized Jobvision response')
  return envelope.data.jobPosts.slice(0, 50).flatMap(raw => {
    const item = raw as {
      id?: string | number; title?: unknown; company?: {nameFa?: unknown; nameEn?: unknown}
      location?: {city?: NamedField; province?: NamedField}
      activationTime?: string | {date?: unknown}
    } | null
    const title = clean(item?.title)
    if (!item || !/^\d+$/.test(String(item.id)) || title.length < 2) return []
    const place = item.location
    const stamp = typeof item.activationTime === 'object' ? item.activationTime?.date : item.activationTime
    const date = clean(stamp).slice(0,10)
    return [{title, url:'https://jobvision.ir/jobs/' + item.id, company:clean(item.company?.nameFa || item.company?.nameEn),
      location:placeName(place?.city) || placeName(place?.province),
      posted_date:/^\d{4}-\d{2}-\d{2}$/.test(date) ? date : undefined,
      source:'jobvision', status:'listed', checked_at}]
  })
}

async function collect(board: Board, query: string, signal: AbortSignal): Promise<{jobs: Job[]; source: SourceReport}> {
  const checked_at = new Date().toISOString()
  const jobinjaUrl = new URL('https://jobinja.ir/jobs')
  jobinjaUrl.searchParams.set('filters[keywords][]', query)
  try {
    let jobs: Job[]
    if (board.id === 'jobinja') {
      jobs = parseJobinja(await readSource(jobinjaUrl, signal), checked_at)
      if (!jobs.length) return {jobs, source:{...board, checked_at, state:'unverified', matched_count:0}}
    } else {
      const url = new URL('https://candidateapi.jobvision.ir/api/v1/JobPost/List')
      const text = await readSource(url, signal, {method:'POST',
        headers:{'Content-Type':'application/json', Origin:'https://jobvision.ir', Referer:'https://jobvision.ir/'},
        body:JSON.stringify({keyword:query, sortBy:1, searchId:null, pageSize:50, requestedPage:1})})
      jobs = parseJobvision(JSON.parse(text), checked_at)
    }
    return {jobs, source:{...board, checked_at, state:jobs.length ? 'partial' : 'success', matched_count:jobs.length}}
  } catch (error) {
    const http_status = error instanceof SourceHttpError ? error.status : undefined
    const failure_kind = http_status === 403 || http_status === 401 ? 'blocked'
      : http_status === 429 ? 'rate_limited'
      : http_status === 404 ? 'not_found'
      : http_status ? 'http_error'
      : error instanceof DOMException && error.name === 'TimeoutError' ? 'timeout'
      : 'connection_failed'
    console.warn(JSON.stringify({event:'source_unavailable', source:board.id, failure_kind, http_status}))
    const searches = board.id === 'jobinja' ? [{term:query, url:jobinjaUrl.href}] : undefined
    return {jobs:[], source:{...board, checked_at, state:'unavailable', failure_kind, http_status, matched_count:0, searches}}
  }
}

export async function searchJobs(query: string, signal: AbortSignal, onSource?: (source: SourceReport) => void) {
  const collected = await Promise.all(boards.map(async board => {
    const result = await collect(board, query, signal)
    onSource?.(result.source)
    return result
  }))
  const jobs = Array.from(new Map(collected.flatMap(response => response.jobs).map(job => [job.url, job])).values())
  return {jobs:jobs.map(job => ({...job, match_terms:[], description:null,
    status_evidence:'Observed in the public source listing. Application availability has not been verified.'})), sources:collected.map(response => response.source), run_id:crypto.randomUUID(),
    model_used:null, warnings:['این جست‌وجو صفحهٔ اول جابینجا و جاب‌ویژن را بر اساس عبارت واردشده بررسی می‌کند.']}
}
