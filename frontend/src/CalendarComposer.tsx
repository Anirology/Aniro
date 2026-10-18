import {useState} from 'react'
import {CalendarBlank,Check,Trash,X} from '@phosphor-icons/react'
import type {GoogleEvent} from './GooglePanel'

export type CalendarSlot={start:string;end:string}
type GoalOption={id:string;title:string;breadcrumb:string;module_id:string|null;archived_at:string|null}
type TaskOption={id:string;title:string;archived_at:string|null}
type ModuleOption={id:string;name:string;track_id:string;archived_at:string|null}
type TrackOption={id:string;name:string;archived_at:string|null}
type Props={slot:CalendarSlot;event?:GoogleEvent;week:string;timezone:string;connected:boolean;colors:Record<string,{background:string;foreground:string}>;goals:GoalOption[];tasks:TaskOption[];modules:ModuleOption[];tracks:TrackOption[];onClose:()=>void;onSaved:()=>Promise<void>}

function parts(value:string,timezone:string){const values=new Intl.DateTimeFormat('en-CA',{timeZone:timezone,year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hourCycle:'h23'}).formatToParts(new Date(value));const get=(key:string)=>values.find(part=>part.type===key)?.value||'00';return `${get('year')}-${get('month')}-${get('day')}T${get('hour')}:${get('minute')}`}
function zonedIso(value:string,timezone:string){const wall=Date.parse(`${value}:00Z`);if(!Number.isFinite(wall))throw new Error('Choose a valid date and time');let guess=wall;for(let index=0;index<3;index++){const shown=parts(new Date(guess).toISOString(),timezone);guess+=wall-Date.parse(`${shown}:00Z`)}return new Date(guess).toISOString()}
function addDays(value:string,days:number){const date=new Date(`${value}T00:00:00Z`);date.setUTCDate(date.getUTCDate()+days);return date.toISOString().slice(0,10)}
async function request(path:string,method:string,body?:unknown){const response=await fetch('/api'+path,{method,headers:{'Content-Type':'application/json'},body:body===undefined?undefined:JSON.stringify(body)});if(!response.ok){const payload=await response.json().catch(()=>({detail:'Request failed'}));throw new Error(payload.detail||'Request failed')}return response.json()}

