// Empty string = relative paths, works with nginx proxy in production
// and Vite dev proxy in development
export const API_URL = '';

// Legacy exports for backwards compatibility
export const API_CONFIG = {
  BASE_URL: API_URL,
  ENDPOINTS: {
    UPLOAD: '/api/upload',
    PROCESS_WORKFLOW: '/api/process-query',
  },
};

export const getApiUrl = (endpoint) => `${API_URL}${endpoint}`;
