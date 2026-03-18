import React, { useState } from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import { Form, Button, Alert, Spinner } from 'react-bootstrap';
import { useAuth } from '../contexts/AuthContext';

export default function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const from = location.state?.from?.pathname || '/';

  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

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
    <div className="auth-container">
      <div className="auth-card fade-in">
        <div className="text-center mb-4">
          <div style={{ fontSize: '2.5rem', marginBottom: '0.5rem' }}>🏠</div>
          <h2>Welcome Back</h2>
          <p className="text-muted" style={{ color: 'var(--text-secondary)' }}>
            Sign in to your YoloHome account
          </p>
        </div>

        {error && <Alert variant="danger" className="mb-3">{error}</Alert>}

        <Form onSubmit={handleSubmit}>
          <Form.Group className="mb-3" controlId="login-username">
            <Form.Label>Username</Form.Label>
            <Form.Control
              type="text"
              placeholder="Enter your username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
              autoFocus
            />
          </Form.Group>

          <Form.Group className="mb-4" controlId="login-password">
            <Form.Label>Password</Form.Label>
            <Form.Control
              type="password"
              placeholder="Enter your password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </Form.Group>

          <Button type="submit" className="w-100 mb-3" disabled={loading}>
            {loading ? <Spinner size="sm" animation="border" /> : 'Sign In'}
          </Button>

          <p className="text-center mb-0" style={{ color: 'var(--text-secondary)', fontSize: '0.9rem' }}>
            Don't have an account?{' '}
            <Link to="/register" style={{ color: 'var(--accent-blue)', textDecoration: 'none', fontWeight: 600 }}>
              Register
            </Link>
          </p>
        </Form>
      </div>
    </div>
  );
}
