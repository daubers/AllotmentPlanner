#!/usr/bin/env bash
# Builds an installable Android APK from the Expo project: no Expo account, no cloud build.
# CI runs exactly this (.gitea/workflows/mobile.yml), and so can you.
#
# Needs Node 22, JDK 17 and the Android SDK (ANDROID_HOME) with its licences accepted. Gradle fetches
# the rest of the SDK it needs. The APK is signed with the debug key that Expo's template uses, which
# is fine for installing on your own phone and useless for the Play Store (see AM-63).
#
#   mobile/scripts/build-android.sh              # writes mobile/dist/allotment-<version>-<commit>.apk
#   ANDROID_ABIS=arm64-v8a,x86_64 mobile/scripts/build-android.sh   # add the emulator's architecture
set -euo pipefail
cd "$(dirname "$0")/.."

abis="${ANDROID_ABIS:-arm64-v8a}"   # every modern phone; building all four ABIs takes about 3x as long
out="${OUT_DIR:-dist}"
version="$(node -p "require('./app.json').expo.version")"
commit="$(git rev-parse --short HEAD 2>/dev/null || echo local)"

npm ci
# Regenerate the native project each time: android/ is not committed.
CI=1 npx expo prebuild --platform android --clean --no-install
# Gentle on memory: a CI runner shared with other jobs killed the Gradle daemon part-way through.
# One worker, Kotlin compiled inside Gradle's JVM rather than a second one, and a capped heap.
echo "Memory: $(free -m 2>/dev/null | awk '/^Mem:/ {print $2 " MB total, " $7 " MB available"}')"
(cd android && ./gradlew --no-daemon --max-workers=2 assembleRelease \
  "-PreactNativeArchitectures=${abis}" \
  -Pkotlin.compiler.execution.strategy=in-process \
  "-Dorg.gradle.jvmargs=-Xmx2g -XX:MaxMetaspaceSize=512m")

mkdir -p "$out"
apk="$out/allotment-${version}-${commit}.apk"
cp android/app/build/outputs/apk/release/app-release.apk "$apk"
echo "Built $apk ($(du -h "$apk" | cut -f1))"
