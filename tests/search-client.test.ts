import { test } from 'node:test'
import { strict as assert } from 'node:assert'
import { readSearchEvents } from '../frontend/lib/search-client.ts'

function streamChunks(text: string) {
  const bytes = new TextEncoder().encode(text)
  return new ReadableStream<Uint8Array>({
    start(controller) {
      // Split within multibyte Persian characters and frame delimiters.
      for (let i = 0; i < bytes.length; i += 3) controller.enqueue(bytes.slice(i, i + 3))
      controller.close()
    },
  })
}

test('decodes Persian streaming events across arbitrary network boundaries', async () => {
  const body = streamChunks('event: status\r\ndata: {"phase":"prepare"}\r\n\r\nevent: result\ndata: {"title":"مدیر محصول"}\n\n')
  const events = await Array.fromAsync(readSearchEvents(body))
  assert.deepEqual(events, [{ type: 'status', data: { phase: 'prepare' } }, { type: 'result', data: { title: 'مدیر محصول' } }])
  assert.equal(body.locked, false)
})

test('parses a final complete frame without a trailing newline', async () => {
  const events = await Array.fromAsync(readSearchEvents(streamChunks('event: result\ndata: {"jobs":[]}')))
  assert.equal(events[0].type, 'result')
})

test('rejects malformed payload and releases the reader', async () => {
  const body = streamChunks('event: result\ndata: [1,2]\n\n')
  await assert.rejects(async () => Array.fromAsync(readSearchEvents(body)))
  assert.equal(body.locked, false)
})

test('cancels the upstream reader when the consumer stops', async () => {
  let cancelled = false
  const body = new ReadableStream<Uint8Array>({
    start(controller) { controller.enqueue(new TextEncoder().encode('event: status\ndata: {"phase":"prepare"}\n\n')) },
    cancel() { cancelled = true },
  })
  for await (const event of readSearchEvents(body)) { assert.equal(event.type, 'status'); break }
  assert.equal(cancelled, true)
})
