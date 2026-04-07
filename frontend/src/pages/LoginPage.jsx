import React, { useState } from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { HiEye, HiEyeOff } from 'react-icons/hi';

export default function LoginPage() {
  const { login }    = useAuth();
  const navigate     = useNavigate();
  const location     = useLocation();
  const from         = location.state?.from?.pathname || '/';

  const [username,     setUsername]     = useState('');
  const [password,     setPassword]     = useState('');
  const [error,        setError]        = useState('');
  const [loading,      setLoading]      = useState(false);
  const [showPassword, setShowPassword] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await login(username, password);
      navigate(from, { replace: true });
    } catch (err) {
      setError(err.response?.data?.detail || 'Login failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="d-flex justify-content-center align-items-center min-vh-100 bg-light">
      <div className="card border-0 shadow p-4 p-md-5" style={{ width: '100%', maxWidth: '420px' }}>

        {/* Header */}
        <div className="text-center mb-4">
          <div style={{ fontSize: '2.5rem' }}>🏠</div>
          <h4 className="fw-bold mt-2 mb-1">Welcome Back</h4>
          <p className="text-muted small mb-0">Sign in to your YoloHome account</p>
        </div>

        {/* Error */}
        {error && (
          <div className="alert alert-danger py-2 small" role="alert">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit}>

          {/* Username */}
          <div className="mb-3">
            <label htmlFor="login-username" className="form-label small fw-semibold">
              Username
            </label>
            <input
              id="login-username"
              type="text"
              className="form-control"
              placeholder="Enter your username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
              autoFocus
            />
          </div>

          {/* Password */}
          <div className="mb-4">
            <label htmlFor="login-password" className="form-label small fw-semibold">
              Password
            </label>
            <div className="input-group">
              <input
                id="login-password"
                type={showPassword ? 'text' : 'password'}
                className="form-control"
                placeholder="Enter your password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
              <button
                type="button"
                className="btn btn-outline-secondary"
                onClick={() => setShowPassword(!showPassword)}
                tabIndex={-1}
              >
                {showPassword ? <HiEyeOff size={16} /> : <HiEye size={16} />}
              </button>
            </div>
          </div>

          {/* Submit */}
          <button
            type="submit"
            className="btn btn-primary w-100 mb-3"
            disabled={loading}
          >
            {loading ? (
              <>
                <span className="spinner-border spinner-border-sm me-2" role="status" />
                Signing in...
              </>
            ) : 'Sign In'}
          </button>

          {/* Register link */}
          <p className="text-center small text-muted mb-0">
            Don't have an account?{' '}
            <Link to="/register" className="text-primary fw-semibold text-decoration-none">
              Register
            </Link>
          </p>

        </form>
      </div>
    </div>
  );
}