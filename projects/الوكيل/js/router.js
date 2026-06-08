/* ====== SPA ROUTER ====== */

function navigateTo(hash) {
  const target = hash.replace('#', '') || 'home'
  document.querySelectorAll('.section').forEach(s => s.classList.remove('active'))
  document.querySelectorAll('[data-nav]').forEach(n => n.classList.remove('active'))
  const section = document.getElementById(target)
  if (section) section.classList.add('active')
  const navLink = document.querySelector(`[data-nav][href="#${target}"]`)
  if (navLink) navLink.classList.add('active')
  if (target === 'articles') renderArticles()
  else if (target === 'budget') renderBudget()
  else if (target === 'faq') renderFAQ()
  const detail = $('articleDetailView')
  if (detail) detail.classList.remove('active')
  const list = $('articleListView')
  if (list) list.classList.remove('hidden')
  window.scrollTo({ top: 0, behavior: 'smooth' })
  const toggle = $('navToggle'), links = $('navLinks')
  if (toggle && links) { toggle.classList.remove('open'); links.classList.remove('open') }
}

function handleRoute() {
  const hash = location.hash || '#home'
  const match = hash.match(/^#article-(.+)$/)
  if (match) {
    navigateTo('articles')
    showArticle(match[1])
  } else { navigateTo(hash) }
}

/* ====== EVENT SETUP ====== */
window.addEventListener('hashchange', handleRoute)

document.querySelectorAll('[data-nav]').forEach(el => {
  el.addEventListener('click', function (e) {
    e.preventDefault()
    const href = this.getAttribute('href')
    history.pushState(null, '', href)
    handleRoute()
  })
})

$('navToggle')?.addEventListener('click', () => {
  $('navLinks').classList.toggle('open')
})

/* Article filter buttons */
document.querySelectorAll('.filter-btn').forEach(btn => {
  btn.addEventListener('click', function () {
    document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'))
    this.classList.add('active')
    renderArticles(this.dataset.filter)
  })
})
