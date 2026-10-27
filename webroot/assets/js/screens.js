(function () {
    'use strict';

    function init() {
        var cards = document.querySelectorAll('.screenshot-card');
        if (cards.length === 0) {
            setTimeout(init, 100);
            return;
        }

        var modal = document.getElementById('modalOverlay');
        var modalImage = document.getElementById('modalImage');
        var modalIndex = document.getElementById('modalIndex');
        var modalTitle = document.getElementById('modalTitle');
        var modalDesc = document.getElementById('modalDesc');
        var modalCounter = document.getElementById('modalCounter');
        var modalClose = document.getElementById('modalClose');
        var modalPrev = document.getElementById('modalPrev');
        var modalNext = document.getElementById('modalNext');

        if (!modal || !modalImage) {
            console.warn('[screens] modal missing');
            return;
        }

        var currentIndex = 0;
        var cardList = Array.prototype.slice.call(cards);

        function openModal(i) {
            if (i < 0 || i >= cardList.length) return;
            currentIndex = i;
            var card = cardList[i];
            var img = card.querySelector('img');
            var h4 = card.querySelector('.screenshot-caption h4');
            var p = card.querySelector('.screenshot-caption p');

            modalImage.src = img ? (img.getAttribute('src') || '') : '';
            if (modalIndex) modalIndex.textContent = i + 1;
            if (modalTitle) modalTitle.textContent = h4 ? h4.textContent : '';
            if (modalDesc) modalDesc.textContent = p ? p.textContent : '';
            if (modalCounter) modalCounter.textContent = (i + 1) + ' / ' + cardList.length;

            modal.classList.add('active');
            document.body.classList.add('modal-open');
        }

        function closeModal() {
            modal.classList.remove('active');
            document.body.classList.remove('modal-open');
        }

        function prevImage() { openModal((currentIndex - 1 + cardList.length) % cardList.length); }
        function nextImage() { openModal((currentIndex + 1) % cardList.length); }

        for (var i = 0; i < cardList.length; i++) {
            (function (index) {
                cardList[index].addEventListener('click', function () { openModal(index); });
            })(i);
        }

        if (modalClose) modalClose.addEventListener('click', closeModal);
        modal.addEventListener('click', function (e) { if (e.target === modal) closeModal(); });
        if (modalPrev) modalPrev.addEventListener('click', function (e) { e.stopPropagation(); prevImage(); });
        if (modalNext) modalNext.addEventListener('click', function (e) { e.stopPropagation(); nextImage(); });

        document.addEventListener('keydown', function (e) {
            if (!modal.classList.contains('active')) return;
            if (e.key === 'Escape') closeModal();
            if (e.key === 'ArrowLeft') prevImage();
            if (e.key === 'ArrowRight') nextImage();
        });

        function toggleAll(open) {
            var rubriques = document.querySelectorAll('.rubrique');
            for (var j = 0; j < rubriques.length; j++) rubriques[j].open = open;
        }

        var btnOpen = document.getElementById('toggleOpen');
        var btnClose = document.getElementById('toggleClose');
        if (btnOpen) btnOpen.addEventListener('click', function () { toggleAll(true); });
        if (btnClose) btnClose.addEventListener('click', function () { toggleAll(false); });

        var navBack = document.getElementById('navBack');
        var navHome = document.getElementById('navHome');
        var navOmega = document.getElementById('navOmega');
        var navReadme = document.getElementById('navReadme');
        var navGuide = document.getElementById('navGuide');
        var navTop = document.getElementById('navTop');

        if (navBack) navBack.addEventListener('click', function () { window.history.back(); });
        if (navHome) navHome.addEventListener('click', function () { window.location.href = '/'; });
        if (navOmega) navOmega.addEventListener('click', function () { window.location.href = '/omega-serv/'; });
        if (navReadme) navReadme.addEventListener('click', function () { window.location.href = '/omega-serv/readme.html'; });
        if (navGuide) navGuide.addEventListener('click', function () { window.location.href = '/omega-serv/guide.html'; });
        if (navTop) navTop.addEventListener('click', function () { window.scrollTo({ top: 0, behavior: 'smooth' }); });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
