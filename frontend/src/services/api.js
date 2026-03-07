import axios from 'axios';

const BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: `${BASE_URL}/api/v1`,
  headers: { 'Content-Type': 'application/json' },
});

export const itemsApi = {
  list: () => api.get('/items/'),
  get: (id) => api.get(`/items/${id}`),
  create: (data) => api.post('/items/', data),
  update: (id, data) => api.put(`/items/${id}`, data),
  remove: (id) => api.delete(`/items/${id}`),
};

export default api;
