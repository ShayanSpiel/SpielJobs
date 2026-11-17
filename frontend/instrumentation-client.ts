import posthog from 'posthog-js'

const token=process.env.NEXT_PUBLIC_POSTHOG_PROJECT_TOKEN
const host=process.env.NEXT_PUBLIC_POSTHOG_HOST
if(token && host){
  posthog.init(token,{
    api_host:'/events',
    ui_host:process.env.NEXT_PUBLIC_POSTHOG_UI_HOST,
    defaults:'2026-08-30',
    autocapture:false,
    capture_pageview:false,
    capture_pageleave:false,
    disable_session_recording:true,
    person_profiles:'identified_only',
    respect_dnt:true,
    // Never send search text, resume text, DOM contents or URL query strings.
    before_send:event=>event ? {...event,properties:{...event.properties,$current_url:location.origin+location.pathname,$referrer:undefined}} : null,
  })
}else if(process.env.NODE_ENV==='development'){
  console.error('NEXT_PUBLIC_POSTHOG_PROJECT_TOKEN / NEXT_PUBLIC_POSTHOG_HOST variable required by PostHog is missing or un-configured, this causes events to be silently missed. This error stops appearing once configured')
}
