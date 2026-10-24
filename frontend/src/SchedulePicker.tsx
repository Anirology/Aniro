import {useEffect,useRef,useState} from 'react'
import {CalendarBlank,CaretLeft,CaretRight,Clock} from '@phosphor-icons/react'
import './schedule-picker.css'

function shiftMinutes(value:string,minutes:number){const date=new Date(`${value}:00Z`);date.setUTCMinutes(date.getUTCMinutes()+minutes);return date.toISOString().slice(0,16)}
function pretty(value:string,dateOnly:boolean){if(!value)return 'Choose a date';const date=new Date(`${value.slice(0,10)}T12:00:00Z`);const day=new Intl.DateTimeFormat('en-US',{weekday:'short',month:'short',day:'numeric',timeZone:'UTC'}).format(date);if(dateOnly)return day;const [hour,minute]=value.slice(11).split(':').map(Number);return `${day} · ${hour%12||12}:${String(minute).padStart(2,'0')} ${hour>=12?'PM':'AM'}`}

export function ScheduleField({label,value,onChange,dateOnly=false,optional=false}:{label:string;value:string;onChange:(value:string)=>void;dateOnly?:boolean;optional?:boolean}){
 const [open,setOpen]=useState(false)
 const pickerRef=useRef<HTMLDivElement>(null)
 useEffect(()=>{if(open)window.requestAnimationFrame(()=>pickerRef.current?.scrollIntoView({block:'nearest',behavior:'smooth'}))},[open])
 const base=value.slice(0,10)||new Date().toISOString().slice(0,10)
 const [month,setMonth]=useState(base.slice(0,7))
 const [year,monthNumber]=month.split('-').map(Number)
 const first=new Date(Date.UTC(year,monthNumber-1,1))
 const offset=(first.getUTCDay()+6)%7
 const days=new Date(Date.UTC(year,monthNumber,0)).getUTCDate()
 const hour=Number(value.slice(11,13)||'09'),minute=Number(value.slice(14,16)||'00')
 const chooseDay=(day:string)=>{onChange(dateOnly?day:`${day}T${String(hour).padStart(2,'0')}:${String(minute).padStart(2,'0')}`)}
 const chooseTime=(nextHour:number,nextMinute:number)=>onChange(`${base}T${String(nextHour).padStart(2,'0')}:${String(nextMinute).padStart(2,'0')}`)
 const changeMonth=(delta:number)=>{const next=new Date(Date.UTC(year,monthNumber-1+delta,1));setMonth(next.toISOString().slice(0,7))}
 return <div className="scheduleField"><span className="scheduleLabel">{label}</span><div className="scheduleFieldActions"><button type="button" className={`scheduleTrigger ${open?'isOpen':''}`} aria-expanded={open} onClick={()=>setOpen(!open)}><CalendarBlank size={17}/><span>{pretty(value,dateOnly)}</span><Clock size={15}/></button>{optional&&value&&<button type="button" className="scheduleClear" onClick={()=>{onChange('');setOpen(false)}}>Clear</button>}</div>{open&&<div className="schedulePicker" ref={pickerRef}><div className="scheduleMonth"><button type="button" aria-label="Previous month" onClick={()=>changeMonth(-1)}><CaretLeft/></button><strong>{new Intl.DateTimeFormat('en-US',{month:'long',year:'numeric',timeZone:'UTC'}).format(first)}</strong><button type="button" aria-label="Next month" onClick={()=>changeMonth(1)}><CaretRight/></button></div><div className="scheduleDays">{['M','T','W','T','F','S','S'].map((name,index)=><span key={index}>{name}</span>)}{Array.from({length:offset},(_,index)=><span key={`gap-${index}`}/>)}{Array.from({length:days},(_,index)=>{const day=`${month}-${String(index+1).padStart(2,'0')}`;return <button key={day} type="button" className={day===value.slice(0,10)?'selected':''} aria-label={day} aria-pressed={day===value.slice(0,10)} onClick={()=>chooseDay(day)}>{index+1}</button>})}</div>{!dateOnly&&<div className="scheduleClock"><span>TIME</span><div className="scheduleHour">{Array.from({length:12},(_,index)=>index+1).map(number=><button key={number} type="button" className={(hour%12||12)===number?'selected':''} onClick={()=>chooseTime(number%12+(hour>=12?12:0),minute)}>{number}</button>)}</div><div className="scheduleMinute">{[0,15,30,45,...(![0,15,30,45].includes(minute)?[minute]:[])].sort((a,b)=>a-b).map(number=><button key={number} type="button" className={minute===number?'selected':''} onClick={()=>chooseTime(hour,number)}>{String(number).padStart(2,'0')}</button>)}<button type="button" className={hour<12?'selected':''} onClick={()=>chooseTime(hour%12,minute)}>AM</button><button type="button" className={hour>=12?'selected':''} onClick={()=>chooseTime(hour%12+12,minute)}>PM</button></div></div>}<div className="schedulePickerFoot"><button type="button" onClick={()=>{chooseDay(new Date().toISOString().slice(0,10));setMonth(new Date().toISOString().slice(0,7))}}>Today</button><button type="button" onClick={()=>setOpen(false)}>Done</button></div></div>}</div>
}

export function ScheduleRange({start,end,onStart,onEnd}:{start:string;end:string;onStart:(value:string)=>void;onEnd:(value:string)=>void}){
 const setStart=(value:string)=>{const duration=start&&end?Math.max(15,Math.round((Date.parse(`${end}:00Z`)-Date.parse(`${start}:00Z`))/60000)):60;onStart(value);onEnd(shiftMinutes(value,duration))}
 return <div className="scheduleRange"><ScheduleField label="Starts" value={start} onChange={setStart}/><ScheduleField label="Ends" value={end} onChange={onEnd}/><div className="scheduleDuration"><span>QUICK LENGTH</span>{[30,45,60,90,120].map(minutes=><button type="button" key={minutes} className={start&&end&&Date.parse(`${end}:00Z`)-Date.parse(`${start}:00Z`)===minutes*60000?'selected':''} onClick={()=>onEnd(shiftMinutes(start,minutes))}>{minutes<60?`${minutes} min`:`${minutes/60} hr`}</button>)}</div><small className="scheduleTimezone">Choose a day, then set the hour and minutes. Times use your Aniro time zone.</small></div>
}
