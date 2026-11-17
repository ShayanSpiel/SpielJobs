'use client'
import { useEffect, useRef } from 'react'
import art from '@/lib/mascot.json'

type Spec = { d:string; transform:string; stroke:number; opacity?:number }
type Point = { x:number; y:number }
type Geometry = { points:Point[]; stroke:number; opacity:number }
type Optical = { scale:number; x:number; y:number }
const N=96, NS='http://www.w3.org/2000/svg'
const logo:Spec[]=[art.mark.xLeft,art.mark.dot,art.mark.line,art.mark.xRight].map(d=>({d,transform:'translate(20 20) scale(5)',stroke:.65}))
const empty:Spec={d:'M80 111L80.01 111L80 111.01Z',transform:'',stroke:.001,opacity:0}
const happy:Spec[]=[...art.happy.map(({d,transform,stroke})=>({d,transform,stroke})),empty]

/** Morphing geometry and optical alignment adapted from the AI Transformation guide's tutor.js. */
export function SpielMark({animated=false}:{animated?:boolean}) {
  const svg=useRef<SVGSVGElement>(null)
  useEffect(()=>{
    const root=svg.current
    if(!root||!animated)return
    const artGroup=root.querySelector<SVGGElement>('[data-face-art]')!
    const features=Array.from(root.querySelectorAll<SVGPathElement>('[data-face-feature]'))
    const cache=new Map<string,Geometry>()
    let geometry:Geometry[]=[],optical:Optical={scale:1,x:0,y:0},frame=0,timer:ReturnType<typeof setTimeout>,disposed=false
    const media=window.matchMedia('(prefers-reduced-motion: reduce)')
    function sample(spec:Spec):Geometry{
      const key=spec.d+'|'+spec.transform
      const existing=cache.get(key);if(existing)return existing
      const probe=document.createElementNS(NS,'path');probe.setAttribute('d',spec.d);if(spec.transform)probe.setAttribute('transform',spec.transform);probe.style.visibility='hidden';root!.append(probe)
      const length=probe.getTotalLength(),matrix=probe.transform.baseVal.consolidate()?.matrix
      const points=Array.from({length:N},(_,i)=>{const p=probe.getPointAtLength(length*i/N);return matrix?{x:matrix.a*p.x+matrix.c*p.y+matrix.e,y:matrix.b*p.x+matrix.d*p.y+matrix.f}:{x:p.x,y:p.y}})
      const scale=matrix?Math.sqrt(Math.abs(matrix.a*matrix.d-matrix.b*matrix.c)):1
      probe.remove();const result={points,stroke:spec.stroke*scale,opacity:spec.opacity??1};cache.set(key,result);return result
    }
    function align(source:Point[],target:Point[]){let best=Infinity,result=target;for(const direction of [1,-1])for(let shift=0;shift<N;shift++){let score=0;for(let i=0;i<N;i+=8){const p=target[(shift+direction*i+N*2)%N];score+=(source[i].x-p.x)**2+(source[i].y-p.y)**2}if(score<best){best=score;result=Array.from({length:N},(_,i)=>target[(shift+direction*i+N*2)%N])}}return result}
    function normalize(target:Spec[]):Optical{if(target!==logo)return{scale:.88,x:9.6,y:17.6};const pts=target.filter(s=>s.opacity!==0).flatMap(s=>sample(s).points),xs=pts.map(p=>p.x),ys=pts.map(p=>p.y),left=Math.min(...xs),right=Math.max(...xs),top=Math.min(...ys),bottom=Math.max(...ys),scale=84/Math.max(right-left,bottom-top);return{scale,x:80-(left+right)/2*scale,y:80-(top+bottom)/2*scale}}
    function pose(value:Optical){optical=value;artGroup.setAttribute('transform',`translate(${value.x} ${value.y}) scale(${value.scale})`)}
    function exact(target:Spec[]){features.forEach((el,i)=>{const spec=target[i]||empty;el.setAttribute('d',spec.d);el.setAttribute('transform',spec.transform);el.setAttribute('stroke-width',String(spec.stroke));el.style.opacity=String(spec.opacity??1)});geometry=target.map(sample);pose(normalize(target));root!.style.visibility='visible'}
    function morph(target:Spec[],duration=720){
      cancelAnimationFrame(frame);if(media.matches||document.hidden){exact(target);return}
      const from=geometry,fromOptical={...optical},toOptical=normalize(target),to=target.map(sample).map((g,i)=>({...g,points:align(from[i].points,g.points)})),start=performance.now()
      features.forEach(el=>el.removeAttribute('transform'))
      const tick=(now:number)=>{if(disposed)return;const raw=Math.min(1,(now-start)/duration),ease=(1-Math.exp(-7*raw)*(1+7*raw))/(1-Math.exp(-7)*8)
        geometry=to.map((g,i)=>({points:g.points.map((p,j)=>({x:from[i].points[j].x+(p.x-from[i].points[j].x)*ease,y:from[i].points[j].y+(p.y-from[i].points[j].y)*ease})),stroke:from[i].stroke+(g.stroke-from[i].stroke)*ease,opacity:from[i].opacity+(g.opacity-from[i].opacity)*ease}))
        features.forEach((el,i)=>{el.setAttribute('d','M'+geometry[i].points.map(p=>p.x.toFixed(2)+' '+p.y.toFixed(2)).join('L')+'Z');el.setAttribute('stroke-width',String(geometry[i].stroke));el.style.opacity=String(geometry[i].opacity)})
        pose({scale:fromOptical.scale+(toOptical.scale-fromOptical.scale)*ease,x:fromOptical.x+(toOptical.x-fromOptical.x)*ease,y:fromOptical.y+(toOptical.y-fromOptical.y)*ease})
        if(raw<1)frame=requestAnimationFrame(tick);else exact(target)
      };frame=requestAnimationFrame(tick)
    }
    exact(logo)
    const cycle=()=>{if(disposed)return;morph(happy);timer=setTimeout(()=>{morph(logo);timer=setTimeout(cycle,7500)},4000)}
    if(animated&&!media.matches)timer=setTimeout(cycle,2500)
    return()=>{disposed=true;clearTimeout(timer);cancelAnimationFrame(frame)}
  },[animated])
  if(!animated)return <svg viewBox="0 0 24 24" className="spiel-face" aria-hidden="true" focusable="false"><path d={Object.values(art.mark).join(' ')} fill="currentColor" stroke="currentColor" strokeWidth={.65} strokeLinejoin="miter"/></svg>
  return <svg ref={svg} viewBox="18 22 124 124" className="spiel-face" aria-hidden="true" focusable="false" style={{visibility:'hidden'}}><g data-face-art>{logo.map((spec,i)=><path key={i} data-face-feature={i} d={spec.d} transform={spec.transform} fill="currentColor" stroke="currentColor" strokeWidth={spec.stroke} strokeLinejoin="miter"/>)}</g></svg>
}
