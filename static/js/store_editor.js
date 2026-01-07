function contentEditor(config) {
    return {
        title: config.title || '',
        contentHtml: '',
        wordCount: 0,
        charCount: 0,
        lastSaved: null,
        config: config,

        activeTab: config.activeTab || 'library',
        duration: config.duration || 15,
        startDate: config.startDate || '',
        endDate: config.endDate || '',
        targetScreen: config.targetScreen || 'all',

        init() {
            this.updateCounts();
        },

        updateCounts() {
            const text = this.contentHtml.replace(/<[^>]*>/g, '');
            this.charCount = text.length;
            this.wordCount = text.trim() ? text.trim().split(/\s+/).length : 0;
        },

        saveDraft() {
            this.save('DRAFT');
        },

        publish() {
            this.save('PUBLISHED');
        },

        save(status) {
            if (!this.config.saveUrl) {
                console.warn('No save URL configured. Content might be new/unsaved.');
                return;
            }

            const formData = new FormData();
            formData.append('title', this.title);
            formData.append('content_html', this.contentHtml);
            formData.append('status', status);
            formData.append('duration', this.duration);
            formData.append('start_date', this.startDate);
            formData.append('end_date', this.endDate);
            formData.append('target_screen', this.targetScreen);

            fetch(this.config.saveUrl, {
                method: 'POST',
                headers: { 'X-CSRFToken': this.config.csrfToken },
                body: formData
            }).then(() => {
                this.lastSaved = new Date().toLocaleTimeString();
            }).catch(err => {
                console.error('Error saving content:', err);
            });
        },

        insertMedia(url) {
            document.execCommand('insertImage', false, url);
            this.updateCounts();
        }
    }
}
