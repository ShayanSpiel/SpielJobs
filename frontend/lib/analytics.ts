import posthog from 'posthog-js'

export function track(event:string,properties:Record<string,string|number|boolean|null>={}){
  if(!process.env.NEXT_PUBLIC_POSTHOG_PROJECT_TOKEN || !process.env.NEXT_PUBLIC_POSTHOG_HOST)return
  try{posthog.capture(event,{app:'spieljobs',...properties})}catch{/* Analytics must not interrupt the user's task. */}
}

export function analyticsHeaders():Record<string,string>{
  if(!process.env.NEXT_PUBLIC_POSTHOG_PROJECT_TOKEN || !process.env.NEXT_PUBLIC_POSTHOG_HOST)return {}
  try{return {'X-POSTHOG-DISTINCT-ID':posthog.get_distinct_id(),'X-POSTHOG-SESSION-ID':posthog.get_session_id()}}catch{return {}}
}
