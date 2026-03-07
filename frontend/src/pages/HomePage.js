import React from 'react';
import { Container, Row, Col, Card, Button } from 'react-bootstrap';
import { Link } from 'react-router-dom';

function HomePage() {
  return (
    <Container className="py-5">
      <Row className="justify-content-center text-center mb-5">
        <Col md={8}>
          <h1 className="display-4 fw-bold">Welcome to YoloHome</h1>
          <p className="lead text-muted">
            A smart home web application built with React, Bootstrap, FastAPI and PostgreSQL.
          </p>
          <Button as={Link} to="/items" variant="primary" size="lg" className="mt-3">
            Manage Items
          </Button>
        </Col>
      </Row>

      <Row className="g-4 justify-content-center">
        <Col md={4}>
          <Card className="h-100 shadow-sm text-center">
            <Card.Body className="p-4">
              <div className="fs-1 mb-3">⚡</div>
              <Card.Title>Fast API Backend</Card.Title>
              <Card.Text className="text-muted">
                Powered by FastAPI and PostgreSQL for high-performance data management.
              </Card.Text>
            </Card.Body>
          </Card>
        </Col>
        <Col md={4}>
          <Card className="h-100 shadow-sm text-center">
            <Card.Body className="p-4">
              <div className="fs-1 mb-3">🎨</div>
              <Card.Title>Modern Frontend</Card.Title>
              <Card.Text className="text-muted">
                Built with React and Bootstrap for a responsive and beautiful UI.
              </Card.Text>
            </Card.Body>
          </Card>
        </Col>
        <Col md={4}>
          <Card className="h-100 shadow-sm text-center">
            <Card.Body className="p-4">
              <div className="fs-1 mb-3">🐳</div>
              <Card.Title>Docker Ready</Card.Title>
              <Card.Text className="text-muted">
                Containerised with Docker Compose for simple local development and deployment.
              </Card.Text>
            </Card.Body>
          </Card>
        </Col>
      </Row>
    </Container>
  );
}

export default HomePage;
