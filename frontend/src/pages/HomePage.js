import React from 'react';
import { Container, Row, Col, Card } from 'react-bootstrap';
import { Link } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';

export default function HomePage() {
  const { user, isAdmin } = useAuth();

  const quickLinks = [
    { to: '/devices', icon: '📡', title: 'Devices', desc: 'Manage your smart home devices', colorClass: 'text-primary bg-primary bg-opacity-10' },
    { to: '/face/recognize', icon: '🔍', title: 'Recognize', desc: 'Test face recognition AI', colorClass: 'text-success bg-success bg-opacity-10' },
    { to: '/face/logs', icon: '📋', title: 'Logs', desc: 'View recognition history', colorClass: 'text-warning bg-warning bg-opacity-10' },
  ];

  if (isAdmin) {
    quickLinks.push({ to: '/face/enrollments',icon: '🧑' , title: 'Enrollments', desc: 'Register faces for recognition', colorClass: 'text-info bg-info bg-opacity-10' });
    quickLinks.push({ to: '/admin/users',icon: '👑' , title: 'Admin', desc: 'Manage users & invitation keys', colorClass: 'text-danger bg-danger bg-opacity-10' });
  }

  return (
    <Container className="py-5">
      <Row className="justify-content-center text-center mb-5">
        <Col md={8}>
          <h1 className="fw-bold fs-2 mb-2">
            Welcome back, <span className="bg-primary bg-gradient text-white px-2 py-1 rounded">{user?.username}</span>
          </h1>
          <p className="text-secondary fs-5">
            Your smart home dashboard
          </p>
        </Col>
      </Row>

      <Row className="g-4 justify-content-center">
        {quickLinks.map((link) => (
          <Col md={4} lg={3} key={link.to}>
            <Link to={link.to} className="text-decoration-none text-dark">
              <Card className="h-100 text-center shadow-lg border-0" style={{ cursor: 'pointer' }}>
                <Card.Body className="p-4">
                  <div className={`mx-auto mb-3 d-flex align-items-center justify-content-center fs-2 rounded-4 ${link.colorClass}`} style={{ width: '60px', height: '60px' }}>
                    {link.icon}
                  </div>
                  <Card.Title className="fs-6">{link.title}</Card.Title>
                  <Card.Text className="small text-muted">{link.desc}</Card.Text>
                </Card.Body>
              </Card>
            </Link>
          </Col>
        ))}
      </Row>

    </Container>
  );
}
