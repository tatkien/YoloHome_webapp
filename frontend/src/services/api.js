import axios from 'axios';

const BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: `${BASE_URL}/api/v1`,
  headers: { 'Content-Type': 'application/json' },
});

// Attach JWT token to every request
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('yh_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Redirect to login on 401 (only for user-auth failures, not device-auth)
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      const detail = error.response?.data?.detail || '';
      // Device-auth 401s should be handled by the page, not trigger a redirect
      const isDeviceAuthError =
        detail.includes('Device-Key') || detail.includes('device credentials');

      if (!isDeviceAuthError) {
        const path = window.location.pathname;
        if (path !== '/login' && path !== '/register') {
          localStorage.removeItem('yh_token');
          localStorage.removeItem('yh_user');
          window.location.href = '/login';
        }
      }
    }
    return Promise.reject(error);
  }
);

export default api;
