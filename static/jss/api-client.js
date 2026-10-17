(function () {
  function buildApiBase(backendUrl) {
    const isLocal = window.location.hostname === 'localhost'
      || window.location.hostname === '127.0.0.1'
      || window.location.protocol === 'file:'
    return backendUrl || (isLocal ? 'http://127.0.0.1:8000' : '')
  }

  async function postJson(url, payload) {
    const res = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })
    if (!res.ok) throw new Error(`Server error: ${res.status}`)
    return res.json()
  }

  window.LearnPilotApi = { buildApiBase, postJson }
})()
