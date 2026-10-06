import type {Data} from './types';

export const SQUAD_SCHEMA=1;
export const DEFAULT_ENTRY_ID=3795318;

export interface OfficialPick {element:number;position:number;multiplier:number;isCaptain:boolean;isViceCaptain:boolean;positionType:number}
export interface OfficialSquad {
 schemaVersion:1;entryId:number;managerName:string;teamName:string;lockedGameweek:number;importedAt:string;
 bankTenths:number;teamValueTenths:number;totalPoints:number;overallRank:number|null;activeChip:string|null;
 chips:{name:string;event:number;time:string}[];picks:OfficialPick[];
}
export interface PlannedMove {out:number;in:number;sellingPriceTenths:number|null;purchasePriceTenths:number;createdAt:string}
export interface PlanningState {
 schemaVersion:1;entryId:number;baseGameweek:number;baseFingerprint:string;updatedAt:string;squad:number[];order:number[];
 captain:number;viceCaptain:number;bankTenths:number|null;freeTransfers:number|null;sellingPrices:Record<string,number>;
 moves:PlannedMove[];locks:number[];exclusions:number[];
}
export interface StoredTeam {schemaVersion:1;official:OfficialSquad;plan:PlanningState;undo:PlanningState[];pendingOfficial?:OfficialSquad}

const integer=(value:unknown,label:string,min=0)=>{if(!Number.isInteger(value)||(value as number)<min)throw Error(`Invalid ${label} in FPL response.`);return value as number;};
const text=(value:unknown,label:string)=>{if(typeof value!=='string'||!value.trim())throw Error(`Missing ${label} in FPL response.`);return value.trim();};
const rank=(value:unknown)=>value===null?null:integer(value,'overall rank',1);
export const fingerprint=(official:Pick<OfficialSquad,'lockedGameweek'|'picks'>)=>`${official.lockedGameweek}:${official.picks.map(p=>p.element).sort((a,b)=>a-b).join(',')}`;

function validateEntryId(value:unknown){const id=Number(value);if(!Number.isInteger(id)||id<1||id>99_999_999)throw Error('Enter a valid numeric FPL Team ID.');return id;}
async function request(url:string,fetcher:typeof fetch){
 const response=await fetcher(url,{headers:{accept:'application/json'},cache:'no-store'});
 if(response.status===404)throw Error('FPL Team ID not found, or this gameweek is not publicly available.');
 if(!response.ok)throw Error(`Official FPL data is unavailable (${response.status}). Try again later.`);
 const type=response.headers.get('content-type')||'';if(!type.includes('json'))throw Error('Official FPL returned an unexpected response.');
 return response.json();
}

export async function fetchOfficialSquad(value:unknown,fetcher:typeof fetch=fetch,base='/api/fpl'):Promise<OfficialSquad>{
 const entryId=validateEntryId(value);
 const entry=await request(`${base}/entry/${entryId}`,fetcher);
 const event=integer(entry.current_event,'current event',1);
 const [picks,history]=await Promise.all([
  request(`${base}/entry/${entryId}/event/${event}/picks`,fetcher),
  request(`${base}/entry/${entryId}/history`,fetcher),
 ]);
 if(!Array.isArray(picks.picks)||picks.picks.length!==15)throw Error('The latest locked FPL squad is incomplete.');
 const rawPicks=picks.picks as Record<string,unknown>[];
 const parsed:OfficialPick[]=rawPicks.map((p):OfficialPick=>({
  element:integer(p.element,'player ID',1),position:integer(p.position,'pick position',1),
  multiplier:integer(p.multiplier,'pick multiplier'),isCaptain:Boolean(p.is_captain),isViceCaptain:Boolean(p.is_vice_captain),
  positionType:integer(p.element_type,'position type',1),
 })).sort((a,b)=>a.position-b.position);
 if(new Set(parsed.map(p=>p.element)).size!==15||new Set(parsed.map(p=>p.position)).size!==15)throw Error('The locked FPL squad contains duplicate picks.');
 const current=Array.isArray(history.current)?history.current.find((x:Record<string,unknown>)=>x.event===event):null;
 const h=picks.entry_history||current;if(!h)throw Error('The latest locked squad has no gameweek history.');
 return {schemaVersion:SQUAD_SCHEMA,entryId,managerName:`${text(entry.player_first_name,'manager name')} ${text(entry.player_last_name,'manager name')}`,
  teamName:text(entry.name||entry.player_team_name||`${entry.player_first_name}'s team`,'team name'),lockedGameweek:event,
  importedAt:new Date().toISOString(),bankTenths:integer(h.bank,'bank'),teamValueTenths:integer(h.value,'team value'),
  totalPoints:integer(entry.summary_overall_points,'total points'),overallRank:rank(entry.summary_overall_rank),activeChip:picks.active_chip??null,
  chips:Array.isArray(history.chips)?history.chips.map((c:Record<string,unknown>)=>({name:text(c.name,'chip'),event:integer(c.event,'chip event',1),time:text(c.time,'chip time')})):[],picks:parsed};
}

