import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

/**
 * BEDROT Load Image - Frontend Extension
 *
 * Provides dynamic group/image list refresh and custom upload routing.
 */

// Constants matching backend
const BASE_FOLDER = "BedRot_custom_image_load";
const DEFAULT_GROUP = "Unsorted";

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
                    // Store original callback
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

                        // Trigger graph update
                        app.graph.setDirtyCanvas(true, false);
                    };

                    // Add refresh button functionality via context menu
                    node.bedrotRefreshGroups = async function() {
                        const groups = await fetchGroups();
                        updateComboOptions(groupWidget, groups);

                        // Also refresh images for current group
                        const images = await fetchImagesForGroup(groupWidget.value);
                        updateComboOptions(imageWidget, images);

                        app.graph.setDirtyCanvas(true, false);
                    };
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

                    app.graph.setDirtyCanvas(true, false);
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
            }
        }, 200);
    }
});
