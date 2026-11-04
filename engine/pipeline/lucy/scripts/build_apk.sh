#!/usr/bin/env bash
set -euo pipefail
folio_root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$folio_root"
folio_sdk="${ANDROID_SDK_ROOT:-${ANDROID_HOME:-}}"
if [[ -z "$folio_sdk" ]]; then
  echo 'Set ANDROID_SDK_ROOT to an Android SDK with platforms;android-35 and build-tools;35.0.0.' >&2
  exit 1
fi
folio_bt="$folio_sdk/build-tools/35.0.0"
folio_jar="$folio_sdk/platforms/android-35/android.jar"
if ! python3 scripts/build_engines.py --verify >/dev/null 2>&1; then
  python3 scripts/build_engines.py "$@"
  python3 scripts/build_engines.py --verify
fi
python3 scripts/create_templates.py
# Prevent deleted classes and resources from surviving incremental APK assembly.
rm -rf build/classes build/generated build/dex
mkdir -p build/classes build/generated build/dex
"$folio_bt/aapt2" compile --dir app/src/main/res -o build/resources.zip
"$folio_bt/aapt2" link -o build/resources-and-assets.apk --manifest app/src/main/AndroidManifest.xml -I "$folio_jar" --java build/generated -A app/src/main/assets --min-sdk-version 26 --target-sdk-version 35 build/resources.zip
find app/src/main/java build/generated -name '*.java' | sort > build/sources.list
if command -v javac >/dev/null 2>&1; then
  javac --release 8 -encoding UTF-8 -classpath "$folio_jar" -d build/classes @build/sources.list
elif [[ -n "${FOLIO_ECJ_JAR:-}" ]]; then
  java -jar "$FOLIO_ECJ_JAR" -8 -encoding UTF-8 -classpath "$folio_jar" -d build/classes @build/sources.list
else
  echo 'Install JDK 17 (javac), or set FOLIO_ECJ_JAR to Eclipse ECJ 3.40.0.' >&2
  exit 1
fi
find build/classes -name '*.class' | sort > build/classes.list
"$folio_bt/d8" --release --min-api 26 --lib "$folio_jar" --output build/dex @build/classes.list
python3 - <<'PY'
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
with ZipFile('build/resources-and-assets.apk', 'r') as linked, ZipFile('build/base.apk', 'w', ZIP_DEFLATED, compresslevel=9) as output:
    if 'AndroidManifest.xml' not in linked.namelist():
        raise ValueError('Resource linking did not produce an Android manifest')
    for item in linked.infolist():
        output.writestr(item, linked.read(item.filename), compress_type=item.compress_type, compresslevel=9)
    for dex in sorted(Path('build/dex').glob('*.dex')):
        output.write(dex, dex.name)
with ZipFile('build/base.apk') as package:
    if not {'AndroidManifest.xml', 'resources.arsc', 'classes.dex'}.issubset(package.namelist()):
        raise ValueError('APK assembly omitted a required component')
PY
"$folio_bt/zipalign" -f -p 4 build/base.apk build/aligned.apk
folio_key="${FOLIO_KEYSTORE:-$folio_root/.cache/preview.jks}"
folio_alias="${FOLIO_KEY_ALIAS:-folio-preview}"
folio_pass="${FOLIO_KEYSTORE_PASSWORD:-android}"
if [[ ! -f "$folio_key" ]]; then
  mkdir -p "$(dirname "$folio_key")"
  keytool -genkeypair -keystore "$folio_key" -storepass "$folio_pass" -keypass "$folio_pass" -alias "$folio_alias" -keyalg RSA -keysize 3072 -validity 10000 -dname 'CN=Lucy Local Preview' -noprompt
fi
folio_version="$(python3 -c 'import xml.etree.ElementTree as E; print(E.parse("app/src/main/AndroidManifest.xml").getroot().get("{http://schemas.android.com/apk/res/android}versionName"))')"
folio_apk="$folio_root/build/Lucy-$folio_version.apk"
FOLIO_SIGN_PASSWORD="$folio_pass" "$folio_bt/apksigner" sign --ks "$folio_key" --ks-key-alias "$folio_alias" --ks-pass env:FOLIO_SIGN_PASSWORD --key-pass env:FOLIO_SIGN_PASSWORD --out "$folio_apk" build/aligned.apk
"$folio_bt/apksigner" verify --verbose "$folio_apk"
(cd build && sha256sum "$(basename "$folio_apk")") > build/SHA256SUMS.txt
echo "Built $folio_apk"
