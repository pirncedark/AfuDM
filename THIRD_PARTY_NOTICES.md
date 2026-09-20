# Third-party software / Üçüncü taraf yazılımlar

AfuDM bundles or optionally downloads third-party software.
Each component remains subject to its own license.

AfuDM bazı üçüncü taraf yazılımları paketinde taşır veya
istek üzerine indirir. Her bileşen kendi lisansına tabidir.

### aria2 1.37.0

- Location: `engine/aria2c.exe`
- Distribution: bundled with AfuDM Core and Full packages
- License: GPL-2.0-or-later with OpenSSL exception
- Source: https://github.com/aria2/aria2/tree/release-1.37.0
- License text: `licenses/aria2-COPYING.txt`
- Binary: unmodified upstream Windows build
### yt-dlp

- Location: `engine/yt-dlp.exe`
- Distribution: downloaded on demand (Settings > Engines)
- License: The Unlicense
- Source: https://github.com/yt-dlp/yt-dlp
- License text: `licenses/yt-dlp-LICENSE.txt`
- Binary: unmodified upstream Windows build

### FFmpeg

- Location: `engine/ffmpeg.exe`
- Distribution: downloaded on demand (Settings > Engines)
- License: GPL-3.0-or-later
- Source: https://github.com/BtbN/FFmpeg-Builds
- License text: `licenses/ffmpeg-LICENSE.txt`
- Binary: unmodified upstream Windows build (`ffmpeg-master-latest-win64-gpl.zip`)
### Python Runtime

Bundled inside `AfuDM.exe`. License texts are in the `licenses/` directory.

- **Python**: PSF License (`licenses/Python-LICENSE.txt`) - https://www.python.org/
- **pywebview**: BSD-3-Clause (`licenses/pywebview-LICENSE.txt`) - https://github.com/r0x0r/pywebview
- **pythonnet**: MIT License (`licenses/pythonnet-LICENSE.txt`) - https://github.com/pythonnet/pythonnet
- **pystray**: LGPL-3.0-only (`licenses/pystray-LICENSE.txt`) - https://github.com/moses-palmer/pystray
- **Pillow**: MIT-CMU (`licenses/Pillow-LICENSE.txt`) - https://github.com/python-pillow/Pillow
- **bottle**: MIT License (`licenses/bottle-LICENSE.txt`) - https://github.com/bottlepy/bottle
