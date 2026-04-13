#!/usr/bin/env bash

# Strict bash safety
set -euo pipefail
IFS=$'\n\t'

# Set up paths first
bin_name="codacy-cli-v2"

# Determine OS-specific paths
os_name=$(uname)
arch=$(uname -m)

case "$arch" in
"x86_64")
  arch="amd64"
  ;;
"x86")
  arch="386"
  ;;
"aarch64"|"arm64")
  arch="arm64"
  ;;
esac

if [ -z "${CODACY_CLI_V2_TMP_FOLDER:-}" ]; then
    if [ "$(uname)" = "Linux" ]; then
        CODACY_CLI_V2_TMP_FOLDER="$HOME/.cache/codacy/codacy-cli-v2"
    elif [ "$(uname)" = "Darwin" ]; then
        CODACY_CLI_V2_TMP_FOLDER="$HOME/Library/Caches/Codacy/codacy-cli-v2"
    else
        CODACY_CLI_V2_TMP_FOLDER=".codacy-cli-v2"
    fi
fi

version_file="$CODACY_CLI_V2_TMP_FOLDER/version.yaml"

# fatal prints an error message to stderr and exits the script with status 1.
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

# get_version_from_yaml reads the version_file and echoes the value of the `version` field if present; returns a non-zero status if the file or version is missing.
get_version_from_yaml() {
    if [ -f "$version_file" ]; then
        local version
        version=$(grep -o 'version: *"[^"]*"' "$version_file" | cut -d'"' -f2 || true)
        if [ -n "${version:-}" ]; then
            echo "$version"
            return 0
        fi
    fi
    return 1
}

# get_latest_version fetches the latest Codacy CLI v2 release tag from GitHub and echoes the tag (e.g., "v1.2.3").
# get_latest_version exits with an error via fatal if a valid version cannot be obtained.
get_latest_version() {
    local response
    if [ -n "${GH_TOKEN:-}" ]; then
        response=$(curl -Lq --fail --silent --show-error --header "Authorization: Bearer $GH_TOKEN" "https://api.github.com/repos/codacy/codacy-cli-v2/releases/latest")
    else
        response=$(curl -Lq --fail --silent --show-error "https://api.github.com/repos/codacy/codacy-cli-v2/releases/latest")
    fi

    handle_rate_limit "$response"
    local version
    version=$(echo "$response" | grep -m 1 tag_name | cut -d'"' -f4 || true)

    if [ -z "${version:-}" ] || ! echo "$version" | grep -qE '^[vV]?[0-9]+'; then
        fatal "Failed to fetch a valid version from GitHub API. Response: $response"
    fi

    echo "$version"
}

# handle_rate_limit checks a GitHub API response for the "API rate limit exceeded" message and calls fatal with an explanatory error if the limit is exceeded.
handle_rate_limit() {
    local response="$1"
    if echo "$response" | grep -q "API rate limit exceeded"; then
          fatal "Error: GitHub API rate limit exceeded. Please try again later"
    fi
}

verify_checksum() {
  local archive_path="$1"
  local checksum_file="$2"
  local tool
  tool=$(sha256_cmd)

  # If checksum contains filename, use tool -c path; else compare strings
  if grep -q "$(basename "$archive_path")" "$checksum_file"; then
    ( cd "$(dirname "$archive_path")" && $tool -c "$(basename "$checksum_file")" )
  else
    local expected_sum actual_sum
    expected_sum=$(tr -d '\r\n' < "$checksum_file")
    actual_sum=$($tool "$archive_path" | awk '{print $1}')
    if [ "$expected_sum" != "$actual_sum" ]; then
      fatal "Checksum verification failed for $(basename "$archive_path")"
    fi
  fi
}

# download_file downloads the file at the given URL into the current directory and fails if neither `curl` nor `wget` is available.
download_file() {
    local url="$1"

    echo "Downloading from URL: ${url}"
    if command -v curl > /dev/null 2>&1; then
        curl -# -LS --fail --silent --show-error "$url" -O
    elif command -v wget > /dev/null 2>&1; then
        wget -q "$url"
    else
        fatal "Error: Could not find curl or wget, please install one."
    fi
}

# download downloads a file from the given URL into the specified output folder.
download() {
    local url="$1"
    local output_folder="$2"

    ( cd "$output_folder" && download_file "$url" )
}

# download_cli downloads and extracts the codacy-cli-v2 release tarball for the given version into the specified bin_folder when the expected binary at bin_path is absent.
download_cli() {
    # OS name lower case
    suffix=$(echo "$os_name" | tr '[:upper:]' '[:lower:]')

    local bin_folder="$1"
    local bin_path="$2"
    local version="$3"

    if [ ! -f "$bin_path" ]; then
        echo "📥 Downloading CLI version $version..."

        remote_file="codacy-cli-v2_${version}_${suffix}_${arch}.tar.gz"
        url="https://github.com/codacy/codacy-cli-v2/releases/download/${version}/${remote_file}"

        # Download archive and checksum, then verify before extracting
        download "$url" "$bin_folder"

        checksum_url="${url}.sha256"
        if command -v curl > /dev/null 2>&1; then
            curl -# -LS --fail --silent --show-error "$checksum_url" -o "${bin_folder}/${remote_file}.sha256" || true
        elif command -v wget > /dev/null 2>&1; then
            wget -q -O "${bin_folder}/${remote_file}.sha256" "$checksum_url" || true
        fi

        if [ -f "${bin_folder}/${remote_file}.sha256" ]; then
            verify_checksum "${bin_folder}/${remote_file}" "${bin_folder}/${remote_file}.sha256"
        else
            fatal "Checksum file not found for ${remote_file}; aborting for safety."
        fi

        # Extract safely to a temp dir then move atomically
        tmp_extract_dir=$(mktemp -d "${bin_folder}/extract.XXXXXX")
        tar xzf "${bin_folder}/${remote_file}" -C "$tmp_extract_dir"
        # Move discovered binary into bin_folder expected path
        if [ -f "$tmp_extract_dir/${bin_name}" ]; then
            mv -f "$tmp_extract_dir/${bin_name}" "$bin_path"
        else
            # Fallback: move everything, preserving expected layout
            mv -f "$tmp_extract_dir"/* "$bin_folder"/
        fi
        rm -rf "$tmp_extract_dir"
    fi
}

# Warn if CODACY_CLI_V2_VERSION is set and update is requested
if [ -n "${CODACY_CLI_V2_VERSION:-}" ] && [ "${1:-}" = "update" ]; then
    echo "⚠️  Warning: Performing update with forced version $CODACY_CLI_V2_VERSION"
    echo "    Unset CODACY_CLI_V2_VERSION to use the latest version"
fi

# Ensure version.yaml exists and is up to date
if [ ! -f "$version_file" ] || [ "${1:-}" = "update" ]; then
    echo "ℹ️  Fetching latest version..."
    version=$(get_latest_version)
    mkdir -p "$CODACY_CLI_V2_TMP_FOLDER"
    echo "version: \"$version\"" > "$version_file"
fi

# Set the version to use
if [ -n "${CODACY_CLI_V2_VERSION:-}" ]; then
    version="$CODACY_CLI_V2_VERSION"
else
    if ! version=$(get_version_from_yaml); then
        fatal "Could not determine Codacy CLI version. Please set CODACY_CLI_V2_VERSION."
    fi
fi

# Set up version-specific paths
bin_folder="${CODACY_CLI_V2_TMP_FOLDER}/${version}"

mkdir -p "$bin_folder"
bin_path="$bin_folder"/"$bin_name"

# Download the tool if not already installed
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
