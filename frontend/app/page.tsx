'use client'
import { useEffect, useRef, useState } from 'react'
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from '@/components/ui/accordion'
import { Button } from '@/components/ui/button'
import { SpielMark } from '@/components/spiel-mark'
import Link from 'next/link'
import { socialLinks } from '@/lib/site'
import { SocialIcon } from '@/components/social-icon'
import { companyBrand } from '@/lib/brands'
import { sourceLogoCandidates, sourceForJob, type SourceIdentity } from '@/lib/source-logos'
import { postedDateLabel, jobStatus, salaryLabel, persianFact, companyLabel, locationLabel } from '@/lib/job-display'

import type { JobSource, Job, Source, Result, Step, Message } from '@/lib/search-types'
import { track, analyticsHeaders } from '@/lib/analytics'
import { searchStream } from '@/lib/search-client'
import { HISTORY_KEY, readHistory, writeHistory, type Conversation } from '@/lib/history'

const api = process.env.NEXT_PUBLIC_SPIELJOBS_API_PROXY === 'true' ? '/api/runtime' :
  process.env.NODE_ENV === 'development' ? 'http://127.0.0.1:8000' : ''
const examples=['حسابدار مسلط به اکسل در تهران','سرپرست فروش در اصفهان','مسلط به Python و SQL در مشهد']
const fa=(n:number)=>new Intl.NumberFormat('fa-IR').format(n)
function Icon({name,className=''}:{name:string;className?:string}){return <i aria-hidden="true" className={`bx bx-${name} ${className}`}/>}
function ProviderLogo({source}:{source?:SourceIdentity}){const [failed,setFailed]=useState<string[]>([]);const urls=sourceLogoCandidates(source);const src=urls.find(url=>!failed.includes(url));return <span className="provider-logo" aria-hidden="true">{src?<img key={src} src={src} alt="" onError={()=>setFailed(previous=>[...previous,src])}/>:<Icon name="world"/>}</span>}

