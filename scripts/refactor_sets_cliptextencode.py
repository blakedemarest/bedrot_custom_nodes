"""
SETS Folder CLIPTextEncode Refactor Script

Batch-refactors ComfyUI workflow PNGs in the SETS folder, replacing positive
CLIPTextEncode nodes with BedrotCLIPTextEncode + BedrotCLIPTextPreview nodes.

Usage:
    python refactor_sets_cliptextencode.py --dry-run        # Analyze without writing
    python refactor_sets_cliptextencode.py --limit 10       # Process first 10 files
    python refactor_sets_cliptextencode.py --single FILE    # Process single file
    python refactor_sets_cliptextencode.py                  # Full run
"""

import argparse
import copy
import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional, Set, Tuple

from PIL import Image
from PIL.PngImagePlugin import PngInfo

# Configuration
SETS_PATH = Path(r"C:\Users\Earth\CSU Fullerton Dropbox\Blake Demarest\favs\SETS")
POSITIVE_ENCODER_TYPES = {"CLIPTextEncode", "smZ CLIPTextEncode"}

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class ProcessStatus(Enum):
    MODIFIED = "modified"
    SKIPPED = "skipped"
    ERROR = "error"
    NO_WORKFLOW = "no_workflow"


@dataclass
class ProcessResult:
    status: ProcessStatus
    message: str
    encoders_replaced: int = 0
    error: Optional[Exception] = None


@dataclass
class ProcessingStats:
    total_files: int = 0
    processed: int = 0
    modified: int = 0
    skipped: int = 0
    errors: int = 0
    encoders_replaced: int = 0
    error_files: list = field(default_factory=list)

    def report(self) -> str:
        return f"""
Processing Complete:
  Total files:       {self.total_files}
  Processed:         {self.processed}
  Modified:          {self.modified}
  Skipped (no pos):  {self.skipped}
  Errors:            {self.errors}
  Encoders replaced: {self.encoders_replaced}
"""


def find_positive_encoders(workflow: dict) -> Set[int]:
    """
    Identify CLIPTextEncode nodes feeding KSampler positive input (slot 1).

    Returns set of node IDs that are positive encoders.
    """
    nodes = workflow.get("nodes", [])
    links = workflow.get("links", [])

    # Build lookups
    nodes_by_id = {node["id"]: node for node in nodes}
    links_by_id = {link[0]: link for link in links}

    positive_encoder_ids = set()

    for node in nodes:
        node_type = node.get("type", "")

        # Find KSampler variants
        if "KSampler" not in node_type:
            continue

        # Find the link connected to input named "positive"
        for inp in node.get("inputs", []):
            if inp.get("name") == "positive" and inp.get("link") is not None:
                link_id = inp["link"]
                link = links_by_id.get(link_id)

                if link:
                    # Link format: [link_id, src_node, src_slot, dst_node, dst_slot, type]
                    src_node_id = link[1]
                    src_node = nodes_by_id.get(src_node_id)

                    if src_node and src_node.get("type") in POSITIVE_ENCODER_TYPES:
                        positive_encoder_ids.add(src_node_id)

    return positive_encoder_ids


def create_preview_node(encoder_node: dict, new_node_id: int, input_link_id: int) -> dict:
    """Create BedrotCLIPTextPreview node positioned relative to encoder."""
    encoder_pos = encoder_node.get("pos", [0, 0])

    # Handle both list and dict position formats
    if isinstance(encoder_pos, dict):
        x = encoder_pos.get("0", 0)
        y = encoder_pos.get("1", 0)
    else:
        x, y = encoder_pos[0], encoder_pos[1]

    return {
        "id": new_node_id,
        "type": "BedrotCLIPTextPreview",
        "pos": [x + 400, y],
        "size": [300, 100],
        "flags": {},
        "order": encoder_node.get("order", 0) + 1,
        "mode": 0,
        "inputs": [
            {
                "name": "processed_text",
                "type": "STRING",
                "link": input_link_id
            }
        ],
        "outputs": [
            {
                "name": "text",
                "type": "STRING",
                "slot_index": 0,
                "links": []
            }
        ],
        "properties": {
            "Node name for S&R": "BedrotCLIPTextPreview"
        },
        "widgets_values": []
    }


