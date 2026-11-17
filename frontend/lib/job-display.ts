const dayMs = 86_400_000

function dateParts(date: Date, options: Intl.DateTimeFormatOptions) {
  return Object.fromEntries(new Intl.DateTimeFormat('en-US-u-ca-persian-nu-latn', options).formatToParts(date).map(part => [part.type, part.value]))
}

/** Publication dates are calendar dates from the source; the current day is in Iran. */
export function postedDateLabel(value: string | null, now = new Date()): string {
  if (!value || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return 'تاریخ نامشخص'
  const parsed = new Date(`${value}T00:00:00Z`)
  if (Number.isNaN(parsed.getTime()) || parsed.toISOString().slice(0, 10) !== value) return 'تاریخ نامشخص'
  const todayParts = new Intl.DateTimeFormat('en-CA', {timeZone:'Asia/Tehran', year:'numeric', month:'2-digit', day:'2-digit'}).formatToParts(now)
  const today = Object.fromEntries(todayParts.map(part => [part.type, part.value]))
  const currentDay = Math.floor(Date.UTC(Number(today.year), Number(today.month) - 1, Number(today.day)) / dayMs)
  const postedDay = Math.floor(parsed.getTime() / dayMs)
  if (postedDay <= currentDay) {
    if (postedDay === currentDay) return 'امروز'
    const weekStart = currentDay - ((new Date(currentDay * dayMs).getUTCDay() + 1) % 7)
    if (postedDay >= weekStart) return 'همین هفته'
    const opts: Intl.DateTimeFormatOptions = {timeZone:'UTC', year:'numeric', month:'numeric'}
    const a = dateParts(parsed, opts), b = dateParts(new Date(currentDay * dayMs), opts)
    if (a.year === b.year && a.month === b.month) return 'این ماه'
  }
  return new Intl.DateTimeFormat('fa-IR', {timeZone:'UTC', year:'numeric', month:'numeric', day:'numeric'}).format(parsed)
}

export function jobStatus(value: string | null | undefined) {
  if (value === 'open' || value === 'active') return {label:'فعال', tone:'active'}
  if (value === 'listed') return {label:'در فهرست منبع', tone:'listed'}
  if (value === 'closed' || value === 'inactive') return {label:'بسته', tone:'closed'}
  return {label:'وضعیت نامشخص', tone:'unknown'}
}

/** Localize numeric facts once, without changing job titles or source URLs. */
export function persianFact(value: string | null | undefined): string {
  return (value || '').replace(/[0-9٠-٩]/g, digit => {
    const code = digit.charCodeAt(0)
    return '۰۱۲۳۴۵۶۷۸۹'[code >= 0x660 ? code - 0x660 : code - 48]
  })
}

export function salaryLabel(value: string | null | undefined): string {
  const text = (value || '').trim()
  if (!text) return 'حقوق اعلام نشده'
  if (/^(negotiable|توافقی)$/i.test(text)) return 'توافقی'
  return persianFact(text.replace(/([0-9۰-۹٠-٩]),(?=[0-9۰-۹٠-٩])/g,'$1٬').replace(/([0-9۰-۹٠-٩])\.(?=[0-9۰-۹٠-٩])/g,'$1٫').replace(/\bIRR\b/g,'ریال').replace(/\bIRT\b/g,'تومان').replace(/\bMONTH(?:LY)?\b/gi,'ماهانه').replace(/\bYEAR(?:LY)?\b/gi,'سالانه').replace(/\bHOUR(?:LY)?\b/gi,'ساعتی'))
}

export function companyLabel(value:string|null|undefined) {
  const parts=(value||'').split('|').map(s=>s.trim()).filter(Boolean)
  return parts.find(s=>/[\u0600-\u06ff]/.test(s))||parts[0]||'شرکت اعلام نشده'
}
export function locationLabel(value:string|null|undefined) {
  if(!value)return 'مکان اعلام نشده'
  return Array.from(new Set(value.split(/[,،]/).map(part=>part.trim()).filter(Boolean))).join('، ')
}
