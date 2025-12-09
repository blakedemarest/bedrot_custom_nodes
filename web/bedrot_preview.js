import { app } from "../../scripts/app.js";
import { ComfyWidgets } from "../../scripts/widgets.js";

/**
 * BEDROT Clip Text Preview - Frontend Extension
 *
 * Creates a read-only text widget to display the processed text
 * from BedrotCLIPTextEncode after execution.
 */

app.registerExtension({
    name: "bedrot.CLIPTextPreview",
    async beforeRegisterNodeDef(nodeType, nodeData, app) {
        if (nodeData.name !== "BedrotCLIPTextPreview") {
            return;
        }

        function populate(text) {
            // Clear existing text widgets (keep input widget if converted)
            if (this.widgets) {
                const isConvertedWidget = +!!this.inputs?.[0]?.widget;
                for (let i = isConvertedWidget; i < this.widgets.length; i++) {
                    this.widgets[i].onRemove?.();
                }
                this.widgets.length = isConvertedWidget;
            }

            // Create text display widgets
            const values = Array.isArray(text) ? text : [text];
            for (const t of values) {
                if (t === undefined || t === null) continue;
                const w = ComfyWidgets["STRING"](
                    this,
                    "preview_" + (this.widgets?.length ?? 0),
                    ["STRING", { multiline: true }],
                    app
                ).widget;
                w.inputEl.readOnly = true;
                w.inputEl.style.opacity = 0.6;
                w.value = String(t);
            }

            // Resize node to fit content
            requestAnimationFrame(() => {
                const sz = this.computeSize();
                if (sz[0] < this.size[0]) sz[0] = this.size[0];
                if (sz[1] < this.size[1]) sz[1] = this.size[1];
                this.onResize?.(sz);
                app.graph.setDirtyCanvas(true, false);
            });
        }

        // Handle execution result - display the text
        const onExecuted = nodeType.prototype.onExecuted;
        nodeType.prototype.onExecuted = function (message) {
            onExecuted?.apply(this, arguments);
            if (message.text) {
                populate.call(this, message.text);
            }
        };

        // Handle loading saved workflows
        const VALUES = Symbol();
        const configure = nodeType.prototype.configure;
        nodeType.prototype.configure = function () {
            this[VALUES] = arguments[0]?.widgets_values;
            return configure?.apply(this, arguments);
        };

        const onConfigure = nodeType.prototype.onConfigure;
        nodeType.prototype.onConfigure = function () {
            onConfigure?.apply(this, arguments);
            const widgets_values = this[VALUES];
            if (widgets_values?.length) {
                requestAnimationFrame(() => {
                    populate.call(this, widgets_values);
                });
            }
        };
    },
});
