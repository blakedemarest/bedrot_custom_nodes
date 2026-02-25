"""
BEDROT Load Image - ComfyUI Custom Node

A LoadImage node with group-based organization.
Groups are folder references stored in groups.json config.
"""

import os
import hashlib
import numpy as np
import torch
from PIL import Image, ImageOps, ImageSequence

import folder_paths
import node_helpers

from .config import load_groups, get_group_path, ensure_default_group, DEFAULT_GROUP


def _get_groups():
    """Get list of available group names, with Unsorted first."""
    ensure_default_group()
    groups = load_groups()

    # Filter to groups whose paths still exist on disk
    valid = [g["name"] for g in groups if os.path.isdir(g["path"])]

    # Sort with Unsorted first
    valid.sort(key=lambda g: (g != DEFAULT_GROUP, g.lower()))

    if not valid:
        valid = [DEFAULT_GROUP]

    return valid


def _get_images_in_group(group):
    """Get list of image files in a specific group."""
    group_path = get_group_path(group)

    if not group_path or not os.path.isdir(group_path):
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
    - Images organized into groups (folder references)
    - Default 'Unsorted' group for quick uploads
    - Add groups via folder picker
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
                    "tooltip": "Image group (folder). Select a group to see its images."
                }),
                "image": (images, {
                    "tooltip": "Select an image from the current group. Drag-drop to upload.",
                    "control_after_generate": True
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
            empty_image = torch.zeros((1, 64, 64, 3), dtype=torch.float32)
            empty_mask = torch.zeros((1, 64, 64), dtype=torch.float32)
            return (empty_image, empty_mask, "")

        group_path = get_group_path(group)
        if not group_path:
            raise ValueError(f"Invalid group: {group}")

        image_path = os.path.join(group_path, image)

        # Validate path stays within group folder
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

        group_path = get_group_path(group)
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

        group_path = get_group_path(group)
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
