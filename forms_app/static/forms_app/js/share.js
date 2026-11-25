(function () {
    document.querySelectorAll('[data-copy]').forEach((button) => {
        button.addEventListener('click', async () => {
            const value = button.dataset.copy;
            try {
                await navigator.clipboard.writeText(value);
                const original = button.textContent;
                button.textContent = 'Tersalin';
                window.setTimeout(() => { button.textContent = original; }, 1400);
            } catch (error) {
                window.prompt('Salin teks berikut:', value);
            }
        });
    });
})();
