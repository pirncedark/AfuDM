import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import vm from 'node:vm';

const source = await readFile(new URL('../extension/download-preflight.js', import.meta.url), 'utf8');
const listeners = {}, sent = [];
let settings = {enabled:true, uzantiAcik:true};
const context = {
  URL, crypto: {randomUUID:()=> 'test-request'},
  location: {href:'https://site.test/page'},
  document: {addEventListener:(name,fn)=>listeners[name]=fn},
  chrome: {storage:{local:{get:async()=>settings},onChanged:{addListener:fn=>listeners.settings=fn}},
    runtime:{sendMessage:async msg=>{sent.push(msg);return {ok:true};}}},
};
vm.runInNewContext(source, context);
await new Promise(resolve=>setImmediate(resolve));
function click(href, attrs={}, extras={}) {
  const anchor = {href,hasAttribute:k=>Object.hasOwn(attrs,k),getAttribute:k=>attrs[k]||''};
  const e = {button:0,composedPath:()=>[{closest:()=>anchor}],preventDefault(){this.stopped=true;},stopImmediatePropagation(){},...extras};
  listeners.click(e); return e;
}
for (const url of ['https://site.test/file.zip','https://site.test/file.pdf','https://site.test/file.torrent','magnet:?xt=urn:btih:abc']) {
  assert.equal(click(url).stopped,true,url);
}
assert.equal(click('https://site.test/opaque',{download:'report.zip'}).stopped,true);
for (const url of ['https://site.test/page','https://site.test/cover.jpg','javascript:void(0)']) {
  assert.equal(click(url).stopped,undefined,url);
}
assert.equal(click('https://site.test/file.zip',{}, {ctrlKey:true}).stopped,undefined);
assert.equal(click('https://site.test/file.zip',{}, {button:1}).stopped,undefined);
listeners.settings({enabled:{newValue:false}},'local');
assert.equal(click('https://site.test/file.zip').stopped,undefined);
assert.equal(sent.length,5);
assert.equal(sent[2].payload.kind,'torrent');
assert.equal(sent[3].payload.kind,'torrent');
console.log('PASS: preflight click, normal links, images, modifiers, disabled, torrent');
