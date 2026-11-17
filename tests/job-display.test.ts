import { test } from 'node:test'
import { strict as assert } from 'node:assert'
import { postedDateLabel, jobStatus } from '../frontend/lib/job-display.ts'

test('uses Iran time and Saturday-start weeks for source publication dates', () => {
  const now = new Date('2026-11-16T12:00:00Z')
  assert.equal(postedDateLabel('2026-11-16', now), 'امروز')
  assert.equal(postedDateLabel('2026-11-14', now), 'همین هفته')
  assert.equal(postedDateLabel('2026-11-12', now), 'این ماه')
  assert.notEqual(postedDateLabel('2026-09-01', now), 'این ماه')
  assert.equal(postedDateLabel('2026-11-17', new Date('2026-11-16T21:00:00Z')), 'امروز')
})

test('does not claim unsupported active status or invent dates', () => {
  assert.equal(jobStatus('unknown').label, 'وضعیت نامشخص')
  assert.equal(jobStatus('listed').label, 'در فهرست منبع')
  assert.notEqual(jobStatus('listed').tone, 'active')
  assert.equal(jobStatus('open').label, 'فعال')
  assert.equal(jobStatus('closed').label, 'بسته')
  assert.equal(postedDateLabel(null), 'تاریخ نامشخص')
  assert.equal(postedDateLabel('2026-02-30'), 'تاریخ نامشخص')
})

test('all numeric salary facts use Persian digits without inventing currency', async () => {
  const { salaryLabel, persianFact } = await import('../frontend/lib/job-display.ts')
  assert.equal(salaryLabel('30 تا ۴۰ میلیون تومان'), '۳۰ تا ۴۰ میلیون تومان')
  assert.equal(salaryLabel('٣٠ تا ٤٠'), '۳۰ تا ۴۰')
  assert.equal(salaryLabel('300000000 IRR MONTH'), '۳۰۰۰۰۰۰۰۰ ریال ماهانه')
  assert.equal(salaryLabel(null), 'حقوق اعلام نشده')
  assert.equal(persianFact('5 سال'), '۵ سال')
})
