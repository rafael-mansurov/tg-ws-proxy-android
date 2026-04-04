(() => {
  function renderLucideIcons() {
    if (!window.lucide || typeof window.lucide.createIcons !== 'function') return;
    window.lucide.createIcons();
  }

  function upgradeCommandPromptIcons() {
    const prompts = document.querySelectorAll('.cmd-prompt');
    prompts.forEach((el) => {
      if (!el) return;
      const txt = (el.textContent || '').trim();
      if (txt !== '$') return;
      el.innerHTML = '<i data-lucide="terminal" style="width:13px;height:13px;stroke-width:2" aria-hidden="true"></i>';
    });
    renderLucideIcons();
  }

  function initAnimatedDetails() {
    const detailsBlocks = Array.from(document.querySelectorAll('details'));
    detailsBlocks.forEach((detailsEl) => {
      if (detailsEl.dataset.detailsAnimated === '1') return;
      const summary = detailsEl.querySelector('summary');
      const body = detailsEl.querySelector('.details-body');
      if (!summary || !body) return;
      if (detailsEl.closest('.faq-section')) return;
      detailsEl.dataset.detailsAnimated = '1';

      let animating = false;
      const duration = 280;
      const computed = window.getComputedStyle(body);
      const basePaddingTop = computed.paddingTop; // e.g. "24px"
      const basePaddingBottom = computed.paddingBottom; // e.g. "28px"
      const basePaddingTopPx = Number.parseFloat(basePaddingTop) || 0;
      const basePaddingBottomPx = Number.parseFloat(basePaddingBottom) || 0;

      summary.addEventListener('click', (e) => {
        e.preventDefault();
        if (animating) return;
        animating = true;

        if (!detailsEl.open) {
          detailsEl.open = true;
          body.style.willChange = 'max-height, opacity, transform, padding-top, padding-bottom';
          body.style.transition = 'none';
          // Сначала "зануляем" padding — так при закрытии/раскрытии не будет резкого скачка.
          body.style.paddingTop = '0px';
          body.style.paddingBottom = '0px';
          const fullHeight = body.scrollHeight + basePaddingTopPx + basePaddingBottomPx;
          body.style.overflow = 'hidden';
          body.style.maxHeight = '0px';
          body.style.opacity = '0';
          body.style.transform = 'translateY(-8px)';

          requestAnimationFrame(() => {
            body.style.transition =
              'max-height ' + duration + 'ms ease, ' +
              'opacity ' + duration + 'ms ease, ' +
              'transform ' + duration + 'ms ease, ' +
              'padding-top ' + duration + 'ms ease, ' +
              'padding-bottom ' + duration + 'ms ease;
            body.style.maxHeight = fullHeight + 'px';
            body.style.opacity = '1';
            body.style.transform = 'translateY(0)';
            body.style.paddingTop = basePaddingTop;
            body.style.paddingBottom = basePaddingBottom;
          });

          setTimeout(() => {
            body.style.transition = '';
            body.style.maxHeight = '';
            body.style.overflow = '';
            body.style.opacity = '';
            body.style.transform = '';
            body.style.paddingTop = '';
            body.style.paddingBottom = '';
            body.style.willChange = '';
            animating = false;
          }, duration + 40);
          return;
        }

        body.style.willChange = 'max-height, opacity, transform, padding-top, padding-bottom';
        body.style.overflow = 'hidden';
        body.style.paddingTop = basePaddingTop;
        body.style.paddingBottom = basePaddingBottom;
        const fullHeight = body.scrollHeight;
        body.style.maxHeight = fullHeight + 'px';
        body.style.opacity = '1';
        body.style.transform = 'translateY(0)';

        requestAnimationFrame(() => {
          body.style.transition =
            'max-height ' + duration + 'ms ease, ' +
            'opacity ' + duration + 'ms ease, ' +
            'transform ' + duration + 'ms ease, ' +
            'padding-top ' + duration + 'ms ease, ' +
            'padding-bottom ' + duration + 'ms ease;
          body.style.maxHeight = '0px';
          body.style.opacity = '0';
          body.style.transform = 'translateY(-8px)';
          body.style.paddingTop = '0px';
          body.style.paddingBottom = '0px';
        });

        setTimeout(() => {
          body.style.transition = '';
          body.style.maxHeight = '';
          body.style.overflow = '';
          body.style.opacity = '';
          body.style.transform = '';
          body.style.paddingTop = '';
          body.style.paddingBottom = '';
          body.style.willChange = '';
          requestAnimationFrame(() => {
            detailsEl.open = false;
          });
          animating = false;
        }, duration + 40);
      });
    });
  }

  function initFaqAccordion() {
    const faqSections = Array.from(document.querySelectorAll('section.faq-section'));
    const DURATION = 360;
    const EASING = 'cubic-bezier(0.22, 1, 0.36, 1)';
    const FAQ_PAD_TOP = '10px';
    const FAQ_PAD_BOTTOM = '16px';
    const FAQ_PAD_TOP_PX = 10;
    const FAQ_PAD_BOTTOM_PX = 16;

    function clearBodyStyles(body) {
      body.style.transition = '';
      body.style.maxHeight = '';
      body.style.opacity = '';
      body.style.transform = '';
      body.style.paddingTop = '';
      body.style.paddingBottom = '';
      body.style.overflow = '';
      body.style.willChange = '';
    }

    function animateOpen(item, body) {
      if (item.dataset.faqAnimating === '1') return;
      item.dataset.faqAnimating = '1';
      item.open = true;
      body.style.overflow = 'hidden';
      body.style.willChange = 'max-height, opacity, transform';
      body.style.transition = 'none';
      body.style.maxHeight = '0px';
      body.style.opacity = '0';
      body.style.transform = 'translateY(-6px)';
      body.style.paddingTop = '0px';
      body.style.paddingBottom = '0px';

      requestAnimationFrame(() => {
        const fullHeight = body.scrollHeight + FAQ_PAD_TOP_PX + FAQ_PAD_BOTTOM_PX;
        requestAnimationFrame(() => {
          body.style.transition = 'max-height ' + DURATION + 'ms ' + EASING + ', opacity ' + DURATION + 'ms ' + EASING + ', transform ' + DURATION + 'ms ' + EASING + ', padding-top ' + DURATION + 'ms ' + EASING + ', padding-bottom ' + DURATION + 'ms ' + EASING;
          body.style.maxHeight = fullHeight + 'px';
          body.style.opacity = '1';
          body.style.transform = 'translateY(0)';
          body.style.paddingTop = FAQ_PAD_TOP;
          body.style.paddingBottom = FAQ_PAD_BOTTOM;
        });
      });

      const onEnd = () => {
        clearBodyStyles(body);
        item.dataset.faqAnimating = '0';
      };
      body.addEventListener('transitionend', onEnd, { once: true });
    }

    function animateClose(item, body) {
      if (item.dataset.faqAnimating === '1') return;
      item.dataset.faqAnimating = '1';
      const fullHeight = body.scrollHeight;
      body.style.overflow = 'hidden';
      body.style.willChange = 'max-height, opacity, transform';
      body.style.transition = 'none';
      body.style.maxHeight = fullHeight + 'px';
      body.style.opacity = '1';
      body.style.transform = 'translateY(0)';
      body.style.paddingTop = FAQ_PAD_TOP;
      body.style.paddingBottom = FAQ_PAD_BOTTOM;

      requestAnimationFrame(() => {
        body.style.transition = 'max-height ' + DURATION + 'ms ' + EASING + ', opacity ' + DURATION + 'ms ' + EASING + ', transform ' + DURATION + 'ms ' + EASING + ', padding-top ' + DURATION + 'ms ' + EASING + ', padding-bottom ' + DURATION + 'ms ' + EASING;
        body.style.maxHeight = '0px';
        body.style.opacity = '0';
        body.style.transform = 'translateY(-6px)';
        body.style.paddingTop = '0px';
        body.style.paddingBottom = '0px';
      });

      const onEnd = () => {
        item.open = false;
        clearBodyStyles(body);
        item.dataset.faqAnimating = '0';
      };
      body.addEventListener('transitionend', onEnd, { once: true });
    }

    faqSections.forEach((section) => {
      const items = Array.from(section.querySelectorAll('details'));
      items.forEach((item) => {
        const summary = item.querySelector('summary');
        const body = item.querySelector('.details-body');
        if (!summary || !body) return;
        item.dataset.faqAnimating = '0';

        summary.addEventListener('click', (e) => {
          e.preventDefault();
          if (item.dataset.faqAnimating === '1') return;

          if (item.open) {
            animateClose(item, body);
            return;
          }

          items.forEach((other) => {
            if (other === item || !other.open) return;
            const otherBody = other.querySelector('.details-body');
            if (!otherBody) return;
            animateClose(other, otherBody);
          });
          animateOpen(item, body);
        });
      });
    });
  }

  function ensureFaqLastQuestion() {
    // В разных страницах есть одинаковый "последний вопрос" в FAQ.
    // Подставляем его автоматически, чтобы не дублировать HTML.
    const telegramHref = APP_CONFIG.TELEGRAM_URL;
    const telegramLinkSelector = `a[href="${telegramHref}"]`;

    const detailsHtml = `
      <details data-faq-last="1">
        <summary>Не нашёл ответ на&nbsp;свой вопрос?</summary>
        <div class="details-body">
          <p>Пиши мне в&nbsp;Telegram — <a href="${telegramHref}" target="_blank" rel="noopener noreferrer">@mansurov_rafael</a>. Отвечаю быстро.</p>
        </div>
      </details>
    `.trim();

    const faqSections = Array.from(document.querySelectorAll('section.faq-section'));
    faqSections.forEach((section) => {
      if (!section) return;
      if (section.querySelector(telegramLinkSelector)) return; // уже вставлен
      const wrapper = document.createElement('div');
      wrapper.innerHTML = detailsHtml;
      const newDetails = wrapper.firstElementChild;
      if (!newDetails || newDetails.tagName !== 'DETAILS') return;
      section.appendChild(newDetails);
    });
  }

  window.copyCmd = function copyCmd(btn, text) {
    const prev = btn.textContent;
    navigator.clipboard.writeText(text).then(() => {
      btn.textContent = 'Скопировано';
      btn.classList.add('copied');
      setTimeout(() => {
        btn.textContent = prev;
        btn.classList.remove('copied');
      }, 1800);
    });
  };

  function initSharedInstructionsUi() {
    upgradeCommandPromptIcons();
    initAnimatedDetails();
    ensureFaqLastQuestion();
    initFaqAccordion();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initSharedInstructionsUi, { once: true });
  } else {
    initSharedInstructionsUi();
  }
})();
