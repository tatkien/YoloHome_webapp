import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { HiEye, HiEyeOff } from 'react-icons/hi';

export default function RegisterPage() {
  const { register } = useAuth();
  const navigate     = useNavigate();

  const [username,          setUsername]          = useState('');
  const [password,          setPassword]          = useState('');
  const [fullName,          setFullName]          = useState('');
  const [registrationCode,  setRegistrationCode]  = useState('');
  const [error,             setError]             = useState('');
  const [loading,           setLoading]           = useState(false);
  const [showPassword,      setShowPassword]      = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await register(username, password, fullName, registrationCode);
      navigate('/', { replace: true });
    } catch (err) {
      setError(err.response?.data?.detail || 'Registration failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="d-flex justify-content-center align-items-center min-vh-100 bg-light">
      <div className="card border-0 shadow p-4 p-md-5" style={{ width: '100%', maxWidth: '420px' }}>

        {/* Header */}
        <div className="text-center mb-4">
          <h4 className="fw-bold mt-2 mb-1">Create Account</h4>
          <p className="text-muted small mb-0">
            Join YoloHome to manage your smart devices
          </p>
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
            <label htmlFor="register-username" className="form-label small fw-semibold">
              Username
            </label>
            <input
              id="register-username"
              type="text"
              className="form-control"
              placeholder="Choose a username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
              autoFocus
            />
          </div>

          {/* Full Name */}
          <div className="mb-3">
            <label htmlFor="register-fullname" className="form-label small fw-semibold">
              Full Name{' '}
              <span className="text-muted fw-normal">(optional)</span>
            </label>
            <input
              id="register-fullname"
              type="text"
              className="form-control"
              placeholder="Your full name"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
            />
          </div>

          {/* Password */}
          <div className="mb-3">
            <label htmlFor="register-password" className="form-label small fw-semibold">
              Password
            </label>
            <div className="input-group">
              <input
                id="register-password"
                type={showPassword ? 'text' : 'password'}
                className="form-control"
                placeholder="Create a password"
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

          {/* Registration Code */}
          <div className="mb-4">
            <label htmlFor="register-code" className="form-label small fw-semibold">
              Registration Code
            </label>
            <input
              id="register-code"
              type="text"
              className="form-control"
              placeholder="Setup code or invitation key"
              value={registrationCode}
              onChange={(e) => setRegistrationCode(e.target.value)}
              required
            />
            <div className="form-text small">
              First user: use the <strong>SETUP_CODE</strong>. Others: use the invitation key from admin.
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
                Creating account...
              </>
            ) : 'Create Account'}
          </button>

          {/* Login link */}
          <p className="text-center small text-muted mb-0">
            Already have an account?{' '}
            <Link to="/login" className="text-primary fw-semibold text-decoration-none">
              Sign In
            </Link>
          </p>

        </form>
      </div>
    </div>
  );
}