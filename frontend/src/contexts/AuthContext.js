import React, { createContext, useContext, useState, useCallback, useEffect } from 'react';
import api from '../services/api';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(null);
  const [loading, setLoading] = useState(true);

  // Restore session from localStorage on mount
  useEffect(() => {
    const savedToken = localStorage.getItem('yh_token');
    const savedUser = localStorage.getItem('yh_user');
    if (savedToken && savedUser) {
      try {
        setToken(savedToken);
        setUser(JSON.parse(savedUser));
      } catch {
        localStorage.removeItem('yh_token');
        localStorage.removeItem('yh_user');
      }
    }
    setLoading(false);
  }, []);

  const persist = useCallback((tokenVal, userVal) => {
    localStorage.setItem('yh_token', tokenVal);
    localStorage.setItem('yh_user', JSON.stringify(userVal));
    setToken(tokenVal);
    setUser(userVal);
  }, []);

  const login = useCallback(async (username, password) => {
    const res = await api.post('/auth/login', { username, password });
    persist(res.data.access_token, res.data.user);
    return res.data;
  }, [persist]);

  const register = useCallback(async (username, password, fullName, registrationCode) => {
    const res = await api.post('/auth/register', {
      username,
      password,
      full_name: fullName || null,
      registration_code: registrationCode,
    });
    persist(res.data.access_token, res.data.user);
    return res.data;
  }, [persist]);

  const logout = useCallback(() => {
    localStorage.removeItem('yh_token');
    localStorage.removeItem('yh_user');
    setToken(null);
    setUser(null);
  }, []);

  const isAdmin = user?.role === 'admin';

  return (
    <AuthContext.Provider value={{ user, token, loading, login, register, logout, isAdmin }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider');
  return ctx;
}
