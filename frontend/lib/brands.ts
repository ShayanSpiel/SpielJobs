/** Official assets inspected on the corresponding first-party sites. */
export const brands: Record<string, {logo:string;fallback?:string;aliases:string[]}> = {
  jobinja:{logo:'/logos/jobinja.png',aliases:['jobinja','جابینجا']},
  jobvision:{logo:'/logos/jobvision.svg',fallback:'https://jobvision.ir/favicon.ico',aliases:['jobvision','جاب ویژن','جاب‌ویژن']},
  azki:{logo:'/logos/azki.svg',fallback:'https://www.azki.com/favicon-96x96.png?v=2',aliases:['azki','azki.com','ازکی','ازکی.کام']},
}
export function companyBrand(name:string|null|undefined) {
  const parts=(name||'').toLowerCase().split('|').map(p=>p.trim().replace(/\u200c/g,' '))
  return Object.values(brands).find(brand=>brand.aliases.some(alias=>parts.includes(alias.toLowerCase().replace(/\u200c/g,' '))))
}
