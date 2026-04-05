#!/usr/bin/env bash
set -euo pipefail

# One-time keystore generator for stable APK updates.
# Produces all 4 values required by GitHub Actions secrets.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
OUTPUT_DIR="${1:-${PROJECT_ROOT}/.secrets/android}"
KEYSTORE_PATH="${OUTPUT_DIR}/release.keystore"

ALIAS="${ANDROID_KEY_ALIAS:-tgwsproxy-release}"
STORE_PASS="${ANDROID_KEYSTORE_PASSWORD:-$(openssl rand -hex 20)}"
ALIAS_PASS="${ANDROID_KEY_ALIAS_PASSWORD:-${STORE_PASS}}"

generate_keystore_local() {
  keytool -genkeypair \
    -v \
    -keystore "${KEYSTORE_PATH}" \
    -storetype PKCS12 \
    -alias "${ALIAS}" \
    -keyalg RSA \
    -keysize 2048 \
    -validity 10000 \
    -dname "CN=TG WS Proxy, OU=Mobile, O=TGWS, L=NA, S=NA, C=US" \
    -storepass "${STORE_PASS}" \
    -keypass "${ALIAS_PASS}"
}

generate_keystore_docker() {
  local mount_dir
  mount_dir="$(cd "${OUTPUT_DIR}" && pwd)"
  docker run --rm \
    -v "${mount_dir}:/work" \
    -w /work \
    eclipse-temurin:17-jdk \
    keytool -genkeypair \
      -v \
      -keystore release.keystore \
      -storetype PKCS12 \
      -alias "${ALIAS}" \
      -keyalg RSA \
      -keysize 2048 \
      -validity 10000 \
      -dname "CN=TG WS Proxy, OU=Mobile, O=TGWS, L=NA, S=NA, C=US" \
      -storepass "${STORE_PASS}" \
      -keypass "${ALIAS_PASS}"
}

mkdir -p "${OUTPUT_DIR}"

if [ -f "${KEYSTORE_PATH}" ]; then
  echo "Error: keystore already exists: ${KEYSTORE_PATH}"
  echo "Keep using this file and do not regenerate unless you know why."
  exit 1
fi

echo "Generating keystore: ${KEYSTORE_PATH}"
if command -v keytool >/dev/null 2>&1; then
  generate_keystore_local
elif command -v docker >/dev/null 2>&1; then
  echo "keytool not found locally, using Docker image eclipse-temurin:17-jdk..."
  generate_keystore_docker
else
  echo "Error: neither keytool nor docker found."
  echo "Install JDK (without Android Studio) or install Docker and retry."
  exit 1
fi

KEYSTORE_BASE64="$(python3 -c 'import base64,sys;print(base64.b64encode(open(sys.argv[1],"rb").read()).decode())' "${KEYSTORE_PATH}")"

echo
echo "=== GitHub Secrets (copy exactly) ==="
echo "ANDROID_KEYSTORE_BASE64=${KEYSTORE_BASE64}"
echo "ANDROID_KEYSTORE_PASSWORD=${STORE_PASS}"
echo "ANDROID_KEY_ALIAS=${ALIAS}"
echo "ANDROID_KEY_ALIAS_PASSWORD=${ALIAS_PASS}"
echo "=== End ==="
echo
echo "IMPORTANT:"
echo "1) Backup ${KEYSTORE_PATH} in a safe place (cloud vault + offline copy)."
echo "2) If this file is lost, future APK updates over installed app will break."
