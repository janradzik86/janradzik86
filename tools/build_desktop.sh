#!/bin/sh
set -e
ROOT="$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)"
SP="${VIRTUAL_ENV:-$HOME/venv}/lib/python3.11/site-packages"
RT=/tmp/wolf-runtime
rm -rf "$RT"
mkdir -p "$RT/py" "$RT/assets"
cp "$ROOT/desktop/wolf.py" "$RT/wolf.py"
cp "$ROOT/assets/logo.png" "$RT/assets/logo.png"
cp -a "$SP/pygame" "$SP/pygame.libs" "$SP/pygame-"*.dist-info "$RT/py/"
cp -a "$SP/PIL" "$SP/pillow.libs" "$SP/pillow-"*.dist-info "$RT/py/"
cp -a "$SP/cryptography" "$SP/cryptography-"*.dist-info "$RT/py/"
cp -a "$SP/cffi" "$SP/cffi-"*.dist-info "$SP/pycparser" "$SP/pycparser-"*.dist-info "$RT/py/"
cp -a "$SP"/_cffi_backend*.so "$RT/py/"
find "$RT" -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
tar -czf /tmp/payload.tgz -C "$RT" .
cd /tmp
ld -r -b binary -o /tmp/payload.o payload.tgz
mkdir -p "$ROOT/dist"
gcc -O2 -s -o "$ROOT/dist/CzarneWilkiPrawdy" "$ROOT/tools/launcher.c" /tmp/payload.o
chmod +x "$ROOT/dist/CzarneWilkiPrawdy"
echo "OK $ROOT/dist/CzarneWilkiPrawdy"
