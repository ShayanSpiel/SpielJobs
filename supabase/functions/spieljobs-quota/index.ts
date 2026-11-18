import { createRemoteJWKSet, jwtVerify } from 'npm:jose@6.1.3'

const owner = 'shayans-projects-a724807f'
const ownerId = 'team_V7TTUJ4DRCPtU6sMwXcJVWWO'
const issuer = 'https://oidc.vercel.com/' + owner
const audience = 'https://vercel.com/' + owner
const subject = 'owner:' + owner + ':project:spieljobs-search:environment:production'
const keys = createRemoteJWKSet(new URL(issuer + '/.well-known/jwks'), {timeoutDuration: 1800})
const databaseUrl = Deno.env.get('SUPABASE_URL')
const databaseKey = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')

const json = (data: unknown, status = 200) =>
  Response.json(data, {status, headers:{'Cache-Control':'no-store'}})

Deno.serve(async request => {
  if (request.method !== 'POST') return json({error:'Method not allowed'}, 405)
  const token = request.headers.get('authorization')?.match(/^Bearer (\S+)$/i)?.[1]
  if (!token) return json({error:'Unauthorized'}, 401)
  try {
    const {payload} = await jwtVerify(token, keys, {
      issuer, audience, subject, algorithms:['RS256'], requiredClaims:['exp','iat','owner_id'],
    })
    if (payload.owner_id !== ownerId) return json({error:'Unauthorized'}, 401)
  } catch {
    return json({error:'Unauthorized'}, 401)
  }
  const clientHash = request.headers.get('x-spieljobs-client-hash')
  if (!clientHash || !/^[a-f0-9]{32}$/.test(clientHash)) return json({error:'Invalid client hash'}, 400)
  if (!databaseUrl || !databaseKey) return json({error:'Quota unavailable'}, 503)
  try {
    const response = await fetch(databaseUrl + '/rest/v1/rpc/spieljobs_take_search_slot', {
      method:'POST',
      headers:{apikey:databaseKey, Authorization:'Bearer ' + databaseKey, 'Content-Type':'application/json'},
      body:JSON.stringify({client_hash:clientHash}),
      signal:AbortSignal.timeout(1800),
    })
    if (response.ok) {
      const admitted = await response.json()
      if (typeof admitted === 'boolean') return json(admitted)
    }
  } catch {
    // Fail closed when the shared quota cannot be checked.
  }
  return json({error:'Quota unavailable'}, 503)
})
