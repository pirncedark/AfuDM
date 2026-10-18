"""Produce location/reproduction evidence from observed artifacts, without fixing products."""
import ast
import json
from common import ROOT, SOURCE, OUT


def line(path, needle):
    for number, text in enumerate(path.read_text(encoding='utf-8').splitlines(), 1):
        if needle in text:
            return number
    return 1


def generate():
    def read(name, default):
        path = OUT / (name + '.json')
        return json.loads(path.read_text(encoding='utf-8')) if path.exists() else default

    lines = []
    source = ast.parse((SOURCE / 'app.py').read_text(encoding='utf-8'))
    api = next(n for n in source.body if isinstance(n, ast.ClassDef) and n.name == 'Api')
    methods = {n.name: n.lineno for n in api.body if isinstance(n, ast.FunctionDef)}
    for row in read('bridge_rows', []):
        if 'skip' in row or (row.get('shape_equal') and not row['py'].get('exception')):
            continue
        name = row['name']
        files = [ROOT / 'app/src/bridge.rs', ROOT / 'app/src/kopru_g.rs', ROOT / 'app/src/kopru_h.rs']
        target = next((p for p in files if '"' + name + '"' in p.read_text(encoding='utf-8')), files[0])
        location = str(target.relative_to(ROOT)).replace('\\', '/') + ':' + str(line(target, '"' + name + '"'))
        lines += ['### 📍 ' + name + ' — ' + location, '',
                  'Yeniden üret: `python -B tests_hata/hepsi.py --only bridge`; kapı çağrısı: `' +
                  json.dumps({'name': name, 'args': row['args']}, ensure_ascii=False) + '`.', '',
                  'Python referansı: `P/app.py:' + str(methods.get(name, 1)) + '`. Beklenen Python biçimi: `' +
                  json.dumps(row['py']['shape'], ensure_ascii=False) + '`. Gerçek Rust biçimi: `' +
                  json.dumps(row['rs']['shape'], ensure_ascii=False) + '`.', '']
        if row['py'].get('exception'):
            lines += ['Python geçersiz girdide `' + row['py']['exception'] + '` yükseltiyor; helper bunu yakalar. '
                      'Bu satır Rust çökmesi veya geçerli girdi başarısızlığı anlamına gelmez.', '']

    fuzz = read('fuzz', {})
    rows = read('fuzz_rows', [])
    if fuzz:
        lines += ['### 📍 POST yanıt uyumsuzlukları', '',
                  'Yeniden üret: `python -B tests_hata/hepsi.py --only fuzz`. Girdiler `tests_hata/scenarios.py` '
                  'içindeki `cases` listesinde; tüm gerçek yanıtlar `tests_hata/rapor/fuzz_rows.json` içinde.', '',
                  '| Konum | Girdi | Beklenen Python | Gerçek Rust |', '|---|---|---|---|']
        for row in rows:
            if not row.get('difference'):
                continue
            path = ROOT / 'crates/afudm-api/src/lib.rs'
            for candidate in [path, ROOT / 'app/src/windows_rota.rs',
                              *[ROOT / ('crates/afudm-extras/src/' + part + '/mod.rs') for part in ('g1', 'g2', 'h')]]:
                if '"' + row['route'] + '"' in candidate.read_text(encoding='utf-8'):
                    path = candidate
                    break
            def compact(value):
                return json.dumps(value, ensure_ascii=False).replace('|', '\\|').replace('\n', ' ')
            lines.append('| `' + str(path.relative_to(ROOT)).replace('\\', '/') + ':' +
                         str(line(path, '"' + row['route'] + '"')) + '` | `' + row['route'] + '` / ' +
                         row['case'] + ' | ' + compact(row['py']) + ' | ' + compact(row['rs']) + ' |')
        lines += ['', 'HTTP durum 0 bir taşıma hatasıdır; tek başına PANIC veya süreç ölümü kanıtı değildir. '
                  'Dev gövde reddedilirken Python bağlantıyı kesebilir. Bu yüzden tüm farklar kesin ürün hatası diye sınıflandırılmaz.', '']

    for row in read('crash', []):
        if row.get('status') == 'GECTI':
            continue
        lines += ['### 📍 Çökme sonrası devam — ' + row['mode'] + ' / ' + row['side'], '',
                  'Konum: `crates/afudm-engine/src/args.rs:50` (Python karşılığı `P/core/daemon.py:148`). '
                  '`--save-session-interval=0` otomatik session kaydını kapatır; `.aria2` için 60 saniye ayrı ayardır.', '',
                  'Yeniden üret: `python -B tests_hata/hepsi.py --only crash`; 192 MiB yerel indirme %40 civarında '
                  'yalnız test PID ağacını zorla kapat, aynı veriyle yeniden başlat. Beklenen: aynı dosyanın kalan '
                  'parçaları indirilir ve SHA-256 eşleşir. Gerçek:', '', '```json',
                  json.dumps({k: row.get(k) for k in ('fraction', 'control_exists', 'session_bytes', 'integrity',
                                                    'sha_ok', 'range_after_restart', 'taskkill_exit')}, indent=2),
                  '```', '', 'Session kaydı gözlemi tek başına kök nedeni kanıtlamaz; üretim yeniden kurma yolu ayrıca incelenmeli.', '']
    (OUT / 'findings.md').write_text('\n'.join(lines) + '\n', encoding='utf-8', newline='\n')


if __name__ == '__main__':
    generate()
