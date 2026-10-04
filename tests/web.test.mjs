import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import ts from 'typescript';
import {webcrypto} from 'node:crypto';
const source=ts.transpile(readFileSync('web/src/data.ts','utf8'),{module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2022});
const {escapeHTML,validateData,loadData,readWatchlist}=await import('data:text/javascript;base64,'+Buffer.from(source).toString('base64'));
test('source strings are escaped, including event-handler quotes',()=>assert.equal(escapeHTML('<img onerror="x">'), '&lt;img onerror=&quot;x&quot;&gt;'));
test('reject unsupported schema',()=>assert.throws(()=>validateData({schema_version:2})));
test('broken browser storage is safe',()=>{globalThis.localStorage={getItem(){throw Error('blocked')}};assert.deepEqual(readWatchlist(),[])});
test('corrupt current snapshot falls back only to verified previous',async()=>{
 const d={schema_version:1,meta:{observed_at:'2026-10-04T00:00:00Z'},catalog:{players:[]},matches:[],player_forecasts:[],gameweek_totals:[]};
 const raw=JSON.stringify(d);const sha=Buffer.from(await webcrypto.subtle.digest('SHA-256',new TextEncoder().encode(raw))).toString('hex');
 const ref={file:`forecast-${sha}.json`,sha256:sha};let calls=0;
 globalThis.fetch=async()=>{calls++;return new Response(calls===1?JSON.stringify({schema_version:1,current:{file:`forecast-${'a'.repeat(64)}.json`,sha256:'a'.repeat(64)},previous:ref}):calls===2?'corrupt':raw)};
 const result=await loadData();assert.equal(result.fallback,true);assert.equal(calls,3);
});
test('invalid manifest path never fetched',async()=>{let calls=0;globalThis.fetch=async()=>{calls++;return new Response(JSON.stringify({schema_version:1,current:{file:'../../secret'}}))};await assert.rejects(loadData());assert.equal(calls,1)});
