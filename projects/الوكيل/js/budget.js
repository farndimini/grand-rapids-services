/* ====== BUDGET MANAGER ====== */

function addIncome() {
  const src = $('incomeSource').value.trim()
  const amt = parseFloat($('incomeAmount').value)
  if (!src || !amt || amt <= 0) { alert('Please enter a valid source and amount.'); return }
  state.incomes.push({ id: Date.now(), source: src, amount: amt })
  saveState(); renderBudget()
  $('incomeSource').value = ''; $('incomeAmount').value = ''
}

function addExpense() {
  const desc = $('expenseDesc').value.trim()
  const cat = $('expenseCat').value
  const amt = parseFloat($('expenseAmount').value)
  if (!desc || !amt || amt <= 0) { alert('Please enter a valid description and amount.'); return }
  state.expenses.push({ id: Date.now(), description: desc, category: cat, amount: amt })
  saveState(); renderBudget()
  $('expenseDesc').value = ''; $('expenseAmount').value = ''
}

function removeIncome(id) {
  state.incomes = state.incomes.filter(i => i.id !== id)
  saveState(); renderBudget()
}

function removeExpense(id) {
  state.expenses = state.expenses.filter(e => e.id !== id)
  saveState(); renderBudget()
}

function renderBudget() {
  const totalIncome = state.incomes.reduce((s, i) => s + i.amount, 0)
  const totalExpenses = state.expenses.reduce((s, e) => s + e.amount, 0)
  const balance = totalIncome - totalExpenses
  const summary = $('budgetSummary')

  if (state.incomes.length === 0 && state.expenses.length === 0) {
    summary.innerHTML = '<p style="color:var(--text-muted)">Add your income and expenses to see your financial summary.</p>'
  } else {
    let pct = totalIncome > 0 ? ((totalExpenses / totalIncome) * 100).toFixed(1) : 0
    summary.innerHTML = `
      <div class="summary-row"><span>Total Income</span><span class="positive">${formatCurrency(totalIncome)}</span></div>
      <div class="summary-row"><span>Total Expenses</span><span class="negative">${formatCurrency(totalExpenses)}</span></div>
      <div class="summary-row total"><span>${balance >= 0 ? 'Remaining' : 'Shortfall'}</span><span class="${balance >= 0 ? 'positive' : 'negative'}">${formatCurrency(Math.abs(balance))}</span></div>
      ${totalIncome > 0 ? `<div style="font-size:.82rem;color:var(--text-muted);text-align:center;margin-top:8px">You spend ${pct}% of your income</div>` : ''}`
  }

  const il = $('incomeList')
  if (state.incomes.length === 0) {
    il.innerHTML = '<li style="color:var(--text-muted);font-size:.88rem">No income added yet.</li>'
  } else {
    il.innerHTML = state.incomes.map(i => `
      <li class="income-item">
        <div class="item-details"><strong>${escHtml(i.source)}</strong><span class="cat">Income</span></div>
        <div style="display:flex;align-items:center;gap:12px"><span class="amount">${formatCurrency(i.amount)}</span>
        <div class="item-actions"><button onclick="removeIncome(${i.id})" title="Remove"><i class="fas fa-trash"></i></button></div></div>
      </li>`).join('')
  }

  const el = $('expenseList')
  if (state.expenses.length === 0) {
    el.innerHTML = '<li style="color:var(--text-muted);font-size:.88rem">No expenses added yet.</li>'
  } else {
    el.innerHTML = state.expenses.map(e => `
      <li class="expense-item">
        <div class="item-details"><strong>${escHtml(e.description)}</strong><span class="cat">${escHtml(e.category)}</span></div>
        <div style="display:flex;align-items:center;gap:12px"><span class="amount">${formatCurrency(e.amount)}</span>
        <div class="item-actions"><button onclick="removeExpense(${e.id})" title="Remove"><i class="fas fa-trash"></i></button></div></div>
      </li>`).join('')
  }

  updateChart()
  updateTips(totalIncome, totalExpenses)
}

function updateChart() {
  const canvas = $('budgetChart')
  if (!canvas) return
  const ctx = canvas.getContext('2d')

  const cats = {}
  state.expenses.forEach(e => { cats[e.category] = (cats[e.category] || 0) + e.amount })
  const labels = Object.keys(cats)
  const data = Object.values(cats)
  const colors = ['#3b5af6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899', '#14b8a6', '#f97316', '#6366f1', '#84cc16']

  if (state.budgetChart) { state.budgetChart.destroy(); state.budgetChart = null }
  if (labels.length === 0) return

  state.budgetChart = new Chart(ctx, {
    type: 'doughnut',
    data: { labels, datasets: [{ data, backgroundColor: colors.slice(0, labels.length), borderWidth: 0 }] },
    options: {
      responsive: true, maintainAspectRatio: true, cutout: '60%',
      plugins: { legend: { position: 'bottom', labels: { color: '#94a3b8', padding: 12, font: { size: 11 } } } }
    }
  })
}

function updateTips(totalIncome, totalExpenses) {
  const tipBox = $('tipBox')
  if (state.incomes.length === 0 || state.expenses.length === 0) { tipBox.style.display = 'none'; return }
  tipBox.style.display = 'block'
  const pct = totalIncome > 0 ? (totalExpenses / totalIncome) * 100 : 0
  let tips = []
  if (pct > 80) tips.push("You're spending over 80% of your income. Try reducing non-essential expenses or finding ways to increase your income.")
  else if (pct > 60) tips.push("You're spending " + pct.toFixed(0) + "% of your income. Consider saving at least 20% to build a stronger financial cushion.")
  else tips.push("You're spending " + pct.toFixed(0) + "% of your income — great control! Consider increasing your investment contributions.")

  const topCat = state.expenses.reduce((a, b) => a.amount > b.amount ? a : b, state.expenses[0])
  if (topCat && topCat.category !== 'Housing') {
    tips.push("Your biggest expense is " + topCat.category + " ($" + topCat.amount.toFixed(0) + "). Can you reduce this by even 10%?")
  }

  const bal = totalIncome - totalExpenses
  if (bal > 0) {
    tips.push("You have " + formatCurrency(bal) + " remaining. Put it toward savings or debt — don't let it disappear on small purchases.")
  } else if (bal < 0) {
    tips.push("Your expenses exceed your income by " + formatCurrency(Math.abs(bal)) + ". Review your variable expenses and find areas to cut back.")
  }

  tipBox.innerHTML = `<h4><i class="fas fa-lightbulb"></i> Smart Tips for You</h4><p>${tips[0]}</p>`
  if (tips.length > 1) tipBox.innerHTML += `<p style="margin-top:10px;padding-top:10px;border-top:1px solid var(--border)">${tips[1]}</p>`
}
