/* ====== AI CHATBOT ====== */
const AI_API = '/api/chat'
const AI_MODELS_URL = '/api/models'

let aiModels = { default: 'gpt-4o-mini' }
let chatModel = 'gpt-4o-mini'
let chatHistory = []
let isProcessing = false

async function loadModels() {
  try {
    const resp = await fetch(AI_MODELS_URL)
    const data = await resp.json()
    aiModels = data.models || {}
    chatModel = data.default || 'gpt-4o-mini'
    const select = $('aiModelSelect')
    if (select) {
      select.innerHTML = Object.entries(aiModels).map(([id, m]) =>
        `<option value="${id}" ${id === chatModel ? 'selected' : ''}>${m.name}</option>`
      ).join('')
    }
  } catch (e) { console.log('Model load skipped (offline)') }
}

function toggleChat() {
  const panel = $('aiChatPanel')
  const btn = $('aiChatBtn')
  panel.classList.toggle('open')
  btn.classList.toggle('active')
  if (panel.classList.contains('open') && chatHistory.length === 0) {
    addBotMessage("👋 Hi! I'm your AI financial assistant. Ask me anything about budgeting, saving, investing, or getting out of debt!")
  }
}

async function sendChatMessage() {
  if (isProcessing) return
  const input = $('aiChatInput')
  const text = input.value.trim()
  if (!text) return

  input.value = ''
  addUserMessage(text)
  chatHistory.push({ role: 'user', content: text })

  isProcessing = true
  const status = $('aiChatStatus')
  status.textContent = 'Thinking...'
  status.style.display = 'block'

  try {
    const resp = await fetch(AI_API, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        messages: chatHistory.slice(-10),
        model: chatModel,
        max_tokens: 800,
        temperature: 0.7,
      })
    })

    if (!resp.ok) {
      const errData = await resp.json()
      throw new Error(errData.error?.message || `HTTP ${resp.status}`)
    }

    const result = await resp.json()
    const content = result.choices?.[0]?.message?.content || 'No response'
    addBotMessage(content)
    chatHistory.push({ role: 'assistant', content })
  } catch (e) {
    addBotMessage("⚠️ Sorry, I couldn't reach the AI. Make sure the backend is running (`python backend.py`). Error: " + e.message.slice(0, 80))
  } finally {
    isProcessing = false
    status.style.display = 'none'
  }
}

function addUserMessage(text) {
  const box = $('aiChatMessages')
  const div = document.createElement('div')
  div.className = 'chat-msg user'
  div.innerHTML = `<div class="msg-bubble">${escHtml(text)}</div>`
  box.appendChild(div)
  box.scrollTop = box.scrollHeight
}

function addBotMessage(text) {
  const box = $('aiChatMessages')
  const div = document.createElement('div')
  div.className = 'chat-msg bot'
  const formatted = text
    .replace(/\n/g, '<br>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
  div.innerHTML = `<div class="msg-avatar"><i class="fas fa-robot"></i></div><div class="msg-bubble">${formatted}</div>`
  box.appendChild(div)
  box.scrollTop = box.scrollHeight
}

function clearChat() {
  chatHistory = []
  $('aiChatMessages').innerHTML = ''
  addBotMessage("👋 Hi! I'm your AI financial assistant. Ask me anything about budgeting, saving, investing, or getting out of debt!")
}

// Enter to send
document.addEventListener('DOMContentLoaded', () => {
  const input = $('aiChatInput')
  if (input) {
    input.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendChatMessage() }
    })
  }
  loadModels()
})
