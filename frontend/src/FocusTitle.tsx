import {useEffect,useState} from 'react'

type TimerState={phase:string;running:boolean;ends_at:string|null;ended_at:string|null}

export default function FocusTitle(){
 const [session,setSession]=useState<TimerState|null>(null)
 const [now,setNow]=useState(Date.now())
 useEffect(()=>{let mounted=true;const load=()=>{void fetch('/api/focus').then(r=>r.ok?r.json():null).then(value=>{if(mounted)setSession(value?.session||null)}).catch(()=>{})};load();const interval=window.setInterval(load,10000);const tick=window.setInterval(()=>setNow(Date.now()),1000);const visible=()=>{if(!document.hidden)load()};document.addEventListener('visibilitychange',visible);const channel=new BroadcastChannel('aniro-focus');channel.onmessage=load;return()=>{mounted=false;window.clearInterval(interval);window.clearInterval(tick);document.removeEventListener('visibilitychange',visible);channel.close();document.title='Aniro'}},[])
 useEffect(()=>{if(!session||session.ended_at||['summary','return','unrecorded'].includes(session.phase)){document.title='Aniro';return}if(!session.running){document.title='Paused · Aniro';return}if(session.phase==='untimed'){document.title='Focus | Aniro';return}if(!session.ends_at){document.title='Aniro';return}const remaining=Math.max(0,Math.ceil((Date.parse(session.ends_at)-now)/1000));const clock=`${String(Math.floor(remaining/60)).padStart(2,'0')}:${String(remaining%60).padStart(2,'0')}`;document.title=`${clock} · ${['focus','starter'].includes(session.phase)?'Focus':'Break'} | Aniro`},[session,now])
 return null
}
