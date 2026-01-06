function playlistEditor(config) {
    return {
        playlistId: config.playlistId,
        items: [],

        init() {
            this.initSortable();
        },

        initSortable() {
            const el = document.getElementById('playlist-sequence');
            if (el && !el.sortable) {
                new Sortable(el, {
                    group: {
                        name: 'shared',
                        pull: false,
                        put: true
                    },
                    animation: 150,
                    ghostClass: 'bg-slate-50',
                    handle: '.cursor-move',
                    onAdd: (evt) => {
                        this.handleItemAdd(evt);
                    },
                    onEnd: (evt) => {
                        this.saveOrder();
                    }
                });
                el.sortable = true;
            }
        },

        handleItemAdd(evt) {
            const itemEl = evt.item;
            const mediaId = itemEl.dataset.id;

            // Remove the dragged element immediately as the backend will re-render the list
            itemEl.remove();

            // Trigger HTMX request to add item
            htmx.ajax('POST', config.urls.addMedia.replace('__MEDIA_ID__', mediaId), {
                target: '#playlist-sequence-container',
                swap: 'outerHTML',
                values: { playlist_id: this.playlistId }
            });
        },

        saveOrder() {
            const items = document.querySelectorAll('.sequence-item');
            const itemIds = Array.from(items).map(item => item.dataset.id);

            const formData = new FormData();
            formData.append('playlist_id', this.playlistId);
            itemIds.forEach(id => formData.append('item', id));

            fetch(config.urls.reorderPlaylist, {
                method: 'POST',
                headers: { 'X-CSRFToken': config.csrfToken },
                body: formData
            });
        }
    }
}
