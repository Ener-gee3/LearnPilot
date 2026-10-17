(function () {
  function setGenerateLoading(containerId, buttonId) {
    const container = document.getElementById(containerId)
    const btn = document.getElementById(buttonId)
    if (btn) {
      btn.disabled = true
      btn.innerHTML = '<span>Generating...</span>'
    }
    if (container) {
      container.style.display = 'block'
      container.innerHTML = `
        <div class="loading">
          <div class="loading-dots">
            <div class="dot"></div><div class="dot"></div><div class="dot"></div>
          </div>
          <div class="loading-text">Searching sources & generating explanation...</div>
        </div>`
    }
  }

  function resetGenerateButton(buttonId) {
    const btn = document.getElementById(buttonId)
    if (btn) {
      btn.disabled = false
      btn.innerHTML = '<span>Generate</span><span>→</span>'
    }
  }

  window.LearnPilotUI = { setGenerateLoading, resetGenerateButton }
})()
