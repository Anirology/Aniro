import {useState} from 'react'
import {Check,X} from '@phosphor-icons/react'
import './today.css'

type Preview={records:number;exported_at:string|null;tables:Record<string,number>}

export default function RestoreBackup({onClose}:{onClose:()=>void}){
  const [payload,setPayload]=useState<Record<string,unknown>|null>(null)
  const [preview,setPreview]=useState<Preview|null>(null)
  const [acknowledged,setAcknowledged]=useState(false)
  const [busy,setBusy]=useState(false)
  const [error,setError]=useState('')
  const [restored,setRestored]=useState<{restored:number;snapshot:string;local_snapshot:string}|null>(null)

  async function choose(file?:File){
    setError('');setPayload(null);setPreview(null);setAcknowledged(false)
    if(!file)return
    if(file.size>10_000_000){setError('Choose a backup smaller than 10 MB.');return}
    setBusy(true)
    try{
      const parsed=JSON.parse(await file.text()) as Record<string,unknown>
      const response=await fetch('/api/import/preview',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(parsed)})
      const result=await response.json()
      if(!response.ok)throw new Error(result.detail||'This backup could not be read.')
      setPayload(parsed);setPreview(result)
    }catch(e){setError(e instanceof SyntaxError?'The file is not valid JSON.':(e as Error).message)}finally{setBusy(false)}
  }

  async function restore(){
    if(!payload||!acknowledged||busy)return
    setBusy(true);setError('')
    try{
      const response=await fetch('/api/import/restore?confirm=true',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)})
      const result=await response.json()
      if(!response.ok)throw new Error(result.detail||'Restore failed.')
      setRestored(result)
    }catch(e){setError((e as Error).message)}finally{setBusy(false)}
  }

  return <div className="backdrop" role="presentation" onMouseDown={event=>{if(event.target===event.currentTarget&&!busy)onClose()}}><div className="dialog restoreDialog" role="dialog" aria-modal="true" aria-label="Restore Aniro backup"><div className="dialogHead"><div><small>RECOVERY</small><h2>Restore a JSON backup</h2></div><button type="button" onClick={onClose} aria-label="Close" disabled={busy}><X/></button></div>{restored?<><p role="status">Restored {restored.restored} records. A snapshot of the previous records was saved:</p><code>{restored.snapshot}</code><p>Google Calendar needs reconnection after a restore.</p><button className="primary" onClick={()=>window.location.reload()}>Reload Aniro</button></>:<><p className="dialogHelp">Choose a JSON file exported by Aniro. Review its contents before replacing records. Aniro saves a snapshot before applying the restore.</p><label className="restoreFile">Backup file<input type="file" accept="application/json,.json" onChange={event=>void choose(event.target.files?.[0])} disabled={busy}/></label>{preview&&<div className="restorePreview"><strong>{preview.records} records found</strong><span>Exported {preview.exported_at?new Date(preview.exported_at).toLocaleString():'at an unknown time'}</span><small>{Object.entries(preview.tables).filter(([,count])=>count>0).map(([name,count])=>`${name.replaceAll('_',' ')}: ${count}`).join(' · ')||'No personal records'}</small></div>}{preview&&<label className="restoreConfirm"><input type="checkbox" checked={acknowledged} onChange={event=>setAcknowledged(event.target.checked)}/> Replace my current Aniro records with this backup. I understand Google Calendar will need reconnecting.</label>}{error&&<p className="formError" role="alert">{error}</p>}<div className="dialogFoot"><button className="subtle" onClick={onClose} disabled={busy}>Cancel</button><button className="primary" disabled={!payload||!acknowledged||busy} onClick={()=>void restore()}><Check size={17}/>{busy?'Working…':'Restore backup'}</button></div></>}</div></div>
}
