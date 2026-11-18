import type { Metadata, Viewport } from 'next'
import { site } from '@/lib/site'
import './globals.css'

const searchImage = { url: '/og-search.jpg', width: 1200, height: 630, alt: 'SpielJobs — جست‌وجوی شغل در ایران' }

export const metadata: Metadata = {
  metadataBase:new URL(site.origin),
  title:{default:site.title,template:'%s | SpielJobs'},
  description:site.description,
  authors:[{name:site.author,url:site.links.home}],
  applicationName:site.name,
  alternates:{canonical:'/'},
  openGraph:{type:'website',url:site.origin,siteName:site.name,locale:'fa_IR',title:site.title,description:site.description,images:[searchImage]},
  twitter:{card:'summary_large_image',site:'@ShayanSpiel',creator:'@ShayanSpiel',title:site.title,description:site.description,images:[searchImage]},
  icons:{icon:[{url:'/favicon.svg',type:'image/svg+xml'},{url:'/icon-32.png',sizes:'32x32',type:'image/png'},{url:'/favicon.ico',sizes:'any'}],apple:[{url:'/apple-touch-icon.png',sizes:'180x180'}]},
  manifest:'/site.webmanifest',
  robots:{index:true,follow:true},
}
export const viewport: Viewport = {width:'device-width',initialScale:1,themeColor:[{media:'(prefers-color-scheme: light)',color:'#eee4d4'},{media:'(prefers-color-scheme: dark)',color:'#0b1220'}]}
const structuredData={
  '@context':'https://schema.org',
  '@graph':[
    {'@type':'WebSite','@id':site.origin+'/#website',url:site.origin,name:site.name,inLanguage:'fa-IR',description:site.description},
    {'@type':'WebApplication',name:site.name,url:site.origin,applicationCategory:'BusinessApplication',operatingSystem:'Web',inLanguage:'fa-IR',description:site.description,author:{'@type':'Person',name:site.author,url:site.links.home,sameAs:[site.links.linkedin,site.links.x,site.links.github]}},
  ],
}
export default function RootLayout({children}:{children:React.ReactNode}) {
  return <html lang="fa" dir="rtl" suppressHydrationWarning><head>
    <script dangerouslySetInnerHTML={{__html:"try{var t=localStorage.getItem('spieljobs-theme');if(t==='dark'||t==='light')document.documentElement.dataset.theme=t}catch(e){}"}}/>
    <script type="application/ld+json" dangerouslySetInnerHTML={{__html:JSON.stringify(structuredData).replace(/</g,'\\u003c')}}/>
    <link rel="preload" href="/fonts/IRANSansXVF.woff2" as="font" type="font/woff2" crossOrigin="anonymous"/>
    <link rel="stylesheet" href="/boxicons.css"/>
  </head><body>{children}</body></html>
}
