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
from urllib.parse import unquote

from .config import (
    load_linked_folders,
    add_linked_folder,
    remove_linked_folder,
    get_linked_folder_path,
    is_linked_folder
)

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


def _resolve_group_path(group):
    """
    Resolve a group name to its absolute filesystem path.

    Args:
        group: Group name (could be local or linked)

    Returns:
        tuple: (path: str, is_linked: bool, validation_base: str)
               validation_base is the folder to validate paths against
    """
    if is_linked_folder(group):
        path = get_linked_folder_path(group)
        if path and os.path.isdir(path):
            return path, True, path
        return None, False, None
    else:
        base_path = _get_base_path()
        path = os.path.join(base_path, group)
        return path, False, base_path


# Ensure base structure exists on module import
_ensure_base_structure()


@PromptServer.instance.routes.get("/bedrot/groups")
async def list_groups(request):
    """List all groups (local + linked) with image counts."""
    base_path = _get_base_path()
    _ensure_base_structure()

    groups = []

    # Local groups (subdirectories)
    try:
        for entry in os.scandir(base_path):
            if entry.is_dir():
                images = _get_image_files(entry.path)
                groups.append({
                    "name": entry.name,
                    "count": len(images),
                    "type": "local"
                })
    except OSError as e:
        return web.json_response({"error": str(e)}, status=500)

    # Linked folders
    linked_folders = load_linked_folders()
    for folder in linked_folders:
        if os.path.isdir(folder["path"]):
            images = _get_image_files(folder["path"])
            groups.append({
                "name": folder["name"],
                "count": len(images),
                "type": "linked",
                "path": folder["path"]
            })

    # Sort groups, but keep Unsorted first
    groups.sort(key=lambda g: (g["name"] != DEFAULT_GROUP, g["name"].lower()))

    return web.json_response(groups)


@PromptServer.instance.routes.get("/bedrot/images/{group}")
async def list_images(request):
    """List images in a specific group (local or linked)."""
    group_raw = request.match_info.get("group", DEFAULT_GROUP)
    group = unquote(group_raw)

    # Try to resolve as linked folder first
    group_path, is_linked, validation_base = _resolve_group_path(group)

    if group_path is None:
        # Not a linked folder, try as local group with sanitization
        try:
            sanitized = _sanitize_path(group)
            base_path = _get_base_path()
            group_path = os.path.join(base_path, sanitized)
            validation_base = base_path
        except ValueError as e:
            return web.json_response({"error": str(e)}, status=400)

    if not is_linked and not _validate_path_within_base(group_path, validation_base):
        return web.json_response({"error": "Invalid group path"}, status=400)

    if not os.path.exists(group_path):
        return web.json_response([])

    images = _get_image_files(group_path)
    images.sort(key=str.lower)

    return web.json_response(images)


