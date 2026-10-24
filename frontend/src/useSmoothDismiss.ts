import {useEffect,useRef,useState} from 'react'

export default function useSmoothDismiss(onClose:()=>void){
 const [closing,setClosing]=useState(false)
 const timer=useRef<number|undefined>(undefined)
 useEffect(()=>()=>window.clearTimeout(timer.current),[])
 const dismiss=()=>{if(closing)return;setClosing(true);timer.current=window.setTimeout(onClose,190)}
 return {closing,dismiss}
}
