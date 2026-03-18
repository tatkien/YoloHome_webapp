import React, { useState, useEffect, useCallback } from 'react';
import { Container, Table, Button, Form, Alert, Spinner, Row, Col, InputGroup } from 'react-bootstrap';
import api from '../services/api';

export default function AdminUsersPage() {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  // Invitation key
  const [invKey, setInvKey] = useState('');
  const [invLoading, setInvLoading] = useState(false);

  const fetchUsers = useCallback(async () => {
    try {
      setLoading(true);
      const res = await api.get('/admin/users/');
      setUsers(res.data);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to load users');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchUsers(); }, [fetchUsers]);

  const handleDelete = async (userId, username) => {
    if (!window.confirm(`Delete user "${username}"? This cannot be undone.`)) return;
    setError('');
    try {
      await api.delete(`/admin/users/${userId}`);
      setSuccess(`User "${username}" deleted`);
      fetchUsers();
      setTimeout(() => setSuccess(''), 3000);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to delete user');
    }
  };

  const handleSetInvKey = async (e) => {
    e.preventDefault();
    setError('');
    setInvLoading(true);
    try {
      const res = await api.put('/admin/users/invitation-key', { invitation_key: invKey });
      setSuccess(`Invitation key updated at ${new Date(res.data.updated_at).toLocaleString()}`);
      setInvKey('');
      setTimeout(() => setSuccess(''), 4000);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to set invitation key');
    } finally {
      setInvLoading(false);
    }
  };

  return (
    <Container className="py-4 fade-in">
      <div className="page-header">
        <h1>👑 Admin Panel</h1>
        <p>Manage users and invitation keys</p>
      </div>

      {error && <Alert variant="danger" dismissible onClose={() => setError('')}>{error}</Alert>}
      {success && <Alert variant="success">{success}</Alert>}

      {/* Invitation Key */}
      <div className="yh-card p-4 mb-4">
        <h5 style={{ fontWeight: 600, marginBottom: '1rem' }}>🔑 Invitation Key</h5>
        <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', marginBottom: '1rem' }}>
          Set the key that new users must provide to register. Changing it invalidates the old key.
        </p>
        <Form onSubmit={handleSetInvKey}>
          <InputGroup>
            <Form.Control
              type="text"
              placeholder="Enter new invitation key"
              value={invKey}
              onChange={(e) => setInvKey(e.target.value)}
              required
            />
            <Button type="submit" disabled={invLoading}>
              {invLoading ? <Spinner size="sm" animation="border" /> : 'Update Key'}
            </Button>
          </InputGroup>
        </Form>
      </div>

      {/* Users Table */}
      <div className="yh-card p-4">
        <div className="d-flex justify-content-between align-items-center mb-3">
          <h5 style={{ fontWeight: 600, margin: 0 }}>👥 Users</h5>
          <span className="badge-device">{users.length} users</span>
        </div>

        {loading ? (
          <div className="text-center py-4"><Spinner animation="border" /></div>
        ) : users.length === 0 ? (
          <p style={{ color: 'var(--text-muted)' }}>No users found.</p>
        ) : (
          <div className="table-responsive">
            <Table hover>
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Username</th>
                  <th>Full Name</th>
                  <th>Role</th>
                  <th>Active</th>
                  <th>Created</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {users.map((u) => (
                  <tr key={u.id}>
                    <td>{u.id}</td>
                    <td style={{ fontWeight: 600 }}>{u.username}</td>
                    <td>{u.full_name || '—'}</td>
                    <td>
                      <span className={u.role === 'admin' ? 'badge-admin' : 'badge-device'}>
                        {u.role}
                      </span>
                    </td>
                    <td>{u.is_active ? '✅' : '❌'}</td>
                    <td style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
                      {new Date(u.created_at).toLocaleDateString()}
                    </td>
                    <td>
                      <Button
                        variant="danger"
                        size="sm"
                        onClick={() => handleDelete(u.id, u.username)}
                      >
                        Delete
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </Table>
          </div>
        )}
      </div>
    </Container>
  );
}
