"""
BEDROT's Clip Text Preview - ComfyUI Custom Node

Displays the processed text output from BedrotCLIPTextEncode.
Connect to the processed_text output to see what text was sent to CLIP.
"""


class BedrotCLIPTextPreview:
    """
    Observability node that displays the processed text from BedrotCLIPTextEncode.
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "processed_text": ("STRING", {
                    "forceInput": True,
                    "tooltip": "Connect to processed_text output from BEDROT's Clip Text Encode"
                }),
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("text",)
    OUTPUT_TOOLTIPS = ("The processed text (pass-through).",)
    OUTPUT_NODE = True
    FUNCTION = "preview"
    CATEGORY = "conditioning"
    DESCRIPTION = "Displays the processed text from BEDROT's Clip Text Encode."

    def preview(self, processed_text):
        """
        Display the processed text in the UI.

        Args:
            processed_text: The processed text from BedrotCLIPTextEncode

        Returns:
            Dict with UI display data and result tuple
        """
        return {"ui": {"text": [processed_text]}, "result": (processed_text,)}


# Node registration for ComfyUI
NODE_CLASS_MAPPINGS = {
    "BedrotCLIPTextPreview": BedrotCLIPTextPreview,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "BedrotCLIPTextPreview": "BEDROT's Clip Text Preview",
}
