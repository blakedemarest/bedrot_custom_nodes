"""
BEDROT Load Image - Config Management

Handles persistence of linked external folders.
"""

import os
import json

CONFIG_FILE = "linked_folders.json"


def _get_config_path():
    """Get path to the config file in the same directory as this module."""
    return os.path.join(os.path.dirname(__file__), CONFIG_FILE)


def _get_base_input_path():
    """Get the base path for local BedRot image storage."""
    import folder_paths
    return os.path.join(folder_paths.get_input_directory(), "BedRot_custom_image_load")


def _get_local_group_names():
    """Get set of local group names (subdirectories in base folder)."""
    base_path = _get_base_input_path()
    if not os.path.exists(base_path):
        return set()

    names = set()
    try:
        for entry in os.scandir(base_path):
            if entry.is_dir():
                names.add(entry.name.lower())
    except OSError:
        pass
    return names


def load_linked_folders():
    """
    Load linked folders from config file.

    Returns:
        list: List of dicts with 'name' and 'path' keys
    """
    config_path = _get_config_path()
    if not os.path.exists(config_path):
        return []

    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get("linked_folders", [])
    except (json.JSONDecodeError, OSError):
        return []


def save_linked_folders(folders):
    """
    Save linked folders to config file.

    Args:
        folders: List of dicts with 'name' and 'path' keys
    """
    config_path = _get_config_path()
    data = {"linked_folders": folders}

    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)


def get_all_linked_names():
    """
    Get set of all linked folder names (lowercase for comparison).

    Returns:
        set: Set of lowercase linked folder names
    """
    folders = load_linked_folders()
    return {f["name"].lower() for f in folders}


def get_linked_folder_path(name):
    """
    Get the absolute path for a linked folder by name.

    Args:
        name: Display name of the linked folder

    Returns:
        str or None: Absolute path if found, None otherwise
    """
    folders = load_linked_folders()
    name_lower = name.lower()
    for folder in folders:
        if folder["name"].lower() == name_lower:
            return folder["path"]
    return None


def add_linked_folder(name, path):
    """
    Add a linked folder to config.

    Args:
        name: Display name for the linked folder
        path: Absolute path to the folder

    Returns:
        tuple: (success: bool, message: str)
    """
    name = name.strip()
    path = path.strip()

    # Validate inputs
    if not name:
        return False, "Name is required"
    if not path:
        return False, "Path is required"

    # Validate path is absolute and exists
    if not os.path.isabs(path):
        return False, "Path must be absolute"
    if not os.path.exists(path):
        return False, f"Path does not exist: {path}"
    if not os.path.isdir(path):
        return False, f"Path is not a directory: {path}"

    # Normalize path for consistent storage
    normalized_path = os.path.normpath(path)
    name_lower = name.lower()

    # Check for duplicate name in linked folders
    folders = load_linked_folders()
    for folder in folders:
        if folder["name"].lower() == name_lower:
            return False, f"A linked folder named '{name}' already exists"

    # Check for duplicate name in local groups
    local_names = _get_local_group_names()
    if name_lower in local_names:
        return False, f"A local group named '{name}' already exists"

    # Check for duplicate path
    for folder in folders:
        if os.path.normpath(folder["path"]).lower() == normalized_path.lower():
            return False, f"This path is already linked as '{folder['name']}'"

    # Add the new linked folder
    folders.append({
        "name": name,
        "path": normalized_path
    })

    save_linked_folders(folders)
    return True, f"Linked folder '{name}' added successfully"


def remove_linked_folder(name):
    """
    Remove a linked folder by name (does not delete actual files).

    Args:
        name: Display name of the linked folder to remove

    Returns:
        tuple: (success: bool, message: str)
    """
    folders = load_linked_folders()
    name_lower = name.lower()
    original_len = len(folders)

    folders = [f for f in folders if f["name"].lower() != name_lower]

    if len(folders) == original_len:
        return False, f"Linked folder '{name}' not found"

    save_linked_folders(folders)
    return True, f"Linked folder '{name}' removed"


def is_linked_folder(name):
    """
    Check if a group name represents a linked folder.

    Args:
        name: Group name to check

    Returns:
        bool: True if name matches a linked folder
    """
    return name.lower() in get_all_linked_names()
