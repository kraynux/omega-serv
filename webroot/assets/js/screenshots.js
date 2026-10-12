    // ============================================
    // CONSTRUCTION DYNAMIQUE DE LA LISTE DES SCREENSHOTS
    // ============================================
    const cards = Array.from(document.querySelectorAll('.screenshot-card'));
    const screenshots = cards.map(card => {
        const title = card.querySelector('.screenshot-caption h4')?.textContent || '';
        const desc = card.querySelector('.screenshot-caption p')?.textContent || '';
        const num = card.querySelector('.screenshot-caption .num')?.textContent || '';
        return { title, desc, num };
    });

    let currentIndex = 0;
    const modal = document.getElementById('modalOverlay');
    const modalImage = document.getElementById('modalImage');
    const modalIndex = document.getElementById('modalIndex');
    const modalTitle = document.getElementById('modalTitle');
    const modalDesc = document.getElementById('modalDesc');
    const modalCounter = document.getElementById('modalCounter');
    const modalClose = document.getElementById('modalClose');
    const modalPrev = document.getElementById('modalPrev');
    const modalNext = document.getElementById('modalNext');

    // ============================================
    // OUVERTURE DU MODAL
    // ============================================
    function openModal(index) {
        if (index < 0 || index >= cards.length) return;
        currentIndex = index;
        const card = cards[index];
        const data = screenshots[index];
        const img = card.querySelector('img');

        // Récupère la source (même si image masquée par onerror)
        let src = '';
        if (img) {
            src = img.getAttribute('src') || img.src || '';
        }

        modalImage.src = src;
        modalIndex.textContent = index + 1;
        modalTitle.textContent = data.title;
        modalDesc.textContent = data.desc;
        modalCounter.textContent = `${index + 1} / ${cards.length}`;
        modal.classList.add('active');
        document.body.style.overflow = 'hidden';
    }

    // ============================================
    // FERMETURE DU MODAL
    // ============================================
    function closeModal() {
        modal.classList.remove('active');
        document.body.style.overflow = '';
    }

    // ============================================
    // NAVIGATION
    // ============================================
    function prevImage() {
        const newIndex = (currentIndex - 1 + cards.length) % cards.length;
        openModal(newIndex);
    }

    function nextImage() {
        const newIndex = (currentIndex + 1) % cards.length;
        openModal(newIndex);
    }

    // ============================================
    // ÉVÉNEMENTS
    // ============================================
    cards.forEach((card, index) => {
        card.addEventListener('click', () => openModal(index));
    });

    modalClose.addEventListener('click', closeModal);
    modal.addEventListener('click', (e) => {
        if (e.target === modal) closeModal();
    });

    modalPrev.addEventListener('click', (e) => {
        e.stopPropagation();
        prevImage();
    });
    modalNext.addEventListener('click', (e) => {
        e.stopPropagation();
        nextImage();
    });

    document.addEventListener('keydown', (e) => {
        if (!modal.classList.contains('active')) return;
        if (e.key === 'Escape') closeModal();
        if (e.key === 'ArrowLeft') prevImage();
        if (e.key === 'ArrowRight') nextImage();
    });

    // ============================================
    // GESTION DES PLACEHOLDERS
    // ============================================
    document.querySelectorAll('.screenshot-img img').forEach(img => {
        img.addEventListener('error', function() {
            this.style.display = 'none';
            const placeholder = this.nextElementSibling;
            if (placeholder && placeholder.classList.contains('placeholder')) {
                placeholder.style.display = 'flex';
            }
        });
    });

    // ============================================
    // TOUT DÉPLIER / REPLIER
    // ============================================
    document.addEventListener('click', (event) => {
        const btn = event.target.closest('[data-toggle-all]');
        if (!btn) return;
        const open = btn.dataset.toggleAll === 'open';
        document.querySelectorAll('.rubrique').forEach(el => el.open = open);
    });
