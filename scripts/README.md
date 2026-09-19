# AfuDM scripts/ — CI & release betikleri

Bu klasördeki `.ps1` dosyaları GitHub Actions (`../.github/workflows/`) ve elle
sürüm çıkışında kullanılır. Windows PowerShell 5.1'de çalışır; **saf ASCII** ile
yazılırlar (BOM'suz UTF-8 Türkçe karakterler PS 5.1'de string'i bozabilir).
Yeni betik eklerken bu kurala uy, Türkçe karakter / em-cizgi kullanma.

| Betik | İş |
|---|---|
| `test.ps1` | Tüm çevrimdışı testleri koşturur (`*_test.py`). `-ParseOnly` ile sadece sözdizimi kapısı. Ağ/gerçek indirme isteyen `smoke.py` ve `api_smoke.py` HARİÇ tutulur. |
| `surum_oku.py` | `core/surum.py` içindeki `SURUM = "X.Y.Z"` değerini stdout'a yazar. Tüm betik/workflow sürümü buradan okur (inline regex yok — PS 5.1 tırnak sorunları). |
| `build_exe.ps1` | Kökteki `AfuDM.spec` ile `python -m PyInstaller` çalıştırır, `dist/AfuDM.exe`yi köke kopyalar. AfuDM çalışıyorsa exe kilitli olur ve net bir hata mesajıyla durur. |
| `build_release.ps1` | `AfuDM.exe` yoksa `build_exe.ps1`'i çağırır, sonra `python paketle.py` ile paket üretir. `-Tag vX.Y.Z` verilirse `core/surum.py` ile eşleşmeyi **gate** olarak denetler (CI'ın asıl tag==HEAD gate'i `release.yml`'dedir). `-Full` → tam paket. |
| `verify_release.ps1` | `AfuDM-v*-win64.zip` içinde zorunlu dosyaların (AfuDM.exe, ui, extension, core, engine/aria2c.exe vb.) var olduğunu doğrular. |
| `smoke_test.ps1` | Zip'i geçici klasöre açar, kritik dosyaları ve yapıyı denetler (gerçek GUI koşusu CI dışıdır). |
| `make_checksums.ps1` | `<zip>.sha256` dosyası üretir: `<hash>  <zip-adi>`. |

## Elle sürüm çıkışı (CI yokken)

```powershell
powershell -ExecutionPolicy Bypass -File scripts\test.ps1
powershell -ExecutionPolicy Bypass -File scripts\build_release.ps1 -Tag v1.6.0
Compress-Archive -Path build_out\paket\AfuDM -DestinationPath build_out\AfuDM-v1.6.0-win64.zip -Force
powershell -ExecutionPolicy Bypass -File scripts\verify_release.ps1
powershell -ExecutionPolicy Bypass -File scripts\smoke_test.ps1
powershell -ExecutionPolicy Bypass -File scripts\make_checksums.ps1
```

Çıktı: `build_out/AfuDM-vX.Y.Z-win64.zip` + `.sha256` (artifact ve GitHub
Release'e yüklenir).