"""
BEDROT's Save Audio - Custom ComfyUI Node

Save audio in any format (WAV, FLAC, MP3, Opus) with auto-incrementing
filenames. Drop-in replacement for the built-in SaveAudio that only
supports FLAC.

Uses the same folder_paths.get_save_image_path() counter system as
SaveAudio/SaveImage, so filenames never collide or overwrite.
"""

import os
import json
from io import BytesIO

import av
import torch
import torchaudio
import folder_paths
from comfy.cli_args import args


# Opus requires specific sample rates
_OPUS_RATES = [8000, 12000, 16000, 24000, 48000]


class BedrotSaveAudio:
    """
    Save audio with selectable format and auto-incrementing filenames.
    Works identically to the built-in SaveAudio but supports WAV, FLAC,
    MP3, and Opus output.
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "audio": ("AUDIO",),
                "filename_prefix": ("STRING", {
                    "default": "audio/ComfyUI",
                    "tooltip": "Prefix for output files. Supports subfolders (e.g. audio/pig1987)."
                }),
                "format": (["wav", "flac", "mp3", "opus"], {
                    "default": "wav",
                    "tooltip": "Output audio format."
                }),
            },
            "optional": {
                "quality": (["V0", "128k", "320k"], {
                    "default": "128k",
                    "tooltip": "Encoding quality for MP3/Opus. Ignored for WAV/FLAC."
                }),
            },
            "hidden": {
                "prompt": "PROMPT",
                "extra_pnginfo": "EXTRA_PNGINFO",
            },
        }

    RETURN_TYPES = ()
    FUNCTION = "save_audio"
    OUTPUT_NODE = True
    CATEGORY = "BEDROT/audio"

    def save_audio(self, audio, filename_prefix="audio/ComfyUI",
                   format="wav", quality="128k", prompt=None,
                   extra_pnginfo=None):
        output_dir = folder_paths.get_output_directory()
        full_output_folder, filename, counter, subfolder, _ = \
            folder_paths.get_save_image_path(filename_prefix, output_dir)

        # Build metadata dict from prompt/workflow info
        metadata = {}
        if not args.disable_metadata:
            if prompt is not None:
                metadata["prompt"] = json.dumps(prompt)
            if extra_pnginfo is not None:
                for key in extra_pnginfo:
                    metadata[key] = json.dumps(extra_pnginfo[key])

        results = []
        for batch_number, waveform in enumerate(audio["waveform"].cpu()):
            batch_filename = filename.replace("%batch_num%", str(batch_number))
            file = f"{batch_filename}_{counter:05d}_.{format}"
            output_path = os.path.join(full_output_folder, file)

            sample_rate = audio["sample_rate"]

            # Handle Opus sample rate requirements
            if format == "opus":
                if sample_rate > 48000:
                    sample_rate = 48000
                elif sample_rate not in _OPUS_RATES:
                    for rate in sorted(_OPUS_RATES):
                        if rate > sample_rate:
                            sample_rate = rate
                            break
                    if sample_rate not in _OPUS_RATES:
                        sample_rate = 48000
                if sample_rate != audio["sample_rate"]:
                    waveform = torchaudio.functional.resample(
                        waveform, audio["sample_rate"], sample_rate
                    )

            # Encode audio via PyAV
            output_buffer = BytesIO()
            container = av.open(output_buffer, mode="w", format=format)

            # Set metadata on container
            for key, value in metadata.items():
                container.metadata[key] = value

            layout = "mono" if waveform.shape[0] == 1 else "stereo"

            # Configure codec based on format
            if format == "wav":
                stream = container.add_stream("pcm_s16le", rate=sample_rate, layout=layout)
            elif format == "flac":
                stream = container.add_stream("flac", rate=sample_rate, layout=layout)
            elif format == "mp3":
                stream = container.add_stream("libmp3lame", rate=sample_rate, layout=layout)
                if quality == "V0":
                    stream.codec_context.qscale = 1
                elif quality == "128k":
                    stream.bit_rate = 128000
                elif quality == "320k":
                    stream.bit_rate = 320000
            elif format == "opus":
                stream = container.add_stream("libopus", rate=sample_rate, layout=layout)
                if quality == "128k":
                    stream.bit_rate = 128000
                elif quality == "320k":
                    stream.bit_rate = 320000
                else:
                    stream.bit_rate = 128000

            # Create audio frame from tensor
            frame = av.AudioFrame.from_ndarray(
                waveform.movedim(0, 1).reshape(1, -1).float().numpy(),
                format="flt",
                layout=layout,
            )
            frame.sample_rate = sample_rate
            frame.pts = 0

            # Encode and mux
            container.mux(stream.encode(frame))
            container.mux(stream.encode(None))  # Flush
            container.close()

            # Write to disk
            output_buffer.seek(0)
            with open(output_path, "wb") as f:
                f.write(output_buffer.getbuffer())

            results.append({
                "filename": file,
                "subfolder": subfolder,
                "type": "output",
            })
            counter += 1

        return {"ui": {"audio": results}}


NODE_CLASS_MAPPINGS = {
    "BedrotSaveAudio": BedrotSaveAudio,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "BedrotSaveAudio": "BEDROT's Save Audio",
}
