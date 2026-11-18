/** Official assets inspected on the corresponding first-party sites. */
export const brands: Record<string, {logo:string;fallback?:string;aliases:string[]}> = {
  jobinja:{logo:'/logos/jobinja.png',aliases:['jobinja','جابینجا']},
  jobvision:{logo:'/logos/jobvision.svg',fallback:'https://jobvision.ir/favicon.ico',aliases:['jobvision','جاب ویژن','جاب‌ویژن']},
  azki:{logo:'/logos/azki.svg',fallback:'https://www.azki.com/favicon-96x96.png?v=2',aliases:['azki','azki.com','ازکی','ازکی.کام']},
  digikala:{logo:'/logos/digikala.svg',aliases:['digikala','digikala.com','دیجی‌کالا','گروه دیجی‌کالا','دیجی‌کالا گروپ','شرکت دیجی‌کالا','نوآوران فن آوازه','تجارت الکترونیک دیجی‌کالا']},
  blubank:{logo:'/logos/blubank.svg',aliases:['blubank','blubank.com','blu','blu bank','بلوبانک','بلو بانک','بلوبانک سامان','بانک دیجیتال بلو']},
}

function normalizeBrand(name:string) {
  return name.normalize('NFKC').toLowerCase().replace(/ي/g,'ی').replace(/ك/g,'ک').replace(/[\s\u200c\u200d-]+/g,'')
}

export function companyBrand(name:string|null|undefined) {
  const parts=(name||'').split('|').map(normalizeBrand)
  return Object.values(brands).find(brand=>brand.aliases.some(alias=>parts.includes(normalizeBrand(alias))))
}
