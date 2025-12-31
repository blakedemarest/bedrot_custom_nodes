import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

/**
 * BEDROT Load Image - Frontend Extension
 *
 * Provides dynamic group/image list refresh, custom upload routing,
 * and image preview functionality.
 */

// Constants matching backend
const BASE_FOLDER = "BedRot_custom_image_load";
const DEFAULT_GROUP = "Unsorted";

/**
 * Build the preview URL for an image in a group
 */
function buildPreviewUrl(group, filename) {
    if (!filename || filename === "[no images]") {
        return null;
    }
    return `/bedrot/view?group=${encodeURIComponent(group)}&filename=${encodeURIComponent(filename)}`;
}

/**
 * Fetch available groups from the API
 */
async function fetchGroups() {
    try {
        const response = await api.fetchApi("/bedrot/groups");
        if (response.ok) {
            const groups = await response.json();
            return groups.map(g => g.name);
        }
    } catch (error) {
        console.error("BEDROT LoadImage: Failed to fetch groups", error);
    }
    return [DEFAULT_GROUP];
}

/**
 * Fetch images for a specific group
 */
async function fetchImagesForGroup(group) {
    try {
        const response = await api.fetchApi(`/bedrot/images/${encodeURIComponent(group)}`);
        if (response.ok) {
            const images = await response.json();
            if (images.length === 0) {
                return ["[no images]"];
            }
            return images;
        }
    } catch (error) {
        console.error("BEDROT LoadImage: Failed to fetch images for group", group, error);
    }
    return ["[no images]"];
}

/**
 * Upload an image to a specific group
 */
async function uploadImageToGroup(file, group) {
    const formData = new FormData();
    formData.append("image", file);
    formData.append("group", group);

    try {
        const response = await api.fetchApi("/bedrot/upload/image", {
            method: "POST",
            body: formData
        });

        if (response.ok) {
            return await response.json();
        } else {
            const error = await response.json();
            console.error("BEDROT LoadImage: Upload failed", error);
            return null;
        }
    } catch (error) {
        console.error("BEDROT LoadImage: Upload error", error);
        return null;
    }
}

/**
 * Update a COMBO widget's options dynamically
 */
function updateComboOptions(widget, options) {
    if (!widget || !widget.options) return;

    widget.options.values = options;

    // If current value not in new options, select first option
    if (!options.includes(widget.value)) {
        widget.value = options[0] || "";
    }
}

