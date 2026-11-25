(function () {
    const root = document.getElementById('builder-root');
    if (!root) return;

    const list = document.getElementById('question-list');
    const empty = document.getElementById('question-empty');
    const count = document.getElementById('question-count');
    const addButton = document.getElementById('add-question');
    const hidden = document.getElementById('id_questions_json');
    const maxQuestions = Number(root.dataset.maxQuestions || 20);
    const initial = JSON.parse(root.dataset.initialQuestions || '[]');
    const typeLabels = {
        short_text: 'Jawaban singkat',
        long_text: 'Jawaban panjang',
        single_choice: 'Pilihan ganda',
        multiple_choice: 'Kotak centang',
        dropdown: 'Dropdown',
        rating: 'Rating',
    };
    const choiceTypes = ['single_choice', 'multiple_choice', 'dropdown'];
    let questions = initial.map(normalize);

    function normalize(question) {
        return {
            question_type: question.question_type || 'short_text',
            text: question.text || '',
            is_required: question.is_required !== false,
            options: Array.isArray(question.options) ? question.options : [],
            rating_max: Number(question.rating_max || 5),
        };
    }

    function syncHidden() {
        hidden.value = JSON.stringify(questions);
        count.textContent = questions.length;
        addButton.disabled = questions.length >= maxQuestions;
        empty.hidden = questions.length > 0;
    }

    function render() {
        list.innerHTML = '';
        questions.forEach((question, index) => {
            const card = document.createElement('article');
            card.className = 'question-editor-card';
            card.dataset.index = index;
            card.innerHTML = `
                <div class="question-editor-head">
                    <span class="question-index">${String(index + 1).padStart(2, '0')}</span>
                    <span class="question-type-label">${typeLabels[question.question_type]}</span>
                    <div class="question-move-actions">
                        <button type="button" class="icon-button move-up" title="Naikkan" ${index === 0 ? 'disabled' : ''}>↑</button>
                        <button type="button" class="icon-button move-down" title="Turunkan" ${index === questions.length - 1 ? 'disabled' : ''}>↓</button>
                        <button type="button" class="icon-button delete-question" title="Hapus">×</button>
                    </div>
                </div>
                <div class="form-field compact-field">
                    <label>Pertanyaan</label>
                    <textarea class="question-text" maxlength="300" rows="2" placeholder="Tulis pertanyaan...">${escapeHtml(question.text)}</textarea>
                    <small class="character-count">${question.text.length}/300 karakter</small>
                </div>
                <div class="question-settings-grid">
                    <div class="form-field compact-field">
                        <label>Tipe pertanyaan</label>
                        <select class="question-type">
                            ${Object.entries(typeLabels).map(([value, label]) => `<option value="${value}" ${question.question_type === value ? 'selected' : ''}>${label}</option>`).join('')}
                        </select>
                    </div>
                    <label class="toggle-row compact-toggle"><input type="checkbox" class="required-toggle" ${question.is_required ? 'checked' : ''}><span><strong>Wajib diisi</strong><small>Responden harus menjawab.</small></span></label>
                </div>
                <div class="dynamic-settings">
                    ${choiceTypes.includes(question.question_type) ? `<div class="form-field compact-field"><label>Opsi jawaban <span class="soft-label">(satu opsi per baris, maksimal 10)</span></label><textarea class="question-options" rows="4" placeholder="Opsi pertama\nOpsi kedua">${escapeHtml(question.options.join('\n'))}</textarea></div>` : ''}
                    ${question.question_type === 'rating' ? `<div class="form-field compact-field rating-setting"><label>Skala rating</label><input class="rating-max" type="number" min="2" max="100" value="${question.rating_max}"><small>Skala dimulai dari 1 sampai nilai maksimum.</small></div>` : ''}
                </div>
            `;
            list.appendChild(card);
        });
        syncHidden();
    }

    function escapeHtml(value) {
        return String(value).replace(/[&<>'"]/g, (char) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#039;', '"': '&quot;' }[char]));
    }

    function syncCard(card) {
        const index = Number(card.dataset.index);
        const question = questions[index];
        question.text = card.querySelector('.question-text').value;
        question.question_type = card.querySelector('.question-type').value;
        question.is_required = card.querySelector('.required-toggle').checked;
        const optionsField = card.querySelector('.question-options');
        question.options = optionsField ? optionsField.value.split('\n').map((option) => option.trim()).filter(Boolean) : [];
        const ratingField = card.querySelector('.rating-max');
        question.rating_max = ratingField ? Number(ratingField.value || 5) : 5;
    }

    list.addEventListener('input', (event) => {
        const card = event.target.closest('.question-editor-card');
        if (!card) return;
        syncCard(card);
        const characterCount = card.querySelector('.character-count');
        if (characterCount) characterCount.textContent = `${questions[Number(card.dataset.index)].text.length}/300 karakter`;
        syncHidden();
    });

    list.addEventListener('change', (event) => {
        const card = event.target.closest('.question-editor-card');
        if (!card) return;
        syncCard(card);
        if (event.target.classList.contains('question-type')) render();
        else syncHidden();
    });

    list.addEventListener('click', (event) => {
        const card = event.target.closest('.question-editor-card');
        if (!card) return;
        syncCard(card);
        const index = Number(card.dataset.index);
        if (event.target.closest('.delete-question')) {
            questions.splice(index, 1);
        } else if (event.target.closest('.move-up') && index > 0) {
            [questions[index - 1], questions[index]] = [questions[index], questions[index - 1]];
        } else if (event.target.closest('.move-down') && index < questions.length - 1) {
            [questions[index + 1], questions[index]] = [questions[index], questions[index + 1]];
        } else {
            return;
        }
        render();
    });

    addButton.addEventListener('click', () => {
        if (questions.length >= maxQuestions) return;
        questions.push(normalize({ text: '' }));
        render();
        const lastText = list.lastElementChild && list.lastElementChild.querySelector('.question-text');
        if (lastText) lastText.focus();
    });

    document.getElementById('questionnaire-builder-form').addEventListener('submit', () => {
        list.querySelectorAll('.question-editor-card').forEach(syncCard);
        syncHidden();
    });

    render();
})();
