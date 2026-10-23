export type TimedCalendarItem={start:string;end:string;all_day:boolean;busy?:boolean}

export function calendarBookedMinutes(items:TimedCalendarItem[],weekStart:number,weekEnd:number){
 const intervals=items.filter(item=>!item.all_day&&item.busy!==false).map(item=>[Math.max(weekStart,new Date(item.start).getTime()),Math.min(weekEnd,new Date(item.end).getTime())]).filter(([start,end])=>Number.isFinite(start)&&Number.isFinite(end)&&end>start).sort((a,b)=>a[0]-b[0])
 let booked=0,start=0,end=0
 for(const [nextStart,nextEnd] of intervals){if(nextStart>end){booked+=Math.max(0,end-start);start=nextStart;end=nextEnd}else end=Math.max(end,nextEnd)}
 return Math.round((booked+Math.max(0,end-start))/60000)
}

export function remainingRoomMinutes(capacityMinutes:number,items:TimedCalendarItem[],weekStart:number,weekEnd:number,now:number){
 const start=Math.max(weekStart,now)
 if(start>=weekEnd||weekEnd<=weekStart)return {room:0,remainingCapacity:0,futureBooked:0,overbooked:false}
 const fraction=(weekEnd-start)/(weekEnd-weekStart)
 const remainingCapacity=Math.round(Math.max(0,capacityMinutes)*fraction)
 const futureBooked=calendarBookedMinutes(items,start,weekEnd)
 return {room:Math.max(0,remainingCapacity-futureBooked),remainingCapacity,futureBooked,overbooked:futureBooked>remainingCapacity}
}