// Register the ComfyUI extension
app.registerExtension({
    name: "bedrot.LoadImage",

    async beforeRegisterNodeDef(nodeType, nodeData, app) {
        if (nodeData.name !== "BedrotLoadImage") {
            return;
        }

        // Store original onNodeCreated
        const onNodeCreated = nodeType.prototype.onNodeCreated;

        nodeType.prototype.onNodeCreated = function() {
            // Call original if exists
            if (onNodeCreated) {
                onNodeCreated.apply(this, arguments);
            }

            const node = this;

            // Set up widget interactions after DOM is ready
            setTimeout(() => {
                const groupWidget = node.widgets?.find(w => w.name === "group");
                const imageWidget = node.widgets?.find(w => w.name === "image");

                if (groupWidget && imageWidget) {
                    // Store current group getter for preview URL construction
                    node.bedrotGetCurrentGroup = () => groupWidget.value || DEFAULT_GROUP;

                    // Function to update image preview
                    const updateImagePreview = () => {
                        const group = groupWidget.value || DEFAULT_GROUP;
                        const filename = imageWidget.value;
                        const previewUrl = buildPreviewUrl(group, filename);

                        // Update the widget's image preview if it exists
                        if (imageWidget.inputEl && imageWidget.inputEl.previousSibling) {
                            const img = imageWidget.inputEl.previousSibling;
                            if (img.tagName === "IMG") {
                                img.src = previewUrl || "";
                            }
                        }

                        // Also try to update via ComfyUI's image widget system
                        if (node.imgs && node.imgs.length > 0) {
                            const img = new Image();
                            img.onload = () => {
                                node.imgs = [img];
                                node.setSizeForImage?.();
                                app.graph.setDirtyCanvas(true, false);
                            };
                            img.src = previewUrl;
                        } else if (previewUrl) {
                            // Initialize image preview
                            const img = new Image();
                            img.onload = () => {
                                node.imgs = [img];
                                node.imageIndex = 0;
                                node.setSizeForImage?.();
                                app.graph.setDirtyCanvas(true, false);
                            };
                            img.src = previewUrl;
                        }
                    };

                    // Store original image callback
                    const originalImageCallback = imageWidget.callback;

                    // Override image widget callback to update preview
                    imageWidget.callback = function(value) {
                        if (originalImageCallback) {
                            originalImageCallback.call(this, value);
                        }
                        updateImagePreview();
                    };

                    // Store original group callback
                    const originalCallback = groupWidget.callback;

                    // Override group widget callback to refresh images
                    groupWidget.callback = async function(value) {
                        // Call original callback if exists
                        if (originalCallback) {
                            originalCallback.call(this, value);
                        }

                        // Fetch images for the new group
                        const images = await fetchImagesForGroup(value);
                        updateComboOptions(imageWidget, images);

                        // Update preview for new selection
                        updateImagePreview();

                        // Trigger graph update
                        app.graph.setDirtyCanvas(true, false);
                    };

                    // Initial preview load
                    updateImagePreview();

                    // Add refresh button functionality via context menu
                    node.bedrotRefreshGroups = async function() {
                        const groups = await fetchGroups();
                        updateComboOptions(groupWidget, groups);

                        // Also refresh images for current group
                        const images = await fetchImagesForGroup(groupWidget.value);
                        updateComboOptions(imageWidget, images);

                        // Update preview
                        updateImagePreview();

                        app.graph.setDirtyCanvas(true, false);
                    };

                    // Add "Add Group" button
                    node.addWidget("button", "Add Group", null, async () => {
                        try {
                            const response = await api.fetchApi("/bedrot/browse/folder", {
                                method: "POST"
                            });
                            const result = await response.json();

                            if (result.cancelled) {
                                return; // User cancelled the dialog
                            }

                            if (result.success) {
                                // Refresh groups and select the new one
                                const groups = await fetchGroups();
                                updateComboOptions(groupWidget, groups);
                                groupWidget.value = result.name;

                                // Refresh images for the new group
                                const images = await fetchImagesForGroup(result.name);
                                updateComboOptions(imageWidget, images);

                                // Update preview for the new group
                                updateImagePreview();

                                app.graph.setDirtyCanvas(true, false);
                            } else if (result.error) {
                                alert("Error adding group: " + result.error);
                            }
                        } catch (error) {
                            console.error("BEDROT LoadImage: Browse folder error", error);
                            alert("Failed to open folder browser");
                        }
                    });

                    // Remove the filter list widget that ComfyUI auto-adds for combo control
                    const filterWidget = node.widgets?.find(w => w.name === "control_filter_list");
                    if (filterWidget) {
                        const filterIndex = node.widgets.indexOf(filterWidget);
                        if (filterIndex > -1) {
                            node.widgets.splice(filterIndex, 1);
                        }
                    }
                }
            }, 100);
        };

        // Add context menu option for refresh
        const getExtraMenuOptions = nodeType.prototype.getExtraMenuOptions;
        nodeType.prototype.getExtraMenuOptions = function(_, options) {
            if (getExtraMenuOptions) {
                getExtraMenuOptions.apply(this, arguments);
            }

            options.unshift({
                content: "Refresh Groups & Images",
                callback: () => {
                    if (this.bedrotRefreshGroups) {
                        this.bedrotRefreshGroups();
                    }
                }
            });
        };

        // Handle file drops on the node
        const onDragOver = nodeType.prototype.onDragOver;
        nodeType.prototype.onDragOver = function(e) {
            if (onDragOver) {
                onDragOver.apply(this, arguments);
            }
            // Accept drag if it contains files
            if (e.dataTransfer && e.dataTransfer.types.includes("Files")) {
                e.preventDefault();
                return true;
            }
            return false;
        };

        const onDragDrop = nodeType.prototype.onDragDrop;
        nodeType.prototype.onDragDrop = async function(e) {
            // Check for files
            if (!e.dataTransfer || !e.dataTransfer.files || e.dataTransfer.files.length === 0) {
                if (onDragDrop) {
                    return onDragDrop.apply(this, arguments);
                }
                return false;
            }

            const node = this;
            const groupWidget = node.widgets?.find(w => w.name === "group");
            const imageWidget = node.widgets?.find(w => w.name === "image");
            const group = groupWidget?.value || DEFAULT_GROUP;

            // Process each dropped file
            for (const file of e.dataTransfer.files) {
                // Check if it's an image
                if (!file.type.startsWith("image/")) {
                    continue;
                }

                // Upload to the current group
                const result = await uploadImageToGroup(file, group);

                if (result && result.name) {
                    // Refresh image list and select the uploaded image
                    const images = await fetchImagesForGroup(group);
                    updateComboOptions(imageWidget, images);

                    // Select the newly uploaded image
                    if (images.includes(result.name)) {
                        imageWidget.value = result.name;
                    }

                    // Update preview with the uploaded image
                    const previewUrl = buildPreviewUrl(group, result.name);
                    if (previewUrl) {
                        const img = new Image();
                        img.onload = () => {
                            node.imgs = [img];
                            node.imageIndex = 0;
                            node.setSizeForImage?.();
                            app.graph.setDirtyCanvas(true, false);
                        };
                        img.src = previewUrl;
                    } else {
                        app.graph.setDirtyCanvas(true, false);
                    }
                }
            }

            return true;
        };
    },

    // Handle loaded graphs
    async loadedGraphNode(node) {
        if (node.type !== "BedrotLoadImage") {
            return;
        }

        // Refresh lists after load to ensure they're current
        setTimeout(async () => {
            const groupWidget = node.widgets?.find(w => w.name === "group");
            const imageWidget = node.widgets?.find(w => w.name === "image");

            if (groupWidget && imageWidget) {
                // Fetch current groups
                const groups = await fetchGroups();
                updateComboOptions(groupWidget, groups);

                // Fetch images for current group
                if (groupWidget.value) {
                    const images = await fetchImagesForGroup(groupWidget.value);
                    updateComboOptions(imageWidget, images);
                }

                // Load image preview
                const group = groupWidget.value || DEFAULT_GROUP;
                const filename = imageWidget.value;
                const previewUrl = buildPreviewUrl(group, filename);

                if (previewUrl) {
                    const img = new Image();
                    img.onload = () => {
                        node.imgs = [img];
                        node.imageIndex = 0;
                        node.setSizeForImage?.();
                        app.graph.setDirtyCanvas(true, false);
                    };
                    img.src = previewUrl;
                }

                // Remove the filter list widget that ComfyUI auto-adds for combo control
                const filterWidget = node.widgets?.find(w => w.name === "control_filter_list");
                if (filterWidget) {
                    const filterIndex = node.widgets.indexOf(filterWidget);
                    if (filterIndex > -1) {
                        node.widgets.splice(filterIndex, 1);
                    }
                }
            }
        }, 200);
    }
});
