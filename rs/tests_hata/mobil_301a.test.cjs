const {test} = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');
const html = fs.readFileSync(path.join(__dirname, '../app/ui/mobil.html'), 'utf8');
const script = html.match(/<script>\s*([\s\S]*?)<\/script>/)[1];
new vm.Script(script); // Tum mobil betigi de sozdizimsel olarak derlenir.
function fixture(url, stored = '', response = {ok:true, token:'phone-token'}) {
  const calls = [], elements = new Map(), handlers = new Map(), storage = new Map([['afudm_anahtar', stored]]);
  let release;
  const pending = new Promise(resolve => release = resolve);
  const ctx = vm.createContext({
    URL, Promise, location:new URL(url),
    localStorage:{getItem:k=>storage.get(k), setItem:(k,v)=>storage.set(k,v)},
    history:{replaceState:(_a,_b,u)=>calls.push(['history',u])},
    document:{getElementById:id=>{
      if (!elements.has(id)) elements.set(id,{style:{},value:'', addEventListener:(event,fn)=>handlers.set(id+':'+event,fn)});
      return elements.get(id);
    }},
    bildir:()=>{}, yenile:()=>calls.push(["refresh"]), klasorleriDoldur:()=>{},
    fetch: async (u,opts)=>{
      calls.push(['fetch',u,opts]);
      if (u.startsWith('/pair')) {await pending; return {ok:response.ok,json:async()=>response};}
      return {ok:true,json:async()=>({ok:true})};
    },
  });
  const begin = script.indexOf('const ANAHTAR_AD');
  // api'nin tamamini da calistir; sonraki fonksiyon siniri sabittir.
  const apiEnd = script.indexOf('\nfunction ', script.indexOf('async function api('));
  vm.runInContext(script.slice(begin,apiEnd),ctx);
  ctx.document.getElementById('baglantiAdres');
  vm.runInContext(script.slice(script.indexOf('/* Yeni QR adresleri'),script.indexOf('/* Worker kaydi')),ctx);
  return {ctx,calls,storage,release,elements,handlers,run:s=>vm.runInContext(s,ctx)};
}
test('QR temizlenir; degis tokus bitmeden kalici token ile API cagrilmaz', async()=>{
  const f=fixture('http://phone/m?code=one-time&x=1#ok','old-token');
  assert.equal(f.calls[0][1],'/m?x=1#ok');
  const init=f.run('eslemeHazir = eslemeBaslat()');
  const api=f.run('api("/snapshot")');
  await Promise.resolve();
  assert.equal(f.calls.filter(c=>c[0]==='fetch').length,1);
  assert.equal(f.calls[1][1],'/pair?code=one-time');
  assert.equal(f.calls[1][2].headers,undefined);
  f.release(); await init; await api;
  assert.equal(f.storage.get('afudm_anahtar'),'phone-token');
  assert.equal(f.calls[2][2].headers['X-AfuDM-Token'],'phone-token');
});
test('eski k baglantisi hemen temizlenir ve header akisina aktarilir',async()=>{
  const f=fixture('http://phone/m?k=legacy-token');
  assert.equal(f.calls[0][1],'/m');
  await f.run('eslemeHazir = eslemeBaslat()');
  await f.run('api("/snapshot")');
  assert.equal(f.storage.get('afudm_anahtar'),'legacy-token');
  assert.equal(f.calls[1][2].headers['X-AfuDM-Token'],'legacy-token');
});
test('suresi dolan QR eski saklanan kimlikle sessizce devam etmez',async()=>{
  const f=fixture('http://phone/m?code=expired','stored-token',{ok:false});
  const init=f.run('eslemeHazir = eslemeBaslat()');
  const api=f.run('api("/snapshot")');
  const checked = Promise.all([assert.rejects(init),assert.rejects(api)]);
  f.release(); await checked;
  assert.equal(f.calls.filter(c=>c[0]==='fetch').length,1);
});
test('kayitli telefon temiz adresle kimligini kullanmaya devam eder',async()=>{
  const f=fixture('http://phone/m','stored-token');
  await f.run('eslemeHazir = eslemeBaslat()');
  await f.run('api("/snapshot")');
  assert.equal(f.calls[1][2].headers['X-AfuDM-Token'],'stored-token');
});

test('yeniden baglan alani yeni QR kodunu degistirir',async()=>{
  const f=fixture('http://phone/m');
  f.elements.get('baglantiAdres').value='http://phone/m?code=fresh';
  const result=f.handlers.get('baglanBtn:click')();
  f.release(); await result;
  assert.equal(f.storage.get('afudm_anahtar'),'phone-token');
  assert.equal(f.calls.find(c=>c[0]==='fetch')[1],'/pair?code=fresh');
  assert.ok(f.calls.some(c=>c[0]==='refresh'));
});
test('baska sunucunun QR kodu mevcut sunucuya gonderilmez',async()=>{
  const f=fixture('http://phone/m');
  f.elements.get('baglantiAdres').value='http://other/m?code=private';
  await f.handlers.get('baglanBtn:click')();
  assert.equal(f.calls.filter(c=>c[0]==='fetch').length,0);
});
