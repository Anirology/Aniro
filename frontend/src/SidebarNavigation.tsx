import {useLayoutEffect,useRef,useState} from 'react'
import {NavLink,useLocation} from 'react-router-dom'
import {CalendarBlank,ChartLine,Compass,Plus,Sparkle,Timer,Wallet} from '@phosphor-icons/react'

const pages=[
 {path:'/clarity',label:'Clarity',Icon:Compass},
 {path:'/plan',label:'Plan',Icon:CalendarBlank},
 {path:'/focus',label:'Study Flow',Icon:Timer},
 {path:'/reflect',label:'Reflect',Icon:ChartLine},
 {path:'/money',label:'Money',Icon:Wallet},
]

type Indicator={left:number;top:number;width:number;height:number;motion:boolean}

export default function SidebarNavigation({onAsk,onCapture}:{onAsk:()=>void;onCapture:()=>void}){
 const location=useLocation()
 const navRef=useRef<HTMLElement>(null)
 const hasPlaced=useRef(false)
 const [indicator,setIndicator]=useState<Indicator|null>(null)

 useLayoutEffect(()=>{
  const nav=navRef.current
  const active=nav?.querySelector<HTMLElement>('.navItem.selected')
  if(!nav||!active)return
  const measure=()=>{
   const navBounds=nav.getBoundingClientRect()
   const bounds=active.getBoundingClientRect()
   const next={left:bounds.left-navBounds.left+nav.scrollLeft,top:bounds.top-navBounds.top+nav.scrollTop,width:bounds.width,height:bounds.height,motion:hasPlaced.current}
   setIndicator(previous=>previous&&Object.keys(next).every(key=>previous[key as keyof Indicator]===next[key as keyof Indicator])?previous:next)
   hasPlaced.current=true
  }
  measure()
  const observer=new ResizeObserver(measure)
  observer.observe(nav)
  observer.observe(active)
  window.addEventListener('resize',measure)
  return()=>{observer.disconnect();window.removeEventListener('resize',measure)}
 },[location.pathname])

 return <nav ref={navRef} className="sidebarNav" aria-label="Main navigation">
  <button type="button" className="navCapture" onClick={onCapture}><Plus size={18}/> Capture</button>
  {indicator&&<span className={`navIndicator${indicator.motion?' motion':''}`} style={{left:indicator.left,top:indicator.top,width:indicator.width,height:indicator.height}} aria-hidden="true"/>}
  {pages.map(({path,label,Icon})=><NavLink key={path} to={path} aria-label={label} className={({isActive})=>`navItem ${isActive?'selected':''}`}><Icon size={21} weight="bold"/><span>{label}</span></NavLink>)}
  <button type="button" className="navItem ask" aria-label="Aniru" onClick={onAsk}><Sparkle size={21}/><span>Aniru</span></button>
 </nav>
}