function CompanyLogo({job}:{job:Job}){
 const [failed,setFailed]=useState<string[]>([])
 const brand=companyBrand(job.company)
 const candidates=[brand?.logo,job.company_logo_url,brand?.fallback].filter((v):v is string=>!!v)
 const src=candidates.find(url=>!failed.includes(url))
 return <span className="company-logo-inline" aria-hidden="true">{src?<img src={src} alt="" loading="lazy" referrerPolicy="no-referrer" onError={()=>setFailed(previous=>[...previous,src])}/>:<Icon name="buildings"/>}</span>
}
function Description({text}:{text:string}){
 const [expanded,setExpanded]=useState(false)
 return <div className="job-description"><strong>دربارهٔ این فرصت</strong><p className={expanded?'description-full':'description-preview'} dir="auto">{text.slice(0,6000)}</p>{text.length>100&&<button className="description-toggle" aria-expanded={expanded} onClick={()=>setExpanded(!expanded)}>{expanded?'نمایش کمتر':'ادامهٔ توضیحات'}<Icon name={expanded?'chevron-up':'chevron-down'}/></button>}</div>
}
function jobinjaSearchLink(source:Source){
 if(source.id!=='jobinja'||source.state!=='unavailable')return null
 const term=source.searches?.[0]?.term
 if(!term)return null
 const url=new URL('https://jobinja.ir/jobs')
 url.searchParams.set('filters[keywords][]',term)
 return url.href
}
const sourceFailures: Record<string, string> = {
 source_maintenance: 'منبع موقتاً در دسترس نیست',
 blocked: 'منبع به SpielJobs دسترسی نداد',
 timeout: 'منبع به‌موقع پاسخ نداد',
 rate_limited: 'منبع تعداد درخواست‌ها را محدود کرد',
 not_found: 'صفحهٔ منبع پیدا نشد',
 connection_failed: 'ارتباط با منبع برقرار نشد',
 http_error: 'منبع موقتاً پاسخ نمی‌دهد',
 schema_changed: 'خواندن فهرست آگهی‌ها ممکن نبود',
}
function SourceChip({source}:{source:Source}){
 const link=jobinjaSearchLink(source)
 const via=source.provider==='jobvision'&&source.id!=='jobvision'?'جاب‌ویژن':source.provider==='hiretik'?'Hiretik':null
 let status='در حال بررسی'
 if(source.state==='stale') status='نتایج آخرین بررسی موفق'
 if(source.state==='partial'||source.state==='success') {
   status=typeof source.matched_count==='number'
      ? (source.matched_count ? fa(source.matched_count)+' نتیجهٔ مرتبط' : 'نتیجهٔ مرتبط پیدا نشد')
      : 'بررسی شد'
 }
 if(source.state==='unavailable'||source.state==='unverified') status=sourceFailures[source.failure_kind||'']||'بررسی منبع کامل نشد'
 if(source.state==='interrupted') status='بررسی متوقف شد'
 return <span className={'source-chip source-'+source.state}>
   <ProviderLogo source={source}/><span>{source.label||source.name}</span><span className="chip-divider"/>
   <span className="chip-status">{status}{via&&' · از طریق '+via}</span>
   {link&&<a href={link} target="_blank" rel="noopener noreferrer" className="source-search-link">باز کردن جابینجا</a>}
 </span>
}
function SourceOverview({sources}:{sources:Source[]}){const [open,setOpen]=useState(sources.length<=2);if(!sources.length)return null;const pending=sources.filter(source=>source.state==='searching').length;return <div className="source-overview"><button type="button" className="source-overview-toggle" aria-expanded={open} onClick={()=>setOpen(!open)}><span className="overview-logos">{sources.slice(0,5).map((source,index)=><span className="overview-logo" title={source.label||source.name} key={source.id||`${source.name}-${index}`}><ProviderLogo source={source}/></span>)}</span><span>{pending?`${fa(pending)} منبع در حال بررسی`:`${fa(sources.filter(s=>s.state==='partial'||s.state==='success').length)} از ${fa(sources.length)} منبع بررسی شد`}</span>{sources.some(s=>s.state==='stale')&&<small>{fa(sources.filter(s=>s.state==='stale').length)} منبع از نسخهٔ قبلی</small>}<span className="overview-more">{open?'بستن':'وضعیت منابع'} <Icon name={open?'chevron-up':'chevron-down'}/></span></button>{open&&<div className="source-list">{sources.map((source,index)=><SourceChip key={source.id||`${source.name}-${index}`} source={source}/>)}</div>}</div>}
function jobSources(job:Job):JobSource[]{return job.sources?.length?job.sources:[{id:job.source,url:job.url}]}
function SourceStack({job,sources}:{job:Job;sources:Source[]}){const evidence=jobSources(job);return <span className="source-stack" aria-label={`منابع: ${evidence.map(item=>sourceForJob(item.id||job.source,sources,item.url||job.url).label||item.id||job.source).join('، ')}`}>{evidence.map((item,index)=>{const source=sourceForJob(item.id||job.source,sources,item.url||job.url);return <span className="source-stack-item" key={`${item.id}-${item.url}-${index}`} title={source.label||source.name}><ProviderLogo source={source}/></span>})}</span>}
function JobRow({job,sources}:{job:Job;sources:Source[]}){return <><div className="job-main"><div className="job-label"><strong dir="auto">{job.title}</strong><span className="job-company-line"><CompanyLogo job={job}/><span dir="auto">{companyLabel(job.company)}</span><b>·</b><span dir="auto">{locationLabel(job.location)}</span></span></div></div><SourceStack job={job} sources={sources}/><div className="job-secondary"><span className="job-date" title={job.posted_date||undefined}>{postedDateLabel(job.posted_date)}</span><span className="job-salary" dir="auto">{salaryLabel(job.salary)}</span><span className={`job-status ${jobStatus(job.status).tone}`}>{jobStatus(job.status).label}</span></div></>}
function JobDetails({job,sources}:{job:Job;sources:Source[]}){const facts=[['حقوق',salaryLabel(job.salary)],['نوع همکاری',job.contract||'اعلام نشده'],['سابقه کار',job.experience||'اعلام نشده'],['تحصیلات',job.education||'اعلام نشده'],['دسته‌بندی',job.category||'اعلام نشده']].filter((entry):entry is [string,string]=>Boolean(entry[1]));const links=[['وب‌سایت',job.website],['لینکدین',job.linkedin],['اینستاگرام',job.instagram]].filter((entry):entry is [string,string]=>Boolean(entry[1]));return <div className="job-details">{!!job.match_terms?.length&&<div className="match-evidence"><span>واژه‌های مطابق</span><div className="match-terms">{job.match_terms.map(term=><span dir="auto" key={term}>{term}</span>)}</div></div>}{job.description&&<Description text={job.description}/>}{facts.length>0&&<dl className="job-facts">{facts.map(([label,value])=><div key={label}><dt>{label}</dt><dd dir="auto">{label==='حقوق'?salaryLabel(value):persianFact(value)}</dd></div>)}</dl>}{!!job.skills?.length&&<div className="job-skills"><strong>مهارت‌های مورد نیاز</strong><div className="match-terms">{job.skills.map(skill=><span dir="auto" key={skill}>{skill}</span>)}</div></div>}{links.length>0&&<div className="job-company-links">{links.map(([label,url])=><a key={label} href={url} target="_blank" rel="noopener noreferrer">{label}<Icon name="link-external"/></a>)}</div>}<p className="verification"><Icon name="info-circle"/> {jobStatus(job.status).tone==='listed'?'این آگهی هنگام جست‌وجو در فهرست منبع دیده شد؛ برای وضعیت پذیرش، صفحهٔ اصلی را بررسی کنید.':jobStatus(job.status).tone==='unknown'?'وضعیت باز بودن این آگهی هنوز تأیید مستقل نشده است.':jobStatus(job.status).tone==='active'?'این آگهی طبق اطلاعات منبع فعال است.':'این آگهی طبق اطلاعات منبع بسته است.'}</p><div className="job-source-links">{jobSources(job).map((item,index)=>{const source=sourceForJob(item.id||job.source,sources,item.url||job.url);return <a className="job-link" onClick={()=>track('job_source_opened',{source:item.id||job.source})} key={`${item.id}-${item.url}-${index}`} href={item.url||job.url} target="_blank" rel="noopener noreferrer"><ProviderLogo source={source}/><span>مشاهده در {source.label||source.name}</span>{item.posted_date&&<small>{postedDateLabel(item.posted_date)}</small>}{item.salary&&<small dir="auto">{salaryLabel(item.salary)}</small>}{item.status&&item.status!=='unknown'&&<small className={`job-source-status ${jobStatus(item.status).tone}`}>{jobStatus(item.status).label}</small>}<Icon name="link-external"/></a>})}</div></div>}
function JobCards({jobs,sources,expanded,onMore}:{jobs:Job[];sources:Source[];expanded:boolean;onMore:()=>void}){const visible=expanded?jobs:jobs.slice(0,3);return <div className="results"><div className="result-heading"><div><span className="eyebrow">نتایج جست‌وجو</span><h3>{fa(jobs.length)} فرصت برای بررسی</h3></div><span className="result-meta">مرتبط‌ترها، اول</span></div><Accordion type="single" collapsible className="jobs-list">{visible.map((job,index)=><AccordionItem key={`${job.url}-${index}`} value={`${index}`}><AccordionTrigger><JobRow job={job} sources={sources}/></AccordionTrigger><AccordionContent><JobDetails job={job} sources={sources}/></AccordionContent></AccordionItem>)}</Accordion>{!expanded&&jobs.length>3&&<button className="more-button" onClick={onMore}>نمایش {fa(jobs.length-3)} فرصت دیگر <Icon name="down-arrow-alt"/></button>}</div>}
function SearchReply({result, expanded, onMore}:{result:Result;expanded:boolean;onMore:()=>void}){
 const {jobs}=result
 const sources=result.sources.filter(source=>source.state!=='not_implemented'&&source.state!=='not_searched'&&!!source.checked_at)
 const legacyWarning='آگهی‌ها با همهٔ معیارهای جست‌وجو هم‌خوان نبودند. یک فیلتر را بردارید و دوباره جست‌وجو کنید.'
 const warnings=(result.warnings||[]).filter(warning=>warning!==legacyWarning)
 const filteredOut=result.filtered_out||(result.warnings||[]).includes(legacyWarning)
 const searched=filteredOut||sources.some(source=>['partial','success','stale'].includes(source.state))
 let emptyMessage=null
 if(!jobs.length){
   if(searched){
     const retry=result.profile?.location?'اگه شهر برات انعطاف‌پذیره، بدون اسم شهر هم امتحان کن.'
       :result.profile?.days?'اگه فرصت‌های قدیمی‌تر هم برات مناسبن، بازهٔ زمانی رو بیشتر کن.'
       :'با یه عنوان ساده‌تر یا اسم یه نقش نزدیک دوباره امتحان کن.'
     emptyMessage={title:'برای این جست‌وجو آگهی مناسبی پیدا نکردم.',detail:retry}
   } else if(sources.length){
     emptyMessage={title:'این بار نتونستم آگهی‌ها رو بررسی کنم.',detail:'کمی بعد دوباره امتحان کن.'}
   } else if(!warnings.length){
     emptyMessage={title:'دنبال چه شغلی هستی؟',detail:'اسم شغل یا مهارتی که برات مهمه رو بنویس تا بگردم.'}
   }
 }
 return <>
   {emptyMessage&&<div className="assistant-copy empty-reply">
     <strong>{emptyMessage.title}</strong>
     <p>{emptyMessage.detail}</p>
   </div>}
   {warnings.map((warning,index)=><p className="notice" key={index}><Icon name="info-circle"/> {warning}</p>)}
   {jobs.length>0&&<JobCards jobs={jobs} sources={result.sources} expanded={expanded} onMore={onMore}/>}
   {sources.length>0&&<div className="source-summary"><SourceOverview sources={sources}/></div>}
 </>
}

