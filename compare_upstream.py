import json

import requests

response = requests.get(
    "https://raw.githubusercontent.com/resonite-modding-group/resonite-mod-manifest/refs/heads/main/manifest.json"
)
upstream_manifest = json.loads(response.text)

with open("manifest.json", "r") as f:
    local_manifest = json.load(f)

only_upstream = []
only_local = []

for author in upstream_manifest["objects"]:
    for mod in upstream_manifest["objects"][author]["entries"]:
        if author not in local_manifest["objects"]:
            only_upstream.append(mod)
        elif mod not in local_manifest["objects"][author]["entries"]:
            only_upstream.append(mod)


for author in local_manifest["objects"]:
    for mod in local_manifest["objects"][author]["entries"]:
        if author not in upstream_manifest["objects"]:
            only_local.append(mod)
        elif mod not in upstream_manifest["objects"][author]["entries"]:
            only_local.append(mod)


sorted_upstream = sorted(only_upstream)
sorted_local = sorted(only_local)

print("Mods only in upstream:")
print("\n".join(sorted_upstream))

print("\n")

print("Mods only in local:")
print("\n".join(sorted_local))
