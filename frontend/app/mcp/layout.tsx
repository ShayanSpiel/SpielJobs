import type { Metadata } from 'next'
import type { ReactNode } from 'react'
export const metadata: Metadata = {
  title: 'MCP جست‌وجوی شغل',
  description: 'جست‌وجوی فرصت‌های شغلی و منابع آن‌ها در Codex، Claude Code و OpenCode با SpielJobs MCP.',
  alternates: { canonical: '/mcp/' },
  openGraph: { title: 'SpielJobs MCP | جست‌وجوی شغل در دستیار هوشمند', url: 'https://job.spielos.xyz/mcp/' },
}
export default function McpLayout({children}:{children:ReactNode}) { return children }
