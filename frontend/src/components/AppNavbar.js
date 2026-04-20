import React from 'react';
import { Navbar, Nav, Container, NavDropdown } from 'react-bootstrap';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';

export default function AppNavbar() {
  const location = useLocation();
  const navigate = useNavigate();
  const { user, logout, isAdmin } = useAuth();

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const isActive = (path) => location.pathname === path;

  return (
    <Navbar className="border-bottom sticky shadow-lg bg-white" expand="md" sticky="top" style={{ padding: '0.5rem 0', zIndex: 1050 }}>
      <Container>
        <Navbar.Brand as={Link} to="/">
          <img src='/home.png' alt='Home Page' width={'10%'} height={'10%'}/>
        </Navbar.Brand>
        <Navbar.Toggle aria-controls="main-nav" />
        <Navbar.Collapse id="main-nav">
          <Nav className="me-auto">
            {user && (
              <>
                <Nav.Link as={Link} to="/" active={isActive('/')}>
                  Home
                </Nav.Link>
                <Nav.Link as={Link} to="/devices" active={isActive('/devices')}>
                  Devices
                </Nav.Link>
                {isAdmin && (
                  <NavDropdown
                    title="Face AI"
                    id="face-dropdown"
                    active={location.pathname.startsWith('/face')}
                  >
                    <NavDropdown.Item as={Link} to="/face/enrollments">
                      🧑 Enrollments
                    </NavDropdown.Item>
                    <NavDropdown.Item as={Link} to="/face/logs">
                      📋 Logs
                    </NavDropdown.Item>
                  </NavDropdown>
                )}

                <Nav.Link as={Link} to="/schedules" active={isActive('/schedules')}>
                  Schedules
                </Nav.Link>             

                {!isAdmin && (
                  <Nav.Link as={Link} to="/face/logs" active={isActive('/face/logs')}>
                    📋 Face Logs
                  </Nav.Link>
                )}
                {isAdmin && (
                  <Nav.Link as={Link} to="/admin/users" active={isActive('/admin/users')}>
                     Admin
                  </Nav.Link>
                )}
              </>
            )}
          </Nav>

          <Nav>
            {user ? (
              <>
                <Nav.Link disabled style={{ color: 'var(--text-muted)', fontWeight: 500, fontSize: '0.85rem' }}>
                  {user.username}
                  {isAdmin && <span className="border border-black rounded-pill bg-warning ms-2" style={{padding: 3}}>admin</span>}
                </Nav.Link>
                <Nav.Link onClick={handleLogout} style={{padding: 4,cursor: 'pointer'}} >
                  Logout
                </Nav.Link>
              </>
            ) : (
              <>
                <Nav.Link as={Link} to="/login" active={isActive('/login')}>
                  Sign In
                </Nav.Link>
                <Nav.Link as={Link} to="/register" active={isActive('/register')}>
                  Register
                </Nav.Link>
              </>
            )}
          </Nav>
        </Navbar.Collapse>
      </Container>
    </Navbar>
  );
}