@PromptServer.instance.routes.post("/bedrot/upload/image")
async def bedrot_upload_image(request):
    """Upload image to a specific group (local or linked)."""
    post = await request.post()
    image = post.get("image")

    if not image or not image.file:
        return web.json_response({"error": "No image provided"}, status=400)

    group = post.get("group", DEFAULT_GROUP)

    # Try to resolve as linked folder first
    group_path, is_linked, validation_base = _resolve_group_path(group)

    if group_path is None:
        # Not a linked folder, try as local group
        try:
            sanitized = _sanitize_path(group)
            base_path = _get_base_path()
            group_path = os.path.join(base_path, sanitized)
            validation_base = base_path
            is_linked = False
        except ValueError:
            # Fall back to default group
            base_path = _get_base_path()
            group_path = os.path.join(base_path, DEFAULT_GROUP)
            validation_base = base_path
            is_linked = False
            group = DEFAULT_GROUP

    if not is_linked and not _validate_path_within_base(group_path, validation_base):
        return web.json_response({"error": "Invalid group path"}, status=400)

    # Create group folder if needed (local only - linked folders should exist)
    if not is_linked:
        os.makedirs(group_path, exist_ok=True)
    elif not os.path.exists(group_path):
        return web.json_response({"error": "Linked folder no longer exists"}, status=400)

    filename = image.filename
    if not filename:
        return web.json_response({"error": "No filename provided"}, status=400)

    filepath = os.path.join(group_path, filename)

    if not _validate_path_within_base(filepath, group_path):
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
            subfolder = group if is_linked else f"{BASE_FOLDER}/{group}"
            return web.json_response({
                "name": filename,
                "subfolder": subfolder,
                "type": "linked" if is_linked else "input",
                "duplicate": True
            })

        # Different file, increment suffix
        filename = f"{split[0]} ({i}){split[1]}"
        filepath = os.path.join(group_path, filename)
        i += 1

    # Save the file
    with open(filepath, "wb") as f:
        f.write(image.file.read())

    subfolder = group if is_linked else f"{BASE_FOLDER}/{group}"
    return web.json_response({
        "name": filename,
        "subfolder": subfolder,
        "type": "linked" if is_linked else "input"
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
    """Rename a local group folder (not linked folders)."""
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"error": "Invalid JSON"}, status=400)

    old_name = data.get("old_name", "")
    new_name = data.get("new_name", "")

    # Prevent renaming linked folders
    if is_linked_folder(old_name):
        return web.json_response({
            "error": "Cannot rename linked folders. Use unlink and re-link with a new name."
        }, status=400)

    try:
        old_name = _sanitize_path(old_name)
        new_name = _sanitize_path(new_name)
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
    """Copy an image from one group to another (supports linked folders)."""
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"error": "Invalid JSON"}, status=400)

    image_name = data.get("image", "")
    src_group = data.get("from_group", "")
    dst_group = data.get("to_group", "")

    # Sanitize image name
    try:
        image_name = _sanitize_path(image_name)
    except ValueError as e:
        return web.json_response({"error": str(e)}, status=400)

    # Resolve source group
    src_group_path, src_linked, src_base = _resolve_group_path(src_group)
    if src_group_path is None:
        try:
            sanitized = _sanitize_path(src_group)
            base_path = _get_base_path()
            src_group_path = os.path.join(base_path, sanitized)
            src_base = base_path
        except ValueError as e:
            return web.json_response({"error": f"Invalid source: {e}"}, status=400)

    # Resolve destination group
    dst_group_path, dst_linked, dst_base = _resolve_group_path(dst_group)
    if dst_group_path is None:
        try:
            sanitized = _sanitize_path(dst_group)
            base_path = _get_base_path()
            dst_group_path = os.path.join(base_path, sanitized)
            dst_base = base_path
            dst_linked = False
        except ValueError as e:
            return web.json_response({"error": f"Invalid destination: {e}"}, status=400)

    src_path = os.path.join(src_group_path, image_name)
    dst_dir = dst_group_path
    dst_path = os.path.join(dst_dir, image_name)

    # Validate paths
    if not _validate_path_within_base(src_path, src_group_path):
        return web.json_response({"error": "Invalid source path"}, status=400)

    if not _validate_path_within_base(dst_path, dst_group_path):
        return web.json_response({"error": "Invalid destination path"}, status=400)

    if not os.path.exists(src_path):
        return web.json_response({"error": "Source image does not exist"}, status=404)

    # Create destination group if needed (local only)
    if not dst_linked:
        os.makedirs(dst_dir, exist_ok=True)
    elif not os.path.exists(dst_dir):
        return web.json_response({"error": "Destination linked folder no longer exists"}, status=400)

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
    """Delete a local group folder (must be empty or force=true). Does not delete linked folders."""
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"error": "Invalid JSON"}, status=400)

    name = data.get("name", "")
    force = data.get("force", False)

    # Prevent deleting linked folders (use unlink instead)
    if is_linked_folder(name):
        return web.json_response({
            "error": "Cannot delete linked folders. Use the unlink endpoint to remove the link."
        }, status=400)

    try:
        name = _sanitize_path(name)
    except ValueError as e:
        return web.json_response({"error": str(e)}, status=400)

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
    """Delete an image from a group (local or linked)."""
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"error": "Invalid JSON"}, status=400)

    image_name = data.get("image", "")
    group = data.get("group", "")

    # Sanitize image name
    try:
        image_name = _sanitize_path(image_name)
    except ValueError as e:
        return web.json_response({"error": str(e)}, status=400)

    # Resolve group
    group_path, is_linked, validation_base = _resolve_group_path(group)
    if group_path is None:
        try:
            sanitized = _sanitize_path(group)
            base_path = _get_base_path()
            group_path = os.path.join(base_path, sanitized)
            validation_base = base_path
        except ValueError as e:
            return web.json_response({"error": str(e)}, status=400)

    image_path = os.path.join(group_path, image_name)

    if not _validate_path_within_base(image_path, group_path):
        return web.json_response({"error": "Invalid image path"}, status=400)

    if not os.path.exists(image_path):
        return web.json_response({"error": "Image does not exist"}, status=404)

    try:
        os.remove(image_path)
    except OSError as e:
        return web.json_response({"error": str(e)}, status=500)

    return web.json_response({"success": True, "image": image_name, "group": group})


