/** Offline release checks never export traces or make model calls. */
import { spawnSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import path from 'node:path'
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const python = process.env.SPIELJOBS_PYTHON || path.join(root, '.venv', 'bin', 'python')
const env = { ...process.env, SPIELJOBS_TRACING_ENABLED: 'false', SPIELJOBS_REQUESTS_PER_MINUTE: '10000', PYTHONPATH: path.join(root, 'backend') }
// Offline fixtures must not inherit paid provider or Redis credentials.
for (const key of ['MISTRAL_API_KEY','GEMINI_API_KEY','LANGFUSE_PUBLIC_KEY','LANGFUSE_SECRET_KEY','UPSTASH_REDIS_REST_URL','UPSTASH_REDIS_REST_TOKEN','POSTHOG_PROJECT_TOKEN','POSTHOG_HOST']) env[key] = ''
const commands = [
  [python, ['-m', 'unittest', 'discover', '-s', 'tests', '-q']],
  [process.execPath, ['--test', 'tests/job-display.test.ts', 'tests/source-logos.test.ts', 'tests/search-client.test.ts', 'tests/history.test.ts']],
  [process.execPath, ['frontend/node_modules/typescript/bin/tsc', '--noEmit', '-p', 'frontend/tsconfig.json']],
]
for (const [command, args] of commands) {
  const result = spawnSync(command, args, { cwd: root, env, stdio: 'inherit' })
  if (result.error || result.status !== 0) process.exit(result.status || 1)
}
