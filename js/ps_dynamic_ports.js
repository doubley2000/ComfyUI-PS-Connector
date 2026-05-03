import { app } from "../../scripts/app.js";

app.registerExtension({
    name: "PS.DynamicWorkflowConfig",
    async beforeRegisterNodeDef(nodeType, nodeData, app) {
        
        // ==========================================
        // 节点 1: PS Workflow Config (PS) 的动态逻辑
        // ==========================================
        if (nodeData.name === "PSWorkflowConfig") {

            const shiftConnections = function(node) {
                if (node._isShifting) return; 
                node._isShifting = true;

                let imageLinks = [];
                let maskLinks = [];

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

                let validMaskLinks = [];
                for (let i = 1; i <= imageLinks.length; i++) {
                    if (maskLinks.length > 0) {
                        validMaskLinks.push(maskLinks.shift());
                    }
                }

                for (let i = 1; i <= 4; i++) {
                    const imgIdx = node.findInputSlot(`image${i}`);
                    if (imgIdx !== -1) node.disconnectInput(imgIdx);
                    const mskIdx = node.findInputSlot(`mask${i}`);
                    if (mskIdx !== -1) node.disconnectInput(mskIdx);
                }

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

            const syncLogicWidgets = function(node) {
                for (let i = 1; i <= 4; i++) {
                    const imgW = node.widgets.find(w => w.name === `img${i}_req`);
                    const mskW = node.widgets.find(w => w.name === `msk${i}_req`);
                    if (imgW && mskW) {
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
                
                const node = this; // 缓存 node 实例
                requestAnimationFrame(() => {
                    if (node.widgets) {
                        node.widgets.forEach(w => {
                            if (w.name.startsWith("img") && w.name.endsWith("_req")) {
                                // V2 修复：使用 callback 替代 Object.defineProperty
                                const origCb = w.callback;
                                w.callback = function(val, ...args) {
                                    w.value = val; // 确保值已更新
                                    syncLogicWidgets(node);
                                    if (origCb) origCb.apply(this, [val, ...args]);
                                };
                            }
                        });
                    }
                    node.updateDynamicUI();
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

                const inputOrder = ["model", "lora", "prompt", "neg_prompt", "image1", "mask1", "image2", "mask2", "image3", "mask3", "image4", "mask4"];
                this.inputs.sort((a, b) => (inputOrder.indexOf(a.name) - inputOrder.indexOf(b.name)));
                
                const widgetOrder = ["size_logic", "width", "height", "long_side_pixels", "img1_req", "msk1_req", "img2_req", "msk2_req", "img3_req", "msk3_req", "img4_req", "msk4_req"];
                this.widgets.sort((a, b) => (widgetOrder.indexOf(a.name) - widgetOrder.indexOf(b.name)));

                if (this.computeSize) {
                    const sz = this.computeSize();
                    this.setSize([this.size[0], sz[1]]);
                }
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

                let connType = null;
                const getInp = this.inputs.find(inp => inp.name === "get");
                
                if (getInp && getInp.link != null) {
                    const linkInfo = app.graph.links[getInp.link];
                    if (linkInfo) {
                        connType = linkInfo.type;
                    }
                }

                const showIsRequired = (connType === "IMAGE" || connType === "MASK");

                if (showIsRequired) {
                    if (!this.widgets.find(w => w.name === "is_required") && this._psWidgetCache["is_required"]) {
                        this.widgets.push(this._psWidgetCache["is_required"]);
                    }
                } else {
                    const idx = this.widgets.findIndex(w => w.name === "is_required");
                    if (idx !== -1) {
                        this._psWidgetCache["is_required"] = this.widgets[idx]; 
                        this.widgets.splice(idx, 1);
                    }
                }

                const widgetOrder = ["ui_label", "is_required"];
                this.widgets.sort((a, b) => (widgetOrder.indexOf(a.name) - widgetOrder.indexOf(b.name)));

                if (this.computeSize) {
                    const sz = this.computeSize();
                    this.setSize([this.size[0], sz[1]]);
                }
                this.setDirtyCanvas(true, true);
            };
        }

        // ==========================================
        // 节点 3: PS Image Preview 的动态逻辑
        // ==========================================
        else if (nodeData.name === "PSImagePreview") {

            const onNodeCreated = nodeType.prototype.onNodeCreated;
            nodeType.prototype.onNodeCreated = function () {
                if (onNodeCreated) onNodeCreated.apply(this, arguments);
                
                const node = this; // 缓存节点实例供回调使用

                // V2 兼容核心：弃用 Object.defineProperty，改用 LiteGraph 原生的 widget.callback
                requestAnimationFrame(() => {
                    if (node.widgets) {
                        const insertW = node.widgets.find(w => w.name === "insert");
                        const returnW = node.widgets.find(w => w.name === "return");
                        
                        if (insertW && returnW) {
                            // 拦截 insert 的点击事件
                            const origInsertCb = insertW.callback;
                            insertW.callback = function(val, ...args) {
                                insertW.value = val;
                                if (val === true) {
                                    returnW.value = false;
                                }
                                if (origInsertCb) origInsertCb.apply(this, [val, ...args]);
                                node.updateDynamicUI(); // 触发 UI 更新
                            };

                            // 拦截 return 的点击事件
                            const origReturnCb = returnW.callback;
                            returnW.callback = function(val, ...args) {
                                returnW.value = val;
                                if (val === true) {
                                    insertW.value = false;
                                }
                                if (origReturnCb) origReturnCb.apply(this, [val, ...args]);
                                node.updateDynamicUI(); // 触发 UI 更新
                            };
                        }
                    }
                    node.updateDynamicUI();
                });
            };

            const onConfigure = nodeType.prototype.onConfigure;
            nodeType.prototype.onConfigure = function(info) {
                if (onConfigure) onConfigure.apply(this, arguments);
                this.updateDynamicUI();
            };

            nodeType.prototype.updateDynamicUI = function () {
                if (!this.inputs || !this.widgets) return;

                const insertWidget = this.widgets.find(w => w.name === "insert");
                const returnWidget = this.widgets.find(w => w.name === "return");
                if (!insertWidget || !returnWidget) return;

                const isInsertOrReturn = insertWidget.value || returnWidget.value;
                const img1Inp = this.inputs.find(inp => inp.name === "image1");
                const img2Inp = this.inputs.find(inp => inp.name === "image2");
                const maskInp = this.inputs.find(inp => inp.name === "mask");

                let changed = false;

                if (isInsertOrReturn) {
                    // 开启任意一个选项：如果 image2 存在，我们需要转移连线并删掉它
                    if (img2Inp) {
                        changed = true;
                        if (img2Inp.link != null) {
                            const link2 = app.graph.links[img2Inp.link];
                            if (link2) {
                                const originNode = app.graph.getNodeById(link2.origin_id);
                                const targetSlot2 = this.findInputSlot("image2");
                                
                                this.disconnectInput(targetSlot2);
                                
                                if (img1Inp && img1Inp.link == null && originNode) {
                                    const targetSlot1 = this.findInputSlot("image1");
                                    if (targetSlot1 !== -1) {
                                        originNode.connect(link2.origin_slot, this, targetSlot1);
                                    }
                                }
                            }
                        }

                        const img2Idx = this.inputs.findIndex(inp => inp.name === "image2");
                        if (img2Idx !== -1) {
                            this.removeInput(img2Idx);
                        }
                    }
                    
                    // 同样，如果 mask 存在也删掉它
                    if (maskInp) {
                        changed = true;
                        if (maskInp.link != null) {
                            const targetSlotMask = this.findInputSlot("mask");
                            this.disconnectInput(targetSlotMask);
                        }
                        const maskIdx = this.inputs.findIndex(inp => inp.name === "mask");
                        if (maskIdx !== -1) {
                            this.removeInput(maskIdx);
                        }
                    }
                } else {
                    // 都关闭的情况下：恢复 image2 和 mask
                    if (!img2Inp) {
                        changed = true;
                        this.addInput("image2", "IMAGE");
                    }
                    if (!maskInp) {
                        changed = true;
                        this.addInput("mask", "MASK");
                    }
                }

                // 如果发生了端口变化，重排列并重置尺寸
                if (changed) {
                    const inputOrder = ["image1", "image2", "mask"];
                    this.inputs.sort((a, b) => {
                        let posA = inputOrder.indexOf(a.name);
                        let posB = inputOrder.indexOf(b.name);
                        if (posA === -1) posA = 999;
                        if (posB === -1) posB = 999;
                        return posA - posB;
                    });

                    // V2 必须调用此方法让节点外框跟随内容缩放
                    if (this.computeSize) {
                        const newSize = this.computeSize();
                        this.setSize([this.size[0], newSize[1]]);
                    }
                }

                this.setDirtyCanvas(true, true);
            };
        }
    }
});
