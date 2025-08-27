import hashlib
import json
import os
import re
import time

import requests


ignore_list = ["net.eia485.GetItemLink"]


def check_github_rate_limit(response):
    remaining = int(response.headers.get("X-RateLimit-Remaining", "1"))
    reset = int(response.headers.get("X-RateLimit-Reset", "0"))
    if remaining == 0:
        wait_time = max(0, reset - int(time.time()))
        print(f"GitHub API rate limit reached. Sleeping for {wait_time} seconds...")
        time.sleep(wait_time + 1)


def get_github_headers():
    token = os.environ.get("GH_TOKEN")
    headers = {}
    if token:
        headers["Authorization"] = f"token {token}"
    return headers


def github_request_with_retry(url, headers=None):
    while True:
        response = requests.get(url, headers=headers)
        if (
            response.status_code == 403
            and "X-RateLimit-Remaining" in response.headers
            and response.headers.get("X-RateLimit-Remaining") == "0"
        ):
            reset = int(response.headers.get("X-RateLimit-Reset", "0"))
            wait_time = max(0, reset - int(time.time()))
            print(f"GitHub API rate limit reached. Sleeping for {wait_time} seconds...")
            time.sleep(wait_time + 1)
            continue
        return response


def check_for_updates(info: dict):
    if not info["sourceLocation"].startswith("https://github.com/"):
        print(f"Skipping non-github mod: {info['name']}")  # Skipping non-github mod
        return info

    if info["id"] in ignore_list:
        print(f"Skipping ignored mod: {info['name']}")
        return info

    # Extract owner/repo from sourceLocation
    parts = info["sourceLocation"].rstrip("/").split("/")
    owner = parts[-2]
    repo = parts[-1]
    api_url = f"https://api.github.com/repos/{owner}/{repo}/releases"

    headers = get_github_headers()
    try:
        response = github_request_with_retry(api_url, headers=headers)
        check_github_rate_limit(response)
        response.raise_for_status()
        releases = response.json()
    except Exception as e:
        print(
            f"Failed to fetch releases for {info['name']}: {e}"
        )  # Failed to fetch releases
        return info

    if "versions" not in info:
        info["versions"] = {}  # Initialize versions dict if missing

    for release in releases:
        tag = release.get("tag_name")
        if not tag or not re.search(r"\d", tag):
            continue  # Ignore tags with no numbers

        stripped_tag = tag.lstrip("Vv")  # Remove leading V/v from tag

        # Strip all pre-release descriptors from tag
        # Pre-release descriptors: rc, b, beta, alpha, preview, dev, test, canary, exp, experimental
        base_version = re.match(
            r"^(\d+(?:\.\d+)*)(?:-?(rc|b|beta|alpha|preview|dev|test|canary|exp|experimental)[\.-]?\d*)?$",
            stripped_tag,
            re.IGNORECASE,
        )
        if base_version:
            base = base_version.group(1)
            if base.count(".") >= 3:
                continue  # Ignore tags with 4 or more version digits
        else:
            base = stripped_tag.split("-")[0]
            if base.count(".") >= 3:
                continue  # Ignore tags with 4 or more version digits

        version_parts = base.split(".")
        if len(version_parts) < 3:
            normalized_tag = ".".join(
                version_parts + ["0"] * (3 - len(version_parts))
            )  # Pad to 3 digits
        else:
            normalized_tag = ".".join(version_parts)

        is_prerelease = bool(
            re.search(
                r"-(rc|b|beta|alpha|preview|dev|test|canary|exp|experimental)",
                stripped_tag,
                re.IGNORECASE,
            )
        )
        if is_prerelease and normalized_tag in info["versions"]:
            continue  # Skip pre-release if normal release exists

        if normalized_tag in info["versions"]:
            continue  # Already present

        release_url = release.get("html_url")  # Get release URL

        artifacts = []  # List to store artifact info
        asset_list = list(release.get("assets", []))  # Get asset list
        archive_exts = (".zip", ".tar.gz", ".tar", ".7z", ".rar")  # Archive extensions

        previous_versions = [
            v for v in info["versions"].keys()
        ]  # Get previous version tags
        previous_versions_sorted = sorted(
            previous_versions,
            key=lambda v: [int(x) if x.isdigit() else x for x in v.split(".")],
            reverse=True,
        )  # Sort previous versions
        previous_artifact_info = {}  # Dict to store previous artifact info
        for prev_version in previous_versions_sorted:
            for prev_artifact in info["versions"][prev_version].get("artifacts", []):
                prev_name = os.path.basename(prev_artifact.get("url", ""))
                if prev_name:
                    if prev_name not in previous_artifact_info:
                        previous_artifact_info[prev_name] = {
                            k: v
                            for k, v in prev_artifact.items()
                            if k not in ("url", "sha256")
                        }  # Copy special args from previous artifact

        for asset in asset_list:
            asset_url = asset.get("browser_download_url")
            asset_name = asset.get("name", "")
            # Ignore archive files entirely
            if asset_name.lower().endswith(archive_exts):
                continue

            try:
                asset_resp = github_request_with_retry(asset_url, headers=headers)
                check_github_rate_limit(asset_resp)
                asset_resp.raise_for_status()
                sha256 = hashlib.sha256(asset_resp.content).hexdigest()
            except Exception as e:
                print(
                    f"Failed to download asset {asset_url}: {e}"
                )  # Failed to download asset
                continue

            artifact_entry = {"url": asset_url, "sha256": sha256}

            prev_info = previous_artifact_info.get(asset_name)
            if prev_info:
                artifact_entry.update(
                    prev_info
                )  # Inherit previous special args if present
            else:
                modname = info.get("name", "").lower()
                is_library = info.get("category", "").lower() == "libraries"
                if (
                    asset_name.lower().endswith(".dll")
                    and modname not in asset_name.lower()
                ):
                    artifact_entry["installLocation"] = (
                        "/rml_libs"  # DLL dependency logic
                    )
                if is_library:
                    artifact_entry["installLocation"] = (
                        "/rml_libs"  # Libraries category
                    )
                config_exts = (
                    ".json",
                    ".toml",
                    ".yaml",
                    ".yml",
                    ".ini",
                    ".conf",
                    ".cfg",
                    ".txt",
                    ".xml",
                    ".properties",
                    ".env",
                    ".config",
                )
                if asset_name.lower().endswith(config_exts):
                    artifact_entry["installLocation"] = (
                        "/rml_config"  # Config file logic
                    )

            artifacts.append(artifact_entry)

        if artifacts:
            info["versions"][normalized_tag] = {
                "releaseUrl": release_url,
                "artifacts": artifacts,
            }  # Add artifacts to version entry

    # Sort versions: newest (highest) first, oldest last
    if "versions" in info and info["versions"]:

        def version_key(v):
            parts = v.split(".")
            return tuple(str(p) for p in parts)

        info["versions"] = dict(
            sorted(
                info["versions"].items(), key=lambda x: version_key(x[0]), reverse=True
            )
        )  # Sort versions

    return info  # Return updated info


root_folder = "manifest"


for author_entry in os.scandir(root_folder):
    if author_entry.is_dir():
        for mod_entry in os.scandir(author_entry.path):
            if mod_entry.is_dir():
                info_path = os.path.join(mod_entry.path, "info.json")
                with open(info_path, "r") as f:
                    info = json.load(f)

                print(f"Processing mod: {info.get('name', mod_entry.name)}")
                new_info = check_for_updates(info)

                with open(info_path, "w", encoding="utf-8") as f:
                    json.dump(new_info, f, indent=4)
