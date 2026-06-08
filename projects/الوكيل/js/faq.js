/* ====== FAQ ====== */

function renderFAQ() {
  const list = $('faqList')
  list.innerHTML = FAQS.map(f => `
    <div class="faq-item" onclick="toggleFaq(this)">
      <div class="faq-q">${escHtml(f.q)} <i class="fas fa-chevron-down"></i></div>
      <div class="faq-a"><p>${escHtml(f.a)}</p></div>
    </div>`).join('')
}

function toggleFaq(el) {
  el.classList.toggle('open')
}
