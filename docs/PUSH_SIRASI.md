# Gönderim sırası

1. Konu dalı aç.
2. Değişiklikleri commit et; pre-commit kancaları denetlesin.
3. `git pull --rebase` çalıştır.
4. Push et; pre-push yerel testleri çalıştırır.
5. Pull request aç.
6. CI'ın yeşil olmasını bekle.
7. Pull request'i squash merge et.
8. Release Please sürüm PR'ı ve CHANGELOG'u hazırlar. Tag biçimi `v2.7.4` olarak korunur; tag mevcut `release.yml` akışını çalıştırıp exe'yi derler ve GitHub Release'i yayımlar.

Kurulum: `pip install pre-commit && pre-commit install`
