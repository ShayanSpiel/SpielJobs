import { brands } from './brands.ts'
export type SourceIdentity = { id?: string; name?: string; label?: string; site_url?: string; icon_url?: string | null; fallback_logo_url?: string | null }

/** Match both the current adapter id and older responses that used display names. */
export function sourceKey(value?: string): string {
  return (value || '').trim().toLowerCase().replace(/[^a-z0-9_-]/g, '')
}

export function sourceForJob<T extends SourceIdentity>(sourceName: string, sources: T[], jobUrl: string): SourceIdentity & { name: string } {
  const key=sourceKey(sourceName)
  const found=sources.find(source=>[sourceKey(source.id),sourceKey(source.name)].includes(key))
  let origin=''
  try { const url=new URL(jobUrl); if(url.protocol==='https:'||url.protocol==='http:')origin=url.origin } catch {}
  return { ...found, name:found?.name||sourceName, site_url:found?.site_url||origin }
}

/** Local assets use adapter ids; unknown sources fall back to adapter-provided artwork. */
export function sourceLogoCandidates(source?: SourceIdentity): string[] {
  if(!source)return []
  const key=sourceKey(source.id||source.name)
  let host=''
  try { if(source.site_url)host=new URL(source.site_url).hostname } catch {}
  // Blu's public brand domain differs from the configured careers domain.
  if(key==='blubank')host='blubank.com'
  return Array.from(new Set([
    brands[key]?.logo,
    brands[key]?.fallback,
    source.icon_url,
    source.fallback_logo_url,
    host ? `https://www.google.com/s2/favicons?domain=${encodeURIComponent(host)}&sz=128` : null,
  ].filter((value): value is string => Boolean(value))))
}
