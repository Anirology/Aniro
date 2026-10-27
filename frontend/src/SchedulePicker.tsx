import {useEffect,useRef,useState} from 'react'
import {CalendarBlank,Clock} from '@phosphor-icons/react'
import './schedule-picker.css'

function shiftMinutes(value:string,minutes:number){
 const date=new Date(`${value}:00Z`)
 date.setUTCMinutes(date.getUTCMinutes()+minutes)
 return date.toISOString().slice(0,16)
}

function today(){
 const now=new Date()
 return `${now.getFullYear()}-${String(now.getMonth()+1).padStart(2,'0')}-${String(now.getDate()).padStart(2,'0')}`
}

function moveDay(value:string,days:number){
 const date=new Date(`${value}T12:00:00Z`)
 date.setUTCDate(date.getUTCDate()+days)
 return date.toISOString().slice(0,10)
}

function pretty(value:string,dateOnly:boolean){
 if(!value)return dateOnly?'Choose a date':'Choose date and time'
 const date=new Date(`${value.slice(0,10)}T12:00:00Z`)
 const day=new Intl.DateTimeFormat('en-US',{weekday:'short',month:'short',day:'numeric',timeZone:'UTC'}).format(date)
 if(dateOnly)return day
 const [hour,minute]=value.slice(11).split(':').map(Number)
 return `${day} · ${hour%12||12}:${String(minute).padStart(2,'0')} ${hour>=12?'PM':'AM'}`
}

export function ScheduleField({label,value,onChange,dateOnly=false,optional=false}:{label:string;value:string;onChange:(value:string)=>void;dateOnly?:boolean;optional?:boolean}){
 const [open,setOpen]=useState(false)
 const pickerRef=useRef<HTMLDivElement>(null)
 useEffect(()=>{if(open)window.requestAnimationFrame(()=>pickerRef.current?.scrollIntoView({block:'nearest',behavior:'smooth'}))},[open])
 const date=value.slice(0,10)||today()
 const time=value.slice(11,16)||'09:00'
 const setDate=(nextDate:string)=>onChange(dateOnly?nextDate:`${nextDate}T${time}`)
 const setTime=(nextTime:string)=>onChange(`${date}T${nextTime}`)
 const quickDates=[{label:'Today',value:today()},{label:'Tomorrow',value:moveDay(today(),1)}]
 const quickTimes=[{label:'9 AM',value:'09:00'},{label:'12 PM',value:'12:00'},{label:'3 PM',value:'15:00'},{label:'6 PM',value:'18:00'}]

 return <div className="scheduleField"><span className="scheduleLabel">{label}</span><div className="scheduleFieldActions"><button type="button" className={`scheduleTrigger ${open?'isOpen':''}`} aria-expanded={open} onClick={()=>setOpen(current=>!current)}><span className="scheduleTriggerIcon"><CalendarBlank size={17}/></span><span>{pretty(value,dateOnly)}</span>{!dateOnly&&<Clock size={15}/>}</button>{optional&&value&&<button type="button" className="scheduleClear" onClick={()=>{onChange('');setOpen(false)}}>Clear</button>}</div>{open&&<div className="schedulePicker" ref={pickerRef}><div className="scheduleQuickDates">{quickDates.map(option=><button type="button" key={option.label} className={date===option.value?'selected':''} onClick={()=>setDate(option.value)}>{option.label}</button>)}</div><div className={`scheduleInputs ${dateOnly?'dateOnly':''}`}><label><span>Date</span><input type="date" value={date} onChange={event=>setDate(event.target.value)}/></label>{!dateOnly&&<label><span>Time</span><input type="time" step="900" value={time} onChange={event=>setTime(event.target.value)}/></label>}</div>{!dateOnly&&<div className="scheduleQuickTimes"><span>Quick times</span><div>{quickTimes.map(option=><button type="button" key={option.value} className={time===option.value?'selected':''} onClick={()=>setTime(option.value)}>{option.label}</button>)}</div></div>}<div className="schedulePickerFoot"><span>{dateOnly?'Select the date above.':'Times use your Aniro time zone.'}</span><button type="button" onClick={()=>setOpen(false)}>Done</button></div></div>}</div>
}

export function ScheduleRange({start,end,onStart,onEnd}:{start:string;end:string;onStart:(value:string)=>void;onEnd:(value:string)=>void}){
 const setStart=(value:string)=>{
  const duration=start&&end?Math.max(15,Math.round((Date.parse(`${end}:00Z`)-Date.parse(`${start}:00Z`))/60000)):60
  onStart(value)
  onEnd(shiftMinutes(value,duration))
 }
 return <div className="scheduleRange"><ScheduleField label="Starts" value={start} onChange={setStart}/><ScheduleField label="Ends" value={end} onChange={onEnd}/><div className="scheduleDuration"><span>Quick length</span>{[30,45,60,90,120].map(minutes=><button type="button" key={minutes} className={start&&end&&Date.parse(`${end}:00Z`)-Date.parse(`${start}:00Z`)===minutes*60000?'selected':''} onClick={()=>onEnd(shiftMinutes(start,minutes))}>{minutes<60?`${minutes} min`:`${minutes/60} hr`}</button>)}</div></div>
}