def modify_encoder_node(node: dict, preview_link_id: int) -> None:
    """
    Modify encoder node in place:
    - Change type to BedrotCLIPTextEncode
    - Add STRING output slot
    """
    # Change type
    node["type"] = "BedrotCLIPTextEncode"

    # Update S&R property
    if "properties" not in node:
        node["properties"] = {}
    node["properties"]["Node name for S&R"] = "BedrotCLIPTextEncode"

    # Ensure outputs exist
    if "outputs" not in node:
        node["outputs"] = []

    outputs = node["outputs"]

    # Ensure slot 0 exists (CONDITIONING)
    if len(outputs) == 0:
        outputs.append({
            "name": "CONDITIONING",
            "type": "CONDITIONING",
            "slot_index": 0,
            "links": []
        })

    # Add slot 1 (STRING for processed_text)
    outputs.append({
        "name": "STRING",
        "type": "STRING",
        "slot_index": 1,
        "links": [preview_link_id]
    })


def create_preview_link(link_id: int, encoder_id: int, preview_id: int) -> list:
    """Create link from encoder slot 1 to preview slot 0."""
    return [
        link_id,      # link_id
        encoder_id,   # src_node_id
        1,            # src_slot (STRING output)
        preview_id,   # dst_node_id
        0,            # dst_slot (processed_text input)
        "STRING"      # type
    ]


def refactor_workflow(workflow: dict) -> Tuple[dict, int]:
    """
    Main refactoring logic.

    Returns:
        Tuple[dict, int]: (modified_workflow, encoder_count)
    """
    workflow = copy.deepcopy(workflow)

    positive_encoder_ids = find_positive_encoders(workflow)

    if not positive_encoder_ids:
        return workflow, 0

    nodes_by_id = {node["id"]: node for node in workflow["nodes"]}
    encoders_modified = 0

    # Get starting IDs
    last_node_id = workflow.get("last_node_id", 0)
    last_link_id = workflow.get("last_link_id", 0)

    # Fallback: compute from existing nodes/links if counters missing
    if last_node_id == 0 and workflow["nodes"]:
        last_node_id = max(n["id"] for n in workflow["nodes"])
    if last_link_id == 0 and workflow.get("links"):
        last_link_id = max(link[0] for link in workflow["links"])

    for encoder_id in positive_encoder_ids:
        encoder_node = nodes_by_id.get(encoder_id)
        if not encoder_node:
            continue

        # Allocate new IDs
        last_node_id += 1
        last_link_id += 1
        preview_id = last_node_id
        link_id = last_link_id

        # 1. Modify encoder node type and outputs
        modify_encoder_node(encoder_node, link_id)

        # 2. Create preview node
        preview_node = create_preview_node(encoder_node, preview_id, link_id)
        workflow["nodes"].append(preview_node)

        # 3. Create link
        new_link = create_preview_link(link_id, encoder_id, preview_id)
        workflow["links"].append(new_link)

        encoders_modified += 1

    # Update counters
    workflow["last_node_id"] = last_node_id
    workflow["last_link_id"] = last_link_id

    return workflow, encoders_modified


def validate_json_roundtrip(data: dict) -> str:
    """
    Verify data can be serialized and deserialized without loss.

    Returns:
        str: JSON string if valid

    Raises:
        ValueError: If roundtrip fails
    """
    try:
        json_str = json.dumps(data, ensure_ascii=False)
        parsed = json.loads(json_str)

        if not isinstance(parsed, dict):
            raise ValueError("Roundtrip produced non-dict")

        return json_str
    except (json.JSONDecodeError, TypeError) as e:
        raise ValueError(f"JSON roundtrip failed: {e}")


def safe_write_png(path: Path, img: Image.Image, original_metadata: dict,
                   modified_workflow: dict) -> None:
    """
    Safely write PNG with modified workflow metadata.

    Uses atomic write pattern: write to temp file, then rename.
    Preserves ALL original metadata keys.

    Raises:
        IOError: If write fails
    """
    # Validate workflow JSON first
    workflow_json = validate_json_roundtrip(modified_workflow)

    # Build new metadata preserving all original keys
    metadata = PngInfo()

    for key, value in original_metadata.items():
        if key == "workflow":
            metadata.add_text("workflow", workflow_json)
        elif isinstance(value, str):
            metadata.add_text(key, value)

    # Atomic write: temp file then rename
    temp_path = path.with_suffix(".tmp.png")

    try:
        img.save(temp_path, format="PNG", pnginfo=metadata)

        # Verify the temp file is valid before replacing
        verify_img = Image.open(temp_path)
        verify_workflow = json.loads(verify_img.info.get("workflow", "{}"))
        if not verify_workflow.get("nodes"):
            raise IOError("Written file has empty/invalid workflow")
        verify_img.close()

        # On Windows, must remove target first
        if path.exists():
            path.unlink()

        temp_path.rename(path)

    except Exception as e:
        # Clean up temp file on failure
        if temp_path.exists():
            temp_path.unlink()
        raise IOError(f"Write failed: {e}")


