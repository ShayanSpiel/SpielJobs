import type { MetadataRoute } from 'next'
import { site } from '@/lib/site'
export default function sitemap(): MetadataRoute.Sitemap {
  return ['','/mcp','/privacy'].map(path=>({url:site.origin+path,changeFrequency:'weekly' as const,priority:path?0.7:1}))
}
