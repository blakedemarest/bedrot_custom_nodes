"""
BEDROT's Load Audio - ComfyUI Custom Node

Load audio files from ComfyUI's input/ directory with control_after_generate
support (randomize/increment/decrement/fixed cycling) and audio preview playback.

Supports all audio formats: WAV, FLAC, MP3, OGG, OPUS, AIFF, and video
containers with embedded audio tracks. Uses PyAV for decoding via the shared
load() helper from comfy_extras.nodes_audio.
"""

import os
import hashlib

import torch
import folder_paths
from comfy_extras.nodes_audio import load


def _get_audio_files():
    """Scan input/ for audio and video files (video containers may have audio tracks)."""
    input_dir = folder_paths.get_input_directory()
    all_files = os.listdir(input_dir)
    audio_files = folder_paths.filter_files_content_types(all_files, ["audio", "video"])
    audio_files = sorted(audio_files)
    if not audio_files:
        return ["[no audio files]"]
    return audio_files


class BedrotLoadAudio:
    """
    Load audio from ComfyUI's input/ directory.

    Features:
    - control_after_generate: randomize/increment/decrement/fixed cycling
    - Audio preview/playback widget in the node after generation
    - All formats via PyAV (WAV, FLAC, MP3, OGG, OPUS, AIFF, video containers)
    """

    @classmethod
    def INPUT_TYPES(cls):
        audio_files = _get_audio_files()
        return {
            "required": {
                "audio": (audio_files, {
                    "default": audio_files[0],
                    "tooltip": "Audio file from input/ directory. Supports randomize/increment/decrement modes.",
                    "control_after_generate": True,
                }),
            },
        }

    RETURN_TYPES = ("AUDIO",)
    RETURN_NAMES = ("audio",)
    FUNCTION = "load_audio"
    OUTPUT_NODE = True
    CATEGORY = "BEDROT/audio"

    def load_audio(self, audio):
        # Handle placeholder when input/ has no audio files
        if audio == "[no audio files]":
            empty_waveform = torch.zeros((1, 2, 1), dtype=torch.float32)
            empty_audio = {"waveform": empty_waveform, "sample_rate": 44100}
            return {"ui": {"audio": []}, "result": (empty_audio,)}

        # Resolve annotated path (e.g. "mysong.wav [input]" -> absolute path)
        audio_path = folder_paths.get_annotated_filepath(audio)

        # Decode via PyAV -- returns (waveform [channels, samples], sample_rate)
        waveform, sample_rate = load(audio_path)

        # AUDIO type expects batch dimension: [batch, channels, samples]
        audio_dict = {
            "waveform": waveform.unsqueeze(0),
            "sample_rate": sample_rate,
        }

        # Strip any [input] annotation to get bare filename for the UI
        bare_filename = audio.split(" [")[0] if " [" in audio else audio

        # Return tensor output + audio preview UI dict
        # type: "input" tells frontend to serve the file from input/ directly
        return {
            "ui": {
                "audio": [{
                    "filename": bare_filename,
                    "subfolder": "",
                    "type": "input",
                }]
            },
            "result": (audio_dict,),
        }

    @classmethod
    def IS_CHANGED(cls, audio):
        """SHA-256 of file content for cache invalidation."""
        if audio == "[no audio files]":
            return ""
        audio_path = folder_paths.get_annotated_filepath(audio)
        if not os.path.exists(audio_path):
            return ""
        m = hashlib.sha256()
        with open(audio_path, "rb") as f:
            m.update(f.read())
        return m.digest().hex()

    @classmethod
    def VALIDATE_INPUTS(cls, audio):
        """Reject execution if the selected file no longer exists."""
        if audio == "[no audio files]":
            return True
        if not folder_paths.exists_annotated_filepath(audio):
            return "Audio file not found: {}".format(audio)
        return True


NODE_CLASS_MAPPINGS = {
    "BedrotLoadAudio": BedrotLoadAudio,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "BedrotLoadAudio": "BEDROT's Load Audio",
}
