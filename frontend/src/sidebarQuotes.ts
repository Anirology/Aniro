import {ArrowCounterClockwise,CalendarBlank,Compass,Timer,Wallet} from '@phosphor-icons/react'

export const sidebarQuotes = {
 '/plan': {Icon:CalendarBlank,quote:'If it’s not scheduled, it’s not real.',author:'Marie Forleo',source:'https://www.marieforleo.com/blog/how-to-manage-time-and-achieve-anything'},
 '/clarity': {Icon:Compass,quote:'Most people think they lack motivation when they really lack clarity.',author:'James Clear',source:'https://jamesclear.com/quotes/most-people-think-they-lack-motivation-when-they-really-lack-clarity'},
 '/focus': {Icon:Timer,quote:'Lost time is never found again.',author:'Benjamin Franklin',source:'https://www.gutenberg.org/cache/epub/36151/pg36151-images.html'},
 '/reflect': {Icon:ArrowCounterClockwise,quote:'Learning without thought is naught; thought without learning is dangerous.',author:'Confucius, translated by Leonard A. Lyall',source:'https://www.gutenberg.org/cache/epub/24055/pg24055-images.html'},
 '/money': {Icon:Wallet,quote:'Know what you spend. Choose what matters.',author:'Aniro',source:''},
} as const
