import type {GoogleEvent} from './GooglePanel'
import type {CalendarSlot} from './CalendarComposer'

type Color={background:string;foreground:string}
export type GoogleColors=Record<string,Color>
type Placed={event:GoogleEvent;start:number;end:number;column:number;columns:number}
const hourHeight=42
const visibleHours=8
function addDays(value:string,days:number){const date=new Date(`${value}T00:00:00Z`);date.setUTCDate(date.getUTCDate()+days);return date.toISOString().slice(0,10)}
function localParts(value:string,timezone:string){const parts=new Intl.DateTimeFormat('en-US',{timeZone:timezone,year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hourCycle:'h23'}).formatToParts(new Date(value));const get=(key:string)=>parts.find(part=>part.type===key)?.value||'00';return {date:`${get('year')}-${get('month')}-${get('day')}`,minute:Number(get('hour'))*60+Number(get('minute'))}}
function label(value:string,timezone:string){return new Intl.DateTimeFormat('en-US',{timeZone:timezone,hour:'numeric',minute:'2-digit'}).format(new Date(value))}
function place(events:GoogleEvent[],date:string,timezone:string):Placed[]{
 const sorted=events.filter(event=>!event.all_day&&event.start&&event.end).map(event=>({event,first:localParts(event.start,timezone),last:localParts(event.end,timezone)})).filter(({first,last})=>first.date<=date&&last.date>=date&&!(last.date===date&&last.minute===0)).map(({event,first,last})=>{const start=first.date===date?first.minute:0;return {event,start,end:last.date===date?Math.max(start+1,last.minute):1440}}).sort((a,b)=>a.start-b.start||a.end-b.end)
 const groups:typeof sorted[]=[]
 for(const item of sorted){const group=groups.at(-1);if(group&&item.start<Math.max(...group.map(entry=>entry.end)))group.push(item);else groups.push([item])}
 return groups.flatMap(group=>{const columnEnds:number[]=[];const placed=group.map(item=>{let column=columnEnds.findIndex(end=>end<=item.start);if(column<0){column=columnEnds.length;columnEnds.push(item.end)}else columnEnds[column]=item.end;return {...item,column}});return placed.map(item=>({...item,columns:columnEnds.length}))})
}

