function contentEditor(config) {
    return {
        title: config.title || '',
        contentHtml: '',
        wordCount: 0,
        charCount: 0,
        lastSaved: null,
        config: config,

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
