"""
BEDROT Load Image - ComfyUI Custom Node

A LoadImage node with group-based organization.
Images are stored in ComfyUI/input/BedRot_custom_image_load/{group}/
"""

import os
import hashlib
import numpy as np
import torch
from PIL import Image, ImageOps, ImageSequence

import folder_paths
import node_helpers

from .config import (
    load_linked_folders,
    get_linked_folder_path,
    is_linked_folder
)

# Constants - must match routes.py
BASE_FOLDER = "BedRot_custom_image_load"
DEFAULT_GROUP = "Unsorted"


def _get_base_path():
    """Get the base path for BedRot image storage."""
    return os.path.join(folder_paths.get_input_directory(), BASE_FOLDER)


def _ensure_base_structure():
    """Ensure the base folder structure exists."""
    base_path = _get_base_path()
    unsorted_path = os.path.join(base_path, DEFAULT_GROUP)
    os.makedirs(unsorted_path, exist_ok=True)
    return base_path


def _resolve_group_path(group):
    """
    Resolve a group name to its absolute filesystem path.

    Args:
        group: Group name (could be local or linked)

    Returns:
        tuple: (path: str, is_linked: bool) or (None, False) if invalid
    """
    if is_linked_folder(group):
        path = get_linked_folder_path(group)
        if path and os.path.isdir(path):
            return path, True
        return None, False
    else:
        base_path = _get_base_path()
        path = os.path.join(base_path, group)
        return path, False


def _get_groups():
    """Get list of available groups (local subdirectories + linked folders)."""
    base_path = _ensure_base_structure()

    groups = []

    # Local groups (subdirectories)
    try:
        for entry in os.scandir(base_path):
            if entry.is_dir():
                groups.append(entry.name)
    except OSError:
        pass

    # Linked folders (from config)
    linked_folders = load_linked_folders()
    for folder in linked_folders:
        # Only add if path still exists
        if os.path.isdir(folder["path"]):
            groups.append(folder["name"])

    # Sort groups, but keep Unsorted first
    groups.sort(key=lambda g: (g != DEFAULT_GROUP, g.lower()))

    # Ensure at least Unsorted exists
    if not groups:
        groups = [DEFAULT_GROUP]

    return groups


def _get_images_in_group(group):
    """Get list of image files in a specific group (local or linked)."""
    group_path, _ = _resolve_group_path(group)

    if not group_path or not os.path.exists(group_path):
        return ["[no images]"]

    files = [f for f in os.listdir(group_path)
             if os.path.isfile(os.path.join(group_path, f))]
    images = folder_paths.filter_files_content_types(files, ["image"])
    images.sort(key=str.lower)

    if not images:
        return ["[no images]"]

    return images


class BedrotLoadImage:
    """
    BEDROT's Load Image node with group-based organization.

    Features:
    - Images organized into groups (subfolders)
    - Default 'Unsorted' group for quick uploads
    - Create new groups via the new_group_name input
    - Drag-drop uploads to current group
    """

    @classmethod
    def INPUT_TYPES(cls):
        groups = _get_groups()
        default_group = groups[0] if groups else DEFAULT_GROUP
        images = _get_images_in_group(default_group)

        return {
            "required": {
                "group": (groups, {
                    "default": default_group,
                    "tooltip": "Image group (subfolder). Select a group to see its images."
                }),
                "image": (images, {
                    "image_upload": True,
                    "tooltip": "Select an image from the current group. Drag-drop to upload."
                }),
            },
        }

    RETURN_TYPES = ("IMAGE", "MASK", "STRING")
    RETURN_NAMES = ("image", "mask", "filename")
    FUNCTION = "load_image"
    CATEGORY = "BEDROT/image"

    def load_image(self, group, image):
        """Load an image from the specified group."""
        # Handle placeholder
        if image == "[no images]":
            # Return empty tensors
            empty_image = torch.zeros((1, 64, 64, 3), dtype=torch.float32)
            empty_mask = torch.zeros((1, 64, 64), dtype=torch.float32)
            return (empty_image, empty_mask, "")

        # Resolve group to absolute path
        group_path, is_linked = _resolve_group_path(group)
        if not group_path:
            raise ValueError(f"Invalid group: {group}")

        image_path = os.path.join(group_path, image)

        # Validate path stays within group folder (for both local and linked)
        try:
            if os.path.commonpath([os.path.abspath(image_path), os.path.abspath(group_path)]) != os.path.abspath(group_path):
                raise ValueError(f"Invalid image path: {image}")
        except ValueError:
            raise ValueError(f"Invalid image path: {image}")

        if not os.path.exists(image_path):
            raise FileNotFoundError(f"Image not found: {image_path}")

        # Load image using the same pattern as ComfyUI's LoadImage
        img = node_helpers.pillow(Image.open, image_path)

        output_images = []
        output_masks = []
        w, h = None, None

        excluded_formats = ['MPO']

        for i in ImageSequence.Iterator(img):
            i = node_helpers.pillow(ImageOps.exif_transpose, i)

            if i.mode == 'I':
                i = i.point(lambda x: x * (1 / 255))
            frame = i.convert("RGB")

            if len(output_images) == 0:
                w = frame.size[0]
                h = frame.size[1]

            if frame.size[0] != w or frame.size[1] != h:
                continue

            frame_np = np.array(frame).astype(np.float32) / 255.0
            frame_tensor = torch.from_numpy(frame_np)[None,]

            # Extract mask from alpha channel
            if 'A' in i.getbands():
                mask = np.array(i.getchannel('A')).astype(np.float32) / 255.0
                mask = 1. - torch.from_numpy(mask)
            elif i.mode == 'P' and 'transparency' in i.info:
                mask = np.array(i.convert('RGBA').getchannel('A')).astype(np.float32) / 255.0
                mask = 1. - torch.from_numpy(mask)
            else:
                mask = torch.zeros((64, 64), dtype=torch.float32, device="cpu")

            output_images.append(frame_tensor)
            output_masks.append(mask.unsqueeze(0))

        if len(output_images) > 1 and img.format not in excluded_formats:
            output_image = torch.cat(output_images, dim=0)
            output_mask = torch.cat(output_masks, dim=0)
        else:
            output_image = output_images[0]
            output_mask = output_masks[0]

        return (output_image, output_mask, image)

    @classmethod
    def IS_CHANGED(cls, group, image):
        """Return hash of file content for cache invalidation."""
        if image == "[no images]":
            return ""

        group_path, _ = _resolve_group_path(group)
        if not group_path:
            return ""

        image_path = os.path.join(group_path, image)

        if not os.path.exists(image_path):
            return ""

        m = hashlib.sha256()
        with open(image_path, 'rb') as f:
            m.update(f.read())
        return m.digest().hex()

    @classmethod
    def VALIDATE_INPUTS(cls, group, image):
        """Validate that the image file exists."""
        if image == "[no images]":
            return True

        group_path, _ = _resolve_group_path(group)
        if not group_path:
            return f"Invalid group: {group}"

        image_path = os.path.join(group_path, image)

        # Security check - path must stay within group folder
        try:
            if os.path.commonpath([os.path.abspath(image_path), os.path.abspath(group_path)]) != os.path.abspath(group_path):
                return f"Invalid image path: {image}"
        except ValueError:
            return f"Invalid image path: {image}"

        if not os.path.exists(image_path):
            return f"Image not found: {group}/{image}"

        return True


# Node registration
NODE_CLASS_MAPPINGS = {
    "BedrotLoadImage": BedrotLoadImage
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "BedrotLoadImage": "BEDROT's Load Image"
}