export default function GoogleWeekView({week,timezone,events,colors,rangeStart,compact=false,onSlot,onEvent}:{week:string;timezone:string;events:GoogleEvent[];colors:GoogleColors;rangeStart:number;compact?:boolean;onSlot:(slot:CalendarSlot)=>void;onEvent:(event:GoogleEvent)=>void}){
 const days=Array.from({length:7},(_,index)=>addDays(week,index))
 const now=localParts(new Date().toISOString(),timezone)
 function chooseSlot(day:string,y:number){const minute=Math.max(rangeStart*60,Math.min((rangeStart+visibleHours)*60-30,rangeStart*60+Math.floor(y/(hourHeight/2))*30));const time=(amount:number)=>`${amount>=1440?addDays(day,1):day}T${String(Math.floor((amount%1440)/60)).padStart(2,'0')}:${String(amount%60).padStart(2,'0')}`;onSlot({start:time(minute),end:time(minute+30)})}
 if(compact)return <div className="googleWeekView"><div className="googleWeekScroll googleWeekCompactScroll"><div className="googleWeekCompact">
  {days.map(day=>{const allDay=events.filter(event=>event.all_day&&event.start<=day&&day<event.end);const timed=place(events,day,timezone);return <section className={`googleWeekCompactDay${day===now.date?' isToday':''}`} key={day} aria-label={new Intl.DateTimeFormat('en-US',{weekday:'long',month:'long',day:'numeric',timeZone:'UTC'}).format(new Date(`${day}T00:00:00Z`))}>
   <div className="googleWeekCompactHead"><span>{new Intl.DateTimeFormat('en-US',{weekday:'short',timeZone:'UTC'}).format(new Date(`${day}T00:00:00Z`))}</span><strong>{Number(day.slice(-2))}</strong></div>
   <div className="googleWeekCompactItems">{allDay.map(event=>{const color=colors[event.color_id||''];return <button type="button" className="googleWeekCompactEvent" key={event.id} onClick={()=>onEvent(event)} style={{background:color?.background||'#e9f2ff',color:color?.foreground||'#18345c'}}><small>All day</small><strong>{event.title}</strong></button>})}{timed.map(({event,start})=>{const color=colors[event.color_id||''];return <button type="button" className="googleWeekCompactEvent" key={`${event.id}-${start}`} onClick={()=>onEvent(event)} style={{background:color?.background||'#e9f2ff',color:color?.foreground||'#18345c'}}><small>{start===0&&localParts(event.start,timezone).date<day?'Continues':label(event.start,timezone)}</small><strong>{event.title}</strong></button>})}{allDay.length===0&&timed.length===0&&<span className="googleWeekCompactEmpty">No items</span>}</div>
  </section>})}
 </div></div></div>
 return <div className="googleWeekView"><div className="googleWeekScroll"><div className="googleWeekBoard">
  <div className="googleWeekCorner">{timezone.split('/').at(-1)?.replaceAll('_',' ')}</div>
  {days.map(day=><div className={`googleWeekDayHead${day===now.date?' isToday':''}`} key={`head-${day}`}><span>{new Intl.DateTimeFormat('en-US',{weekday:'short',timeZone:'UTC'}).format(new Date(`${day}T00:00:00Z`))}</span><strong>{Number(day.slice(-2))}</strong></div>)}
  <div className="googleWeekAllDayLabel">All day</div>
  {days.map(day=><div className="googleWeekAllDay" key={`all-${day}`}>{events.filter(event=>event.all_day&&event.start<=day&&day<event.end).map(event=>{const color=colors[event.color_id||''];return <button type="button" key={event.id} onClick={()=>onEvent(event)} title={event.title} style={{background:color?.background||'#c2d7f8',color:color?.foreground||'#18345c'}}>{event.title}</button>})}</div>)}
  <div className="googleWeekHours">{Array.from({length:visibleHours},(_,index)=>{const hour=rangeStart+index;return <div key={hour}>{new Intl.DateTimeFormat('en-US',{hour:'numeric',timeZone:'UTC'}).format(new Date(Date.UTC(2026,0,1,hour)))}</div>})}</div>
  {days.map(day=><div className={`googleWeekColumn${day===now.date?' isToday':''}`} key={`column-${day}`} role="button" tabIndex={0} aria-label={`Add event on ${day} between ${rangeStart}:00 and ${rangeStart+visibleHours}:00`} onClick={e=>chooseSlot(day,e.clientY-e.currentTarget.getBoundingClientRect().top)} onKeyDown={e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();chooseSlot(day,2*hourHeight)}}}>{place(events,day,timezone).filter(({start,end})=>end>rangeStart*60&&start<(rangeStart+visibleHours)*60).map(({event,start,end,column,columns})=>{const color=colors[event.color_id||''];const visibleStart=Math.max(start,rangeStart*60),visibleEnd=Math.min(end,(rangeStart+visibleHours)*60);return <button type="button" key={event.id} className={`googleWeekEvent${visibleEnd-visibleStart<=45?' isCompact':''}`} onClick={e=>{e.stopPropagation();onEvent(event)}} title={`${event.title} · ${label(event.start,timezone)}`} aria-label={`${event.title}, ${label(event.start,timezone)}`} style={{top:`${(visibleStart-rangeStart*60)*hourHeight/60}px`,height:`${(visibleEnd-visibleStart)*hourHeight/60}px`,left:`${column*100/columns}%`,width:`${100/columns}%`,background:color?.background||'#c2d7f8',color:color?.foreground||'#18345c'}}><small>{label(event.start,timezone)}</small><strong>{event.title}</strong></button>})}</div>)}
 </div></div></div>
}
