import axios from 'axios'

const service = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:5101',
  timeout: 300000,
  headers: { 'Content-Type': 'application/json' },
})

service.interceptors.response.use(
  (response) => {
    const res = response.data
    if (!res.success && res.success !== undefined) {
      console.error('API Error:', res.error || res.message || 'Unknown error')
      return Promise.reject(new Error(res.error || res.message || 'Error'))
    }
    return res
  },
  (error) => {
    if (error?.response?.data && typeof error.response.data === 'object') {
      const data = error.response.data
      const msg = data.error || data.message
      if (msg) {
        const status = error.response.status
        return Promise.reject(new Error(`HTTP ${status}: ${msg}`))
      }
    }
    return Promise.reject(error)
  }
)

export const requestWithRetry = async (requestFn, maxRetries = 3, delay = 1000) => {
  for (let i = 0; i < maxRetries; i++) {
    try {
      return await requestFn()
    } catch (error) {
      if (i === maxRetries - 1) throw error
      await new Promise((resolve) => setTimeout(resolve, delay * Math.pow(2, i)))
    }
  }
}

export default service