def process_png(path: Path, dry_run: bool = False) -> ProcessResult:
    """
    Process a single PNG file.

    Args:
        path: Path to PNG file
        dry_run: If True, analyze but do not write

    Returns:
        ProcessResult
    """
    try:
        img = Image.open(path)
        original_metadata = dict(img.info)
    except Exception as e:
        return ProcessResult(ProcessStatus.ERROR, f"Cannot open file: {e}", error=e)

    if "workflow" not in original_metadata:
        img.close()
        return ProcessResult(ProcessStatus.NO_WORKFLOW, "No workflow metadata found")

    try:
        workflow = json.loads(original_metadata["workflow"])
    except json.JSONDecodeError as e:
        img.close()
        return ProcessResult(ProcessStatus.ERROR, f"Invalid JSON in source: {e}", error=e)

    try:
        modified_workflow, encoder_count = refactor_workflow(workflow)
    except Exception as e:
        img.close()
        return ProcessResult(ProcessStatus.ERROR, f"Refactor failed: {e}", error=e)

    if encoder_count == 0:
        img.close()
        return ProcessResult(ProcessStatus.SKIPPED, "No positive encoder found")

    if dry_run:
        img.close()
        return ProcessResult(
            ProcessStatus.MODIFIED,
            f"Would replace {encoder_count} encoder(s)",
            encoders_replaced=encoder_count
        )

    try:
        safe_write_png(path, img, original_metadata, modified_workflow)
        img.close()
        return ProcessResult(
            ProcessStatus.MODIFIED,
            f"Replaced {encoder_count} encoder(s)",
            encoders_replaced=encoder_count
        )
    except IOError as e:
        img.close()
        return ProcessResult(ProcessStatus.ERROR, f"Write failed: {e}", error=e)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Refactor SETS folder CLIPTextEncode to BEDROT nodes"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Analyze files without writing changes"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Process only first N files (for testing)"
    )
    parser.add_argument(
        "--single",
        type=str,
        default=None,
        help="Process a single file (full path)"
    )

    return parser.parse_args()


def main():
    args = parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Handle single file mode
    if args.single:
        single_path = Path(args.single)
        if not single_path.exists():
            logger.error(f"File not found: {single_path}")
            return

        print(f"Processing single file: {single_path}")
        if args.dry_run:
            print("DRY RUN MODE - No files will be modified")

        result = process_png(single_path, dry_run=args.dry_run)
        print(f"Result: {result.status.value} - {result.message}")
        return

    # Verify SETS path exists
    if not SETS_PATH.exists():
        logger.error(f"SETS path does not exist: {SETS_PATH}")
        return

    # Stream PNG files using os.walk (faster than rglob on Windows)
    import os
    print(f"Processing PNG files in {SETS_PATH}...", flush=True)
    if args.dry_run:
        print("DRY RUN MODE - No files will be modified", flush=True)
    print(flush=True)

    stats = ProcessingStats()
    i = 0

    for root, dirs, files in os.walk(SETS_PATH):
        for filename in files:
            if not filename.lower().endswith('.png'):
                continue

            if args.limit and i >= args.limit:
                break

            png_path = Path(root) / filename
            i += 1

            # Progress update every 500 files
            if i % 500 == 0:
                print(f"Progress: {i} files processed, {stats.modified} modified", flush=True)

            result = process_png(png_path, dry_run=args.dry_run)
            stats.processed += 1

            if result.status == ProcessStatus.MODIFIED:
                stats.modified += 1
                stats.encoders_replaced += result.encoders_replaced
                logger.debug(f"Modified: {png_path}")
            elif result.status == ProcessStatus.SKIPPED:
                stats.skipped += 1
            elif result.status == ProcessStatus.NO_WORKFLOW:
                stats.skipped += 1
                logger.debug(f"No workflow: {png_path}")
            elif result.status == ProcessStatus.ERROR:
                stats.errors += 1
                stats.error_files.append((png_path, result.message))
                logger.warning(f"Error in {png_path}: {result.message}")

        if args.limit and i >= args.limit:
            break

    stats.total_files = i
    print(stats.report(), flush=True)

    if stats.error_files and args.verbose:
        print("Error details:")
        for path, msg in stats.error_files[:10]:
            print(f"  {path}: {msg}")
        if len(stats.error_files) > 10:
            print(f"  ... and {len(stats.error_files) - 10} more")


if __name__ == "__main__":
    main()
