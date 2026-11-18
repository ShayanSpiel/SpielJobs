/** Product identity and verified public destinations. Deployment overrides live here. */
export const site = {
  name: 'SpielJobs',
  origin: process.env.NEXT_PUBLIC_SITE_URL || 'https://job.spielos.xyz',
  title: 'SpielJobs | جست‌وجوی شغل در ایران',
  description: 'عنوان شغل، مهارت یا شهر را بنویسید؛ فرصت‌های منابع در دسترس را با جزئیات و لینک اصلی یک‌جا ببینید.',
  author: 'Shayan Tawabi',
  links: {
    home: 'https://spielos.xyz/',
    contact: 'https://spielos.xyz/fa/contact/',
    linkedin: 'https://www.linkedin.com/in/shayantawabi/',
    x: 'https://x.com/ShayanSpiel',
    github: 'https://github.com/ShayanSpiel',
    repository: process.env.NEXT_PUBLIC_PROJECT_REPOSITORY || 'https://github.com/ShayanSpiel/SpielJobs',
  },
} as const

export const socialLinks = [
  {label:'LinkedIn',icon:'bxl-linkedin',href:site.links.linkedin},
  {label:'GitHub',icon:'bxl-github',href:site.links.github},
] as const
