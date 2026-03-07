import axios from 'axios';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

export const deviceService = {
  getDevices: () => apiClient.get('/api/v1/devices').then((res) => res.data),
  getDevice: (id) => apiClient.get(`/api/v1/devices/${id}`).then((res) => res.data),
  toggleDevice: (id) => apiClient.patch(`/api/v1/devices/${id}/toggle`).then((res) => res.data),
  getStats: () => apiClient.get('/api/v1/devices/stats').then((res) => res.data),
};

export default apiClient;
