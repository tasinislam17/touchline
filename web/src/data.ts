import type {Data} from './types';
export const escapeHTML = (s:unknown) => String(s ?? '').replace(/[&<>"']/g, c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]!));
export function validateData(d:unknown): asserts d is Data {
 const x=d as Data;
 if(x?.schema_version!==1 || !x.meta || !Number.isFinite(Date.parse(x.meta.observed_at)) || !Array.isArray(x.catalog?.players) || !Array.isArray(x.matches) || !Array.isArray(x.player_forecasts) || !Array.isArray(x.gameweek_totals)) throw Error('Unsupported forecast format.');
 if(x.player_forecasts.some(p=>!Number.isFinite(p.points))) throw Error('Invalid forecast values.');
}
export async function loadData():Promise<{data:Data;fallback:boolean}> {
 const response=await fetch('/data/manifest.json',{cache:'no-store'});
 if(!response.ok) throw Error('Forecasts have not been published yet. Run the local publication command.');
 const manifest=await response.json();
 if(manifest.schema_version!==1) throw Error('Unsupported manifest.');
 for(const [i,ref] of [manifest.current,manifest.previous].entries()) {
  if(!ref || !/^forecast-[a-f0-9]{64}\.json$/.test(ref.file)) continue;
  try {
   const r=await fetch(`/data/${ref.file}`);if(!r.ok) throw Error('Snapshot unavailable');
   const bytes=await r.arrayBuffer();
   const sha=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))).map(b=>b.toString(16).padStart(2,'0')).join('');
   if(sha!==ref.sha256) throw Error('Forecast integrity check failed');
   const data=JSON.parse(new TextDecoder().decode(bytes));validateData(data);return {data,fallback:i===1};
  } catch(e) {if(i===1 || !manifest.previous) throw e;}
 }
 throw Error('No valid published forecast.');
}
export function readWatchlist():number[] {try {const d=JSON.parse(localStorage.getItem('the-dugout:watchlist:v1')||'[]');return Array.isArray(d)?d.filter(x=>Number.isInteger(x)):[];}catch{return [];}}
