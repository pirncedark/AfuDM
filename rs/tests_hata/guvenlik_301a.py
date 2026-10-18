"""301A QR regresyonu: yalniz izole test exe'si, gecici veri ve rastgele portlar."""
import tempfile
from urllib.parse import urlsplit, parse_qs
from common import App, request


def main():
    with tempfile.TemporaryDirectory(prefix='afudm301a_') as tmp:
        app = App('rs', tmp)
        try:
            app.start()
            opened = app.call('telefon_ayarla', [True])
            value = opened['json']
            assert value.get('ok') and value.get('acik'), 'LAN acilamadi'
            url = value['adres']
            parts = urlsplit(url)
            params = parse_qs(parts.query)
            assert 'k' not in params and app.token not in url, 'QR kalici kimlik tasiyor'
            code = params['code'][0]
            assert len(code) == 64
            host = parts.hostname
            port = parts.port
            assert port not in (6810, 6811)
            assert request(port, '/pair?code=wrong', host=host)['status'] == 403
            paired = request(port, '/pair?code=' + code, host=host)
            assert paired['status'] == 200 and paired['json']['token'] == app.token
            assert request(port, '/pair?code=' + code, host=host)['status'] == 403
            assert request(port, '/snapshot', token=paired['json']['token'], host=host)['status'] == 200
            again = app.call('telefon_durumu', [])['json']['adres']
            assert parse_qs(urlsplit(again).query)['code'][0] != code
            assert request(port, '/pair', host=host)['status'] == 403
            assert request(port, '/pair')['status'] == 403
            print('QR_LAN: GECTI (kalici token yok; yanlis kod, tek kullanim, yeni kod, API kimligi, kapali yerel esleme)', flush=True)
        finally:
            app.close()
            assert not app.owned(), 'Izole test sureci kapanmadi'
            print('CLEANUP: GECTI (yalniz sahip olunan test surecleri)', flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
