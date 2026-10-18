"""Render observed T2 artifacts; absent evidence always remains KALDI."""
import json
from datetime import datetime
from common import ROOT, OUT


def read(name, default=None):
    path = OUT / (name + '.json')
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else default


def cell(value):
    return str(value).replace('|', '\\|').replace('\n', ' ')[:400]


def main():
    from findings import generate
    generate()
    lines = ['# T2 hata ve dayanıklılık sonuçları', '',
             'Üretim kodundaki hatalar düzeltilmedi. Bu rapor gerçek test çıktılarını ve kapsam sınırlarını ayırır.', '',
             'Rapor zamanı: ' + datetime.now().isoformat(timespec='seconds'), '',
             '## Durum', '', '| Madde | Sonuç | Kanıt |', '|---|---|---|']
    sections = [('1 — POST fuzz', 'fuzz'), ('2 — Çökme/yeniden başlatma', 'crash'),
                ('3a — Kopya DB göçü', 'migration'), ('3b — Eski güncelleyici', 'updater'),
                ('4 — Köprü metotları', 'bridge'), ('4 — Panel/LAN', 'network'),
                ('5 — RAM/CPU/disk', 'resources')]
    for title, name in sections:
        data = read(name)
        good = (bool(data) and all(r.get('status') == 'GECTI' for r in data)) if isinstance(data, list) else bool(data and data.get('status') == 'GECTI')
        status = 'GEÇTİ' if good else 'KALDI' if data else 'KALDI — çıktı yok'
        lines.append(f'| {title} | {status} | [ham JSON](../../tests_hata/rapor/{name}.json) |')
    cleanup = read('cleanup', {})
    lines += ['', 'Süreç temizliği: `' + json.dumps(cleanup, ensure_ascii=False) + '`.', '',
              '## Tekrarlama', '', '```powershell', 'python -B tests_hata/verify.py',
              'python -B tests_hata/hepsi.py', 'python -B tests_hata/upgrade.py',
              'python -B tests_hata/report.py', '```', '',
              'Hepsi komutu 1, 2, 4 ve 5’i çalıştırır. Bir senaryo kaldığında çıkış kodu 1 olur; bu bir test bulgusudur.', '',
              '## 1 — Hatalı girdiler', '']
    fuzz = read('fuzz', {})
    lines += ['```json', json.dumps(fuzz, ensure_ascii=False, indent=2), '```', '',
              'Bütün yanıt çiftleri: [fuzz_rows.json](../../tests_hata/rapor/fuzz_rows.json).', '']
    rows = read('fuzz_rows', [])
    planned = len(rows)
    executed = [r for r in rows if 'skip' not in r]
    server_errors = sum(r.get(side, {}).get('status', 0) >= 500 for r in executed for side in ('py', 'rs'))
    disconnects = sum(r.get(side, {}).get('status') == 0 for r in executed for side in ('py', 'rs'))
    lines += ['', f'Planlanan vaka: {planned}; güvenlik nedeniyle atlanan: {planned-len(executed)}; '
              f'her tarafta gönderilen: {len(executed)}. Gerçek HTTP 500+: {server_errors}; '
              f'taşıma hatası: {disconnects}.', '',
              '| Yol | Farklı yanıt veren girdiler | 500/bağlantı hatası |', '|---|---|---|']
    for route in sorted({r['route'] for r in rows}):
        subset = [r for r in rows if r['route'] == route]
        lines.append('| ' + route + ' | ' + ', '.join(r['case'] for r in subset if r.get('difference')) +
                     ' | ' + ', '.join(r['case'] for r in subset if r.get('failure')) + ' |')
    lines += ['', '## 2 — Çökme ve devam', '',
              '| Tür | Taraf | Sonuç | Çökme yüzdesi | .aria2 | Session bayt | DB | SHA | Range devam | taskkill kodu |',
              '|---|---|---|---:|---|---:|---|---|---|---:|']
    for r in read('crash', []):
        lines.append('| ' + ' | '.join(cell(r.get(k)) for k in
                     ('mode', 'side', 'status', 'fraction', 'control_exists', 'session_bytes', 'integrity', 'sha_ok', 'range_after_restart', 'taskkill_exit')) + ' |')
    lines += ['', 'taskkill engellenirse yalnız sahip olunan süreç tanıtıcılarıyla zorla sonlandırma uygulanır. '
              'SHA-256 ve yeniden açıldıktan sonraki HTTP Range kayıtları ham JSON’dadır; yalnız dosya boyutu başarı sayılmaz.', '',
              '## 3 — Güncelleme provası', '']
    for name in ('migration', 'updater'):
        lines += ['```json', json.dumps(read(name, {}), ensure_ascii=False, indent=2), '```', '']
    lines += ['Kaynak sürümü 2.9.6’dır; 2.9.8 sürüm değeri yalnız izole helper içinde uygulanmıştır. '
              'Bu, özgün 2.9.8 kaynak sürümünün çalıştırıldığı anlamına gelmez. Gerçek DB bağlantısı açılmadan DB/WAL/SHM fiziksel olarak kopyalanır; '
              'SQLite yalnız kopyayı açar. Canlı dosyaların art arda kopyalanması atomik snapshot garantisi vermez. '
              'Göç testi SqliteStore göçünü çalıştırır; kullanıcı kuyruğunu başlatmaz. '
              'Güncelleyicide gerçek indirme, SHA kontrolü, zip açma, yedekleme ve kopyalama yolu çalışır; son EXE açılışı yakalanır.', '',
              '### Release iş akışı önerisi — uygulanmadı', '',
              '1. `.github/workflows/release.yml` içindeki quality-gate ve tag/main kontrollerini koru. '
              '`scripts/surum_oku.py` kontrolüne ek olarak `rs/app/Cargo.toml` ve Rust sürüm sabitinin tag ile eşitliğini denetle.',
              '2. Windows job’a sabitlenmiş Rust araç zincirini ekle. PyInstaller adımı yerine '
              '`cargo build --release --locked --manifest-path rs/app/Cargo.toml` çalıştır; `test-kapisi` özelliğini açma.',
              '3. Kök çalışma alanı ve ayrı app çalışma alanında fmt, test ve clippy kontrollerini çalıştır. '
              'Yayın öncesi bu T2 senaryolarındaki KALDI bulgularını çöz.',
              '4. `rs/scripts/build_release_rust.ps1` önerilir (bu görevde scripts sahipliği yok; oluşturulmadı). '
              'Betik `rs/app/target/release/AfuDM.exe` dosyasını geçici `AfuDM/` köküne, gerekli motorları `AfuDM/engine/`, '
              'UI dosyalarını `AfuDM/ui/` içine koymalı. Kullanıcı data klasörünü pakete alma.',
              '5. Kökü koruyarak `AfuDM-v3.0.0-win64.zip` oluştur. SHA-256 dosyası aynı isim + `.sha256` olsun. '
              'Önceki Python paketleme betiğinin PyInstaller çıktı yolunu Rust staging yoluna uyarla veya yeni betiğe yönlendir.',
              '6. Mevcut verify_release/smoke_test betiklerini Rust paketine uyarlayıp izole veri/port ve penceresiz prova yaptır. '
              'Eski güncelleyicinin gerçek uygulama provası da kapı olmalı. Artifact/checksum/release notes/yayın adımlarını koru.', '',
              'Üretilen prova zip’i geçici klasördeydi; kalıcı yayın paketi üretilmedi. '
              'Prova varsayılan DEBUG EXE’yi kullanır; optimize release paketi doğrulanmış sayılmaz.', '',
              '## 4 — Köprü ve ağ', '', '```json',
              json.dumps(read('bridge', {}), ensure_ascii=False, indent=2), '```', '',
              '| Metot | Python sonuç biçimi | Rust sonuç biçimi |', '|---|---|---|']
    for r in read('bridge_rows', []):
        if 'skip' not in r and (not r.get('shape_equal') or r['py'].get('exception')):
            lines.append('| ' + r['name'] + ' | ' + cell(r['py']) + ' | ' + cell(r['rs']) + ' |')
    lines += ['', 'Atlanan metotlar (başarı sayılmaz):', '']
    for r in read('bridge_rows', []):
        if 'skip' in r:
            lines.append('- `' + r['name'] + '`: ' + r['skip'])
    lines += ['', 'Kapı güvenlik yanıtları:', '', '```json',
              json.dumps(read('gate_security', []), ensure_ascii=False, indent=2), '```', '',
              'Panel/LAN sonuçları:', '', '```json', json.dumps(read('network', []), ensure_ascii=False, indent=2), '```', '',
              'Panel normalde 6821 kullanır; bu testte mevcut kurulumla çakışmayı önlemek için geçici port seçilir. '
              'Test kapısı yalnız 127.0.0.1’e bağlanır; token ister ve Origin başlığını reddeder.', '',
              '## 5 — Ölçümler', '',
              '| Senaryo | Taraf | Örnek | WS MiB ort. | Private MiB ort. | CPU % ort. | Yazma MiB/s ort. | En çok süreç |',
              '|---|---|---:|---:|---:|---:|---:|---:|']
    for r in read('resources', {}).get('summary', []):
        vals = [r[k] for k in ('phase', 'side', 'samples', 'working_set_mib_avg', 'private_mib_avg', 'cpu_percent_avg', 'write_mib_s_avg', 'max_processes')]
        lines.append('| ' + ' | '.join(f'{v:.3f}' if isinstance(v, float) else str(v) for v in vals) + ' |')
    lines += ['', 'Working Set/Private Bytes ve CPU/disk sayaçları bütün mevcut alt süreçler dahil psutil ile toplanır. '
              'CPU % tek mantıksal çekirdek ölçeğindedir (çok çekirdekte 100’ü geçebilir). '
              'İndirme pencereleri 60 saniyedir; indirme erken biterse kalan boş süre de ortalamaya girer. '
              'Her taraf 1 GiB HTTP ve üç eşzamanlı 128 MiB dosya indirir. İçerik SHA-256 ile denetlenir. '
              'Rust DEBUG derlemesidir. Test boot üretim IdleRpc uyku döngüsünü çalıştırmadığı için '
              'bu veriler nihai üretim performansı veya uyku davranışı karşılaştırması değildir.', '',
              '## Yazılan dosyalar ve sözleşme sınırları', '',
              '- `app/Cargo.toml`: varsayılan kapalı `test-kapisi` özelliği.',
              '- `app/src/main.rs`: özellik kapıları; varsayılan boot/tray/single-instance yolu korunur.',
              '- `app/src/test_kapisi.rs`: token korumalı köprü, izole boot, kopya DB göç modu ve güvenlik birim testi.',
              '- `tests_hata/`: Python headless helper, ortak izolasyon, beş senaryo, güncelleme provası, doğrulama, rapor betiği, README ve ham çıktılar.',
              '- `docs/sonuc/SONUC_T2.md`: bu rapor.', '',
              'Python iş mantığı taşınmadı; mevcut Python Api ve Rust bridge::api_call/dispatch gerçek uygulamaları çağrıldı. '
              '✅ Token/Origin/uzak adres birim testi ve her çağrının biçim kaydı. '
              '⚠ Pencere, işletim sistemi değişikliği ve dış internet gerektiren metotlar yukarıda gerekçeleriyle atlandı. '
              '⚠ Üretim Aria2Daemon 6810..6830 aralığını tarar; bu testte çalıştırılmaz. '
              'Üretim argümanları include edilip Manager’a ayrı RPC enjekte edilir. '
              'reliability_health/reliability_restart_engine bu nedenle atlanır. '
              'Sentinel kontrolleri bütün sistem yazma izlemesi değildir. Üretim uyku/restart ve tüm 146 metot kapsamı tamamlandı sayılmaz.', '',
              'Uygulama hata düzeltmesi: yok. Önceki turdan kalan test kodundaki migration EXE yolu '
              '`tests_hata/bin/AfuDM_test.exe` olarak düzeltildi; varsayılan EXE’de göç modu derlenmez. '
              'Runner sonraki koşularda eski sonuçları başarı saymamak için seçili senaryo özetlerini temizler.', '',
              'Son turda yalnız test betikleri düzeltildi: çökme ilerlemesi DB alanı `done_bytes` yerine '
              'snapshot alanı `completedLength` üzerinden okunur; panel yetkilendirme testi mevcut `/api/liste` '
              'yolunu kullanır. API envanterindeki `windows` özelliği açıkça atlanarak 146 benzersiz adın '
              'tamamı kayda alınır. 115 çağrı ve 31 atlama vardır. Hatalı ilerleme alanıyla başlatılan '
              'ilk prova yalnız kendi süreç ağacı kapatılarak durduruldu; sonuç olarak kullanılmadı. '
              'Kaynak ölçümü ve göç/güncelleme kanıtları önceki turdan korundu; eksik senaryolar '
              '`--only` ile ayrı izole çalıştırmalarda tamamlandı. '
              'Üretilen EXE `tests_hata/bin/` altında yereldir ve git dışında tutulur.', '',
              '## Derleme / test / clippy gerçek çıktıları', '']
    for r in read('verification', []):
        lines += ['### ' + r['name'], '', '`' + ' '.join(r['command']) + '`', '',
                  'Çıkış: `' + str(r['exit_code']) + '`' +
                  (', binary test kapısı işareti: `' + str(r['gate_path_in_binary']) + '`' if 'gate_path_in_binary' in r else ''), '']
        log = OUT / (r['name'] + '.log')
        if log.exists():
            lines += ['```text', '\n'.join(log.read_text(encoding='utf-8', errors='replace').splitlines()[-30:]), '```', '']
    issues = OUT / 'findings.md'
    if issues.exists():
        lines += ['## 📍 Yeniden üretilebilir bulgular', '', issues.read_text(encoding='utf-8'), '']
    errors = read('runner_errors', [])
    if errors:
        lines += ['## Runner istisnaları', '', '```json', json.dumps(errors, ensure_ascii=False, indent=2), '```']
    dest = ROOT / 'docs/sonuc/SONUC_T2.md'
    dest.write_text('\n'.join(lines) + '\n', encoding='utf-8', newline='\n')
    print(dest)


if __name__ == '__main__':
    main()
