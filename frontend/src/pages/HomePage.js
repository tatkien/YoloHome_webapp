import React from 'react';
import { Container, Row, Col, Card } from 'react-bootstrap';
import { Link } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';

export default function HomePage() {
  const { user, isAdmin } = useAuth();

  const quickLinks = [
    { to: '/devices', icon: '📡', title: 'Devices', desc: 'Manage your smart home devices', color: '#4c7ef3' },
    { to: '/face/enrollments', icon: '🧑', title: 'Enrollments', desc: 'Register faces for recognition', color: '#a78bfa' },
    { to: '/face/recognize', icon: '🔍', title: 'Recognize', desc: 'Test face recognition AI', color: '#34d399' },
    { to: '/face/logs', icon: '📋', title: 'Logs', desc: 'View recognition history', color: '#fbbf24' },
  ];

  if (isAdmin) {
    quickLinks.push({ to: '/admin/users', icon: '👑', title: 'Admin', desc: 'Manage users & invitation keys', color: '#f87171' });
  }

  return (
    <Container className="py-5 fade-in">
      <Row className="justify-content-center text-center mb-5">
        <Col md={8}>
          <div style={{ fontSize: '3rem', marginBottom: '0.5rem' }}>🏠</div>
          <h1 style={{ fontWeight: 700, fontSize: '2.2rem', marginBottom: '0.5rem' }}>
            Welcome back, <span style={{ background: 'var(--gradient-primary)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>{user?.username}</span>
          </h1>
          <p style={{ color: 'var(--text-secondary)', fontSize: '1.1rem' }}>
            Your smart home dashboard
          </p>
        </Col>
      </Row>

      <Row className="g-4 justify-content-center">
        {quickLinks.map((link) => (
          <Col md={4} lg={3} key={link.to}>
            <Link to={link.to} style={{ textDecoration: 'none' }}>
              <Card className="h-100 text-center" style={{ cursor: 'pointer' }}>
                <Card.Body className="p-4">
                  <div style={{
                    width: '60px',
                    height: '60px',
                    borderRadius: '16px',
                    background: `${link.color}15`,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontSize: '1.8rem',
                    margin: '0 auto 1rem',
                  }}>
                    {link.icon}
                  </div>
                  <Card.Title style={{ fontSize: '1rem' }}>{link.title}</Card.Title>
                  <Card.Text style={{ fontSize: '0.85rem' }}>{link.desc}</Card.Text>
                </Card.Body>
              </Card>
            </Link>
          </Col>
        ))}
      </Row>

      <Row className="justify-content-center mt-5">
        <Col md={8}>
          <div className="yh-card p-4">
            <Row className="text-center g-4">
              <Col xs={4}>
                <div style={{ fontSize: '1.5rem', marginBottom: '0.25rem' }}>⚡</div>
                <div style={{ fontWeight: 600, fontSize: '0.85rem' }}>FastAPI Backend</div>
                <div style={{ color: 'var(--text-muted)', fontSize: '0.75rem' }}>High-performance API</div>
              </Col>
              <Col xs={4}>
                <div style={{ fontSize: '1.5rem', marginBottom: '0.25rem' }}>🤖</div>
                <div style={{ fontWeight: 600, fontSize: '0.85rem' }}>Face Recognition</div>
                <div style={{ color: 'var(--text-muted)', fontSize: '0.75rem' }}>RetinaFace + ArcFace</div>
              </Col>
              <Col xs={4}>
                <div style={{ fontSize: '1.5rem', marginBottom: '0.25rem' }}>🐳</div>
                <div style={{ fontWeight: 600, fontSize: '0.85rem' }}>Docker Ready</div>
                <div style={{ color: 'var(--text-muted)', fontSize: '0.75rem' }}>Compose for deploy</div>
              </Col>
            </Row>
          </div>
        </Col>
      </Row>
    </Container>
  );
}
