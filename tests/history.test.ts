import { test } from 'node:test'
import { strict as assert } from 'node:assert'
import { historySnapshot, readHistory, writeHistory, HISTORY_KEY } from '../frontend/lib/history.ts'
import type { Conversation } from '../frontend/lib/history.ts'

const sample = (): Conversation => ({ id:'chat', title:'مدیر محصول', updatedAt:new Date().toISOString(), messages:[
  {id:'user',role:'user',text:'مدیر محصول',filename:'private-resume.pdf'},
  {id:'answer',role:'assistant',result:{jobs:[],sources:[],warnings:[],model_used:null,resume:'PRIVATE'} as never},
] })

test('history survives serialization while excluding resume contents and filenames', () => {
  const json=JSON.stringify(historySnapshot([sample()]))
  assert.ok(!json.includes('private-resume'))
  assert.ok(!json.includes('PRIVATE'))
  assert.equal(readHistory(json)[0].messages[0].text,'مدیر محصول')
})
test('expired and corrupt histories are discarded', () => {
  const chat=sample();chat.updatedAt='2020-01-01T00:00:00Z'
  assert.deepEqual(historySnapshot([chat]),[])
  assert.deepEqual(readHistory('{bad'),[])
  assert.deepEqual(readHistory('[{"id":"bad"}]'),[])
})
test('empty history is saved without displaying a false storage error', () => {
  const memory=new Map<string,string>()
  assert.equal(writeHistory({setItem:(key,value)=>{memory.set(key,value)}},[]),true)
  assert.equal(memory.get(HISTORY_KEY),'[]')
})
test('quota failures are explicit and do not throw into the chat UI', () => {
  assert.equal(writeHistory({setItem:()=>{throw Error('quota')}},[sample()]),false)
})
test('interrupted searches restore as stopped and do not look like active work', () => {
  const chat=sample();chat.messages=[{id:'pending',role:'assistant',steps:[{phase:'search'}]}]
  assert.equal(historySnapshot([chat])[0].messages[0].stopped,true)
})
