"""
BEDROT Load Image - API Routes

Custom endpoints for group-based image management.
All groups are folder references stored in groups.json config.
"""

from server import PromptServer
from aiohttp import web
import folder_paths
import os
import hashlib
from urllib.parse import unquote

from .config import (
    load_groups,
    get_group_path,
    add_group,
    remove_group,
    rename_group,
    ensure_default_group,
    DEFAULT_GROUP
)


def _sanitize_filename(name):
    """
    Sanitize a filename to prevent directory traversal.
    Returns cleaned name or raises ValueError if invalid.
    """
    if not name or not isinstance(name, str):
        raise ValueError("Invalid filename: empty or not a string")

    # Strip path separators and parent refs
    clean = os.path.basename(name)

    if not clean or clean == "." or clean == "..":
        raise ValueError("Invalid filename")

    return clean


def _get_image_files(directory):
    """Get list of image files in a directory."""
    if not os.path.isdir(directory):
        return []

    files = [f for f in os.listdir(directory)
             if os.path.isfile(os.path.join(directory, f))]
    return folder_paths.filter_files_content_types(files, ["image"])


def _validate_path_within(target_path, base_path):
    """Validate that target path is within the base path."""
    target_abs = os.path.abspath(target_path)
    base_abs = os.path.abspath(base_path)
    return os.path.commonpath([target_abs, base_abs]) == base_abs


# Ensure default group exists on module import
ensure_default_group()


# ============================================================================
# Group Management Endpoints
# ============================================================================

@PromptServer.instance.routes.get("/bedrot/groups")
async def list_groups(request):
    """List all groups with image counts."""
    groups = load_groups()
    result = []

    for group in groups:
        path = group["path"]
        exists = os.path.isdir(path)
        count = len(_get_image_files(path)) if exists else 0
        result.append({
            "name": group["name"],
            "count": count,
            "exists": exists
        })

    # Sort with Unsorted first
    result.sort(key=lambda g: (g["name"] != DEFAULT_GROUP, g["name"].lower()))

    return web.json_response(result)


@PromptServer.instance.routes.post("/bedrot/group/rename")
async def rename_group_endpoint(request):
    """Rename a group (changes config entry, not filesystem folder)."""
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"error": "Invalid JSON"}, status=400)

    old_name = data.get("old_name", "")
    new_name = data.get("new_name", "")

    success, message = rename_group(old_name, new_name)

    if success:
        return web.json_response({"success": True, "old_name": old_name, "new_name": new_name})
    else:
        return web.json_response({"error": message}, status=400)


@PromptServer.instance.routes.post("/bedrot/group/delete")
async def delete_group_endpoint(request):
    """Remove a group from config (does not delete the folder on disk)."""
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"error": "Invalid JSON"}, status=400)

    name = data.get("name", "")

    success, message = remove_group(name)

    if success:
        return web.json_response({"success": True, "name": name})
    else:
        return web.json_response({"error": message}, status=400)


# ============================================================================
# Image Management Endpoints
# ============================================================================

@PromptServer.instance.routes.get("/bedrot/images/{group}")
async def list_images(request):
    """List images in a specific group."""
    group_raw = request.match_info.get("group", DEFAULT_GROUP)
    group = unquote(group_raw)

    group_path = get_group_path(group)
    if not group_path:
        return web.json_response([])

    if not os.path.isdir(group_path):
        return web.json_response([])

    images = _get_image_files(group_path)
    images.sort(key=str.lower)

    return web.json_response(images)


@PromptServer.instance.routes.post("/bedrot/upload/image")
async def upload_image(request):
    """Upload image to a specific group."""
    post = await request.post()
    image = post.get("image")

    if not image or not image.file:
        return web.json_response({"error": "No image provided"}, status=400)

    group = post.get("group", DEFAULT_GROUP)
    group_path = get_group_path(group)

    if not group_path:
        return web.json_response({"error": f"Unknown group: {group}"}, status=400)

    if not os.path.isdir(group_path):
        return web.json_response({"error": "Group folder no longer exists"}, status=400)

    filename = image.filename
    if not filename:
        return web.json_response({"error": "No filename provided"}, status=400)

    try:
        filename = _sanitize_filename(filename)
    except ValueError as e:
        return web.json_response({"error": str(e)}, status=400)

    filepath = os.path.join(group_path, filename)

    if not _validate_path_within(filepath, group_path):
        return web.json_response({"error": "Invalid file path"}, status=400)

    # Handle duplicates -- check hash, add suffix if different file
    split = os.path.splitext(filename)
    i = 1
    while os.path.exists(filepath):
        hasher_existing = hashlib.sha256()
        hasher_new = hashlib.sha256()

        with open(filepath, "rb") as f:
            hasher_existing.update(f.read())

        hasher_new.update(image.file.read())
        image.file.seek(0)

        if hasher_existing.hexdigest() == hasher_new.hexdigest():
            return web.json_response({
                "name": filename,
                "group": group,
                "duplicate": True
            })

        filename = f"{split[0]} ({i}){split[1]}"
        filepath = os.path.join(group_path, filename)
        i += 1

    # Save the file
    with open(filepath, "wb") as f:
        f.write(image.file.read())

    return web.json_response({
        "name": filename,
        "group": group
    })


