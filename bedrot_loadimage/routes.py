"""
BEDROT Load Image - API Routes

Custom endpoints for group-based image management.
"""

from server import PromptServer
from aiohttp import web
import folder_paths
import os
import shutil
import hashlib

# Constants
BASE_FOLDER = "BedRot_custom_image_load"
DEFAULT_GROUP = "Unsorted"


def _get_base_path():
    """Get the base path for BedRot image storage."""
    return os.path.join(folder_paths.get_input_directory(), BASE_FOLDER)


def _sanitize_path(name):
    """
    Sanitize user-provided path component to prevent directory traversal.
    Returns cleaned name or raises ValueError if invalid.
    """
    if not name or not isinstance(name, str):
        raise ValueError("Invalid path: empty or not a string")

    # Normalize and strip dangerous characters
    clean = os.path.normpath(name).replace("\\", "/")

    # Remove leading slashes and dots
    clean = clean.lstrip("/").lstrip("\\")

    # Reject if contains parent directory references or drive letters
    if ".." in clean or ":" in clean or clean.startswith("/"):
        raise ValueError("Invalid path: contains forbidden characters")

    # Reject if empty after cleaning
    if not clean or clean == ".":
        raise ValueError("Invalid path: resolves to empty")

    return clean


def _ensure_base_structure():
    """Ensure the base folder structure exists with default Unsorted group."""
    base_path = _get_base_path()
    unsorted_path = os.path.join(base_path, DEFAULT_GROUP)
    os.makedirs(unsorted_path, exist_ok=True)
    return base_path


def _get_image_files(directory):
    """Get list of image files in a directory."""
    if not os.path.exists(directory):
        return []

    files = [f for f in os.listdir(directory)
             if os.path.isfile(os.path.join(directory, f))]
    return folder_paths.filter_files_content_types(files, ["image"])


def _validate_path_within_base(target_path, base_path):
    """Validate that target path is within the base path."""
    target_abs = os.path.abspath(target_path)
    base_abs = os.path.abspath(base_path)
    return os.path.commonpath([target_abs, base_abs]) == base_abs


# Ensure base structure exists on module import
_ensure_base_structure()


@PromptServer.instance.routes.get("/bedrot/groups")
async def list_groups(request):
    """List all groups with image counts."""
    base_path = _get_base_path()
    _ensure_base_structure()

    groups = []
    try:
        for entry in os.scandir(base_path):
            if entry.is_dir():
                images = _get_image_files(entry.path)
                groups.append({
                    "name": entry.name,
                    "count": len(images)
                })

        # Sort groups, but keep Unsorted first
        groups.sort(key=lambda g: (g["name"] != DEFAULT_GROUP, g["name"].lower()))

    except OSError as e:
        return web.json_response({"error": str(e)}, status=500)

    return web.json_response(groups)


@PromptServer.instance.routes.get("/bedrot/images/{group}")
async def list_images(request):
    """List images in a specific group."""
    try:
        group = _sanitize_path(request.match_info.get("group", DEFAULT_GROUP))
    except ValueError as e:
        return web.json_response({"error": str(e)}, status=400)

    base_path = _get_base_path()
    group_path = os.path.join(base_path, group)

    if not _validate_path_within_base(group_path, base_path):
        return web.json_response({"error": "Invalid group path"}, status=400)

    if not os.path.exists(group_path):
        return web.json_response([])

    images = _get_image_files(group_path)
    images.sort(key=str.lower)

    return web.json_response(images)


@PromptServer.instance.routes.post("/bedrot/upload/image")
async def bedrot_upload_image(request):
    """Upload image to a specific group."""
    post = await request.post()
    image = post.get("image")

    if not image or not image.file:
        return web.json_response({"error": "No image provided"}, status=400)

    # Get and sanitize group
    try:
        group = _sanitize_path(post.get("group", DEFAULT_GROUP))
    except ValueError:
        group = DEFAULT_GROUP

    base_path = _get_base_path()
    group_path = os.path.join(base_path, group)

    if not _validate_path_within_base(group_path, base_path):
        return web.json_response({"error": "Invalid group path"}, status=400)

    # Create group folder if needed
    os.makedirs(group_path, exist_ok=True)

    filename = image.filename
    if not filename:
        return web.json_response({"error": "No filename provided"}, status=400)

    filepath = os.path.join(group_path, filename)

    if not _validate_path_within_base(filepath, base_path):
        return web.json_response({"error": "Invalid file path"}, status=400)

    # Handle duplicates - add number suffix if needed
    split = os.path.splitext(filename)
    i = 1
    while os.path.exists(filepath):
        # Check if it's the same file by hash
        hasher_existing = hashlib.sha256()
        hasher_new = hashlib.sha256()

        with open(filepath, "rb") as f:
            hasher_existing.update(f.read())

        hasher_new.update(image.file.read())
        image.file.seek(0)

        if hasher_existing.hexdigest() == hasher_new.hexdigest():
            # Same file, just return existing
            return web.json_response({
                "name": filename,
                "subfolder": f"{BASE_FOLDER}/{group}",
                "type": "input",
                "duplicate": True
            })

        # Different file, increment suffix
        filename = f"{split[0]} ({i}){split[1]}"
        filepath = os.path.join(group_path, filename)
        i += 1

    # Save the file
    with open(filepath, "wb") as f:
        f.write(image.file.read())

    return web.json_response({
        "name": filename,
        "subfolder": f"{BASE_FOLDER}/{group}",
        "type": "input"
    })


