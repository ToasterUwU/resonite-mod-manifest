import hashlib
import json
import os
import re
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed


def get_github_headers():
    token = os.environ.get("GH_TOKEN")
    headers = {}
    if token:
        headers["Authorization"] = f"token {token}"
    return headers


def resolve_correct_url_and_hash(url, version_key):
    # Regex to extract owner, repo, tag, filename
    match = re.match(
        r"https://github\.com/([^/]+)/([^/]+)/releases/download/([^/]+)/(.+)", url
    )
    if not match:
        return None, None, None

    owner, repo, wrong_tag, filename = match.groups()
    api_url = f"https://api.github.com/repos/{owner}/{repo}/releases"

    headers = get_github_headers()
    try:
        response = requests.get(api_url, headers=headers)
        response.raise_for_status()
        releases = response.json()
    except Exception as e:
        print(f"  [Auto-Fix] Failed to fetch releases for {owner}/{repo}: {e}")
        return None, None, None

    for release in releases:
        tag = release.get("tag_name", "")
        # Check if the tag matches the version key (e.g. 2.2.1 is in v2.2.1-b)
        stripped = tag.lstrip("vV")
        if stripped.startswith(version_key) or version_key in tag:
            # We found a candidate release!
            for asset in release.get("assets", []):
                if asset.get("name") == filename:
                    # Found the correct asset!
                    new_url = asset.get("browser_download_url")
                    new_release_url = release.get("html_url")

                    # Now fetch the file to get the hash
                    try:
                        resp = requests.get(new_url, stream=True, timeout=30)
                        resp.raise_for_status()
                        h = hashlib.sha256()
                        for chunk in resp.iter_content(chunk_size=8192):
                            h.update(chunk)
                        return new_url, new_release_url, h.hexdigest()
                    except Exception as e:
                        print(f"  [Auto-Fix] Failed to download {new_url}: {e}")
                        return None, None, None
    return None, None, None


def verify_and_update_mod(info_path):
    with open(info_path, "r", encoding="utf-8") as f:
        try:
            info = json.load(f)
        except json.JSONDecodeError:
            print(f"Error parsing {info_path}")
            return False

    modified = False

    if "versions" not in info:
        return False

    for version, v_data in info["versions"].items():
        if "artifacts" not in v_data:
            continue

        for artifact in v_data["artifacts"]:
            url = artifact.get("url")
            stored_sha256 = artifact.get("sha256")
            if not url or not stored_sha256:
                continue

            try:
                response = requests.get(url, stream=True, timeout=30)

                if response.status_code == 404 and url.startswith(
                    "https://github.com/"
                ):
                    print(
                        f"[{info.get('name', 'Unknown')}] {version} 404 Not Found for {url}. Attempting to auto-fix..."
                    )
                    new_url, new_release_url, new_sha256 = resolve_correct_url_and_hash(
                        url, version
                    )
                    if new_url and new_sha256:
                        print(f"  -> Fixed URL: {new_url}")
                        artifact["url"] = new_url
                        artifact["sha256"] = new_sha256
                        if (
                            new_release_url
                            and v_data.get("releaseUrl") != new_release_url
                        ):
                            v_data["releaseUrl"] = new_release_url
                        modified = True
                    else:
                        print("  -> Could not auto-fix URL.")
                    continue

                response.raise_for_status()

                h = hashlib.sha256()
                for chunk in response.iter_content(chunk_size=8192):
                    h.update(chunk)
                computed_sha256 = h.hexdigest()

                if computed_sha256 != stored_sha256:
                    print(
                        f"[{info.get('name', 'Unknown')}] {version} Hash mismatch for {url}: {stored_sha256} -> {computed_sha256}"
                    )
                    artifact["sha256"] = computed_sha256
                    modified = True
            except requests.exceptions.RequestException as e:
                # Catch other request exceptions
                print(
                    f"[{info.get('name', 'Unknown')}] {version} Failed to fetch {url}: {e}"
                )

    if modified:
        with open(info_path, "w", encoding="utf-8") as f:
            json.dump(info, f, indent=4)
        return True
    return False


def main():
    root_folder = "manifest"
    info_paths = []

    if not os.path.exists(root_folder):
        return

    for author_entry in os.scandir(root_folder):
        if author_entry.is_dir():
            for mod_entry in os.scandir(author_entry.path):
                if mod_entry.is_dir():
                    info_path = os.path.join(mod_entry.path, "info.json")
                    if os.path.exists(info_path):
                        info_paths.append(info_path)

    updated_count = 0
    with ThreadPoolExecutor(max_workers=10) as executor:
        future_to_path = {
            executor.submit(verify_and_update_mod, path): path for path in info_paths
        }
        for future in as_completed(future_to_path):
            try:
                if future.result():
                    updated_count += 1
            except Exception:
                pass

    print(f"Verification complete. Updated {updated_count} files.")


if __name__ == "__main__":
    main()
