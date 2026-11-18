import type { Metadata } from 'next'
import type { ReactNode } from 'react'
import { site } from '@/lib/site'

const title = 'SpielJobs MCP | جست‌وجوی شغل در دستیار هوشمند'
const description = 'جست‌وجوی فرصت‌های شغلی و منابع آن‌ها در Codex، Claude Code و OpenCode با SpielJobs MCP.'
const image = {
  url: '/og-mcp.jpg',
  width: 1200,
  height: 630,
  alt: 'SpielJobs MCP — جست‌وجوی شغل در Codex، Claude Code و OpenCode',
}

export const metadata: Metadata = {
  title: 'MCP جست‌وجوی شغل',
  description,
  alternates: { canonical: '/mcp/' },
  openGraph: {
    type: 'website',
    url: '/mcp/',
    siteName: site.name,
    locale: 'fa_IR',
    title,
    description,
    images: [image],
  },
  twitter: {
    card: 'summary_large_image',
    site: '@ShayanSpiel',
    creator: '@ShayanSpiel',
    title,
    description,
    images: [image],
  },
}
export default function McpLayout({children}:{children:ReactNode}) { return children }
