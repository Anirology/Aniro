import {useState} from 'react'
import {Barbell,BookOpen,Briefcase,Camera,Check,Code,Coins,Globe,GraduationCap,Heart,House,Leaf,Lightbulb,MusicNotes,Palette,PenNib,Star,Target,Trophy,UsersThree,YoutubeLogo} from '@phosphor-icons/react'
import './pickers.css'

export const iconMap:Record<string,typeof Target> = {
  target:Target, education:GraduationCap, career:Briefcase, relationships:Heart,
  health:Barbell, money:Coins, code:Code, design:PenNib, youtube:YoutubeLogo,
  people:UsersThree, home:House, book:BookOpen, idea:Lightbulb, music:MusicNotes,
  camera:Camera, globe:Globe, nature:Leaf, trophy:Trophy, star:Star, art:Palette,
}

const colorOptions = [
  {key:'lime',label:'Lime',hex:'#C6FB4A'},
  {key:'bit',label:'Blue',hex:'#5C9DF7'},
  {key:'design',label:'Purple',hex:'#A77CF7'},
  {key:'youtube',label:'Red',hex:'#F36362'},
  {key:'health',label:'Orange',hex:'#F6A652'},
  {key:'relationships',label:'Pink',hex:'#EE85B5'},
  {key:'clubs',label:'Teal',hex:'#5FC9B4'},
]

export function ColorPicker({value,onChange}:{value:string;onChange:(value:string)=>void}){
  return <fieldset className="pickerField"><legend>Color</legend><div className="colorGrid" role="group" aria-label="Choose a color">{colorOptions.map(color=><button key={color.key} type="button" className={`colorChoice ${value===color.key?'isSelected':''}`} aria-label={`${color.label} color`} aria-pressed={value===color.key} onClick={()=>onChange(color.key)}><span className="colorSwatch" style={{backgroundColor:color.hex}}>{value===color.key&&<Check size={16} weight="bold"/>}</span><span>{color.label}</span></button>)}</div></fieldset>
}

export function IconPicker({value,onChange}:{value:string;onChange:(value:string)=>void}){
  const [open,setOpen]=useState(false)
  const Current=iconMap[value]||Target
  return <div className="pickerField"><span className="pickerLabel">Icon</span><button type="button" className="iconPickerTrigger" aria-label={`Choose icon. Current: ${value}`} aria-expanded={open} onClick={()=>setOpen(!open)}><Current size={24} weight="duotone"/><span>{value}</span><span aria-hidden="true">{open?'▴':'▾'}</span></button>{open&&<div className="iconGrid" role="group" aria-label="Choose an icon">{Object.entries(iconMap).map(([key,Icon])=><button key={key} type="button" title={key} aria-label={`${key} icon`} aria-pressed={value===key} className={`iconChoice ${value===key?'isSelected':''}`} onClick={()=>{onChange(key);setOpen(false)}}><Icon size={24} weight="duotone"/></button>)}</div>}</div>
}