function Activity({steps,active,failed,sources,detail=false}:{steps:Step[];active:boolean;failed?:boolean;sources?:Source[];detail?:boolean}){if(!steps.length)return null;if(!active&&!failed&&!detail)return <details className="completed-activity"><summary><Icon name="check"/><span>جست‌وجو تمام شد</span><small>مشاهدهٔ روند بررسی</small></summary><Activity steps={steps} active={false} sources={sources} detail/></details>;const finalSources=sources||[...steps].reverse().find(step=>step.phase==='rank')?.sources;return <div className={`activity ${failed?'activity-failed':''}`} aria-live="polite"><div className="activity-heading"><span className={active?'activity-orbit running':'activity-orbit'}><Icon name={active?'loader-alt':failed?'error-circle':'check'}/></span><span>{active?'در حال انجام جست‌وجو':failed?'جست‌وجو کامل نشد':'جست‌وجو انجام شد'}</span>{active&&<span className="activity-dots"><i/><i/><i/></span>}</div><div className="activity-steps">{steps.map((step,i)=>{const current=active&&i===steps.length-1;const incomplete=failed&&i===steps.length-1;const labels:Record<string,[string,string]>={prepare:['آماده‌سازی درخواست',step.interpretation==='resume'?'در حال تحلیل رزومه':step.interpretation==='complex_prompt'?'در حال تحلیل درخواست':'در حال آماده‌سازی درخواست'],search:['بررسی منابع','در حال بررسی منابع'],rank:['مرتب‌سازی فرصت‌ها','در حال مرتب‌سازی فرصت‌ها']};const title=labels[step.phase]||[step.phase,step.phase];return <div className={`activity-step ${current?'current':''} ${incomplete?'incomplete':''}`} key={`${step.phase}-${i}`}><span className="step-indicator"><Icon name={current?'loader-alt':incomplete?'error-circle':'check'}/></span><div className="step-body">{incomplete?`${title[0]} متوقف شد`:current?title[1]:`${title[0]} انجام شد`}{step.phase==='search'&&step.terms?.length?<small dir="auto">{step.terms.join(' · ')}</small>:null}{step.phase==='search'&&active&&step.group?<small>{step.group==='career_pages'?'بررسی صفحات شغلی شرکت‌ها':'بررسی سایت‌های کاریابی'}</small>:null}{step.phase==='search'&&step.sources?.length?<SourceOverview sources={step.sources.map(source=>{const latest=finalSources?.find(item=>(item.id||item.name)===(source.id||source.name));return latest||(!active&&failed?{...source,state:'interrupted'}:source)})}/>:null}</div></div>})}</div></div>}

