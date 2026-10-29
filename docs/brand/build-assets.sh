#!/bin/sh
# Renders the chosen logo (option B, the map pin) into the app's icon files.
# Needs macOS (Chrome for rendering, sips for resizing). Run from the repository root:
#   sh docs/brand/build-assets.sh
set -e
SRC=docs/brand/source
TMP=$(mktemp -d)
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

# render NAME  -> $TMP/NAME.png at 1024 px with a transparent background
render() {
  printf '<!doctype html><body style="margin:0;background:transparent"><img src="file://%s/%s.svg" width="1024" height="1024" style="display:block">' "$PWD/$SRC" "$1" > "$TMP/$1.html"
  "$CHROME" --headless=new --disable-gpu --hide-scrollbars --force-device-scale-factor=1 \
    --default-background-color=00000000 --window-size=1024,1024 --virtual-time-budget=3000 \
    --screenshot="$TMP/$1.png" "file://$TMP/$1.html" >/dev/null 2>&1
}
size() { sips -z "$3" "$3" "$TMP/$1.png" --out "$2" >/dev/null; }

for n in icon-square foreground background monochrome splash favicon; do render $n; done

# Phone app (Expo)
cp "$TMP/icon-square.png" mobile/assets/icon.png
cp "$TMP/splash.png" mobile/assets/splash-icon.png
size foreground mobile/assets/android-icon-foreground.png 512
size background mobile/assets/android-icon-background.png 512
size monochrome mobile/assets/android-icon-monochrome.png 432
size favicon mobile/assets/favicon.png 48

# Web app
mkdir -p frontend/public
cp docs/brand/source/favicon.svg frontend/public/favicon.svg
size icon-square frontend/public/apple-touch-icon.png 180
echo "done; temp files in $TMP"
