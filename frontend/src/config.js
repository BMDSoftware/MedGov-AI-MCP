// API Configuration
export const API_CONFIG = {
  BASE_URL: import.meta.env.VITE_API_URL || 'http://localhost:5001',
  ENDPOINTS: {
    UPLOAD: '/api/upload',
    PROCESS_QUERY: '/api/process-query',
    HEALTH: '/api/health'
  }
}

export const getApiUrl = (endpoint) => {
  return `${API_CONFIG.BASE_URL}${endpoint}`
}