export default function Home(){
 const [query,setQuery]=useState(''),[resume,setResume]=useState(''),[filename,setFilename]=useState(''),[messages,setMessages]=useState<Message[]>([]),[loading,setLoading]=useState(false),[uploading,setUploading]=useState(false),[error,setError]=useState(''),[theme,setTheme]=useState<'light'|'dark'>('light'),[themeReady,setThemeReady]=useState(false),[sidebarOpen,setSidebarOpen]=useState(false)
 const [chats,setChats]=useState<Conversation[]>([]),[activeChat,setActiveChat]=useState(''),[historyReady,setHistoryReady]=useState(false),[restored,setRestored]=useState(false),[historyError,setHistoryError]=useState(false)
 const input=useRef<HTMLInputElement>(null),composerInput=useRef<HTMLTextAreaElement>(null),bottom=useRef<HTMLDivElement>(null),abort=useRef<AbortController|null>(null)
 useEffect(()=>()=>abort.current?.abort(),[])
 useEffect(()=>{try{const saved=readHistory(localStorage.getItem(HISTORY_KEY));setChats(saved);if(saved[0]){setActiveChat(saved[0].id);setMessages(saved[0].messages);setRestored(true)}}catch{setHistoryError(true)}finally{setHistoryReady(true)}},[])
 useEffect(()=>{if(!historyReady||!activeChat||!messages.length)return;setChats(previous=>{const title=messages.find(m=>m.role==='user')?.text||'جست‌وجوی رزومه';return [{id:activeChat,title:title.slice(0,80),updatedAt:new Date().toISOString(),messages},...previous.filter(c=>c.id!==activeChat)].slice(0,20)})},[messages,activeChat,historyReady])
 useEffect(()=>{if(!historyReady)return;try{setHistoryError(!writeHistory(localStorage,chats))}catch{setHistoryError(true)}},[chats,historyReady])
 function newChat(){if(loading||uploading)return;setRestored(false);setMessages([]);setQuery('');setResume('');setFilename('');setActiveChat(crypto.randomUUID());setSidebarOpen(false)}
 function selectChat(chat:Conversation){if(loading||uploading)return;setRestored(true);setActiveChat(chat.id);setMessages(chat.messages);setResume('');setFilename('');setQuery('');setSidebarOpen(false)}
 function deleteChat(id:string){if(loading||uploading)return;setChats(previous=>previous.filter(c=>c.id!==id));if(activeChat===id)newChat()}

 useEffect(()=>{const shortcut=(event:KeyboardEvent)=>{if((event.metaKey||event.ctrlKey)&&event.key.toLowerCase()==='k'&&!loading){event.preventDefault();newChat()}};window.addEventListener('keydown',shortcut);return()=>window.removeEventListener('keydown',shortcut)},[loading,uploading])
 useEffect(()=>{try{const saved=localStorage.getItem('spieljobs-theme');if(saved==='dark'||saved==='light')setTheme(saved)}catch{}finally{setThemeReady(true)}},[])
 useEffect(()=>{if(!themeReady)return;document.documentElement.dataset.theme=theme;try{localStorage.setItem('spieljobs-theme',theme)}catch{}},[theme,themeReady])
 useEffect(()=>{const close=(event:KeyboardEvent)=>{if(event.key==='Escape')setSidebarOpen(false)};window.addEventListener('keydown',close);return()=>window.removeEventListener('keydown',close)},[])
 useEffect(()=>{bottom.current?.scrollIntoView({behavior:'smooth',block:'end'})},[messages,loading])
 function update(id:string,fn:(m:Message)=>Message){setMessages(previous=>previous.map(m=>m.id===id?fn(m):m))}
 async function submit(value=query){const q=value.trim()||(resume?'فرصت‌های شغلی مناسب رزومه من':'');if(!api||!q||loading||uploading||!historyReady)return;setRestored(false);const conversationId=activeChat||crypto.randomUUID();if(!activeChat)setActiveChat(conversationId);const id=crypto.randomUUID();setError('');setQuery('');setMessages(previous=>[...previous,{id:crypto.randomUUID(),role:'user',text:q,filename,usedResume:Boolean(resume)},{id,role:'assistant',steps:[]}]);setLoading(true);const controller=new AbortController();abort.current=controller
 track('search_submitted',{has_resume:!!resume,query_length:q.length})
 try {
   const events = await searchStream(api, q, resume, controller.signal, conversationId, analyticsHeaders())
   let completed = false
   for await (const event of events) {
     const payload = event.data
     if (event.type === 'status') {
       update(id, m => ({ ...m, steps: [...(m.steps || []), payload as unknown as Step] }))
     } else if (event.type === 'source_progress') {
       const progress = payload as { sources?: Source[]; group?: string }
       update(id, m => ({ ...m, steps: (m.steps || []).map(step => {
         if (step.phase !== 'search') return step
         const sources = [...(step.sources || [])]
         for (const source of progress.sources || []) {
           const index = sources.findIndex(item => (item.id || item.name) === (source.id || source.name))
           if (index < 0) sources.push(source)
           else sources[index] = source
         }
         return { ...step, sources, group: progress.group || step.group }
       }) }))
     } else if (event.type === 'result') {
       if(process.env.NODE_ENV==='development')console.info('SpielJobs runtime',{run_id:payload.run_id,trace_id:payload.trace_id,runtime:payload.runtime})
       if (!Array.isArray(payload.jobs) || !Array.isArray(payload.sources)) throw Error('پاسخ سرور ناقص بود.')
       completed = true
       track('search_completed',{result_count:payload.jobs.length,source_count:payload.sources.length,run_id:String(payload.run_id||'')})
       update(id, m => ({ ...m, result: payload as unknown as Result }))
     } else if (event.type === 'error') {
       completed = true
       update(id, m => ({ ...m, error: String(payload.message || 'جست‌وجو متوقف شد.') }))
     }
   }
   if (!completed) throw Error('ارتباط پیش از پایان جست‌وجو قطع شد.')
 }catch(e){track(controller.signal.aborted?'search_stopped':'search_failed');if(controller.signal.aborted)update(id,m=>({...m,stopped:true}));else update(id,m=>({...m,error:e instanceof Error&&e.name==='TimeoutError'?'جست‌وجو بیش از حد طول کشید. دوباره امتحان کنید.':e instanceof TypeError?'ارتباط با سرور قطع شد. دوباره امتحان کنید.':e instanceof Error?e.message:'خطایی در جست‌وجو رخ داد.'}))}finally{setLoading(false);abort.current=null}}
 async function upload(file?:File){
 if(!api||!file||uploading)return;
 if(file.size>2_000_000||!/\.(pdf|docx)$/i.test(file.name)){
   setError('رزومه را در قالب PDF یا Word و با حجم حداکثر ۲ مگابایت بارگذاری کنید.');
   if(input.current)input.current.value='';
   return;
 }
 setUploading(true);setError('');try{if(!api)throw Error('جست‌وجو فعلاً در دسترس نیست.');const data=new FormData();data.append('file',file);const response=await fetch(`${api}/resume`,{method:'POST',body:data,signal:AbortSignal.timeout(20_000)});const body=await response.json();if(!response.ok)throw Error('متن رزومه خوانده نشد. یک PDF متنی یا فایل Word دیگر را امتحان کنید.');setResume(body.text);setFilename(file.name)}catch(e){setError(e instanceof Error&&e.name==='TimeoutError'?'خواندن رزومه بیش از حد طول کشید. دوباره امتحان کنید.':e instanceof TypeError||e instanceof SyntaxError?'ارتباط با سرویس رزومه قطع شد. دوباره امتحان کنید.':e instanceof Error?e.message:'خواندن رزومه ممکن نبود. دوباره امتحان کنید.')}finally{setUploading(false);if(input.current)input.current.value=''}}
 const last=messages[messages.length-1]
 const lastSearch=[...messages].reverse().find(m=>m.role==='user')
 const needsResume=Boolean(lastSearch?.usedResume&&!resume)
 return <div className="app-shell">{sidebarOpen&&<button className="mobile-sidebar-backdrop" aria-label="بستن منو" onClick={()=>setSidebarOpen(false)}/>}<aside id="main-sidebar" className={`sidebar ${sidebarOpen?'mobile-open':''}`}><div className="brand"><div className="brand-mark"><SpielMark animated/></div><div><strong dir="ltr">SpielJobs<span>.</span></strong><small>دستیار جست‌وجوی شغل</small></div></div><button className="new-chat" onClick={newChat} disabled={loading||uploading}><Icon name="plus"/> جست‌وجوی جدید <span>⌘ K</span></button><div className="sidebar-section"><div className="sidebar-caption">فضای کاری</div><div className="nav-active"><Icon name="message-rounded-dots"/> جست‌وجوی فرصت‌ها <Icon name="chevron-left"/></div></div><div className="history-section"><div className="sidebar-caption">جست‌وجوهای اخیر <small>روی این دستگاه · ۷ روز</small></div>{chats.length?chats.map(chat=><div className={`history-item ${activeChat===chat.id?'selected':''}`} key={chat.id}><button disabled={loading||uploading} onClick={()=>selectChat(chat)} title={chat.title}><Icon name="history"/><span dir="auto">{chat.title}</span></button><button disabled={loading||uploading} aria-label={`حذف جست‌وجو ${chat.title}`} onClick={()=>deleteChat(chat.id)}><Icon name="x"/></button></div>):<p className="history-empty">اولین جست‌وجوی شما اینجا می‌ماند.</p>}{historyError&&<p className="history-empty" role="status">مرورگر نتوانست تاریخچه را ذخیره کند.</p>}</div><div className="side-spacer"/><div className="sidebar-note"><Icon name="layer"/><div><strong>جست‌وجوی زنده</strong><p>نتایج بر اساس منابع در دسترس نمایش داده می‌شوند.</p></div></div><nav className="sidebar-social" aria-label="پیوندها و تنظیم نمایش">
  {socialLinks.map(link=><a key={link.label} href={link.href} target="_blank" rel="noopener noreferrer" aria-label={link.label} title={link.label}><SocialIcon name={link.icon}/></a>)}
  <button type="button" onClick={()=>setTheme(theme==='light'?'dark':'light')} aria-label={theme==='light'?'فعال کردن حالت تیره':'فعال کردن حالت روشن'} title={theme==='light'?'حالت تیره':'حالت روشن'}><Icon name={theme==='light'?'moon':'sun'}/></button>
 </nav></aside>
 <main className="main-panel"><header className="topbar"><div className="mobile-header"><Link href="/" className="mobile-head-logo" aria-label="SpielJobs"><SpielMark animated/></Link><button className="mobile-search-label" onClick={()=>composerInput.current?.focus()}><Icon name="search"/> جست‌وجو</button><Link className="mobile-mcp-link" href="/mcp">MCP</Link><button className="mobile-menu-button" aria-label="باز کردن منو" aria-controls="main-sidebar" aria-expanded={sidebarOpen} onClick={()=>setSidebarOpen(true)}><Icon name="sidebar"/></button></div><div className="top-title"><span className="mobile-brand"><SpielMark animated/></span><strong>دستیار جست‌وجوی شغل</strong><span className="top-divider"/><span className="top-description">فرصت مناسب، نزدیک‌تر از همیشه</span></div><div className="top-actions"><Link className="top-mcp-link" href="/mcp">MCP <Icon name="link-external"/></Link><span className="prototype-badge"><span/> نسخه آزمایشی</span><button className="mobile-theme" aria-label="تغییر حالت نمایش" onClick={()=>setTheme(theme==='light'?'dark':'light')}><Icon name={theme==='light'?'moon':'sun'}/></button></div></header>
 <div className="chat-scroll"><div className="conversation">{messages.length===0?<section className="welcome" aria-busy={!historyReady}><div className="welcome-icon"><SpielMark animated/></div><div className="welcome-kicker"><span/> دستیار شغلی شما</div><h1>شغل بعدی‌ات را<br/><span>از اینجا پیدا کن.</span></h1><p>عنوان شغل، مهارت یا شهر را بنویس. فرصت‌های منابع در دسترس را یک‌جا ببین؛ برای بررسی یا درخواست، مستقیم به منبع برو.</p><div className="suggestion-label">برای شروع امتحان کنید</div><div className="suggestions">{examples.map(s=><button key={s} disabled={!api||!historyReady||uploading} onClick={()=>submit(s)}><Icon name="search"/><span>{s}</span><Icon name="arrow-back"/></button>)}</div></section>:<div className="messages">{restored&&<div className="saved-result-notice"><span>{needsResume?'برای تکرار این جست‌وجو، رزومه‌ات را دوباره اضافه کن.':'نتایج ذخیره‌شده‌اند؛ وضعیت فرصت‌ها ممکن است تغییر کرده باشد.'}</span><button disabled={!api||loading||uploading||needsResume} onClick={()=>submit(lastSearch?.text||'')}>جست‌وجوی دوباره</button></div>}{messages.map(m=>m.role==='user'?<div className="user-message" key={m.id}><div className="user-bubble"><p dir="auto">{m.text}</p>{m.filename&&<span className="attachment-inline"><Icon name="file"/>{m.filename}</span>}</div><div className="user-avatar"><Icon name="user"/></div></div>:<div className="assistant-message" key={m.id}><div className="assistant-avatar"><SpielMark animated={loading&&last?.id===m.id}/></div><div className="assistant-body"><div className="assistant-name">دستیار SpielJobs <span>· جست‌وجوی زنده</span></div><Activity steps={m.steps||[]} active={loading&&last?.id===m.id} failed={!!m.error||!!m.stopped} sources={m.result?.sources}/>{m.error&&<div className="message-error"><Icon name="error-circle"/>{m.error}</div>}{m.stopped&&<div className="message-error">جست‌وجو متوقف شد.</div>}{m.result&&<SearchReply result={m.result} expanded={!!m.expanded} onMore={()=>update(m.id,x=>({...x,expanded:true}))}/>}</div></div>)}</div>}<div ref={bottom}/></div></div>
 <div className="composer-wrap"><div className="composer-inner">{!api&&<div className="composer-error" role="status">جست‌وجوی شغل فعلاً در دسترس نیست. کمی بعد دوباره امتحان کنید.</div>}{error&&<div className="composer-error" role="alert">{error}</div>}<div className="composer"><textarea ref={composerInput} value={query} onChange={e=>setQuery(e.target.value)} onKeyDown={e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();submit()}}} rows={2} maxLength={2000} placeholder="شغل، مهارت یا شهر؛ مثلاً حسابدار در تهران" aria-label="عبارت جست‌وجو"/><div className="composer-bottom"><div className="composer-tools">{api&&<><input ref={input} type="file" accept="application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document" hidden onChange={e=>upload(e.target.files?.[0])}/><button className="attach-button" onClick={()=>input.current?.click()} disabled={!api||uploading} title="افزودن رزومه PDF یا DOCX"><Icon name={uploading?'loader-alt':'paperclip'}/><span>{uploading?'در حال خواندن...':'افزودن رزومه'}</span></button></>}{filename&&<span className="attached-file"><Icon name="file"/><span dir="ltr">{filename}</span><button aria-label="حذف رزومه" onClick={()=>{setResume('');setFilename('')}}><Icon name="x"/></button></span>}</div>{loading?<Button type="button" onClick={()=>abort.current?.abort()} className="send-button stop-button" title="توقف"><Icon name="stop"/></Button>:<Button type="button" onClick={()=>submit()} disabled={!api||!historyReady||uploading||(!query.trim()&&!resume)} className="send-button" title="ارسال"><Icon name="up-arrow-alt"/></Button>}</div></div><div className="composer-foot"><span>Enter برای ارسال <b>·</b> Shift + Enter برای خط جدید</span>{api&&<span>رزومهٔ اختیاری: PDF یا DOCX تا ۲ مگابایت، برای خواندن به سرور ارسال می‌شود · <Link href="/privacy">نحوهٔ پردازش داده‌ها</Link></span>}</div></div></div></main></div>
}
