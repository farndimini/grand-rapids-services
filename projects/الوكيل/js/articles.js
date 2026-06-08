/* ====== ARTICLES ====== */

function renderArticles(filter) {
  filter = filter || 'all'
  const grid = $('articlesGrid')
  const filtered = filter === 'all' ? ARTICLES : ARTICLES.filter(a => a.category === filter)
  if (filtered.length === 0) {
    grid.innerHTML = '<p style="color:var(--text-muted);text-align:center;padding:40px">No articles in this category yet.</p>'
    return
  }
  grid.innerHTML = filtered.map(a => `
    <div class="article-card" onclick="openArticle('${a.slug}')">
      <div class="article-card-body">
        <span class="article-cat ${a.category}">${a.category}</span>
        <h3>${escHtml(a.title)}</h3>
        <p>${escHtml(a.excerpt)}</p>
        <div class="article-meta">
          <span><i class="far fa-clock"></i> 5 min read</span>
          <span><i class="far fa-folder"></i> ${escHtml(a.category)}</span>
        </div>
      </div>
    </div>`).join('')
}

function openArticle(slug) {
  const a = ARTICLES.find(x => x.slug === slug)
  if (!a) return
  history.pushState(null, '', '#article-' + slug)
  showArticle(slug)
}

function showArticle(slug) {
  const a = ARTICLES.find(x => x.slug === slug)
  if (!a) return
  const list = $('articleListView'), detail = $('articleDetailView'), content = $('articleContent')
  list.classList.add('hidden'); detail.classList.add('active')
  content.innerHTML = `
    <button class="back-btn" onclick="closeArticle()"><i class="fas fa-arrow-left"></i> Back to articles</button>
    <h1>${a.title}</h1>
    <div style="display:flex;gap:16px;font-size:.82rem;color:var(--text-muted);margin-bottom:20px">
      <span><i class="far fa-clock"></i> 5 min read</span>
      <span><i class="far fa-folder"></i> ${a.category}</span>
    </div>
    ${a.content}`
  window.scrollTo({ top: 0, behavior: 'smooth' })
  document.querySelectorAll('#articleContent .back-btn').forEach(b => { b.addEventListener('click', closeArticle) })
  document.querySelectorAll('#articleContent [data-nav]').forEach(el => {
    el.addEventListener('click', function (e) {
      e.preventDefault()
      const href = this.getAttribute('href')
      history.pushState(null, '', href)
      handleRoute()
    })
  })
  applyArticleCTA()
}

function applyArticleCTA() {
  document.querySelectorAll('#articleContent .cta-box .btn').forEach(btn => {
    if (!btn.hasAttribute('data-nav-listener')) {
      btn.setAttribute('data-nav-listener', '1')
      btn.addEventListener('click', function (e) {
        e.preventDefault()
        const href = this.getAttribute('href')
        history.pushState(null, '', href)
        handleRoute()
      })
    }
  })
}

function closeArticle() {
  const list = $('articleListView'), detail = $('articleDetailView')
  list.classList.remove('hidden'); detail.classList.remove('active')
  history.pushState(null, '', '#articles')
  window.scrollTo({ top: 0, behavior: 'smooth' })
}
