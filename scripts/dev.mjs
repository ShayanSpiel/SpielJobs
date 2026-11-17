import { spawn, spawnSync } from 'node:child_process'
import { createHash } from 'node:crypto'
import { existsSync, readdirSync, readFileSync, writeFileSync } from 'node:fs'
import http from 'node:http'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const frontend = path.join(root, 'frontend')
const requirements = path.join(root, 'backend', 'requirements.txt')
const venv = path.join(root, '.venv')
const python = path.join(venv, process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python')
const marker = path.join(venv, '.spieljobs-requirements')
const next = path.join(frontend, 'node_modules', 'next', 'dist', 'bin', 'next')
const backendSources = path.join(root, 'backend', 'spieljobs')
const revision = 'iran-mvp-' + createHash('sha256').update(Buffer.concat([...readdirSync(backendSources).filter(name=>name.endsWith('.py') || name.endsWith('.json')).sort().map(name=>readFileSync(path.join(backendSources,name))),readFileSync(requirements)])).digest('hex').slice(0,12)
let backend, web, stopping = false

function command(executable, args, options = {}) {
  const result = spawnSync(executable, args, {cwd:root, stdio:'inherit', ...options})
  if (result.error || result.status !== 0) throw new Error(`${executable} failed${result.error ? `: ${result.error.message}` : ` (exit ${result.status})`}`)
}

async function probe(port, endpoint) {
  return new Promise(resolve => {
    const req=http.get(`http://127.0.0.1:${port}${endpoint}`, {timeout:port===3000 ? 10000 : 1500}, response => {
      let body=''
      response.on('data',chunk => { body+=chunk; if(body.length>4096) req.destroy() })
      response.on('end',()=>{ try {resolve({reachable:true,data:JSON.parse(body)})} catch {resolve({reachable:true,data:null})} })
    })
    req.on('error',error=>resolve({reachable:false,error:error.code}))
    req.on('timeout',()=>req.destroy())
  })
}
const health=()=>probe(8000,'/health')

async function waitForBackend() {
  for (let attempt=0;attempt<80;attempt++) {
    if (backend?.exitCode !== null) throw new Error('The backend exited during startup.')
    const result=await health()
    if(result.data?.runtime_revision===revision) return
    await new Promise(resolve=>setTimeout(resolve,250))
  }
  throw new Error('The backend did not become ready on port 8000.')
}

function stopOldBackend() {
  const pids=spawnSync('lsof',['-nP','-tiTCP:8000','-sTCP:LISTEN'],{encoding:'utf8'}).stdout?.trim().split(/\s+/).filter(Boolean) || []
  if (!pids.length) throw new Error('Port 8000 is occupied and its process could not be identified.')
  for (const pid of pids) {
    const cmd=spawnSync('ps',['-p',pid,'-o','command='],{encoding:'utf8'}).stdout || ''
    if (!cmd.includes('uvicorn') || !cmd.includes('spieljobs.server:app')) throw new Error(`Port 8000 belongs to another process (${pid}); it was left running.`)
  }
  for (const pid of pids) process.kill(Number(pid),'SIGTERM')
}

function shutdown(code=0) {
  if(stopping) return
  stopping=true
  if(web && web.exitCode===null) web.kill('SIGTERM')
  if(backend && backend.exitCode===null) backend.kill('SIGTERM')
  process.exitCode=code
}

async function main() {
  const [existing, existingWeb]=await Promise.all([health(),probe(3000,'/api/health')])
  if(!existing.reachable && existing.error && existing.error!=='ECONNREFUSED') throw new Error(`Cannot access the local backend port: ${existing.error}`)
  if(!existingWeb.reachable && existingWeb.error && existingWeb.error!=='ECONNREFUSED') throw new Error(`Cannot access the local frontend port: ${existingWeb.error}`)
  if(existingWeb.reachable && existingWeb.data?.app!=='spieljobs') throw new Error('Port 3000 is used by another service; it was left running.')
  if (existing.reachable && !String(existing.data?.runtime_revision || '').startsWith('iran-mvp-') && !['2026-11-16-search-v2','unified-dev-v1','unified-dev-v2','unified-dev-v3','unified-dev-v4','unified-dev-v5',revision].includes(existing.data?.runtime_revision)) {
    throw new Error('Port 8000 is used by another service; it was left running.')
  }
  if (!existsSync(next)) {
    console.log('Installing frontend dependencies…')
    command('npm',['install'],{cwd:frontend})
  }
  if (existing.data?.runtime_revision !== revision) {
    if (!existsSync(python)) {
      console.log('Creating the SpielJobs Python environment…')
      command(process.platform === 'win32' ? 'python' : 'python3',['-m','venv',venv])
    }
    const hash=createHash('sha256').update(readFileSync(requirements)).digest('hex')
    if (!existsSync(marker) || readFileSync(marker,'utf8') !== hash) {
      console.log('Installing backend dependencies…')
      command(python,['-m','pip','install','-r',requirements])
      writeFileSync(marker,hash)
    }
    if(existing.reachable) {
      console.log('Replacing the previous SpielJobs backend…')
      stopOldBackend()
      for(let i=0;i<30;i++) { if(!(await health()).reachable) break; await new Promise(resolve=>setTimeout(resolve,200)) }
    }
    backend=spawn(python,['-m','uvicorn','spieljobs.server:app','--host','127.0.0.1','--port','8000'],{
      cwd:root, stdio:'inherit', env:{...process.env,PYTHONPATH:path.join(root,'backend')}
    })
    backend.on('error',error=>{console.error('Backend:',error.message);shutdown(1)})
    backend.on('exit',code=>{if(!stopping){console.error('Backend stopped.');shutdown(code || 1)}})
    await waitForBackend()
  } else console.log('Using the running SpielJobs backend.')
  // Recheck after replacing a worker: its parent launcher may also stop
  // the frontend it owned when that old backend exits.
  const currentWeb=await probe(3000,'/api/health')
  if(currentWeb.reachable && currentWeb.data?.app!=='spieljobs') throw new Error('Port 3000 is used by another service; it was left running.')
  if(currentWeb.reachable) {
    console.log('Using the running SpielJobs frontend at http://localhost:3000')
    // Keep this launcher alive even if both services were already running.
    const timer=setInterval(()=>{},60_000)
    for(const signal of ['SIGINT','SIGTERM']) process.once(signal,()=>clearInterval(timer))
  } else {
    web=spawn(process.execPath,[next,'dev','-p','3000'],{cwd:frontend,stdio:'inherit',env:process.env})
    web.on('error',error=>{console.error('Frontend:',error.message);shutdown(1)})
    web.on('exit',code=>{if(!stopping) shutdown(code || 1)})
  }
}

for(const signal of ['SIGINT','SIGTERM']) process.on(signal,()=>shutdown())
main().catch(error=>{console.error(`SpielJobs: ${error.message}`);shutdown(1)})