@PromptServer.instance.routes.post("/bedrot/group/create")
async def create_group(request):
    """Create a new group folder."""
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"error": "Invalid JSON"}, status=400)

    try:
        name = _sanitize_path(data.get("name", ""))
    except ValueError as e:
        return web.json_response({"error": str(e)}, status=400)

    base_path = _get_base_path()
    group_path = os.path.join(base_path, name)

    if not _validate_path_within_base(group_path, base_path):
        return web.json_response({"error": "Invalid group path"}, status=400)

    if os.path.exists(group_path):
        return web.json_response({"error": "Group already exists"}, status=409)

    try:
        os.makedirs(group_path)
    except OSError as e:
        return web.json_response({"error": str(e)}, status=500)

    return web.json_response({"success": True, "name": name})


@PromptServer.instance.routes.post("/bedrot/group/rename")
async def rename_group(request):
    """Rename a group folder."""
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"error": "Invalid JSON"}, status=400)

    try:
        old_name = _sanitize_path(data.get("old_name", ""))
        new_name = _sanitize_path(data.get("new_name", ""))
    except ValueError as e:
        return web.json_response({"error": str(e)}, status=400)

    # Prevent renaming the default Unsorted group
    if old_name == DEFAULT_GROUP:
        return web.json_response({"error": "Cannot rename the Unsorted group"}, status=400)

    base_path = _get_base_path()
    old_path = os.path.join(base_path, old_name)
    new_path = os.path.join(base_path, new_name)

    if not _validate_path_within_base(old_path, base_path):
        return web.json_response({"error": "Invalid source path"}, status=400)

    if not _validate_path_within_base(new_path, base_path):
        return web.json_response({"error": "Invalid destination path"}, status=400)

    if not os.path.exists(old_path):
        return web.json_response({"error": "Source group does not exist"}, status=404)

    if os.path.exists(new_path):
        return web.json_response({"error": "Destination group already exists"}, status=409)

    try:
        os.rename(old_path, new_path)
    except OSError as e:
        return web.json_response({"error": str(e)}, status=500)

    return web.json_response({"success": True, "old_name": old_name, "new_name": new_name})


@PromptServer.instance.routes.post("/bedrot/image/copy")
async def copy_image_to_group(request):
    """Copy an image from one group to another."""
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"error": "Invalid JSON"}, status=400)

    try:
        image_name = _sanitize_path(data.get("image", ""))
        src_group = _sanitize_path(data.get("from_group", ""))
        dst_group = _sanitize_path(data.get("to_group", ""))
    except ValueError as e:
        return web.json_response({"error": str(e)}, status=400)

    base_path = _get_base_path()
    src_path = os.path.join(base_path, src_group, image_name)
    dst_dir = os.path.join(base_path, dst_group)
    dst_path = os.path.join(dst_dir, image_name)

    # Validate all paths
    if not _validate_path_within_base(src_path, base_path):
        return web.json_response({"error": "Invalid source path"}, status=400)

    if not _validate_path_within_base(dst_path, base_path):
        return web.json_response({"error": "Invalid destination path"}, status=400)

    if not os.path.exists(src_path):
        return web.json_response({"error": "Source image does not exist"}, status=404)

    # Create destination group if needed
    os.makedirs(dst_dir, exist_ok=True)

    # Handle name collision in destination
    final_name = image_name
    if os.path.exists(dst_path):
        split = os.path.splitext(image_name)
        i = 1
        while os.path.exists(dst_path):
            final_name = f"{split[0]} ({i}){split[1]}"
            dst_path = os.path.join(dst_dir, final_name)
            i += 1

    try:
        shutil.copy2(src_path, dst_path)
    except OSError as e:
        return web.json_response({"error": str(e)}, status=500)

    return web.json_response({
        "success": True,
        "image": final_name,
        "from_group": src_group,
        "to_group": dst_group
    })


@PromptServer.instance.routes.post("/bedrot/group/delete")
async def delete_group(request):
    """Delete a group folder (must be empty or force=true)."""
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"error": "Invalid JSON"}, status=400)

    try:
        name = _sanitize_path(data.get("name", ""))
    except ValueError as e:
        return web.json_response({"error": str(e)}, status=400)

    force = data.get("force", False)

    # Prevent deleting the default Unsorted group
    if name == DEFAULT_GROUP:
        return web.json_response({"error": "Cannot delete the Unsorted group"}, status=400)

    base_path = _get_base_path()
    group_path = os.path.join(base_path, name)

    if not _validate_path_within_base(group_path, base_path):
        return web.json_response({"error": "Invalid group path"}, status=400)

    if not os.path.exists(group_path):
        return web.json_response({"error": "Group does not exist"}, status=404)

    # Check if empty
    contents = os.listdir(group_path)
    if contents and not force:
        return web.json_response({
            "error": "Group is not empty. Use force=true to delete anyway.",
            "count": len(contents)
        }, status=400)

    try:
        if force:
            shutil.rmtree(group_path)
        else:
            os.rmdir(group_path)
    except OSError as e:
        return web.json_response({"error": str(e)}, status=500)

    return web.json_response({"success": True, "name": name})


@PromptServer.instance.routes.post("/bedrot/image/delete")
async def delete_image(request):
    """Delete an image from a group."""
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"error": "Invalid JSON"}, status=400)

    try:
        image_name = _sanitize_path(data.get("image", ""))
        group = _sanitize_path(data.get("group", ""))
    except ValueError as e:
        return web.json_response({"error": str(e)}, status=400)

    base_path = _get_base_path()
    image_path = os.path.join(base_path, group, image_name)

    if not _validate_path_within_base(image_path, base_path):
        return web.json_response({"error": "Invalid image path"}, status=400)

    if not os.path.exists(image_path):
        return web.json_response({"error": "Image does not exist"}, status=404)

    try:
        os.remove(image_path)
    except OSError as e:
        return web.json_response({"error": str(e)}, status=500)

    return web.json_response({"success": True, "image": image_name, "group": group})
