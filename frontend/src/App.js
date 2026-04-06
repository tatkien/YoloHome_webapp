import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { AuthProvider } from './contexts/AuthContext';
import AppNavbar from './components/AppNavbar';
import PrivateRoute from './components/PrivateRoute';
import HomePage from './pages/HomePage';
import LoginPage from './pages/LoginPage';
import RegisterPage from './pages/RegisterPage';
import DevicesPage from './pages/DevicesPage';
import AdminUsersPage from './pages/AdminUsersPage';
import FaceEnrollmentsPage from './pages/FaceEnrollmentsPage';
import FaceRecognizePage from './pages/FaceRecognizePage';
import FaceLogsPage from './pages/FaceLogsPage';

function App() {
  return (
    <Router>
      <AuthProvider>
        <AppNavbar />
        <Routes>
          {/* Public */}
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />

          {/* Protected */}
          <Route path="/" element={<PrivateRoute><HomePage /></PrivateRoute>} />
          <Route path="/devices" element={<PrivateRoute><DevicesPage /></PrivateRoute>} />

          {/* Face Recognition */}
          <Route path="/face/enrollments" element={<PrivateRoute adminOnly><FaceEnrollmentsPage /></PrivateRoute>} />
          <Route path="/face/recognize" element={<FaceRecognizePage />} />
          <Route path="/face/logs" element={<PrivateRoute><FaceLogsPage /></PrivateRoute>} />

          {/* Admin */}
          <Route path="/admin" element={<PrivateRoute adminOnly><AdminUsersPage /></PrivateRoute>} />
        </Routes>
      </AuthProvider>
    </Router>
  );
}

export default App;
