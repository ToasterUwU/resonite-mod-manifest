"""
Utils for the other python scripts
"""

import subprocess
import sys
from typing import Any

from packaging.version import InvalidVersion, Version

# Sorts below every version `packaging` can parse.
_UNPARSEABLE = Version("0")


class ShellCommandError(RuntimeError):
    """A shell command exited with a non-zero status."""


def parse_version(version: str) -> tuple[int, Version, str]:
    """
    Build a sort key for a version string.

    `packaging` covers the normal cases, including pre-release suffixes such as
    "1.2.0-rc1". Anything it cannot parse sorts below every valid version, with
    the raw string as a tiebreaker. The key elements are always the same types,
    so two keys can always be compared against each other.

    Parameters:
    version: The version string, e.g. a key of a mod's "versions" object
    """

    try:
        return (1, Version(version), "")
    except InvalidVersion:
        return (0, _UNPARSEABLE, version)


def is_valid_version(version: str) -> bool:
    """
    Check whether a version string can be parsed at all.

    Parameters:
    version: The version string to check
    """

    try:
        Version(version)
    except InvalidVersion:
        return False
    return True


def should_show_mod(mod: dict[str, Any]) -> bool:
    """
    Checks if mod should be shown.

    Parameters:
    mod: The mod in question
    """

    # Exclude deprecated and file only
    if "flags" in mod and ("deprecated" in mod["flags"] or "file" in mod["flags"]):
        return False

    # # Don't show mods with only vulnerable versions
    # only_vulnerable_versions = True
    # for version in mod["versions"]:
    #     if "flags" not in version:
    #         only_vulnerable_versions = False
    #     else:
    #         if not any(flag.startswith("vulnerability:") for flag in version["flags"]):
    #             only_vulnerable_versions = False

    # if only_vulnerable_versions:
    #     return False

    # Only show mods with versions
    return bool(mod["versions"])


def map_mod_versions(versions: dict[str, Any], mod_guid: str) -> list[dict[str, Any]]:
    """
    Filters unwanted mod versions away, and turns them into a list

    Parameters:
    versions: The mod's versions
    mod_guid: The mod's GUID
    """

    versions_list: list[dict[str, Any]] = []
    for version_id, mod_version in versions.items():
        try:
            mod_version["id"] = Version(version_id)
            # Skip over listing pre-release versions
            if (
                "preRelease" in mod_version
                or mod_version["id"].is_prerelease
                or mod_version["id"].is_devrelease
            ):
                continue
            versions_list.append(mod_version)
        except (InvalidVersion, TypeError) as err:
            print(
                f"Failed to process [{mod_guid}/{version_id}], reason: {err}",
                file=sys.stderr,
            )

    return versions_list


def exec_shell(command: str) -> str:
    """
    Execute a shell command, and throws an exception if it fails, otherwise return the output.

    Parameters:
    command: The command to execute in the system shell
    """
    [status, output] = subprocess.getstatusoutput(command)
    if status != 0:
        raise ShellCommandError(f"{command} exited with status {status}, output: {output}")
    return output


def hex_to_int(s: str) -> int:
    """
    Convert a hex code to an int
    """
    return int(s.lstrip("#"), 16)
