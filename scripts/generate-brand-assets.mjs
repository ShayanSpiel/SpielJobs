/** Derive exact brand assets from the canonical SVG; no generated logo geometry. */
import { createRequire } from 'node:module'
const sharp=createRequire(new URL('../frontend/package.json',import.meta.url))('sharp')
import { readFile, writeFile } from 'node:fs/promises'
const root=new URL('../frontend/public/',import.meta.url)
const svg=await readFile(new URL('favicon.svg',root))
for(const size of [16,32,180,192,512]) {
  const filename=size===180?'apple-touch-icon.png':`icon-${size}.png`
  await sharp(svg).resize(size,size).png().toFile(new URL(filename,root).pathname)
}
const png=await sharp(svg).resize(32,32).png().toBuffer()
const header=Buffer.alloc(22)
header.writeUInt16LE(1,2);header.writeUInt16LE(1,4);header[6]=32;header[7]=32;header.writeUInt16LE(1,10);header.writeUInt16LE(32,12);header.writeUInt32LE(png.length,14);header.writeUInt32LE(22,18)
await writeFile(new URL('favicon.ico',root),Buffer.concat([header,png]))
const mark=svg.toString().match(/<path d="([^"]+)"/)[1]
const og=`<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="630"><rect width="1200" height="630" fill="#0b1220"/><circle cx="1050" cy="90" r="290" fill="#172c49"/><g transform="translate(900 170) scale(9)"><path d="${mark}" fill="#60a5fa"/></g><text x="80" y="280" font-family="Arial,sans-serif" font-size="108" font-weight="700" fill="#f1f5f9">SpielJobs<tspan fill="#60a5fa">.</tspan></text><text x="84" y="355" font-family="Arial,sans-serif" font-size="32" fill="#aab3c7">One search. Traceable opportunities.</text><text x="84" y="540" font-family="Arial,sans-serif" font-size="25" fill="#aab3c7">Iran pilot · job.spielos.xyz · by SpielOS</text></svg>`
await sharp(Buffer.from(og)).png().toFile(new URL('og-image.png',root).pathname)
console.log('Generated favicon, app icons and social image from canonical SpielOS mark.')
