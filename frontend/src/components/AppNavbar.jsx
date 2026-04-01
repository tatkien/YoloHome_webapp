import React, { useState, useEffect } from 'react';
import { Navbar, Nav, Container, NavDropdown } from 'react-bootstrap';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { PersonCircle, ShieldFill } from 'react-bootstrap-icons';

function AppNavbar() {
  const location = useLocation();
  const navigate  = useNavigate();

  const [user,    setUser]    = useState(null);
  const [loading, setLoading] = useState(true);

  // ── Fetch current user on mount + when auth changes ──
  const fetchMe = async () => {
    try {
      const res = await fetch('/api/v1/auth/me', { credentials: 'include' });
      if (!res.ok) { setUser(null); return; }
      setUser(await res.json());
    } catch {
      setUser(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchMe();

    // Re-fetch when login/logout fires a custom event
    window.addEventListener('auth-change', fetchMe);
    return () => window.removeEventListener('auth-change', fetchMe);
  }, []);

  const handleLogout = async () => {
    try {
      await fetch('/api/v1/auth/logout', { method: 'POST', credentials: 'include' });
    } catch { /* ignore */ } finally {
      localStorage.removeItem('loggedInUser');
      localStorage.removeItem('token');
      setUser(null);
      window.dispatchEvent(new Event('auth-change'));
      navigate('/');
    }
  };

  const isAdmin = user?.role === 'admin';

  return (
    <Navbar bg="dark" variant="dark" expand="md" sticky="top">
      <Container>
        <Navbar.Brand as={Link} to="/">
          🏠 YoloHome
        </Navbar.Brand>

        <Navbar.Toggle aria-controls="main-nav" />

        <Navbar.Collapse id="main-nav">
          <Nav className="ms-auto align-items-center">

            <Nav.Link as={Link} to="/" active={location.pathname === '/'}>
              Home
            </Nav.Link>

            <Nav.Link as={Link} to="/items" active={location.pathname.startsWith('/items')}>
              Items
            </Nav.Link>

            {isAdmin && (
              <Nav.Link
                as={Link}
                to="/admin"
                active={location.pathname.startsWith('/admin')}
                className="d-flex align-items-center gap-1"
              >
                <ShieldFill size={13} className="text-warning" />
                Admin
              </Nav.Link>
            )}

            {/* ── Auth section ── */}
            {loading ? (
              <Nav.Link disabled>
                <span className="spinner-border spinner-border-sm text-light" />
              </Nav.Link>

            ) : user ? (
              <NavDropdown
                align="end"
                title={
                  <span className="d-inline-flex align-items-center gap-2">
                    <PersonCircle size={20} className="text-light" />
                    <span className="text-light" style={{ fontSize: '0.9rem' }}>
                      {user.username}
                    </span>
                    {isAdmin && (
                      <span className="badge bg-warning text-dark" style={{ fontSize: '0.65rem' }}>
                        Admin
                      </span>
                    )}
                  </span>
                }
                id="user-dropdown"
              >
                <NavDropdown.Header className="small text-muted">
                  {user.email}
                </NavDropdown.Header>

                <NavDropdown.Divider />

                {isAdmin && (
                  <NavDropdown.Item as={Link} to="/admin">
                    <ShieldFill size={13} className="me-2 text-warning" />
                    Admin Panel
                  </NavDropdown.Item>
                )}

                <NavDropdown.Item as={Link} to="/me">
                  <PersonCircle size={13} className="me-2" />
                  Profile
                </NavDropdown.Item>

                <NavDropdown.Divider />

                <NavDropdown.Item
                  onClick={handleLogout}
                  className="text-danger"
                >
                  Logout
                </NavDropdown.Item>
              </NavDropdown>

            ) : (
              <Nav.Link
                as={Link}
                to="/login"
                active={location.pathname.startsWith('/login')}
              >
                Login
              </Nav.Link>
            )}

          </Nav>
        </Navbar.Collapse>
      </Container>
    </Navbar>
  );
}

export default AppNavbar;