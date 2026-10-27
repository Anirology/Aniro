import {Link} from 'react-router-dom'

type Record={id:string;task_title:string|null;recorded_minutes:number|null;status:string|null;note:string;next_action:string;learning_checked:boolean;difficulty:boolean;ended_at:string}

export default function FocusResults({records}:{records:Record[]}){
 if(!records.length)return null
 return <section className="stageCard sectionCard focusResults"><div className="sectionHeader"><div><h2>Work attempts</h2><p>Recorded focus, task completion, and checked learning are separate.</p></div><Link className="subtle" to="/focus">Open Study Flow</Link></div><div className="focusResultsList">{records.map(row=><article key={row.id}><div><strong>{row.task_title||'Unlinked session'}</strong><small>{new Date(row.ended_at).toLocaleString()} · {row.recorded_minutes===null?'Unrecorded':`${row.recorded_minutes} min recorded`} · {row.status==='done'?'Task done':row.status==='partial'?'Partly done':row.status==='working'?'Still working':'No task status'}{row.learning_checked?' · Learning checked':''}</small>{row.note&&<p>{row.note}</p>}{row.next_action&&<p>Next: {row.next_action}</p>}</div></article>)}</div></section>
}
