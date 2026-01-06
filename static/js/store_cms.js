function storeCMS(config) {
    return {
        // --- State ---
        zoom: 45,
        elements: [],
        selectedElement: null,
        hasUnsavedChanges: false,

        // History / Undo-Redo
        history: [],
        historyIndex: -1,
        isUndoing: false,

        // Interaction
        resizingPanel: null,
        resizingElement: null,
        draggingElement: null,
        draggingOver: null,
        showMediaPicker: false,

        // Snapping & Guides
        guides: { x: [], y: [] },
        snapThreshold: 10,

        // Layout Metrics
        leftPanelWidth: 280,
        rightPanelWidth: 320,
        startMouse: { x: 0, y: 0 },
        startDims: { width: 0, height: 0, x: 0, y: 0 },

        init() {
            const savedData = config.savedData || [];
            this.elements = Array.isArray(savedData) ? savedData : [];
            this.recordState();

            // Keyboard Shortcuts
            window.addEventListener('keydown', (e) => {
                // Undo: Ctrl+Z
                if ((e.ctrlKey || e.metaKey) && e.key === 'z' && !e.shiftKey) {
                    e.preventDefault();
                    this.undo();
                }
                // Redo: Ctrl+Y or Ctrl+Shift+Z
                if ((e.ctrlKey || e.metaKey) && (e.key === 'y' || (e.shiftKey && e.key === 'z'))) {
                    e.preventDefault();
                    this.redo();
                }
                // Delete
                if (e.key === 'Delete' || e.key === 'Backspace') {
                    if (this.selectedElement && document.activeElement.tagName !== 'INPUT' && document.activeElement.tagName !== 'TEXTAREA') {
                        this.deleteSelected();
                    }
                }
                // Escape
                if (e.key === 'Escape') {
                    this.selectedElement = null;
                    this.showMediaPicker = false;
                }
            });

            window.addEventListener('media-selected', (e) => this.handleMediaSelection(e.detail));
        },

        // --- History Management ---
        recordState() {
            if (this.isUndoing) return;
            // Truncate future if we're in the middle
            if (this.historyIndex < this.history.length - 1) {
                this.history = this.history.slice(0, this.historyIndex + 1);
            }
            // Push deep copy
            this.history.push(JSON.stringify(this.elements));
            this.historyIndex++;
            this.hasUnsavedChanges = true;
        },

        undo() {
            if (this.historyIndex > 0) {
                this.isUndoing = true;
                this.historyIndex--;
                this.elements = JSON.parse(this.history[this.historyIndex]);
                this.selectedElement = null; // Deselect to avoid ghost selection
                this.$nextTick(() => this.isUndoing = false);
            }
        },

        redo() {
            if (this.historyIndex < this.history.length - 1) {
                this.isUndoing = true;
                this.historyIndex++;
                this.elements = JSON.parse(this.history[this.historyIndex]);
                this.selectedElement = null;
                this.$nextTick(() => this.isUndoing = false);
            }
        },

        // --- Layer Management ---
        // Z-Index is implicitly handled by array order (last = top)
        moveLayer(id, direction) {
            const index = this.elements.findIndex(el => el.id === id);
            if (index === -1) return;

            const el = this.elements[index];
            let newIndex = index;

            if (direction === 'up') newIndex = Math.min(index + 1, this.elements.length - 1);
            if (direction === 'down') newIndex = Math.max(index - 1, 0);
            if (direction === 'front') newIndex = this.elements.length - 1;
            if (direction === 'back') newIndex = 0;

            if (newIndex !== index) {
                this.elements.splice(index, 1);
                this.elements.splice(newIndex, 0, el);
                this.recordState();
            }
        },

        toggleLock(id) {
            const el = this.elements.find(e => e.id === id);
            if (el) {
                el.locked = !el.locked;
                this.recordState();
            }
        },

        toggleVisibility(id) {
            const el = this.elements.find(e => e.id === id);
            if (el) {
                el.visible = !el.visible;
                // If hiding selected, deselect
                if (!el.visible && this.selectedElement === id) {
                    this.selectedElement = null;
                }
                this.recordState();
            }
        },

        // --- Drag & Snap ---
        handleGlobalMouseMove(event) {
            // 1. Panel Resizing
            if (this.resizingPanel) {
                const delta = event.clientX - this.startMouse.x;
                if (this.resizingPanel === 'left') {
                    this.leftPanelWidth = Math.max(200, Math.min(this.startDims.width + delta, 500));
                } else {
                    this.rightPanelWidth = Math.max(250, Math.min(this.startDims.width - delta, 500));
                }
                return;
            }

            // 2. Element Dragging (with Snapping)
            if (this.draggingElement) {
                const el = this.elements.find(e => e.id === this.draggingElement);
                if (!el || el.locked) return;

                const scale = this.zoom / 100;
                const deltaX = (event.clientX - this.startMouse.x) / scale;
                const deltaY = (event.clientY - this.startMouse.y) / scale;

                let newX = this.startDims.x + deltaX;
                let newY = this.startDims.y + deltaY;

                // Reset guides
                this.guides = { x: [], y: [] };

                // Snapping Logic
                const centerX = newX + el.width / 2;
                const centerY = newY + el.height / 2;
                const rightX = newX + el.width;
                const bottomY = newY + el.height;
                const canvasW = 1920;
                const canvasH = 1080;

                // Snap to Canvas Center
                if (Math.abs(centerX - canvasW / 2) < this.snapThreshold) {
                    newX = canvasW / 2 - el.width / 2;
                    this.guides.x.push(canvasW / 2);
                }
                if (Math.abs(centerY - canvasH / 2) < this.snapThreshold) {
                    newY = canvasH / 2 - el.height / 2;
                    this.guides.y.push(canvasH / 2);
                }

                el.x = newX;
                el.y = newY;
                return; // Don't record state on every mouse move, only on Up
            }

            // 3. Element Resizing
            if (this.resizingElement) {
                const el = this.getSelected();
                if (!el || el.locked) return;

                const scale = this.zoom / 100;
                const deltaX = (event.clientX - this.startMouse.x) / scale;
                const deltaY = (event.clientY - this.startMouse.y) / scale;

                const handle = this.resizingElement;

                if (handle.includes('e')) el.width = Math.max(20, this.startDims.width + deltaX);
                if (handle.includes('w')) {
                    const newWidth = Math.max(20, this.startDims.width - deltaX);
                    el.width = newWidth;
                    el.x = this.startDims.x + (this.startDims.width - newWidth);
                }
                if (handle.includes('s')) el.height = Math.max(20, this.startDims.height + deltaY);
                if (handle.includes('n')) {
                    const newHeight = Math.max(20, this.startDims.height - deltaY);
                    el.height = newHeight;
                    el.y = this.startDims.y + (this.startDims.height - newHeight);
                }
            }
        },

        handleGlobalMouseUp() {
            if (this.draggingElement || this.resizingElement) {
                this.recordState(); // Commit change
            }
            this.resizingPanel = null;
            this.draggingElement = null;
            this.resizingElement = null;
            this.guides = { x: [], y: [] }; // Clear guides
            document.body.style.cursor = '';
            document.body.style.userSelect = '';
        },

        // --- Standard Methods ---
        startDrag(event, id) {
            if (event.button !== 0 || this.resizingElement) return;
            const el = this.elements.find(e => e.id === id);
            if (el.locked) return;

            this.draggingElement = id;
            this.selectElement(id);
            this.startMouse = { x: event.clientX, y: event.clientY };
            this.startDims = { x: el.x, y: el.y };
        },

        startElementResize(event, handle) {
            event.stopPropagation();
            const el = this.getSelected();
            if (el.locked) return;

            this.resizingElement = handle;
            this.startMouse = { x: event.clientX, y: event.clientY };
            this.startDims = { width: el.width, height: el.height, x: el.x, y: el.y };
        },

        startPanelResize(event, panel) {
            this.resizingPanel = panel;
            this.startMouse = { x: event.clientX, y: event.clientY };
            this.startDims = {
                width: panel === 'left' ? this.leftPanelWidth : this.rightPanelWidth,
                height: 0, x: 0, y: 0
            };
            document.body.style.cursor = 'col-resize';
            document.body.style.userSelect = 'none';
        },

        addElement(type) {
            const id = 'el_' + Date.now();
            const defaults = {
                heading: { width: 400, height: 80, content: 'New Heading', fontSize: 36, color: '#111827', textAlign: 'center' },
                paragraph: { width: 400, height: 120, content: 'Double click to edit text', fontSize: 18, color: '#374151', textAlign: 'left' },
                image: { width: 300, height: 200, content: '', objectFit: 'cover' },
                video: { width: 400, height: 225, content: '', autoplay: false, loop: false, muted: false },
                weather: { width: 250, height: 150, city: 'London', unit: 'c' },
                clock: { width: 200, height: 100, timezone: 'local', showDate: true, showSeconds: false },
                qrcode: { width: 150, height: 150, url: 'https://example.com', color: '#000000' },
                instagram: { width: 300, height: 350, source: '@instagram', mode: 'grid' }
            };

            const config = defaults[type] || { width: 200, height: 100 };

            this.elements.push({
                id: id,
                type: type,
                x: 1920 / 2 - config.width / 2,
                y: 1080 / 2 - config.height / 2,
                width: config.width,
                height: config.height,
                content: config.content || '',
                backgroundColor: '',
                opacity: 100,
                shadow: 'none',
                locked: false,
                visible: true,

                // Specific defaults
                fontSize: config.fontSize,
                color: config.color,
                textAlign: config.textAlign,
                objectFit: config.objectFit,
                autoplay: config.autoplay,
                loop: config.loop,
                muted: config.muted,
                city: config.city,
                unit: config.unit,
                timezone: config.timezone,
                showDate: config.showDate,
                showSeconds: config.showSeconds,
                url: config.url,
                source: config.source,
                mode: config.mode
            });

            this.selectedElement = id;
            this.recordState();
        },

        selectElement(id) {
            this.selectedElement = id;
        },

        getSelected() {
            return this.elements.find(el => el.id === this.selectedElement) || {};
        },

        deleteElement(id) {
            this.elements = this.elements.filter(el => el.id !== id);
            if (this.selectedElement === id) this.selectedElement = null;
            this.recordState();
        },

        deleteSelected() {
            if (this.selectedElement) this.deleteElement(this.selectedElement);
        },

        duplicateSelected() {
            const selected = this.getSelected();
            if (selected && selected.id) {
                const newId = 'el_' + Date.now();
                const newElement = { ...selected, id: newId, x: selected.x + 20, y: selected.y + 20 };
                this.elements.push(newElement);
                this.selectedElement = newId;
                this.recordState();
            }
        },

        // ... (keep existing media helpers if needed or rely on previous pattern)
        openMediaPicker() {
            this.showMediaPicker = true;
            if (window.htmx) {
                htmx.ajax('GET', config.urls.mediaLibrary + '?picker=true', '#media-picker-content');
            }
        },

        handleMediaSelection(media) {
            const element = this.getSelected();
            if (element && media.url) {
                element.content = media.url;
                this.showMediaPicker = false;
                this.recordState();
            }
        },

        handleImageDrop(event, id) {
            const file = event.dataTransfer.files[0];
            if (!file || !file.type.startsWith('image/')) return;

            const element = this.elements.find(el => el.id === id);
            const formData = new FormData();
            formData.append('file', file);
            formData.append('media_type', 'IMAGE');

            fetch(config.urls.uploadMedia, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': config.csrfToken,
                    'X-Requested-With': 'XMLHttpRequest'
                },
                body: formData
            })
                .then(res => res.json())
                .then(data => {
                    if (data.status === 'success' && element) {
                        element.content = data.url;
                        this.recordState();
                    } else {
                        alert('Upload failed: ' + (data.message || 'Unknown error'));
                    }
                });
        },

        saveLayoutName(name) {
            // Optional: trigger save or just update history
        },

        saveLayout() {
            const formData = new FormData();
            formData.append('layout_data', JSON.stringify(this.elements));
            formData.append('canvas_width', 1920);
            formData.append('canvas_height', 1080);
            formData.append('status', 'PUBLISHED');

            const btn = event.currentTarget || document.querySelector('button[title="Save & Publish"]');
            const originalText = btn ? btn.innerHTML : '';
            if (btn) btn.innerHTML = '<span class="material-symbols-outlined text-lg">sync</span> Saving...';

            fetch(config.urls.saveLayout, {
                method: 'POST',
                headers: { 'X-CSRFToken': config.csrfToken },
                body: formData
            })
                .then(response => {
                    if (response.ok) {
                        this.hasUnsavedChanges = false;
                        if (btn) {
                            btn.innerHTML = '<span class="material-symbols-outlined text-lg">check</span> Saved!';
                            setTimeout(() => btn.innerHTML = originalText, 1000);
                        }
                    } else {
                        alert('Error saving layout');
                        if (btn) btn.innerHTML = originalText;
                    }
                })
                .catch(error => {
                    console.error('Error:', error);
                    alert('Error saving layout');
                    if (btn) btn.innerHTML = originalText;
                });
        },

        previewLayout() {
            alert("Preview Mode not implemented yet.");
        },

        getShadowStyle(shadowType) {
            const shadows = {
                'none': 'none',
                'sm': '0 1px 2px 0 rgb(0 0 0 / 0.05)',
                'md': '0 4px 6px -1px rgb(0 0 0 / 0.1)',
                'lg': '0 10px 15px -3px rgb(0 0 0 / 0.1)',
                'xl': '0 20px 25px -5px rgb(0 0 0 / 0.1)'
            };
            return shadows[shadowType] || 'none';
        }
    }
}