# ============================================================================
# Linked Folder Management Endpoints
# ============================================================================

@PromptServer.instance.routes.get("/bedrot/linked/list")
async def list_linked_folders(request):
    """List all linked folders with their paths and status."""
    folders = load_linked_folders()

    result = []
    for folder in folders:
        exists = os.path.isdir(folder["path"])
        image_count = 0
        if exists:
            image_count = len(_get_image_files(folder["path"]))

        result.append({
            "name": folder["name"],
            "path": folder["path"],
            "exists": exists,
            "count": image_count
        })

    return web.json_response(result)


@PromptServer.instance.routes.post("/bedrot/linked/add")
async def add_linked_folder_endpoint(request):
    """Add a new linked external folder."""
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"error": "Invalid JSON"}, status=400)

    name = data.get("name", "").strip()
    path = data.get("path", "").strip()

    if not name:
        return web.json_response({"error": "Name is required"}, status=400)
    if not path:
        return web.json_response({"error": "Path is required"}, status=400)

    success, message = add_linked_folder(name, path)

    if success:
        return web.json_response({"success": True, "message": message})
    else:
        return web.json_response({"error": message}, status=400)


@PromptServer.instance.routes.post("/bedrot/linked/remove")
async def remove_linked_folder_endpoint(request):
    """Remove a linked folder (does not delete actual files on disk)."""
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"error": "Invalid JSON"}, status=400)

    name = data.get("name", "").strip()

    if not name:
        return web.json_response({"error": "Name is required"}, status=400)

    success, message = remove_linked_folder(name)

    if success:
        return web.json_response({"success": True, "message": message})
    else:
        return web.json_response({"error": message}, status=404)


