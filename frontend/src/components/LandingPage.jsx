import React from 'react';
import { Link } from 'react-router-dom';
import { Container, Row, Col, Button } from 'react-bootstrap';
import { Brain, BookOpen, Users } from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';

const LandingPage = () => {
  const { user } = useAuth();

  return (
    <div className="min-vh-100 bg-light">
      {/* Header/Hero Section */}
      <header className="text-white py-5" style={{ 
        background: '#8A6BC1',
        minHeight: '600px',
        display: 'flex',
        alignItems: 'center'
      }}>
        <Container>
          <Row className="mb-5">
            <Col className="d-flex justify-content-between align-items-center">
              <h1 className="h2 mb-0" style={{ fontFamily: 'Lora, serif' }}>DreamPath</h1>
              <div>
                {user ? (
                  <Link to="/dashboard">
                    <Button variant="light" className="px-4 me-2">Dashboard</Button>
                  </Link>
                ) : (
                  <Link to="/login">
                    <Button variant="light" className="px-4 me-2">Log In</Button>
                  </Link>
                )}
              </div>
            </Col>
          </Row>
          <Row className="align-items-center">
            <Col md={8} className="mx-auto text-center">
              <h2 className="display-4 fw-bold mb-4" style={{ fontFamily: 'Lora, serif' }}>
                Plan Your Academic Journey with Purpose
              </h2>
              <p className="lead mb-4">
                In a changing world, DreamPath helps students prepare for their dream careers by aligning their college journey with their interests and goals.
              </p>
              <Link to="/signup">
                <Button variant="primary" size="lg" className="d-flex align-items-center mx-auto" style={{ backgroundColor:'rgb(151 123 203)', border: 'none', fontFamily: 'Lora, serif' }}>
                  Get Started
                  <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="ms-2" style={{ width: '20px', height: '20px' }}>
                    <path d="M5 12h14"></path>
                    <path d="m12 5 7 7-7 7"></path>
                  </svg>
                </Button>
              </Link>
            </Col>
          </Row>
        </Container>
      </header>

      {/* How It Works Section */}
      <section className="py-5 bg-white">
        <Container>
          <h2 className="text-center mb-5" style={{ fontFamily: 'Lora, serif' }}>How DreamPath Works</h2>
          <div style={{
            color: '#6c757d',
            fontSize: 18,
            marginBottom: 20,
            textAlign: 'center',
            fontFamily: 'Lora, serif',
            fontWeight: 400
          }}>
            A career-oriented, AI-powered advisor that personalizes your college experience.
          </div>
          <Row>
            <Col md={4} className="mb-4">
              <div className="bg-light p-4 rounded h-100">
                <div className="d-inline-flex align-items-center justify-content-center mb-3" style={{ width: '48px', height: '48px', borderRadius: '50%', backgroundColor: '#f3e8ff' }}>
                  <Brain size={24} color="#8A6BC1" />
                </div>
                <h3 className="h4 mb-3">Deep Industry Knowledge</h3>
                <p className="text-muted">Grounded in research about careers, changing specifications, and other dynamic factors to make accurate, actionable recommendations.</p>
              </div>
            </Col>
            <Col md={4} className="mb-4">
              <div className="bg-light p-4 rounded h-100">
                <div className="d-inline-flex align-items-center justify-content-center mb-3" style={{ width: '48px', height: '48px', borderRadius: '50%', backgroundColor: '#f3e8ff' }}>
                  <BookOpen size={24} color="#8A6BC1" />
                </div>
                <h3 className="h4 mb-3">Smart Course Planning</h3>
                <p className="text-muted">Get personalized course recommendations based on your interests, major requirements, and career goals.</p>
              </div>
            </Col>
            <Col md={4} className="mb-4">
              <div className="bg-light p-4 rounded h-100">
                <div className="d-inline-flex align-items-center justify-content-center mb-3" style={{ width: '48px', height: '48px', borderRadius: '50%', backgroundColor: '#f3e8ff' }}>
                  <Users size={24} color="#8A6BC1" />
                </div>
                <h3 className="h4 mb-3">Club Involvement</h3>
                <p className="text-muted">Discover a range student organizations and activities that align with your interests and enhance your college experience.</p>
              </div>
            </Col>
          </Row>
        </Container>
      </section>

      {/* Footer */}
      <footer className="bg-dark text-white py-4">
        <Container>
          <Row className="align-items-center">
            <Col md={6} className="mb-3 mb-md-0">
              <h2 className="h4 mb-0" style={{ fontFamily: 'Lora, serif' }}>DreamPath</h2>
            </Col>
          </Row>
          <Row>
            <Col>
              <p className="text-muted small mt-3 mb-0">© 2025 DreamPath. All rights reserved.</p>
            </Col>
          </Row>
        </Container>
      </footer>
    </div>
  );
};

export default LandingPage; 