@PromptServer.instance.routes.post("/bedrot/image/copy")
async def copy_image(request):
    """Copy an image from one group to another."""
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"error": "Invalid JSON"}, status=400)

    image_name = data.get("image", "")
    src_group = data.get("from_group", "")
    dst_group = data.get("to_group", "")

    try:
        image_name = _sanitize_filename(image_name)
    except ValueError as e:
        return web.json_response({"error": str(e)}, status=400)

    src_path = get_group_path(src_group)
    dst_path = get_group_path(dst_group)

    if not src_path:
        return web.json_response({"error": f"Unknown source group: {src_group}"}, status=400)
    if not dst_path:
        return web.json_response({"error": f"Unknown destination group: {dst_group}"}, status=400)

    src_file = os.path.join(src_path, image_name)
    dst_file = os.path.join(dst_path, image_name)

    if not _validate_path_within(src_file, src_path):
        return web.json_response({"error": "Invalid source path"}, status=400)
    if not _validate_path_within(dst_file, dst_path):
        return web.json_response({"error": "Invalid destination path"}, status=400)

    if not os.path.exists(src_file):
        return web.json_response({"error": "Source image does not exist"}, status=404)

    # Handle name collision
    import shutil
    final_name = image_name
    if os.path.exists(dst_file):
        split = os.path.splitext(image_name)
        i = 1
        while os.path.exists(dst_file):
            final_name = f"{split[0]} ({i}){split[1]}"
            dst_file = os.path.join(dst_path, final_name)
            i += 1

    try:
        shutil.copy2(src_file, dst_file)
    except OSError as e:
        return web.json_response({"error": str(e)}, status=500)

    return web.json_response({
        "success": True,
        "image": final_name,
        "from_group": src_group,
        "to_group": dst_group
    })


@PromptServer.instance.routes.post("/bedrot/image/delete")
async def delete_image(request):
    """Delete an image from a group."""
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"error": "Invalid JSON"}, status=400)

    image_name = data.get("image", "")
    group = data.get("group", "")

    try:
        image_name = _sanitize_filename(image_name)
    except ValueError as e:
        return web.json_response({"error": str(e)}, status=400)

    group_path = get_group_path(group)
    if not group_path:
        return web.json_response({"error": f"Unknown group: {group}"}, status=400)

    image_path = os.path.join(group_path, image_name)

    if not _validate_path_within(image_path, group_path):
        return web.json_response({"error": "Invalid image path"}, status=400)

    if not os.path.exists(image_path):
        return web.json_response({"error": "Image does not exist"}, status=404)

    try:
        os.remove(image_path)
    except OSError as e:
        return web.json_response({"error": str(e)}, status=500)

    return web.json_response({"success": True, "image": image_name, "group": group})


# ============================================================================
# Folder Picker & Image Viewer
# ============================================================================

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

    # Register as group
    success, message = add_group(folder_name, folder_path)

    if success:
        return web.json_response({
            "success": True,
            "name": folder_name,
            "path": folder_path
        })
    else:
        return web.json_response({"error": message}, status=400)


@PromptServer.instance.routes.get("/bedrot/view")
async def view_image(request):
    """Serve image from any group for preview."""
    import mimetypes

    group = request.query.get("group", DEFAULT_GROUP)
    filename = request.query.get("filename", "")

    if not filename or filename == "[no images]":
        return web.Response(status=400, text="No filename provided")

    group_path = get_group_path(group)
    if not group_path:
        return web.Response(status=400, text=f"Unknown group: {group}")

    try:
        safe_filename = _sanitize_filename(filename)
    except ValueError as e:
        return web.Response(status=400, text=str(e))

    image_path = os.path.join(group_path, safe_filename)

    if not _validate_path_within(image_path, group_path):
        return web.Response(status=403, text="Access denied")

    if not os.path.exists(image_path):
        return web.Response(status=404, text="Image not found")

    mime_type, _ = mimetypes.guess_type(image_path)
    if not mime_type:
        mime_type = "application/octet-stream"

    return web.FileResponse(image_path, headers={"Content-Type": mime_type})
