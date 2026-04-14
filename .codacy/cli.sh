#!/usr/bin/env bash

set -euo pipefail
IFS=$'\n\t'

bin_name="codacy-cli-v2"

os_name="$(uname)"
arch="$(uname -m)"

case "$arch" in
    x86_64)
        arch="amd64"
        ;;
    x86)
        arch="386"
        ;;
    aarch64 | arm64)
        arch="arm64"
        ;;
esac

if [ -z "${CODACY_CLI_V2_TMP_FOLDER:-}" ]; then
    case "$os_name" in
        Linux)
            CODACY_CLI_V2_TMP_FOLDER="$HOME/.cache/codacy/codacy-cli-v2"
            ;;
        Darwin)
            CODACY_CLI_V2_TMP_FOLDER="$HOME/Library/Caches/Codacy/codacy-cli-v2"
            ;;
        *)
            CODACY_CLI_V2_TMP_FOLDER=".codacy-cli-v2"
            ;;
    esac
fi

version_file="$CODACY_CLI_V2_TMP_FOLDER/version.yaml"

fatal() {
    echo "Error: $*" >&2
    exit 1
}

sha256_cmd() {
    if command -v sha256sum >/dev/null 2>&1; then
        echo "sha256sum"
    elif command -v shasum >/dev/null 2>&1; then
        echo "shasum -a 256"
    else
        fatal "No sha256 utility found (sha256sum or shasum). Please install coreutils."
    fi
}

get_version_from_yaml() {
    if [ -f "$version_file" ]; then
        local version
        version="$(grep -o 'version: *"[^"]*"' "$version_file" | cut -d'"' -f2 || true)"
        if [ -n "${version:-}" ]; then
            echo "$version"
            return 0
        fi
    fi
    return 1
}

get_latest_version() {
    local response
    local version

    if [ -n "${GH_TOKEN:-}" ]; then
        response="$(
            curl -Lq --fail --silent --show-error \
                --header "Authorization: Bearer $GH_TOKEN" \
                "https://api.github.com/repos/codacy/codacy-cli-v2/releases/latest"
        )"
    else
        response="$(
            curl -Lq --fail --silent --show-error \
                "https://api.github.com/repos/codacy/codacy-cli-v2/releases/latest"
        )"
    fi

    handle_rate_limit "$response"

    version="$(echo "$response" | grep -m 1 tag_name | cut -d'"' -f4 || true)"

    if [ -z "${version:-}" ] || ! echo "$version" | grep -qE '^[vV]?[0-9]+'; then
        fatal "Failed to fetch a valid version from GitHub API. Response: $response"
    fi

    echo "$version"
}

handle_rate_limit() {
    local response="$1"

    if echo "$response" | grep -q "API rate limit exceeded"; then
        fatal "GitHub API rate limit exceeded. Please try again later."
    fi
}

verify_checksum() {
    local archive_path="$1"
    local checksum_file="$2"
    local tool
    local expected_sum
    local actual_sum

    tool="$(sha256_cmd)"

    if grep -Fq "$(basename "$archive_path")" "$checksum_file"; then
        (
            cd "$(dirname "$archive_path")" || exit 1
            $tool -c "$(basename "$checksum_file")"
        )
    else
        expected_sum="$(tr -d '\r\n' < "$checksum_file")"
        actual_sum="$($tool "$archive_path" | awk '{print $1}')"

        if [ "$expected_sum" != "$actual_sum" ]; then
            fatal "Checksum verification failed for $(basename "$archive_path")"
        fi
    fi
}

download_file() {
    local url="$1"
    local output_path="${2:-}"

    echo "Downloading from URL: $url"

    if command -v curl >/dev/null 2>&1; then
        if [ -n "$output_path" ]; then
            curl -# -LS --fail --silent --show-error "$url" -o "$output_path"
        else
            curl -# -LS --fail --silent --show-error "$url" -O
        fi
    elif command -v wget >/dev/null 2>&1; then
        if [ -n "$output_path" ]; then
            wget -q -O "$output_path" "$url"
        else
            wget -q "$url"
        fi
    else
        fatal "Could not find curl or wget. Please install one."
    fi
}

download() {
    local url="$1"
    local output_folder="$2"

    (
        cd "$output_folder" || exit 1
        download_file "$url"
    )
}

download_to_path() {
    local url="$1"
    local output_path="$2"

    download_file "$url" "$output_path"
}

download_cli() {
    local bin_folder="$1"
    local bin_path="$2"
    local version="$3"
    local suffix
    local remote_file
    local url
    local archive_path
    local checksum_url
    local checksum_path
    local tmp_extract_dir

    suffix="$(echo "$os_name" | tr '[:upper:]' '[:lower:]')"

    if [ -f "$bin_path" ]; then
        return 0
    fi

    echo "📥 Downloading CLI version $version..."

    remote_file="codacy-cli-v2_${version}_${suffix}_${arch}.tar.gz"
    url="https://github.com/codacy/codacy-cli-v2/releases/download/${version}/${remote_file}"
    archive_path="${bin_folder}/${remote_file}"
    checksum_url="${url}.sha256"
    checksum_path="${archive_path}.sha256"

    download "$url" "$bin_folder"
    download_to_path "$checksum_url" "$checksum_path"

    if [ ! -s "$checksum_path" ]; then
        fatal "Checksum file is empty or missing for ${remote_file}"
    fi

    verify_checksum "$archive_path" "$checksum_path"

    tmp_extract_dir="$(mktemp -d "${bin_folder}/extract.XXXXXX")"
    trap 'rm -rf "$tmp_extract_dir"' RETURN

    tar -xzf "$archive_path" -C "$tmp_extract_dir"

    if [ -f "${tmp_extract_dir}/${bin_name}" ]; then
        mv -f "${tmp_extract_dir}/${bin_name}" "$bin_path"
    else
        mv -f "${tmp_extract_dir}"/* "$bin_folder"/
    fi

    rm -f "$archive_path" "$checksum_path"
}

if [ -n "${CODACY_CLI_V2_VERSION:-}" ] && [ "${1:-}" = "update" ]; then
    echo "⚠️  Warning: Performing update with forced version $CODACY_CLI_V2_VERSION"
    echo "    Unset CODACY_CLI_V2_VERSION to use the latest version"
fi

if [ ! -f "$version_file" ] || [ "${1:-}" = "update" ]; then
    fetched_version=""
    echo "ℹ️  Fetching latest version..."
    fetched_version="$(get_latest_version)"
    mkdir -p "$CODACY_CLI_V2_TMP_FOLDER"
    echo "version: \"$fetched_version\"" > "$version_file"
fi

if [ -n "${CODACY_CLI_V2_VERSION:-}" ]; then
    version="$CODACY_CLI_V2_VERSION"
else
    if ! version="$(get_version_from_yaml)"; then
        fatal "Could not determine Codacy CLI version. Please set CODACY_CLI_V2_VERSION."
    fi
fi

bin_folder="${CODACY_CLI_V2_TMP_FOLDER}/${version}"
bin_path="${bin_folder}/${bin_name}"

mkdir -p "$bin_folder"

download_cli "$bin_folder" "$bin_path" "$version"
chmod +x "$bin_path"

run_command="$bin_path"
if [ ! -f "$run_command" ] || [ ! -x "$run_command" ]; then
    fatal "Codacy cli v2 binary could not be found or is not executable at $run_command."
fi

if [ "$#" -eq 1 ] && [ "${1:-}" = "download" ]; then
    echo "Codacy cli v2 download succeeded"
else
    "$run_command" "$@"
fi
