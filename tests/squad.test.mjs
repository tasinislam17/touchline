import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import ts from 'typescript';

const source=ts.transpile(readFileSync('web/src/squad.ts','utf8'),{module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2022});
const squad=await import('data:text/javascript;base64,'+Buffer.from(source).toString('base64'));
const players=[];let id=1;for(const [position,count] of [[1,2],[2,5],[3,5],[4,3]])for(let i=0;i<count+1;i++)players.push({id:id++,position,team:i%5+1,price_tenths:50+i});
const data={catalog:{players},meta:{},matches:[],player_forecasts:[],gameweek_totals:[]};
const pickIds=[1,2,4,5,6,7,8,10,11,12,13,14,16,17,18];
const official={schemaVersion:1,entryId:42,managerName:'Test Manager',teamName:'Test XI',lockedGameweek:5,importedAt:'2026-10-01T00:00:00Z',bankTenths:13,teamValueTenths:1014,totalPoints:300,overallRank:123,activeChip:null,chips:[],picks:pickIds.map((element,i)=>({element,position:i+1,multiplier:i===0?2:i<11?1:0,isCaptain:i===0,isViceCaptain:i===1,positionType:players.find(p=>p.id===element).position}))};

test('official importer reads only the public locked squad contract',async()=>{
 const calls=[];const fetcher=async url=>{calls.push(url);let value;
  if(url.endsWith('/entry/42'))value={current_event:5,player_first_name:'Test',player_last_name:'Manager',name:'Test XI',summary_overall_points:300,summary_overall_rank:123};
  else if(url.endsWith('/picks'))value={active_chip:null,entry_history:{bank:13,value:1014},picks:official.picks.map(p=>({element:p.element,position:p.position,multiplier:p.multiplier,is_captain:p.isCaptain,is_vice_captain:p.isViceCaptain,element_type:p.positionType}))};
  else value={current:[{event:5,bank:13,value:1014}],chips:[]};
  return new Response(JSON.stringify(value),{headers:{'content-type':'application/json'}});
 };
 const result=await squad.fetchOfficialSquad(42,fetcher,'/api/fpl');
 assert.equal(result.teamName,'Test XI');assert.equal(result.picks.length,15);assert.equal(result.bankTenths,13);
 assert.deepEqual(calls,['/api/fpl/entry/42','/api/fpl/entry/42/event/5/picks','/api/fpl/entry/42/history']);
});

test('planning state keeps unavailable financial fields explicit',()=>{
 const plan=squad.createPlan(official);assert.equal(plan.bankTenths,null);assert.equal(plan.freeTransfers,null);assert.deepEqual(plan.squad,pickIds);
 assert.doesNotThrow(()=>squad.validatePlan(plan,data,42));
});

test('replacement preserves positional shape and records actual selling price separately',()=>{
 const plan=squad.createPlan(official);const next=squad.replacePlayer(plan,1,3,48,players.find(p=>p.id===3).price_tenths,data);
 assert.equal(next.squad.includes(1),false);assert.equal(next.squad.includes(3),true);assert.equal(next.moves[0].sellingPriceTenths,48);assert.equal(next.sellingPrices['1'],48);
 assert.throws(()=>squad.replacePlayer(plan,1,9,null,50,data),/same FPL position/);
});

test('changed official squad never overwrites an edited plan',()=>{
 const plan=squad.replacePlayer(squad.createPlan(official),1,3,null,52,data);const stored={schemaVersion:1,official,plan,undo:[]};
 const incoming=structuredClone(official);incoming.lockedGameweek=6;incoming.picks[0].element=3;
 const result=squad.reconcile(stored,incoming);assert.equal(result.plan.moves.length,1);assert.equal(result.pendingOfficial.lockedGameweek,6);
});

test('team storage is isolated by Team ID and corrupt data is ignored',()=>{
 const values=new Map();globalThis.localStorage={getItem:key=>values.get(key)??null,setItem:(key,value)=>values.set(key,value)};
 const value={schemaVersion:1,official,plan:squad.createPlan(official),undo:[]};squad.writeStoredTeam(value);
 assert.equal(squad.readStoredTeam(42).official.entryId,42);assert.equal(squad.readStoredTeam(43),null);
 values.set(squad.storageKey(42),'{bad');assert.equal(squad.readStoredTeam(42),null);
});

test('import rejects another team and malformed squad shapes',()=>{
 const plan=squad.createPlan(official);assert.throws(()=>squad.validatePlan(plan,data,7),/another team/);
 plan.squad.pop();assert.throws(()=>squad.validatePlan(plan,data,42),/15 unique/);
});

test('invalid and unavailable Team IDs fail with specific messages',async()=>{
 let called=false;await assert.rejects(()=>squad.fetchOfficialSquad('abc',async()=>{called=true;}),/valid numeric FPL Team ID/);assert.equal(called,false);
 const missing=async()=>new Response('{}',{status:404,headers:{'content-type':'application/json'}});
 await assert.rejects(()=>squad.fetchOfficialSquad(99999999,missing),/not found/);
});
