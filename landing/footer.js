(() => {
  const footer = document.getElementById('sharedFooter');
  if (!footer) return;

  footer.innerHTML = `
    <div class="footer-actions">
      <a class="btn btn-ghost" href="${APP_CONFIG.DONATE_URL}" target="_blank" rel="noopener noreferrer">
        <i data-lucide="coffee" style="width:13px;height:13px;stroke-width:2" aria-hidden="true"></i>
        Поддержать
      </a>
      <a class="btn btn-primary" href="${APP_CONFIG.TELEGRAM_URL}" target="_blank" rel="noopener noreferrer">
        <i data-lucide="send" style="width:15px;height:13px;stroke-width:2" aria-hidden="true"></i>
        Связаться со\u00a0мной
      </a>
    </div>
  `;

  if (window.lucide && typeof window.lucide.createIcons === 'function') {
    window.lucide.createIcons();
  }
})();