export default function CalendarComposer({slot,event,week,timezone,connected,colors,goals,tasks,modules,tracks,onClose,onSaved}:Props){
 const [mode,setMode]=useState<'event'|'task'>(connected?'event':'task')
 const [start,setStart]=useState(event&&!event.all_day?parts(event.start,timezone):slot.start)
 const [end,setEnd]=useState(event&&!event.all_day?parts(event.end,timezone):slot.end)
 const [title,setTitle]=useState(event?.title||'')
 const [description,setDescription]=useState(event?.description||'')
 const [location,setLocation]=useState(event?.location||'')
 const [allDay,setAllDay]=useState(Boolean(event?.all_day))
 const [startDate,setStartDate]=useState(event?.all_day?event.start:slot.start.slice(0,10))
 const [endDate,setEndDate]=useState(event?.all_day?addDays(event.end,-1):slot.start.slice(0,10))
 const [colorId,setColorId]=useState(event?.color_id||'')
 const [taskId,setTaskId]=useState('new')
 const [goalId,setGoalId]=useState('')
 const [moduleId,setModuleId]=useState('')
 const [sync,setSync]=useState(connected)
 const [error,setError]=useState('')
 const [busy,setBusy]=useState(false)
 const [createdTaskId,setCreatedTaskId]=useState('')
 const [createdBlockId,setCreatedBlockId]=useState('')
 const [requestId]=useState(()=>crypto.randomUUID().replaceAll('-',''))
 const activeGoals=goals.filter(goal=>!goal.archived_at)
 const activeTasks=tasks.filter(task=>!task.archived_at)
 const activeModules=modules.filter(module=>!module.archived_at&&tracks.some(track=>track.id===module.track_id&&!track.archived_at))
 async function save(e:React.FormEvent){e.preventDefault();setBusy(true);setError('');let savedBlock=createdBlockId;try{
  const startIso=mode==='task'||!allDay?zonedIso(start,timezone):'',endIso=mode==='task'||!allDay?zonedIso(end,timezone):''
  if(mode==='task'||!allDay){if(new Date(endIso)<=new Date(startIso))throw new Error('End time must follow start time')}
  else if(endDate<startDate)throw new Error('End date must not precede start date')
  if(mode==='event'||event){
   const body={title:title.trim(),all_day:allDay,...(allDay?{start_date:startDate,end_date:addDays(endDate,1)}:{start:startIso,end:endIso}),description,location,color_id:colorId,request_id:requestId}
   await request(`/integrations/google/events${event?`/${encodeURIComponent(event.id)}`:''}`,event?'PUT':'POST',body)
  }else{
   let currentTask=taskId==='new'?createdTaskId:taskId
   let currentBlock=createdBlockId
   if(!currentTask){const goal=activeGoals.find(item=>item.id===goalId);const result=await request('/task-blocks','POST',{title:title.trim(),goal_id:goalId||null,module_id:goal?.module_id||moduleId||null,week_start:week,start_at:startIso,end_at:endIso});currentTask=result.task.id;currentBlock=result.block.id;savedBlock=currentBlock;setCreatedTaskId(currentTask);setCreatedBlockId(currentBlock)}
   if(!currentBlock){const result=await request('/calendar-blocks','POST',{task_id:currentTask,start_at:startIso,end_at:endIso});currentBlock=result.id;savedBlock=currentBlock;setCreatedBlockId(currentBlock)}
   if(sync&&connected)await request(`/integrations/google/blocks/${currentBlock}/sync`,'POST',{confirm:true})
  }
  await onSaved();onClose()
 }catch(caught){await onSaved();setError(`${(caught as Error).message}${savedBlock?' The local block is saved; retry sync here or edit it in Weekly Goals.':''}`)}finally{setBusy(false)}}
 async function remove(){if(!event||!confirm(`Delete “${event.title}” from Google Calendar?`))return;setBusy(true);setError('');try{await request(`/integrations/google/events/${encodeURIComponent(event.id)}?confirm=true`,'DELETE');await onSaved();onClose()}catch(caught){setError((caught as Error).message)}finally{setBusy(false)}}
 return <div className="backdrop" role="presentation" onMouseDown={e=>{if(e.target===e.currentTarget)onClose()}}><form className="dialog calendarComposer" role="dialog" aria-modal="true" aria-label={event?'Edit Google event':'Add calendar item'} onSubmit={e=>void save(e)}><div className="dialogHead"><div><small>CALENDAR</small><h2>{event?'Edit event':'Add to calendar'}</h2></div><button type="button" aria-label="Close" onClick={onClose}><X/></button></div><div className="fields">
  {!event&&<div className="calendarMode" role="group" aria-label="Calendar item type"><button type="button" className={mode==='event'?'selected':''} disabled={!connected} onClick={()=>setMode('event')}>Google event</button><button type="button" className={mode==='task'?'selected':''} onClick={()=>setMode('task')}>Aniro task</button></div>}
  {(mode==='event'||event)?<><label>Event title<input autoFocus required maxLength={240} value={title} onChange={e=>setTitle(e.target.value)}/></label><label>Location (optional)<input maxLength={500} value={location} onChange={e=>setLocation(e.target.value)}/></label><label>Description (optional)<textarea rows={3} maxLength={2000} value={description} onChange={e=>setDescription(e.target.value)}/></label><label className="calendarCheck"><input type="checkbox" checked={allDay} onChange={e=>setAllDay(e.target.checked)}/> All day</label>{Object.keys(colors).length>0&&<div className="calendarColorField"><span>Event color</span><div className="calendarColors"><button type="button" className={!colorId?'selected':''} aria-label="Default color" title="Default color" onClick={()=>setColorId('')} style={{background:'#c2d7f8'}}>✓</button>{Object.entries(colors).map(([id,color])=><button type="button" key={id} className={colorId===id?'selected':''} aria-label={`Color ${id}`} title={`Color ${id}`} onClick={()=>setColorId(id)} style={{background:color.background,color:color.foreground}}>{colorId===id?'✓':''}</button>)}</div></div>}</>:<><label>Task<select value={taskId} disabled={Boolean(createdTaskId)} onChange={e=>setTaskId(e.target.value)}><option value="new">Create a new task</option>{activeTasks.map(task=><option key={task.id} value={task.id}>{task.title}</option>)}</select></label>{taskId==='new'&&<><label>Task title<input autoFocus required maxLength={240} value={title} onChange={e=>setTitle(e.target.value)} placeholder="What will you do?"/></label><label>Weekly goal / group<select value={goalId} onChange={e=>{setGoalId(e.target.value);setModuleId('')}}><option value="">Standalone commitment</option>{activeGoals.map(goal=><option key={goal.id} value={goal.id}>{goal.breadcrumb} → {goal.title}</option>)}</select></label>{!goalId&&<label>Module (optional)<select value={moduleId} onChange={e=>setModuleId(e.target.value)}><option value="">No module</option>{activeModules.map(module=><option key={module.id} value={module.id}>{tracks.find(track=>track.id===module.track_id)?.name} → {module.name}</option>)}</select></label>}</>}{connected&&<label className="calendarCheck"><input type="checkbox" checked={sync} onChange={e=>setSync(e.target.checked)}/> Add this task block to Google Calendar</label>}</>}
  {allDay&&(mode==='event'||event)?<div className="calendarTimeFields"><label>Start date<input required type="date" value={startDate} onChange={e=>setStartDate(e.target.value)}/></label><label>End date<input required type="date" min={startDate} value={endDate} onChange={e=>setEndDate(e.target.value)}/></label></div>:<div className="calendarTimeFields"><label>Starts<input required type="datetime-local" value={start} onChange={e=>setStart(e.target.value)}/></label><label>Ends<input required type="datetime-local" value={end} onChange={e=>setEnd(e.target.value)}/></label></div>}
  {error&&<p className="formError" role="alert">{error}</p>}
 </div><div className="dialogFoot">{event&&<button className="subtle calendarDelete" type="button" disabled={busy} onClick={()=>void remove()}><Trash size={16}/> Delete</button>}<button type="button" className="subtle" onClick={onClose}>Cancel</button><button className="primary" disabled={busy}><Check size={17}/>{busy?'Saving…':event?'Save changes':mode==='event'?'Create in Google':'Create task and block'}</button></div><p className="calendarComposerHint"><CalendarBlank size={15}/> Dragging is not required; change the start and end fields at any time.</p></form></div>
}
