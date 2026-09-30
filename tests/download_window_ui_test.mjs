import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
const code = fs.readFileSync(new URL('../ui/download.js', import.meta.url), 'utf8');
async function fixture(item, categorized = true, probe = undefined) {
  const nodes = new Map();
  const node = id => { if (!nodes.has(id)) nodes.set(id, {value:'', textContent:'', hidden:false}); return nodes.get(id); };
  const calls = [];
  const windowState = {reset:0};
  const pendingItems = [item];
  const api = {
    probe_link: probe,
    pencere_durumu: async () => windowState,
    dil: async () => 'en', baslik: async title => calls.push(['title',title]),
    bekleyen_listesi: async () => ({ogeler:[{id:98,source:'clipboard',url:'other'},...pendingItems]}),
    bekleyen_goster: async id => { calls.push(['shown',id]); return {ok:true}; },
    kaydet_bilgi: async (...args) => { calls.push(['defaults',...args]); return {kategori:'belge',ana:'/downloads',kategori_klasorleri:categorized,klasorler:{belge:'/downloads/Documents'},dosya_adi:'invented',video_quality:'720'}; },
    bekleyen_onayla: async (id,options) => { calls.push(['confirm',id,options]); pendingItems.splice(pendingItems.findIndex(item=>item.id===id),1); return {ok:true,gid:'g1'}; },
    indirme_durumu: async () => ({item:{}}),
  };
  const window = {pywebview:{api},addEventListener(){}};
  vm.runInNewContext(code,{window,document:{getElementById:node,title:''},lang:{t:key=>'EN:'+key,setLang(){},applyStatic(){}},setInterval(){}});
  await window.afudmDownloadRefresh();
  return {nodes,calls,window,node,windowState,pendingItems};
}
{
 const f=await fixture({id:1,source:'browser',url:'https://example.test/get',filename:'report.pdf',kind:'http'});
 assert.equal(f.node('folder').value,'/downloads/Documents');
 await f.node('start').onclick();
 assert.deepEqual(JSON.parse(JSON.stringify(f.calls.find(x=>x[0]==='confirm')[2])),{filename:'report.pdf',dest_dir:'/downloads/Documents',kategori:'belge'});
 assert.equal(f.calls.find(x=>x[0]==='shown')[1],1);
 assert.equal(f.calls.find(x=>x[0]==='defaults')[2],'report.pdf');
 assert.ok(f.calls.find(x=>x[0]==='title')[1].includes('EN:download.title'));
 await f.window.afudmDownloadRefresh();
 assert.equal(f.node('progressLabel').textContent,'EN:download.failed');
 f.windowState.reset++;
 await f.window.afudmDownloadRefresh();
 assert.equal(f.node('confirmPane').hidden,false);
 assert.equal(f.node('progressPane').hidden,true);
}
{
 const f=await fixture({id:2,source:'browser',url:'https://example.test/watch?v=x',kind:'video',quality:'720',audio_only:true},false);
 assert.equal(f.node('name').value,'');
 assert.equal(f.node('quality').value,'audio');
 assert.equal(f.node('folder').value,'/downloads');
 await f.node('start').onclick();
 const options=f.calls.find(x=>x[0]==='confirm')[2];
 assert.equal(options.audio_only,true);
 assert.equal(options.quality,'720');

}
{
 const f=await fixture({id:3,source:'browser',url:'https://example.test/watch',kind:'video',quality:'1080'});
 assert.equal(f.node('quality').value,'1080');
 f.node('quality').value='audio';
 f.node('quality').onchange();
 await f.node('start').onclick();
 const options=f.calls.find(x=>x[0]==='confirm')[2];
 assert.equal(options.quality,'audio');
 assert.equal(options.audio_only,true);
}
{
 const f=await fixture({id:4,source:'browser',url:'https://example.test/watch',kind:'video',quality:'720',audio_only:false});
 assert.equal(f.node('quality').value,'720');
 await f.node('start').onclick();
 const options=f.calls.find(x=>x[0]==='confirm')[2];
 assert.equal(options.quality,'720');
 assert.equal(options.audio_only,false);
}
{
 const f=await fixture({id:5,source:'browser',url:'https://example.test/one',filename:'one.pdf',kind:'http'});
 await f.node('start').onclick();
 await f.window.afudmDownloadRefresh();
 assert.equal(f.node('progressPane').hidden,false);
 f.pendingItems.push({id:6,source:'browser',url:'https://example.test/two',filename:'two.pdf',kind:'http'});
 await f.window.afudmDownloadRefresh();
 assert.equal(f.node('confirmPane').hidden,false);
 assert.equal(f.node('progressPane').hidden,true);
 assert.equal(f.node('name').value,'two.pdf');
 assert.equal(f.calls.filter(x=>x[0]==='shown').at(-1)[1],6);
}
const app=fs.readFileSync(new URL('../ui/app.js',import.meta.url),'utf8');
assert.ok(app.includes('.filter((item) => item.source !== "browser")'));
const html=fs.readFileSync(new URL('../ui/download.html',import.meta.url),'utf8');
assert.ok(html.indexOf('src="i18n.js"')<html.indexOf('src="download.js"'));
console.log('download window UI: passed');
{
 let resolve;
 const f=await fixture({id:7,source:'browser',url:'https://example.test/1706.03762',kind:'http'},true,
   () => new Promise(r => {resolve=r;}));
 resolve({ok:true,filename:'X.pdf',kategori:'belge'});
 await new Promise(r=>setImmediate(r));
 assert.equal(f.node('name').value,'X.pdf');
}
{
 let resolve;
 const f=await fixture({id:8,source:'browser',url:'https://example.test/pdf',kind:'http'},true,
   () => new Promise(r => {resolve=r;}));
 f.node('name').value='manual.pdf'; f.node('name').oninput();
 resolve({ok:true,filename:'X.pdf',kategori:'belge'});
 await new Promise(r=>setImmediate(r));
 assert.equal(f.node('name').value,'manual.pdf');
 await f.node('start').onclick();
 assert.equal(f.calls.find(x=>x[0]==='confirm')[2].filename_edited,true);
}
for (const probe of [async()=>{throw new Error('offline');},()=>new Promise(()=>{})]) {
 const f=await fixture({id:9,source:'browser',url:'https://example.test/pdf',kind:'http'},true,probe);
 await f.node('start').onclick();
 assert.ok(f.calls.some(x=>x[0]==='confirm'));
}
