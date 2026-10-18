const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const ts = require('typescript')

const source = fs.readFileSync(path.join(__dirname, '../src/calendarMath.ts'), 'utf8')
const compiled = ts.transpileModule(source, {compilerOptions:{module:ts.ModuleKind.CommonJS}}).outputText
const exportsFromModule = {}
new Function('exports', compiled)(exportsFromModule)
const {calendarBookedMinutes} = exportsFromModule

const weekStart = Date.parse('2026-10-12T00:00:00Z')
const weekEnd = Date.parse('2026-10-19T00:00:00Z')
const item = (start,end,all_day=false,busy=true) => ({start,end,all_day,busy})
assert.equal(calendarBookedMinutes([
  item('2026-10-13T09:00:00Z','2026-10-13T10:00:00Z'),
  item('2026-10-13T09:30:00Z','2026-10-13T11:00:00Z'),
  item('2026-10-13T12:00:00Z','2026-10-13T13:00:00Z',false,false),
  item('2026-10-14','2026-10-15',true),
  item('2026-10-11T23:30:00Z','2026-10-12T00:30:00Z'),
],weekStart,weekEnd),150)
assert.equal(calendarBookedMinutes([],weekStart,weekEnd),0)
console.log('Calendar booked-time checks passed')
