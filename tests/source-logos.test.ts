import { test } from 'node:test'
import { strict as assert } from 'node:assert'
import { existsSync } from 'node:fs'
import { sourceForJob, sourceLogoCandidates } from '../frontend/lib/source-logos.ts'

test('legacy Jobinja responses resolve to a bundled image', () => {
  const source=sourceForJob('Jobinja', [{ name:'Jobinja' }], 'https://jobinja.ir/companies/example/jobs/123')
  assert.equal(source.site_url,'https://jobinja.ir')
  assert.equal(sourceLogoCandidates(source)[0],'/logos/jobinja.png')
  assert.ok(existsSync('frontend/public/logos/jobinja.png'))
})
test('adapter identifiers match names case insensitively', () => {
  const source=sourceForJob('jobinja', [{id:'jobinja',name:'Jobinja',label:'جابینجا',site_url:'https://jobinja.ir'}], 'https://jobinja.ir/jobs/1')
  assert.equal(source.label,'جابینجا')
})
test('unknown source artwork is not assigned to Jobinja', () => {
  assert.deepEqual(sourceLogoCandidates({name:'Example'}),[])
  assert.ok(!sourceLogoCandidates({name:'Example'}).includes('/logos/jobinja.png'))
})
