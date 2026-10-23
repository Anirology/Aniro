import {useState} from 'react'
import {ArrowRight,CalendarBlank,Check,Clock,Plus} from '@phosphor-icons/react'
import type {Goal,Task,Block} from './Plan'
import './today.css'

type Vision={id:string;title:string}
type Props={
 date:string;week:string;timezone:string;goals:Goal[];visions:Vision[];tasks:Task[];blocks:Block[];
 onRecord:(block:Block,status:'done'|'partial'|'missed')=>void;
 onQuickRecord:(block:Block,status:'done'|'missed')=>Promise<void>;
 onBatchReview:(items:{block_id:string;status:'done'|'missed'}[])=>Promise<void>;
 onRecordTask:(task:Task)=>void;onMove:(block:Block)=>void;onMoveTomorrow:(block:Block)=>Promise<void>;onAddTask:()=>void;
 onOpenGoals:()=>void;onGoToday:()=>void
}
const dayOf=(iso:string,tz:string)=>new Intl.DateTimeFormat('en-CA',{timeZone:tz,year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date(iso))
const timeOf=(iso:string,tz:string)=>new Intl.DateTimeFormat('en-US',{timeZone:tz,hour:'numeric',minute:'2-digit'}).format(new Date(iso))
const prettyDay=(date:string)=>new Intl.DateTimeFormat('en-US',{timeZone:'UTC',weekday:'long',month:'long',day:'numeric'}).format(new Date(date+'T00:00:00Z'))

export default function TodayPanel({date,week,timezone,goals,visions,tasks,blocks,onRecord,onQuickRecord,onBatchReview,onRecordTask,onMove,onMoveTomorrow,onAddTask,onOpenGoals,onGoToday}:Props){
 const [review,setReview]=useState<Record<string,'done'|'missed'|'keep'>>({})
 const [busy,setBusy]=useState(false)
 const inWeek=date>=week&&date<new Date(Date.parse(week+'T00:00:00Z')+7*86400000).toISOString().slice(0,10)
 if(!inWeek)return <section className="todayPanel todayAway"><div><span className="todayEyebrow">RESUME</span><h2>Plan for {prettyDay(date)}</h2><p>Return to this week to pick up your next step.</p></div><button className="primary" onClick={onGoToday}>Go to today <ArrowRight size={17}/></button></section>
 const active=blocks.filter(b=>!b.archived_at&&dayOf(b.start_at,timezone)===date).sort((a,b)=>a.start_at.localeCompare(b.start_at))
 const unfinished=active.filter(b=>b.status==='planned'||b.status==='partial')
 const past=blocks.filter(b=>!b.archived_at&&dayOf(b.start_at,timezone)<date&&(b.status==='planned'||b.status==='partial')).sort((a,b)=>b.start_at.localeCompare(a.start_at))
 const taskFor=(b:Block)=>tasks.find(t=>t.id===b.task_id)
 const goalFor=(t?:Task)=>goals.find(g=>g.id===t?.goal_id)
 const next=unfinished.find(b=>Date.parse(b.end_at)>Date.now())||unfinished[0]||past[0]
 const nextTask=next&&taskFor(next),nextGoal=goalFor(nextTask)
 const nextVision=visions.find(v=>v.id===nextGoal?.parent_vision_id)
 const unblocked=tasks.filter(t=>!t.archived_at&&t.status!=='done'&&t.status!=='moved'&&!blocks.some(b=>!b.archived_at&&b.task_id===t.id))
 const reviewable=[...past,...unfinished]
 const selected=Object.entries(review).filter(([,status])=>status!=='keep').map(([block_id,status])=>({block_id,status:status as 'done'|'missed'}))
 async function saveReview(){if(!selected.length)return;setBusy(true);try{await onBatchReview(selected);setReview({})}finally{setBusy(false)}}
 async function quick(status:'done'|'missed'){if(!next)return;setBusy(true);try{await onQuickRecord(next,status)}finally{setBusy(false)}}
 async function tomorrow(){if(!next)return;setBusy(true);try{await onMoveTomorrow(next)}finally{setBusy(false)}}
 return <section className="todayPanel" aria-label="Resume your work">
  <div className="todayIntro"><div><span className="todayEyebrow">RESUME</span><h2>{prettyDay(date)}</h2><p>{next?'One useful step is enough to restart.':'Choose one small step to begin.'}</p></div><button className="todayTextButton" onClick={onOpenGoals}>Weekly goals <ArrowRight size={16}/></button></div>
  <div className="todayGrid">
   <div className="todayFocus"><span className="todayEyebrow">{next?'PICK UP HERE':'READY WHEN YOU ARE'}</span>
    {next&&nextTask?<><div className="todayFocusHead"><span className={`todayDot tone-${nextGoal?.color_key||'lime'}`}/><h3>{nextTask.title}</h3></div><p className="todayTime"><Clock size={15}/>{prettyDay(dayOf(next.start_at,timezone))} · {timeOf(next.start_at,timezone)} – {timeOf(next.end_at,timezone)}</p><p className="todayPath">{nextGoal?.title||'Standalone task'}</p>{nextVision&&<p className="todayVision">Working toward: {nextVision.title}</p>}<div className="todayActions"><button className="primary" disabled={busy} onClick={()=>void quick('done')}><Check size={16}/> Done</button><button className="subtle" onClick={()=>onRecord(next,'partial')}>Partly done</button>{nextTask&&next.sync_state!=="imported"&&new Date(Date.parse(date+"T00:00:00Z")+86400000).toISOString().slice(0,10)<new Date(Date.parse(nextTask.week_start+"T00:00:00Z")+7*86400000).toISOString().slice(0,10)&&<button className="subtle" disabled={busy} onClick={()=>void tomorrow()}>Tomorrow</button>}<button className="todayTextButton" onClick={()=>onMove(next)}>Choose time</button><button className="todayTextButton" disabled={busy} onClick={()=>void quick('missed')}>Skip</button></div></>:unblocked[0]?<><h3>{unblocked[0].title}</h3><p className="todayPath">Already on your list. Record progress or schedule it when ready.</p><button className="primary" onClick={()=>onRecordTask(unblocked[0])}>Check in <ArrowRight size={16}/></button></>:<><h3>Choose a small step for today.</h3><p className="todayPath">Capture a thought in one line. Add detail later if it helps.</p><button className="primary" onClick={onAddTask}><Plus size={16}/> Add a task</button></>}
   </div>
   <div className="todaySide"><div className="todaySideHead"><CalendarBlank size={17}/><strong>Today</strong><span>{active.length}</span></div>{active.length===0?<p className="todayEmpty">Nothing scheduled today.</p>:active.map(b=>{const t=taskFor(b),g=goalFor(t);return <div className="todayBlock" key={b.id}><span className="todayBlockTime">{timeOf(b.start_at,timezone)}</span><span className={`todayDot tone-${g?.color_key||'lime'}`}/><strong>{t?.title||'Task'}</strong><button onClick={()=>onRecord(b,b.status==='done'?'done':'partial')}>{b.status==='done'?'Done':'Check in'}</button></div>})}{unblocked.length>0&&<div className="todayUnblocked"><small>ALSO ON YOUR LIST</small>{unblocked.slice(0,3).map(t=><button key={t.id} onClick={()=>onRecordTask(t)}>{t.title}<ArrowRight size={14}/></button>)}</div>}</div>
  </div>
  {reviewable.length>0&&<details className="todayResume"><summary>Review unfinished blocks ({reviewable.length})</summary><p>Optional. Mark several at once, or leave them for later.</p>{reviewable.map(b=><div key={b.id}><span>{taskFor(b)?.title||'Task'} · {prettyDay(dayOf(b.start_at,timezone))}</span><select aria-label={`Review ${taskFor(b)?.title||'task'}`} value={review[b.id]||'keep'} onChange={e=>setReview({...review,[b.id]:e.target.value as 'done'|'missed'|'keep'})}><option value="keep">Keep</option><option value="done">Done</option><option value="missed">Skip</option></select><button onClick={()=>onMove(b)}>Move</button></div>)}<button className="primary" disabled={!selected.length||busy} onClick={()=>void saveReview()}>Save {selected.length} reviewed</button></details>}
 </section>
}
