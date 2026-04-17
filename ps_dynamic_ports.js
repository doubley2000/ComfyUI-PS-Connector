import { app } from "../../scripts/app.js";

app.registerExtension({
    name: "PS.DynamicWorkflowConfig",
    async beforeRegisterNodeDef(nodeType, nodeData, app) {
        
        // ==========================================
        // 节点 1: PS Workflow Config (PS) 的动态逻辑
        // ==========================================
        if (nodeData.name === "PSWorkflowConfig") {

            // --- 核心工具函数：处理连线移位 ---
            const shiftConnections = function(node) {
                if (node._isShifting) return; // 防止递归死循环
                node._isShifting = true;

                let imageLinks = [];
                let maskLinks = [];

                // 1. 收集当前所有 image 和 mask 的连线信息
                for (let i = 1; i <= 4; i++) {
                    const imgInp = node.inputs.find(inp => inp.name === `image${i}`);
                    const mskInp = node.inputs.find(inp => inp.name === `mask${i}`);
                    
                    if (imgInp && imgInp.link !== null) {
                        const link = app.graph.links[imgInp.link];
                        if (link) imageLinks.push(link);
                    }
                    if (mskInp && mskInp.link !== null) {
                        const link = app.graph.links[mskInp.link];
                        if (link) maskLinks.push(link);
                    }
                }

                // 2. 检查：如果 image 没了，对应的 mask 必须断开
                let validMaskLinks = [];
                for (let i = 1; i <= imageLinks.length; i++) {
                    if (maskLinks.length > 0) {
                        validMaskLinks.push(maskLinks.shift());
                    }
                }

                // 3. 断开所有旧连线
                for (let i = 1; i <= 4; i++) {
                    const imgIdx = node.findInputSlot(`image${i}`);
                    if (imgIdx !== -1) node.disconnectInput(imgIdx);
                    const mskIdx = node.findInputSlot(`mask${i}`);
                    if (mskIdx !== -1) node.disconnectInput(mskIdx);
                }

                // 4. 重新按顺序连接
                imageLinks.forEach((link, idx) => {
                    const targetSlot = node.findInputSlot(`image${idx + 1}`);
                    if (targetSlot !== -1) {
                        const originNode = app.graph.getNodeById(link.origin_id);
                        originNode.connect(link.origin_slot, node, targetSlot);
                    }
                });

                validMaskLinks.forEach((link, idx) => {
                    const targetSlot = node.findInputSlot(`mask${idx + 1}`);
                    if (targetSlot !== -1) {
                        const originNode = app.graph.getNodeById(link.origin_id);
                        originNode.connect(link.origin_slot, node, targetSlot);
                    }
                });

                node._isShifting = false;
            };

            // --- 核心工具函数：同步逻辑开关 ---
            const syncLogicWidgets = function(node) {
                for (let i = 1; i <= 4; i++) {
                    const imgW = node.widgets.find(w => w.name === `img${i}_req`);
                    const mskW = node.widgets.find(w => w.name === `msk${i}_req`);
                    if (imgW && mskW) {
                        // 如果 Image 逻辑为假，Mask 逻辑强制为假
                        if (imgW.value === false) {
                            mskW.value = false;
                        }
                    }
                }
            };

            const onNodeCreated = nodeType.prototype.onNodeCreated;
            nodeType.prototype.onNodeCreated = function () {
                if (onNodeCreated) onNodeCreated.apply(this, arguments);
                if (!this._psWidgetCache) this._psWidgetCache = {};
                
                this.onWidgetChanged = (name, value) => {
                    if (name.startsWith("img") && name.endsWith("_req")) {
                        syncLogicWidgets(this);
                    }
                };

                requestAnimationFrame(() => {
                    this.updateDynamicUI();
                });
            };

            const onConfigure = nodeType.prototype.onConfigure;
            nodeType.prototype.onConfigure = function(info) {
                if (onConfigure) onConfigure.apply(this, arguments);
                this.updateDynamicUI();
            };

            const onConnectionsChange = nodeType.prototype.onConnectionsChange;
            nodeType.prototype.onConnectionsChange = function (type, index, connected, link_info) {
                if (onConnectionsChange) onConnectionsChange.apply(this, arguments);

                if (type === 1 && !connected && !this._isShifting) {
                    setTimeout(() => {
                        shiftConnections(this);
                        this.updateDynamicUI();
                    }, 10);
                } else {
                    this.updateDynamicUI();
                }
            };

            nodeType.prototype.updateDynamicUI = function () {
                if (!this.inputs || !this.widgets) return;

                const isConnected = (name) => {
                    const input = this.inputs.find(inp => inp.name === name);
                    return input && input.link != null;
                };

                // 推导可见性
                let desiredInputs = ["image1"];
                let desiredWidgets = [];

                if (isConnected("prompt")) desiredInputs.push("neg_prompt");

                for (let i = 1; i <= 4; i++) {
                    if (isConnected(`image${i}`)) {
                        desiredWidgets.push(`img${i}_req`);
                        desiredInputs.push(`mask${i}`);

                        if (isConnected(`mask${i}`)) {
                            desiredWidgets.push(`msk${i}_req`);
                        }
                        
                        if (i < 4) desiredInputs.push(`image${i + 1}`);
                    }
                }

                // 物理管理 Widgets
                const allDynWidgets = ["img1_req", "msk1_req", "img2_req", "msk2_req", "img3_req", "msk3_req", "img4_req", "msk4_req"];
                for (let i = this.widgets.length - 1; i >= 0; i--) {
                    const w = this.widgets[i];
                    if (allDynWidgets.includes(w.name)) {
                        this._psWidgetCache[w.name] = w;
                        if (!desiredWidgets.includes(w.name)) this.widgets.splice(i, 1);
                    }
                }
                desiredWidgets.forEach(name => {
                    if (!this.widgets.find(w => w.name === name) && this._psWidgetCache[name]) {
                        this.widgets.push(this._psWidgetCache[name]);
                    }
                });

                // 物理管理 Inputs
                const allDynInputs = ["neg_prompt", "image1", "image2", "image3", "image4", "mask1", "mask2", "mask3", "mask4"];
                const inputTypes = { "neg_prompt": "STRING", "image1": "IMAGE", "image2": "IMAGE", "image3": "IMAGE", "image4": "IMAGE", "mask1": "MASK", "mask2": "MASK", "mask3": "MASK", "mask4": "MASK" };

                for (let i = this.inputs.length - 1; i >= 0; i--) {
                    const inp = this.inputs[i];
                    if (allDynInputs.includes(inp.name) && !desiredInputs.includes(inp.name) && inp.link == null) {
                        if (inp.name !== "image1") this.removeInput(i); 
                    }
                }
                desiredInputs.forEach(name => {
                    if (!this.inputs.find(inp => inp.name === name)) {
                        this.addInput(name, inputTypes[name]);
                    }
                });

                // 排序
                const inputOrder = ["model", "lora", "prompt", "neg_prompt", "image1", "mask1", "image2", "mask2", "image3", "mask3", "image4", "mask4"];
                this.inputs.sort((a, b) => (inputOrder.indexOf(a.name) - inputOrder.indexOf(b.name)));
                
                const widgetOrder = ["size_logic", "width", "height", "long_side_pixels", "img1_req", "msk1_req", "img2_req", "msk2_req", "img3_req", "msk3_req", "img4_req", "msk4_req"];
                this.widgets.sort((a, b) => (widgetOrder.indexOf(a.name) - widgetOrder.indexOf(b.name)));

                this.setDirtyCanvas(true, true);
            };
        } 
        
        // ==========================================
        // 节点 2: PS Get (Custom UI) 的动态逻辑
        // ==========================================
        else if (nodeData.name === "PSGetNode") {

            const onNodeCreated = nodeType.prototype.onNodeCreated;
            nodeType.prototype.onNodeCreated = function () {
                if (onNodeCreated) onNodeCreated.apply(this, arguments);
                if (!this._psWidgetCache) this._psWidgetCache = {};
                
                // 缓存并默认隐藏 is_required
                const idx = this.widgets.findIndex(w => w.name === "is_required");
                if (idx !== -1) {
                    this._psWidgetCache["is_required"] = this.widgets[idx];
                }

                requestAnimationFrame(() => {
                    this.updateDynamicUI();
                });
            };

            const onConfigure = nodeType.prototype.onConfigure;
            nodeType.prototype.onConfigure = function(info) {
                if (onConfigure) onConfigure.apply(this, arguments);
                this.updateDynamicUI();
            };

            const onConnectionsChange = nodeType.prototype.onConnectionsChange;
            nodeType.prototype.onConnectionsChange = function (type, index, connected, link_info) {
                if (onConnectionsChange) onConnectionsChange.apply(this, arguments);
                this.updateDynamicUI();
            };

            nodeType.prototype.updateDynamicUI = function () {
                if (!this.inputs || !this.widgets) return;

                // 判断连接进来的类型
                let connType = null;
                const getInp = this.inputs.find(inp => inp.name === "get");
                
                if (getInp && getInp.link != null) {
                    const linkInfo = app.graph.links[getInp.link];
                    // linkInfo.type 里面存的是原节点的输出类型（"IMAGE", "MASK", "INT", 等等）
                    if (linkInfo) {
                        connType = linkInfo.type;
                    }
                }

                // 仅在连接类型是 IMAGE 或 MASK 时显示 is_required 选项
                const showIsRequired = (connType === "IMAGE" || connType === "MASK");

                if (showIsRequired) {
                    // 如果被隐藏了，从缓存里拿出来放进去
                    if (!this.widgets.find(w => w.name === "is_required") && this._psWidgetCache["is_required"]) {
                        this.widgets.push(this._psWidgetCache["is_required"]);
                    }
                } else {
                    // 不是的话，直接移除它（隐藏）
                    const idx = this.widgets.findIndex(w => w.name === "is_required");
                    if (idx !== -1) {
                        this._psWidgetCache["is_required"] = this.widgets[idx]; // 再次确保安全缓存
                        this.widgets.splice(idx, 1);
                    }
                }

                // 排序：保证 ui_label 在上，is_required 在下
                const widgetOrder = ["ui_label", "is_required"];
                this.widgets.sort((a, b) => (widgetOrder.indexOf(a.name) - widgetOrder.indexOf(b.name)));

                this.setDirtyCanvas(true, true);
            };
        }
    }
});
