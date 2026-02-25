"""
BEDROT Load Image - Config Management

Unified group registry. Every group is a name -> folder path mapping.
"""

import os
import json

CONFIG_FILE = "groups.json"
LEGACY_CONFIG_FILE = "linked_folders.json"
BASE_FOLDER = "BedRot_custom_image_load"
DEFAULT_GROUP = "Unsorted"


def _get_module_dir():
    """Get the directory containing this module."""
    return os.path.dirname(__file__)


def _get_config_path():
    """Get path to the groups config file."""
    return os.path.join(_get_module_dir(), CONFIG_FILE)


def _get_legacy_config_path():
    """Get path to the old linked_folders.json config."""
    return os.path.join(_get_module_dir(), LEGACY_CONFIG_FILE)


def _get_default_group_path():
    """Get the default Unsorted group path inside ComfyUI input."""
    import folder_paths
    return os.path.join(folder_paths.get_input_directory(), BASE_FOLDER, DEFAULT_GROUP)


def _get_base_input_path():
    """Get the base path for local BedRot image storage."""
    import folder_paths
    return os.path.join(folder_paths.get_input_directory(), BASE_FOLDER)


def _migrate_from_legacy():
    """
    Migrate from old linked_folders.json format to unified groups.json.
    Scans local subdirectories and merges with linked folders.
    Returns the merged group list.
    """
    groups = []
    seen_paths = set()
    seen_names = set()

    # Scan local subdirectories in BedRot_custom_image_load/
    base_path = _get_base_input_path()
    if os.path.isdir(base_path):
        try:
            for entry in os.scandir(base_path):
                if entry.is_dir():
                    abs_path = os.path.normpath(entry.path)
                    groups.append({"name": entry.name, "path": abs_path})
                    seen_paths.add(abs_path.lower())
                    seen_names.add(entry.name.lower())
        except OSError:
            pass

    # Read old linked folders config
    legacy_path = _get_legacy_config_path()
    if os.path.exists(legacy_path):
        try:
            with open(legacy_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                for folder in data.get("linked_folders", []):
                    norm_path = os.path.normpath(folder["path"])
                    name_lower = folder["name"].lower()
                    path_lower = norm_path.lower()
                    # Skip duplicates
                    if path_lower not in seen_paths and name_lower not in seen_names:
                        groups.append({"name": folder["name"], "path": norm_path})
                        seen_paths.add(path_lower)
                        seen_names.add(name_lower)
        except (json.JSONDecodeError, OSError):
            pass

    # Ensure Unsorted exists
    unsorted_path = os.path.normpath(_get_default_group_path())
    if DEFAULT_GROUP.lower() not in seen_names:
        os.makedirs(unsorted_path, exist_ok=True)
        groups.insert(0, {"name": DEFAULT_GROUP, "path": unsorted_path})

    return groups


def ensure_default_group():
    """Ensure the Unsorted group entry exists in config and on disk."""
    groups = load_groups()
    unsorted_path = os.path.normpath(_get_default_group_path())

    for g in groups:
        if g["name"].lower() == DEFAULT_GROUP.lower():
            # Entry exists, just ensure directory exists
            os.makedirs(g["path"], exist_ok=True)
            return

    # Add Unsorted entry
    os.makedirs(unsorted_path, exist_ok=True)
    groups.insert(0, {"name": DEFAULT_GROUP, "path": unsorted_path})
    save_groups(groups)


def load_groups():
    """
    Load all groups from config.

    Returns:
        list: List of dicts with 'name' and 'path' keys
    """
    config_path = _get_config_path()

    if os.path.exists(config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get("groups", [])
        except (json.JSONDecodeError, OSError):
            pass

    # Config doesn't exist -- migrate from legacy or create fresh
    groups = _migrate_from_legacy()
    save_groups(groups)
    return groups


def save_groups(groups):
    """
    Save groups to config file.

    Args:
        groups: List of dicts with 'name' and 'path' keys
    """
    config_path = _get_config_path()
    data = {"groups": groups}

    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)


def get_group_path(name):
    """
    Get the absolute path for a group by name.

    Args:
        name: Display name of the group

    Returns:
        str or None: Absolute path if found, None otherwise
    """
    groups = load_groups()
    name_lower = name.lower()
    for group in groups:
        if group["name"].lower() == name_lower:
            return group["path"]
    return None


def add_group(name, path):
    """
    Add a group to config.

    Args:
        name: Display name for the group
        path: Absolute path to the folder

    Returns:
        tuple: (success: bool, message: str)
    """
    name = name.strip()
    path = path.strip()

    if not name:
        return False, "Name is required"
    if not path:
        return False, "Path is required"

    if not os.path.isabs(path):
        return False, "Path must be absolute"
    if not os.path.exists(path):
        return False, f"Path does not exist: {path}"
    if not os.path.isdir(path):
        return False, f"Path is not a directory: {path}"

    normalized_path = os.path.normpath(path)
    name_lower = name.lower()

    groups = load_groups()

    # Check for duplicate name
    for group in groups:
        if group["name"].lower() == name_lower:
            return False, f"A group named '{name}' already exists"

    # Check for duplicate path
    for group in groups:
        if os.path.normpath(group["path"]).lower() == normalized_path.lower():
            return False, f"This path is already registered as '{group['name']}'"

    groups.append({"name": name, "path": normalized_path})
    save_groups(groups)
    return True, f"Group '{name}' added successfully"


def remove_group(name):
    """
    Remove a group by name (does not delete the folder on disk).

    Args:
        name: Display name of the group to remove

    Returns:
        tuple: (success: bool, message: str)
    """
    if name.lower() == DEFAULT_GROUP.lower():
        return False, "Cannot remove the Unsorted group"

    groups = load_groups()
    name_lower = name.lower()
    original_len = len(groups)

    groups = [g for g in groups if g["name"].lower() != name_lower]

    if len(groups) == original_len:
        return False, f"Group '{name}' not found"

    save_groups(groups)
    return True, f"Group '{name}' removed"


def rename_group(old_name, new_name):
    """
    Rename a group in config (does not rename the folder on disk).

    Args:
        old_name: Current display name
        new_name: New display name

    Returns:
        tuple: (success: bool, message: str)
    """
    old_name = old_name.strip()
    new_name = new_name.strip()

    if not new_name:
        return False, "New name is required"

    if old_name.lower() == DEFAULT_GROUP.lower():
        return False, "Cannot rename the Unsorted group"

    groups = load_groups()
    old_lower = old_name.lower()
    new_lower = new_name.lower()

    # Check new name doesn't conflict
    for group in groups:
        if group["name"].lower() == new_lower:
            return False, f"A group named '{new_name}' already exists"

    # Find and rename
    for group in groups:
        if group["name"].lower() == old_lower:
            group["name"] = new_name
            save_groups(groups)
            return True, f"Group renamed from '{old_name}' to '{new_name}'"

    return False, f"Group '{old_name}' not found"
