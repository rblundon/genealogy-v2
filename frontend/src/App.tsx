import { useState, useEffect } from 'react'

interface HealthStatus {
  status: string
}

function App() {
  const [apiStatus, setApiStatus] = useState<string>('checking...')

  useEffect(() => {
    const checkApi = async () => {
      try {
        const response = await fetch(
          import.meta.env.VITE_API_URL || 'http://localhost:8000'
        )
        const data: HealthStatus = await response.json()
        setApiStatus(data.status || 'connected')
      } catch {
        setApiStatus('disconnected')
      }
    }
    checkApi()
  }, [])

  return (
    <div style={{ padding: '2rem', fontFamily: 'system-ui, sans-serif' }}>
      <h1>Genealogy Research Tool</h1>
      <p>API Status: {apiStatus}</p>
    </div>
  )
}

export default App