export function createPlan(official:OfficialSquad):PlanningState{
 const captain=official.picks.find(p=>p.isCaptain)?.element||official.picks[0].element;
 const viceCaptain=official.picks.find(p=>p.isViceCaptain)?.element||official.picks[1].element;
 return {schemaVersion:SQUAD_SCHEMA,entryId:official.entryId,baseGameweek:official.lockedGameweek,baseFingerprint:fingerprint(official),updatedAt:new Date().toISOString(),
  squad:official.picks.map(p=>p.element),order:official.picks.map(p=>p.element),captain,viceCaptain,bankTenths:null,freeTransfers:null,
  sellingPrices:{},moves:[],locks:[],exclusions:[]};
}
export const clonePlan=(plan:PlanningState):PlanningState=>structuredClone(plan);
export function validatePlan(value:unknown,data:Data,entryId?:number):PlanningState{
 const p=value as PlanningState;if(p?.schemaVersion!==SQUAD_SCHEMA||!Number.isInteger(p.entryId)||(entryId&&p.entryId!==entryId))throw Error('This planning file belongs to another team or schema version.');
 for(const key of ['squad','order','moves','locks','exclusions'] as const)if(!Array.isArray(p[key]))throw Error(`Planning file is missing ${key}.`);
 if(p.squad.length!==15||p.order.length!==15||new Set(p.squad).size!==15||new Set(p.order).size!==15||p.order.some(id=>!p.squad.includes(id)))throw Error('A planning squad must contain 15 unique ordered players.');
 const catalog=new Map(data.catalog.players.map(x=>[x.id,x]));if(p.squad.some(id=>!catalog.has(id)))throw Error('Planning file contains a player outside this forecast snapshot.');
 const counts=[0,0,0,0,0];for(const id of p.squad)counts[catalog.get(id)!.position]++;
 if(counts.slice(1).join(',')!=='2,5,5,3')throw Error('Planning squad must contain 2 goalkeepers, 5 defenders, 5 midfielders and 3 forwards.');
 if(!p.squad.includes(p.captain)||!p.squad.includes(p.viceCaptain)||p.captain===p.viceCaptain)throw Error('Captain and vice-captain must be different squad players.');
 for(const n of [p.bankTenths,p.freeTransfers])if(n!==null&&(!Number.isInteger(n)||n<0))throw Error('Bank and free transfers must be non-negative whole units.');
 return clonePlan(p);
}
export function replacePlayer(plan:PlanningState,outId:number,inId:number,sellingPriceTenths:number|null,purchasePriceTenths:number,data:Data){
 const next=clonePlan(plan);const index=next.squad.indexOf(outId);if(index<0||next.squad.includes(inId))throw Error('Choose one player in your squad and one different replacement.');
 const out=data.catalog.players.find(p=>p.id===outId),incoming=data.catalog.players.find(p=>p.id===inId);if(!out||!incoming||out.position!==incoming.position)throw Error('Replacement must have the same FPL position.');
 next.squad[index]=inId;next.order[next.order.indexOf(outId)]=inId;if(next.captain===outId)next.captain=inId;if(next.viceCaptain===outId)next.viceCaptain=inId;
 if(sellingPriceTenths!==null)next.sellingPrices[String(outId)]=sellingPriceTenths;
 next.moves.push({out:outId,in:inId,sellingPriceTenths,purchasePriceTenths,createdAt:new Date().toISOString()});next.updatedAt=new Date().toISOString();return next;
}
export function reconcile(stored:StoredTeam,incoming:OfficialSquad):StoredTeam{
 if(stored.official.entryId!==incoming.entryId)throw Error('Cannot reconcile different Team IDs.');
 if(fingerprint(stored.official)===fingerprint(incoming))return {...stored,official:incoming,pendingOfficial:undefined};
 if(stored.plan.moves.length||stored.plan.baseFingerprint!==fingerprint(stored.official))return {...stored,pendingOfficial:incoming};
 return {schemaVersion:SQUAD_SCHEMA,official:incoming,plan:createPlan(incoming),undo:[]};
}
export function storageKey(entryId:number){return `the-dugout:team:${entryId}:v1`;}
export function readStoredTeam(entryId:number):StoredTeam|null{try{const raw=localStorage.getItem(storageKey(entryId));if(!raw)return null;const value=JSON.parse(raw);return value?.schemaVersion===SQUAD_SCHEMA&&value.official?.entryId===entryId?value:null;}catch{return null;}}
export function writeStoredTeam(value:StoredTeam){localStorage.setItem(storageKey(value.official.entryId),JSON.stringify(value));localStorage.setItem('the-dugout:last-team:v1',String(value.official.entryId));}
export function lastTeamId(){try{return validateEntryId(localStorage.getItem('the-dugout:last-team:v1')||DEFAULT_ENTRY_ID);}catch{return DEFAULT_ENTRY_ID;}}
