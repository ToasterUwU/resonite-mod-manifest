import json

import requests

response = requests.get(
    "https://raw.githubusercontent.com/resonite-modding-group/resonite-mod-manifest/refs/heads/main/manifest.json"
)
upstream_manifest = json.loads(response.text)

with open("manifest.json", "r") as f:
    local_manifest = json.load(f)

only_upstream = {}
only_local = {}

upstream_outdated = {}


def parse_version(v):
    parts = v.split(".")
    result = []
    for x in parts[:3]:
        try:
            result.append(int(x))
        except ValueError:
            result.append(x)
    while len(result) < 3:
        result.append(0)
    return tuple(result)


for author in upstream_manifest["objects"]:
    for mod in sorted(upstream_manifest["objects"][author]["entries"]):
        if author not in local_manifest["objects"]:
            only_upstream[mod] = upstream_manifest["objects"][author]["entries"][mod]
            only_upstream[mod]["author"] = list(upstream_manifest["objects"][author]["author"].keys())[0]
            only_upstream[mod]["author_id"] = author
        elif mod not in sorted(local_manifest["objects"][author]["entries"]):
            only_upstream[mod] = upstream_manifest["objects"][author]["entries"][mod]
            only_upstream[mod]["author"] = list(upstream_manifest["objects"][author]["author"].keys())[0]
            only_upstream[mod]["author_id"] = author


for author in local_manifest["objects"]:
    for mod in sorted(local_manifest["objects"][author]["entries"]):
        if author not in upstream_manifest["objects"]:
            only_local[mod] = local_manifest["objects"][author]["entries"][mod]
            only_local[mod]["author"] = list(local_manifest["objects"][author]["author"].keys())[0]
            only_local[mod]["author_id"] = author
        elif mod not in sorted(upstream_manifest["objects"][author]["entries"]):
            only_local[mod] = local_manifest["objects"][author]["entries"][mod]
            only_local[mod]["author"] = list(local_manifest["objects"][author]["author"].keys())[0]
            only_local[mod]["author_id"] = author
        else:
            local_versions = local_manifest["objects"][author]["entries"][mod].get("versions", {})
            upstream_versions = upstream_manifest["objects"][author]["entries"][mod].get("versions", {})
            if local_versions and upstream_versions:
                local_latest = max(local_versions.keys(), key=parse_version)
                upstream_latest = max(upstream_versions.keys(), key=parse_version)
                if parse_version(local_latest) > parse_version(upstream_latest):
                    upstream_outdated[mod] = local_manifest["objects"][author]["entries"][mod]
                    upstream_outdated[mod]["author"] = list(local_manifest["objects"][author]["author"].keys())[0]
                    upstream_outdated[mod]["author_id"] = author


with open("README_TEMPLATE.md", "r") as f:
    readme_template = f.read()

local_only_formatted = ""
for id, data in only_local.items():
    local_only_formatted += (
        f"- [{data['name']}]({data['sourceLocation']}) (by {data['author']})\n"
    )

readme_template = readme_template.replace("%MISSING_UPSTREAM%", local_only_formatted)

upstream_outdated_formatted = ""
for id, data in upstream_outdated.items():
    local_versions = data.get("versions", {})
    upstream_versions = upstream_manifest["objects"][data["author_id"]]["entries"][id].get("versions", {})
    local_latest = max(local_versions.keys(), key=parse_version) if local_versions else "?"
    upstream_latest = max(upstream_versions.keys(), key=parse_version) if upstream_versions else "?"
    upstream_outdated_formatted += (
        f"- [{data['name']}]({data['sourceLocation']}) (by {data['author']}) "
        f" - {local_latest} vs {upstream_latest}\n"
    )

readme_template = readme_template.replace("%OUTDATED_UPSTREAM%", upstream_outdated_formatted)

with open("README.md", "w+") as f:
    f.write(readme_template)

print("Only in local manifest:")
print(local_only_formatted)

print("Only in upstream manifest:")
print(only_upstream)

print("Outdated upstream mods:")
print(upstream_outdated_formatted)