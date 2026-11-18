'use client'
import Link from 'next/link'
import { useState } from 'react'
import { track } from '@/lib/analytics'
import { site } from '@/lib/site'
import { brands } from '@/lib/brands'
import { SpielMark } from '@/components/spiel-mark'

type Client='Codex'|'Claude Code'|'OpenCode'
const clients:Client[]=['Codex','Claude Code','OpenCode']
const logos:Record<Client,string>={'Codex':'/logos/clients/codex.svg','Claude Code':'/logos/clients/claude-code.svg','OpenCode':'/logos/clients/opencode.svg'}
const localCommands:Record<Client,string>={
  'Codex':'codex mcp add spieljobs -- "/مسیر/spieljobs/scripts/run-mcp.sh"',
  'Claude Code':'claude mcp add --transport stdio spieljobs -- "/مسیر/spieljobs/scripts/run-mcp.sh"',
  'OpenCode':'opencode mcp add spieljobs --global -- "/مسیر/spieljobs/scripts/run-mcp.sh"',
}
const companies = [
 ['digikala.com','دیجی‌کالا'], ['snapp.ir','اسنپ'], ['snappfood.ir','اسنپ‌فود'],
 ['tapsi.ir','تپسی'], ['divar.ir','دیوار'], ['cafebazaar.ir','کافه‌بازار'],
 ['azki.com','ازکی'], ['yektanet.com','یکتانت'], ['tapsell.ir','تپسل'],
 ['blubank.com','بلوبانک'], ['alibaba.ir','علی‌بابا'], ['mydigipay.com','دیجی‌پی'],
 ['snapp.market','اسنپ‌مارکت'], ['filimo.com','فیلیمو'], ['torob.com','ترب'],
 ['nobitex.ir','نوبیتکس'], ['doctoreto.com','دکترتو'], ['jabama.com','جاباما'],
 ['digiexpress.ir','دیجی‌اکسپرس'], ['aparat.com','آپارات'],
]
function BrandLogo({domain,name,local}:{domain:string;name:string;local?:string}) {
 const [failed,setFailed]=useState(false)
 return <span className="mcp-company-logo">{failed ? <span aria-hidden="true">{name.slice(0,1)}</span> : <img src={local || (domain==='azki.com'?brands.azki.logo:`https://www.google.com/s2/favicons?domain=${domain}&sz=128`)} alt={`نشان ${name}`} loading="lazy" onError={()=>setFailed(true)}/>}</span>
}
function ClientMark({name}:{name:Client}){return <span className={`client-mark client-${name.toLowerCase().replace(' ','-')}`}><img src={logos[name]} alt=""/></span>}
export default function McpPage(){
 const [client,setClient]=useState<Client>('Codex'),[copied,setCopied]=useState(false)
 const endpoint=process.env.NEXT_PUBLIC_MCP_URL
 const commands:Record<Client,string>=endpoint?{
   'Codex':`codex mcp add spieljobs --url ${endpoint}`,
   'Claude Code':`claude mcp add --transport http spieljobs ${endpoint}`,
   'OpenCode':`opencode mcp add spieljobs --global --url ${endpoint}`,
 }:localCommands
 async function copy(){try{await navigator.clipboard.writeText(commands[client]);setCopied(true);track('mcp_connection_command_copied',{client,transport:endpoint?'http':'stdio'});setTimeout(()=>setCopied(false),1800)}catch{setCopied(false)}}
 if (endpoint && process.env.NEXT_PUBLIC_SPIELJOBS_SUPABASE_SEARCH === 'true') {
  return (
   <main className="mcp-page" dir="rtl">
    <header className="mcp-nav">
     <Link className="mcp-brand" href="/"><span className="mcp-mark"><SpielMark animated/></span><b dir="ltr">SpielJobs<span>.</span></b></Link>
     <div className="mcp-nav-actions"><Link href="/">جست‌وجوی وب</Link></div>
    </header>
    <section className="mcp-hero">
     <div className="mcp-badge"><span/> SPIELJOBS MCP · نسخه آزمایشی</div>
     <h1>جست‌وجوی شغل<br/><span>از داخل دستیار شما</span></h1>
     <p>یک عنوان شغلی مثل «حسابدار» وارد کنید. SpielJobs صفحهٔ اول جاب‌ویژن و جابینجا را بررسی می‌کند و لینک آگهی‌ها و وضعیت هر منبع را برمی‌گرداند.</p>
    </section>
    <section className="mcp-section mcp-source-overview" aria-label="منابع جست‌وجو">
     <div className="mcp-source-grid">
      <article><BrandLogo domain="jobvision.ir" name="جاب‌ویژن" local={brands.jobvision.logo}/><div><h3>جاب‌ویژن</h3><p>جست‌وجوی کلیدواژه</p></div></article>
      <article><BrandLogo domain="jobinja.ir" name="جابینجا" local={brands.jobinja.logo}/><div><h3>جابینجا</h3><p>نتایج وابسته به دسترسی منبع</p></div></article>
     </div>
    </section>
    <section className="mcp-section mcp-connect">
     <div className="mcp-connect-copy"><h2>اتصال به دستیار</h2><p>کلاینت خود را انتخاب کنید و دستور اتصال را اجرا کنید. ابزار <code dir="ltr">search_live_jobs</code> عبارت <code dir="ltr">query</code> را می‌پذیرد. این نسخه جست‌وجوی رزومه ندارد.</p></div>
     <div className="mcp-terminal">
      <div className="client-tabs">{clients.map(c=><button className={c===client?'selected':''} key={c} onClick={()=>{setClient(c);setCopied(false)}}>{c}</button>)}</div>
      <div className="copy-code"><pre dir="ltr"><code>{commands[client]}</code></pre><button onClick={copy} type="button">{copied?'کپی شد':'کپی دستور'}</button></div>
     </div>
    </section>
   </main>
  )
 }
 return <main className="mcp-page" dir="rtl"><header className="mcp-nav"><Link className="mcp-brand" href="/"><span className="mcp-mark"><SpielMark animated/></span><b dir="ltr">SpielJobs<span>.</span></b></Link><div className="mcp-nav-actions"><a href="#problem">مسئله</a><a href="#functions">ابزارهای MCP</a><a href="#connect">راهنمای اتصال</a><Link className="mcp-nav-cta" href="/">بازگشت به جست‌وجو <i className="bx bx-left-arrow-alt"/></Link></div></header>
 <section className="mcp-hero"><div className="mcp-badge"><span/> SPIELJOBS MCP · نسخه آزمایشی</div><h1>جست‌وجوی شغل،<br/><span>نتایج چند منبع، یک‌جا.</span></h1><p>به‌جای رفت‌وآمد بین سایت‌های کاریابی، به دستیار خود بگویید دنبال چه نقشی هستید. SpielJobs آگهی‌های منبع متصل را جست‌وجو می‌کند، با درخواست یا متن رزومهٔ شما تطبیق می‌دهد و نتایج را با تاریخ و لینک اصلی، یک‌جا به گفت‌وگو می‌آورد.</p><div className="mcp-actions"><a className="mcp-primary" href="#connect">اتصال به دستیار <i className="bx bx-left-arrow-alt"/></a><a className="mcp-secondary" href="#problem">چرا SpielJobs؟ <i className="bx bx-down-arrow-alt"/></a></div><div className="mcp-client-strip"><span>قابل اتصال به</span><div>{clients.map(name=><b className="client-brand" key={name}><ClientMark name={name}/>{name}</b>)}</div></div><div className="mcp-hero-art"><div className="mcp-halo halo-one"/><div className="mcp-halo halo-two"/><div className="mcp-avatar"><SpielMark animated/></div><span className="mcp-orbit-chip orbit-a"><i className="bx bx-search"/> جست‌وجوی زنده</span><span className="mcp-orbit-chip orbit-b"><i className="bx bx-link-alt"/> لینک منبع</span><span className="mcp-orbit-chip orbit-c"><i className="bx bx-check-shield"/> وضعیت پوشش</span></div></section>
 <section className="mcp-source-overview" aria-label="منابع جست‌وجوی شغل">
 <div className="mcp-source-heading"><span>فرصت‌ها کجا پراکنده‌اند؟</span><small>یک مسیر برای جمع‌کردن جست‌وجوها</small></div>
 <div className="mcp-source-grid">
 <article><BrandLogo domain="jobinja.ir" name="جابینجا" local={brands.jobinja.logo}/><div><h3>جابینجا</h3><p>جست‌وجوی زندهٔ آگهی‌های شغلی</p></div><span className="mcp-status available">متصل · آزمایشی</span></article>
 <article><BrandLogo domain="jobvision.ir" name="جاب‌ویژن" local={brands.jobvision.logo}/><div><h3>جاب‌ویژن</h3><p>فرصت‌های منتشرشده در پلتفرم کاریابی</p></div><span className="mcp-status available">آزمایشی · وابسته به دسترسی</span></article>
 <article><span className="mcp-company-logo"><i className="bx bx-buildings"/></span><div><h3>صفحهٔ استخدام شرکت‌ها</h3><p>آگهی‌ها مستقیم از وب‌سایت کارفرما</p></div><span className="mcp-status available">بررسی آزمایشی</span></article>
 </div></section>
 <section id="problem" className="mcp-section problem-section"><div className="mcp-section-label">مسئله چیست؟</div><h2>فرصت‌ها پراکنده‌اند.<br/><span>جست‌وجوی شما نباید پراکنده باشد.</span></h2><div className="problem-grid"><div><p>یک موقعیت در جابینجاست، دیگری در جاب‌ویژن و یکی فقط در صفحهٔ استخدام شرکت. هر بار باید چند سایت را باز کنید، عنوان‌های فارسی و انگلیسی را امتحان کنید و تاریخ انتشار و ارتباط هر آگهی با رزومه‌تان را جداگانه بسنجید. جست‌وجوی پراکنده یعنی وقت بیشتر، نتایج تکراری و فرصت‌هایی که ممکن است نبینید.</p><p>SpielJobs این مسیر را به یک درخواست تبدیل می‌کند: نقش، مهارت یا متن رزومه را بدهید؛ موتور جست‌وجو نتایج منبع متصل را جمع می‌کند، آگهی‌های مشابه را با تطبیق محتاطانه و حفظ لینک هر منبع گروه‌بندی می‌کند و فرصت‌ها را بر اساس تطابق واژه‌ها مرتب می‌کند. به‌جای فهرست لینک‌های پراکنده، عنوان، شرکت، مکان، تاریخ موجود و لینک اصلی را کنار هم می‌بینید.</p></div><div className="problem-quote"><i className="bx bx-search-alt"/><strong>یک درخواست.<br/>نتایج قابل پیگیری.</strong><small>با شفافیت دربارهٔ منبع و محدودیت‌ها</small></div></div></section>
 <section className="mcp-section mcp-companies"><div className="mcp-section-label">شرکت‌هایی که دنبال فرصت‌هایشان می‌گردید</div><h2>۲۰ نام آشنا. فرصت‌های پراکنده.</h2><p className="mcp-section-intro">از پلتفرم‌های بزرگ تا فین‌تک و تجارت الکترونیک؛ فرصت یک شرکت ممکن است در کاریابی یا فقط در سایت خودش منتشر شود.</p><div className="mcp-company-grid">{companies.map(([domain,name])=><div className="mcp-company" key={domain}><BrandLogo domain={domain} name={name}/><strong>{name}</strong></div>)}</div><p className="mcp-company-caption">نمونه‌هایی از شرکت‌های فناوری ایران؛ نمایش لوگو به معنی همکاری، اتصال به صفحهٔ استخدام یا وجود آگهی فعال نیست.</p></section>
 <section className="mcp-section"><div className="mcp-section-label">جست‌وجویی که از درخواست شما شروع می‌شود</div><h2>کمتر بگردید. مرتبط‌تر پیدا کنید.</h2><div className="mcp-benefits">
 <article><i className="bx bx-layer"/><h3>نتایج چند منبع، یک‌جا</h3><p>نتایج جست‌وجوهای انجام‌شده در منبع متصل، با حذف لینک تکراری و اطلاعات هر فرصت.</p></article>
 <article><i className="bx bx-search"/><h3>فرصت‌های قابل جست‌وجو</h3><p>بر اساس عنوان، کلیدواژه، مهارت یا متن رزومه؛ با نمایش واژه‌های مطابق برای هر نتیجه.</p></article>
 <article><i className="bx bx-time-five"/><h3>آگهی‌های تازه‌تر</h3><p>مثلاً «مدیر محصول در ۷ روز اخیر». فقط آگهی‌های دارای تاریخ قابل تشخیص وارد این فیلتر می‌شوند.</p></article>
 <article><i className="bx bx-history"/><h3>آخرین جست‌وجوها</h3><p>جست‌وجوهای وب تا ۷ روز روی همین دستگاه ذخیره می‌شوند. گفت‌وگوها را باز کنید، دوباره جست‌وجو کنید یا حذف کنید. متن و فایل رزومه در تاریخچه ذخیره نمی‌شوند.</p><span className="mcp-status">ذخیره روی دستگاه · بدون ورود</span></article>
 </div></section>
 <section id="how" className="mcp-section"><div className="mcp-section-label">چطور کار می‌کند؟</div><h2>از درخواست تا آگهی اصلی.</h2><p className="mcp-section-intro">MCP پل ارتباطی دستیار با موتور جست‌وجوی SpielJobs است. دستیار ابزار را فراخوانی می‌کند؛ سرور منابع متصل را می‌خواند و نتیجهٔ ساختاریافته را برای نمایش در همان گفت‌وگو برمی‌گرداند.</p><div className="mcp-steps"><article><span>۰۱</span><i className="bx bx-message-rounded-dots"/><h3>درخواست خود را بنویسید</h3><p>عنوان شغلی، مهارت‌ها، محدودهٔ زمانی یا متن رزومه‌تان را به دستیار بدهید.</p></article><article><span>۰۲</span><i className="bx bx-search-alt"/><h3>منابع متصل بررسی می‌شوند</h3><p>موتور، عبارت‌های جست‌وجو را آماده می‌کند، منبع متصل را می‌خواند و نتایج را فیلتر و مرتب می‌کند. تحلیل رزومه یا درخواست پیچیده می‌تواند از مدل استفاده کند.</p></article><article><span>۰۳</span><i className="bx bx-link-external"/><h3>به منبع اصلی بروید</h3><p>دستیار نتایج، لینک اصلی و وضعیت هر منبع بررسی‌شده را نشان می‌دهد.</p></article></div></section>
 <section id="functions" className="mcp-section"><div className="mcp-section-label">ابزارهای MCP</div><h2>یک ابزار. از جست‌وجو تا تطبیق.</h2><p className="mcp-section-intro">نسخهٔ فعلی یک تابع در اختیار دستیار می‌گذارد. جست‌وجوی کلیدواژه، فیلتر زمانی و تطبیق متن رزومه، همگی از همین ابزار استفاده می‌کنند.</p>
 <div className="mcp-tool"><div className="mcp-tool-title"><i className="bx bx-code-alt"/><code dir="ltr">search_live_jobs</code><span className="mcp-status available">در دسترس</span></div><p>جست‌وجوی زنده، گروه‌بندی محتاطانهٔ آگهی‌های مشابه با حفظ لینک هر منبع و مرتب‌سازی نتایج بر اساس ارتباط؛ همراه با گزارش وضعیت منابع.</p><dl><div><dt><code>query</code><span>الزامی · ۱ تا ۲۰۰۰ نویسه</span></dt><dd>شرح نقش، مهارت یا بازهٔ زمانی؛ مثلاً «مدیر محصول در تهران، ۷ روز اخیر».</dd></div><div><dt><code>resume_text</code><span>اختیاری · حداکثر ۳۰٬۰۰۰ نویسه</span></dt><dd>متن رزومه برای استخراج مهارت‌ها و افزودن آن‌ها به عبارت‌های جست‌وجو.</dd></div><div><dt><code>session_id</code><span>اختیاری · شناسهٔ گفت‌وگو</span></dt><dd>شناسهٔ بدون اطلاعات شخصی برای پیگیری جست‌وجوهای یک گفت‌وگو.</dd></div></dl><div className="mcp-tool-output"><strong>پاسخ ابزار</strong><code dir="ltr">jobs · jobs[].sources · sources · profile · warnings · model_used</code><p>فرصت‌ها با اطلاعات موجود، لینک هر منبع، منابع احتمالی یک آگهی، زمان بررسی و محدودیت‌های جست‌وجو.</p></div></div>
 <div className="mcp-prompt"><i className="bx bx-message-rounded-dots"/><div><small>نمونهٔ درخواست از دستیار</small><p>«با استفاده از SpielJobs، فرصت‌های مدیر محصول در تهران در ۷ روز اخیر را پیدا کن؛ لینک اصلی و وضعیت منابع را هم نشان بده.»</p></div></div></section>
 <section className="mcp-section transparency-section"><div><div className="mcp-section-label">شفاف و قابل بررسی</div><h2>آنچه الان واقعاً کار می‌کند.</h2><p>این نسخه به‌صورت آزمایشی جابینجا، جاب‌ویژن و صفحه‌های استخدام شرکت‌های منتخب را بررسی می‌کند. دسترسی و ساختار هر منبع متفاوت است؛ وضعیت واقعی هر بررسی در پاسخ نشان داده می‌شود و ممکن است برخی منابع نتیجه ندهند. «در فهرست منبع» یعنی آگهی هنگام جست‌وجو دیده شده؛ «فعال» فقط با تأیید صریح منبع نمایش داده می‌شود. وضعیت پذیرش را در لینک اصلی بررسی کنید.</p></div><div className="transparency-cards"><div><i className="bx bx-check-circle"/><span><strong>جست‌وجوی زنده</strong><small>در منابعی که در پاسخ نشان داده شده‌اند</small></span></div><div><i className="bx bx-link"/><span><strong>لینک اصلی</strong><small>برای بررسی جزئیات و ارسال درخواست</small></span></div><div><i className="bx bx-info-circle"/><span><strong>پوشش محدود</strong><small>بدون ادعای فهرست کامل فرصت‌ها</small></span></div></div></section>
 <section id="connect" className="mcp-section mcp-connect"><div className="mcp-connect-copy"><div className="mcp-section-label">{endpoint?'REMOTE MCP SERVER':'LOCAL MCP SERVER'}</div><h2>آمادهٔ اتصال؟</h2><p>{endpoint?'بدون نصب سرور محلی، ابزار را به دستیار خود متصل کنید. دستور کلاینت خود را کپی و اجرا کنید.':'اتصال محلی با stdio در دسترس است. ابتدا وابستگی‌های پروژه را نصب کنید، سپس مسیر پروژه را در دستور جایگزین کنید.'}</p><div className="mcp-note"><i className="bx bx-info-circle"/><span>{endpoint?'اتصال بدون حساب کاربری است. رزومه تنها با درخواست شما به ارائه‌دهندهٔ مدل ارسال می‌شود.':'اتصال عمومی پس از تأیید استقرار فعال می‌شود؛ فعلاً از اتصال محلی یا جست‌وجوی وب استفاده کنید.'}</span></div><Link href="/">امتحان جست‌وجوی تحت وب <i className="bx bx-left-arrow-alt"/></Link></div><div className="mcp-terminal"><div className="terminal-top"><span><i/><i/><i/></span><small>TERMINAL</small><i className="bx bx-terminal"/></div><div className="terminal-inner"><div className="client-tabs">{clients.map(c=><button key={c} className={client===c?'selected':''} onClick={()=>{setClient(c);setCopied(false)}}><ClientMark name={c}/>{c}</button>)}</div>{!endpoint&&<><p>۱. کد پروژه را دریافت کنید و وابستگی‌ها را نصب کنید:</p><pre dir="ltr"><code>{'git clone https://github.com/ShayanSpiel/SpielJobs.git spieljobs\ncd spieljobs\npython3 -m venv .venv\n.venv/bin/pip install -r backend/requirements.txt'}</code></pre></>}<p>{endpoint?'دستور اتصال را کپی و اجرا کنید:':'۲. مسیر کامل پروژه را در دستور زیر جایگزین و اجرا کنید:'}</p><div className="copy-code"><pre dir="ltr"><code>{commands[client]}</code></pre><button onClick={copy} aria-label="کپی دستور"><i className={`bx bx-${copied?'check':'copy'}`}/></button></div><small>برای تحلیل هوشمند رزومه، کلید Mistral یا Gemini را در محیط اجرای سرور تنظیم کنید. رزومه در صورت استفاده از مدل برای ارائه‌دهندهٔ آن ارسال می‌شود.</small></div></div></section><footer className="mcp-footer"><div><span dir="ltr">{site.name} · MCP</span><small>ساختهٔ شایان توابی · پیدا کردن فرصت، با شواهد روشن.</small></div><nav aria-label="لینک‌های پروژه و سازنده"><a href={site.links.repository||site.links.github} target="_blank" rel="noopener noreferrer"><i className="bx bxl-github"/>{site.links.repository?'GitHub پروژه':'GitHub'}</a><a href={site.links.linkedin} target="_blank" rel="noopener noreferrer"><i className="bx bxl-linkedin"/>LinkedIn</a><a href={site.links.x} target="_blank" rel="noopener noreferrer"><i className="bx bxl-twitter"/>X</a><a href={site.links.home}>SpielOS</a><a href={site.links.contact}>تماس و همکاری</a><Link href="/privacy">حریم خصوصی</Link></nav></footer></main>
}
