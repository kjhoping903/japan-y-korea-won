import fs from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';
class Element {
 constructor(tag='div'){this.tag=tag;this.children=[];this.attrs={};this.events={};this.textContent='';this.hidden=false}
 append(...nodes){this.children.push(...nodes)} replaceChildren(...nodes){this.children=nodes}
 setAttribute(k,v){this.attrs[k]=v} addEventListener(k,v){this.events[k]=v}
}
const ids=new Map();
const document={getElementById(id){if(!ids.has(id))ids.set(id,new Element());return ids.get(id)},querySelectorAll:()=>[],createElement:tag=>new Element(tag),createElementNS:(_,tag)=>new Element(tag)};
const context=vm.createContext({document,Intl,Date,Set,Math,Number,JSON,Array,Error,Blob,URL,setTimeout,setInterval:()=>0,fetch:()=>new Promise(()=>{})});
const html=fs.readFileSync(new URL('./index.html',import.meta.url),'utf8');
vm.runInContext(html.match(/<script>([\s\S]*?)<\/script>/)[1],context);
// Isolated synthetic graph test inputs; never saved as actual production readings.
const record=(date,value)=>({record_id:'test-'+date,reading:{record_date:date,normalized_value:Number(value),unit:'KRW/100 JPY',source_time:null},decimal_value:value,display_value:Number(value).toFixed(2),metadata:{source_reference_date:'2026-10-07'},first_fetched_at:date+'T03:00:00Z',last_fetched_at:date+'T03:00:00Z',comparison:{text:'이전 기록과 동일'}});
const draw=(records,status={freshness:'fresh',error_code:'none'})=>{context.data={records,current:records.at(-1)||null,status,attempt:{},actual_dates:records.map(r=>r.reading.record_date),evidence_waiting:records.length<2};vm.runInContext('renderLive(data)',context)};
draw([]);assert.equal(ids.get('chartMessage').textContent,'아직 저장된 환율이 없습니다.');assert.equal(ids.get('value').textContent,'아직 정상 데이터 없음');
let a=record('2026-10-08','846.0600');draw([a]);assert.equal(ids.get('chartMessage').textContent,'다른 KST 날짜의 기록을 기다리고 있습니다.');
assert.equal(ids.get('plot').children.filter(x=>x.tag==='circle').length,1);
a=record('2026-10-08','846.56789012345678900');draw([a]);
assert.equal(ids.get('rows').children.length,1);assert.equal(ids.get('rows').children[0].children[1].textContent,'846.57 KRW');
let b=record('2026-10-10','847.0001');draw([a,b]);
assert.equal(ids.get('plot').children.filter(x=>x.tag==='circle').length,2);assert.equal(ids.get('plot').children.filter(x=>x.tag==='polyline').length,1);
assert.equal(ids.get('rows').children.length,2);
ids.get('plot').children.find(x=>x.tag==='circle').events.click();
assert.match(ids.get('tooltip').textContent,/2026-10-08.*846.57.*출처 시각 미제공.*마지막 정상 조회/);
const points=ids.get('plot').children.filter(x=>x.tag==='circle').map(x=>x.attrs);
draw([a,b],{freshness:'stale',error_code:'timeout'});
assert.deepEqual(ids.get('plot').children.filter(x=>x.tag==='circle').map(x=>x.attrs),points);
assert.equal(ids.get('rows').children.length,2);assert.match(ids.get('notice').textContent,/오래된 값 · 마지막 정상 조회값/);
assert.equal(ids.get('plot').children.filter(x=>x.tag==='text'&&/^\d+\.\d{2}$/.test(x.textContent)).length,5);
console.log('PASS: graph/table empty, one point, same-day update, next-date addition without invented dates, tooltip, failure preservation, Y-axis ticks');