@PromptServer.instance.routes.post("/bedrot/browse/folder")
async def browse_for_folder(request):
    """Open native Windows folder picker and register selected folder as a group."""
    import ctypes
    from ctypes import wintypes
    import asyncio

    def open_folder_dialog():
        """Open modern Windows File Explorer folder picker using IFileOpenDialog."""
        try:
            from ctypes import windll, byref, c_void_p, c_ulong, c_wchar_p, POINTER, WINFUNCTYPE
            import comtypes.client

            # Use comtypes for clean COM interface access
            from comtypes.shelllink import IShellItem
            from comtypes import GUID, CoCreateInstance, CLSCTX_INPROC_SERVER

            # IFileOpenDialog GUID
            CLSID_FileOpenDialog = GUID("{DC1C5A9C-E88A-4DDE-A5A1-60F82A20AEF7}")

            # File dialog options
            FOS_PICKFOLDERS = 0x20
            FOS_FORCEFILESYSTEM = 0x40

            # Create dialog
            file_dialog = CoCreateInstance(
                CLSID_FileOpenDialog,
                None,
                CLSCTX_INPROC_SERVER,
                comtypes.client.CreateObject
            )

            # Set folder picker option
            options = file_dialog.GetOptions()
            file_dialog.SetOptions(options | FOS_PICKFOLDERS | FOS_FORCEFILESYSTEM)

            # Show dialog
            hr = file_dialog.Show(None)

            if hr != 0:
                return None

            # Get result
            result = file_dialog.GetResult()
            folder_path = result.GetDisplayName(0x80058000)  # SIGDN_FILESYSPATH

            return folder_path

        except ImportError:
            # Fallback: use ctypes directly if comtypes not available
            pass
        except Exception as e:
            print(f"[BEDROT LoadImage] Folder dialog (comtypes) error: {e}")

        # Fallback implementation using pure ctypes
        try:
            from ctypes import windll, byref, c_void_p, c_ulong, POINTER, cast, create_unicode_buffer
            import uuid

            ole32 = windll.ole32
            shell32 = windll.shell32

            # Initialize COM
            ole32.CoInitialize(None)

            # GUIDs as bytes
            CLSID_FileOpenDialog = uuid.UUID("{DC1C5A9C-E88A-4DDE-A5A1-60F82A20AEF7}").bytes_le
            IID_IFileOpenDialog = uuid.UUID("{D57C7288-D4AD-4768-BE02-9D969532D960}").bytes_le

            # File dialog options
            FOS_PICKFOLDERS = 0x20
            FOS_FORCEFILESYSTEM = 0x40

            # Create FileOpenDialog
            file_dialog = c_void_p()
            hr = ole32.CoCreateInstance(
                CLSID_FileOpenDialog,
                None,
                1,  # CLSCTX_INPROC_SERVER
                IID_IFileOpenDialog,
                byref(file_dialog)
            )

            if hr != 0 or not file_dialog:
                ole32.CoUninitialize()
                return None

            # Get vtable pointer
            vtable = cast(file_dialog, POINTER(c_void_p))[0]
            vtable = cast(vtable, POINTER(c_void_p * 30))

            # Define function types for COM methods
            # IFileDialog vtable offsets:
            # 0-2: IUnknown (QueryInterface, AddRef, Release)
            # 3: Show
            # 4: SetFileTypes
            # 5: SetFileTypeIndex
            # 6: GetFileTypeIndex
            # 7: Advise
            # 8: Unadvise
            # 9: SetOptions
            # 10: GetOptions
            # ...
            # 20: GetResult (for IFileOpenDialog)

            GetOptions = ctypes.WINFUNCTYPE(ctypes.c_long, c_void_p, POINTER(c_ulong))(vtable.contents[10])
            SetOptions = ctypes.WINFUNCTYPE(ctypes.c_long, c_void_p, c_ulong)(vtable.contents[9])
            Show = ctypes.WINFUNCTYPE(ctypes.c_long, c_void_p, c_void_p)(vtable.contents[3])
            GetResult = ctypes.WINFUNCTYPE(ctypes.c_long, c_void_p, POINTER(c_void_p))(vtable.contents[20])
            Release = ctypes.WINFUNCTYPE(c_ulong, c_void_p)(vtable.contents[2])

            # Get current options and add folder picker flag
            options = c_ulong()
            GetOptions(file_dialog, byref(options))
            SetOptions(file_dialog, options.value | FOS_PICKFOLDERS | FOS_FORCEFILESYSTEM)

            # Show the dialog
            hr = Show(file_dialog, None)

            folder_path = None
            if hr == 0:
                # Get the selected item
                shell_item = c_void_p()
                hr = GetResult(file_dialog, byref(shell_item))

                if hr == 0 and shell_item:
                    # Get IShellItem vtable
                    item_vtable = cast(shell_item, POINTER(c_void_p))[0]
                    item_vtable = cast(item_vtable, POINTER(c_void_p * 10))

                    # IShellItem::GetDisplayName is at offset 5
                    # SIGDN_FILESYSPATH = 0x80058000
                    GetDisplayName = ctypes.WINFUNCTYPE(
                        ctypes.c_long, c_void_p, c_ulong, POINTER(c_wchar_p)
                    )(item_vtable.contents[5])

                    path_ptr = c_wchar_p()
                    hr = GetDisplayName(shell_item, 0x80058000, byref(path_ptr))

                    if hr == 0 and path_ptr.value:
                        folder_path = path_ptr.value
                        ole32.CoTaskMemFree(path_ptr)

                    # Release shell item
                    ItemRelease = ctypes.WINFUNCTYPE(c_ulong, c_void_p)(item_vtable.contents[2])
                    ItemRelease(shell_item)

            # Release dialog
            Release(file_dialog)
            ole32.CoUninitialize()

            return folder_path

        except Exception as e:
            print(f"[BEDROT LoadImage] Folder dialog error: {e}")
            import traceback
            traceback.print_exc()
            return None

    # Run dialog in thread pool to not block event loop
    loop = asyncio.get_event_loop()
    folder_path = await loop.run_in_executor(None, open_folder_dialog)

    if not folder_path:
        return web.json_response({"cancelled": True})

    # Auto-name using folder name
    folder_name = os.path.basename(folder_path)

    # Register as linked folder
    success, message = add_linked_folder(folder_name, folder_path)

    if success:
        return web.json_response({
            "success": True,
            "name": folder_name,
            "path": folder_path
        })
    else:
        return web.json_response({"error": message}, status=400)
