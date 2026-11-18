/** One public origin; the Python service stays independently deployable. */
const apiOrigin = process.env.SPIELJOBS_API_URL
if (apiOrigin) {
  const url = new URL(apiOrigin)
  if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password || url.search || url.hash || url.pathname !== '/') {
    throw new Error('SPIELJOBS_API_URL must be an HTTP(S) origin without credentials or a path')
  }
  if (process.env.VERCEL && url.protocol !== 'https:') throw new Error('Production API must use HTTPS')
}
const nextConfig = {
  distDir: process.env.NEXT_DIST_DIR || '.next',
  poweredByHeader: false,
  env: {
    // Expose only the availability of the server-side rewrite.
    NEXT_PUBLIC_SPIELJOBS_API_PROXY: apiOrigin ? 'true' : 'false',
  },
  skipTrailingSlashRedirect:true,
  async rewrites() {
    const routes=apiOrigin ? [{ source: '/api/runtime/:path*', destination: `${apiOrigin.replace(/\/$/, '')}/:path*` }] : []
    const analytics=process.env.NEXT_PUBLIC_POSTHOG_HOST
    if(analytics){
      const url=new URL(analytics)
      if(url.protocol!=='https:' || !['us.i.posthog.com','eu.i.posthog.com'].includes(url.hostname)) throw Error('PostHog host must be an official HTTPS ingestion origin')
      routes.push({source:'/events/static/:path*',destination:`${url.origin.replace('.i.posthog.com','-assets.i.posthog.com')}/static/:path*`},{source:'/events/:path*',destination:`${url.origin}/:path*`})
    }
    return routes
  },
  async headers() {
    return [{ source: '/:path*', headers: [
      { key: 'X-Content-Type-Options', value: 'nosniff' },
      { key: 'Referrer-Policy', value: 'strict-origin-when-cross-origin' },
      { key: 'X-Frame-Options', value: 'DENY' },
      { key: 'Permissions-Policy', value: 'camera=(), microphone=(), geolocation=()' },
    ] }]
  },
}
export default phase => ({ ...nextConfig, distDir: process.env.NEXT_DIST_DIR || (phase === 'phase-development-server' ? '.next-dev' : '.next') })
