import { useState, useEffect } from 'react'

const API_BASE_URL = 'http://localhost:5000/api'

function App() {
  const [status, setStatus] = useState('')
  const [error, setError] = useState('')
  const [isScanning, setIsScanning] = useState(false)
  const [scanData, setScanData] = useState([])

  // API 調用函數
  const callAPI = async (endpoint, method = 'POST') => {
    try {
      const response = await fetch(`${API_BASE_URL}${endpoint}`, { method })
      const data = await response.json()
      
      if (data.success) {
        setStatus(data.message)
        setError('')
      } else {
        setError(data.message)
        setStatus('')
      }
    } catch (err) {
      setError(err.message)
      setStatus('')
    }
  }

  // 獲取盤點數據
  useEffect(() => {
    let interval
    if (isScanning) {
      interval = setInterval(async () => {
        try {
          const response = await fetch(`${API_BASE_URL}/inventory/data`)
          const data = await response.json()
          if (data.success && data.data.length > 0) {
            setScanData(prev => [...prev, ...data.data])
          }
        } catch (err) {
          console.error('獲取盤點數據失敗:', err)
        }
      }, 1000)
    }
    return () => clearInterval(interval)
  }, [isScanning])

  // 處理盤點開關
  const handleInventory = async () => {
    const endpoint = isScanning ? '/inventory/stop' : '/inventory/start'
    await callAPI(endpoint)
    setIsScanning(!isScanning)
    if (!isScanning) {
      setScanData([])
    }
  }

  return (
    <div>
      <h1>RFID 控制面板</h1>
      
      <div>
        <h2>盤點控制</h2>
        <button onClick={handleInventory}>
          {isScanning ? '停止盤點' : '開始盤點'}
        </button>
        
        {isScanning && (
          <div>
            <h3>掃描結果:</h3>
            {scanData.map((tag, index) => (
              <div key={index}>{tag}</div>
            ))}
          </div>
        )}
      </div>

      <div>
        <h2>Select 參數控制</h2>
        <div>
          <button onClick={() => callAPI('/select/get')}>
            獲取 Select 參數
          </button>
          <button onClick={() => callAPI('/select/set')}>
            設置 Select 參數
          </button>
          <button onClick={() => callAPI('/select/mode')}>
            設置 Select 模式
          </button>
        </div>
      </div>

      <div>
        <h2>記憶體操作</h2>
        <div>
          <button onClick={() => callAPI('/memory/write')}>
            寫入數據
          </button>
          <button onClick={() => callAPI('/memory/lock')}>
            鎖定記憶體
          </button>
        </div>
      </div>

      {status && (
        <div>
          <p>狀態: {status}</p>
        </div>
      )}
      
      {error && (
        <div>
          <p>錯誤: {error}</p>
        </div>
      )}
    </div>
  )
}

export default App