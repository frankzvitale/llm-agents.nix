#!/usr/bin/env nix
#! nix shell --inputs-from .# nixpkgs#python3 --command python3

"""Update CoCo from Snowflake's stable release manifest."""

import sys
from pathlib import Path
from typing import Any
from urllib.parse import quote

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

from updater import fetch_json, fetch_text, load_hashes, save_hashes
from updater.hash import hex_to_sri

BASE_URL = "https://sfc-repo.snowflakecomputing.com/cortex-code-cli/a4643c4278"
HASHES_FILE = Path(__file__).parent / "hashes.json"
PLATFORMS = {
    "x86_64-linux": ("linux", "amd64"),
    "aarch64-linux": ("linux", "arm64"),
    "aarch64-darwin": ("darwin", "arm64"),
}


def main() -> None:
    """Update hashes.json to the release selected by the stable pointer."""
    current = load_hashes(HASHES_FILE)["version"]
    latest = fetch_text(f"{BASE_URL}/stable_version.txt").strip()

    print(f"Current: {current}, Latest: {latest}")
    # Snowflake may move the stable pointer backwards when rolling back a release.
    if current == latest:
        print("Already up to date")
        return

    encoded_version = quote(latest, safe="")
    response = fetch_json(f"{BASE_URL}/{encoded_version}/manifest.json")
    if not isinstance(response, dict):
        msg = "Release manifest is not a JSON object"
        raise TypeError(msg)
    manifest: dict[str, Any] = response

    if manifest.get("version") != latest:
        msg = (
            f"Manifest version does not match stable pointer: {manifest.get('version')}"
        )
        raise ValueError(msg)

    packages = manifest.get("packages")
    if not isinstance(packages, dict):
        msg = "Release manifest has no packages object"
        raise TypeError(msg)

    hashes: dict[str, str] = {}
    for system, (os_name, arch) in PLATFORMS.items():
        os_packages = packages.get(os_name)
        if not isinstance(os_packages, dict):
            msg = f"Release manifest has no packages for {os_name}"
            raise TypeError(msg)

        package = os_packages.get(arch)
        if not isinstance(package, dict):
            msg = f"Release manifest has no package for {os_name}-{arch}"
            raise TypeError(msg)

        expected_name = f"coco-{latest}-{os_name}-{arch}.tar.gz"
        if package.get("name") != expected_name:
            msg = f"Unexpected artifact for {system}: {package.get('name')}"
            raise ValueError(msg)

        checksum = package.get("checksum")
        if not isinstance(checksum, str):
            msg = f"Release manifest has no checksum for {system}"
            raise TypeError(msg)

        hashes[system] = hex_to_sri(checksum)
        print(f"  {system}: {hashes[system]}")

    save_hashes(HASHES_FILE, {"version": latest, "hashes": hashes})
    print(f"Updated to {latest}")


if __name__ == "__main__":
    main()
