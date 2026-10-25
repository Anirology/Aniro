import {useLocation} from 'react-router-dom'
import {sidebarQuotes} from './sidebarQuotes'
import './sidebar-footer.css'

export default function SidebarFooter(){
 const {pathname}=useLocation()
 const item=sidebarQuotes[pathname as keyof typeof sidebarQuotes]||sidebarQuotes['/plan']
 const {Icon}=item
 return <div className="sideFooter quoteFooter"><Icon size={23} weight="regular" aria-hidden="true"/><p>“{item.quote}”</p>{item.source?<a href={item.source} target="_blank" rel="noopener noreferrer" aria-label={`Source: ${item.author}`}>— {item.author}</a>:<span>{item.author}</span>}</div>
}
