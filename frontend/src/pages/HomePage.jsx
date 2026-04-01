import React from 'react';
import { Container, Row, Col, Card, Button, Badge } from 'react-bootstrap';
import { Link } from 'react-router-dom';

function HomePage({ user }) {
  return (
    <div style={{ background: '#FFF8F0', minHeight: '100vh', color: '#C08552' }}>

      {/* Hero */}
      <Container className="py-5">
        <Row className="align-items-center py-5">
          <Col md={6} className="mb-5 mb-md-0">
            <Badge
              bg="warning"
              text="dark"
              className="mb-3 px-3 py-2 rounded-pill fw-normal"
              style={{ fontSize: '0.75rem', letterSpacing: '0.1em' }}
            >
              🟡 Smart Home Platform
            </Badge>

            <h1 className="display-4 fw-bold mb-3" style={{ color: '#4B2E2B', lineHeight: 1.1 }}>
              Your home,{' '}
              <span style={{ color: '#F59E0B' }}>intelligently</span>{' '}
              managed.
            </h1>

            <p className="lead mb-4" style={{ color: '#888', fontWeight: 300 }}>
              YoloHome brings together your devices, data, and controls
              into one fast and beautiful interface.
            </p>

            <div className="d-flex gap-3 flex-wrap">
              <Button
                as={Link}
                to="/items"
                variant="warning"
                size="lg"
                className="fw-semibold text-dark px-4"
              >
                Manage Items →
              </Button>

              {user ? (
                <Button
                  as={Link}
                  to="/items"
                  variant="outline-light"
                  size="lg"
                  className="px-4"
                >
                  👤 Welcome, {user.name}
                </Button>
              ) : (
                <Button
                  as={Link}
                  to="/login"
                  variant="outline-secondary"
                  size="lg"
                  className="px-4"
                  style={{background:'#C08552', color:'white'}}
                >
                  Sign in
                </Button>
              )}
            </div>
          </Col>

          {/* Stat cards */}
          <Col md={6}>
            <Row className="g-3">
              {[
                { label: 'Devices Online', value: '12', icon: '💡' },
                { label: 'Active Now',     value: '8',  icon: '⚡' },
                { label: 'Alerts',         value: '0',  icon: '🔔' },
                { label: 'Uptime',         value: '99%',icon: '📶' },
              ].map(({ label, value, icon }) => (
                <Col xs={6} key={label}>
                  <Card
                    className="h-100 border-0 text-center p-3"
                    style={{ background: '#1A1A1A', color: '#F5F5F5' }}
                  >
                    <div style={{ fontSize: '1.8rem' }}>{icon}</div>
                    <div
                      className="fw-bold my-1"
                      style={{ fontSize: '1.8rem', color: '#F59E0B' }}
                    >
                      {value}
                    </div>
                    <div style={{ fontSize: '0.8rem', color: '#888' }}>{label}</div>
                  </Card>
                </Col>
              ))}
            </Row>
          </Col>
        </Row>

        <hr style={{ borderColor: 'rgba(255,255,255,0.07)' }} />

        {/* Feature Cards */}
        <Row className="g-4 py-5">
          <Col xs={12}>
            <p
              className="text-uppercase mb-4"
              style={{ fontSize: '0.75rem', letterSpacing: '0.15em', color: '#888' }}
            >
              What powers it
            </p>
          </Col>
          {[
            { icon: '⚡', title: 'FastAPI Backend',  text: 'High-performance API layer built on FastAPI and PostgreSQL, designed for real-time responsiveness.', num: '01' },
            { icon: '🎨', title: 'Modern Frontend',  text: 'React and Bootstrap combine to deliver a responsive, polished interface that works on any device.',   num: '02' },
            { icon: '🐳', title: 'Docker Ready',     text: 'Containerised with Docker Compose for seamless local development and one-command deployment.',        num: '03' },
          ].map(({ icon, title, text, num }) => (
            <Col md={4} key={num}>
              <Card
                className="h-100 border-0 p-4"
                style={{ background: '#111', color: '#F5F5F5' }}
              >
                <div style={{ fontSize: '2rem', marginBottom: '12px' }}>{icon}</div>
                <div className="d-flex justify-content-between align-items-start mb-2">
                  <Card.Title className="fw-bold mb-0" style={{ color: '#F5F5F5' }}>
                    {title}
                  </Card.Title>
                  <span style={{ fontSize: '0.75rem', color: 'rgba(255,255,255,0.15)' }}>
                    {num}
                  </span>
                </div>
                <Card.Text style={{ color: '#888', fontWeight: 300, fontSize: '0.9rem' }}>
                  {text}
                </Card.Text>
              </Card>
            </Col>
          ))}
        </Row>
      </Container>
    </div>
  );
}

export default HomePage;