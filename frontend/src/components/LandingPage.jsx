import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Container, Row, Col, Button } from 'react-bootstrap';
import { supabase } from '../lib/supabase';

const LandingPage = () => {
  const [user, setUser] = useState(null);

  useEffect(() => {
    const checkAuth = async () => {
      const { data: { user } } = await supabase.auth.getUser();
      setUser(user);
    };
    checkAuth();
  }, []);

  return (
    <div className="min-vh-100 bg-light">
      {/* Header/Hero Section */}
      <header className="text-white py-5" style={{ 
        background: 'linear-gradient(135deg, #8A6BC1 0%, #6A4C93 100%)',
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
                DreamPath helps students align courses, clubs, and alumni connections with their career goals and personal interests.
              </p>
              <Link to="/signup">
                <Button variant="primary" size="lg" className="d-flex align-items-center mx-auto">
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
            A career-oriented, AI-powered college advisor that personalizes:
          </div>
          <Row>
            <Col md={4} className="mb-4">
              <div className="bg-light p-4 rounded h-100">
                <div className="bg-purple-100 p-3 rounded-circle d-inline-flex align-items-center justify-content-center mb-3" style={{ width: '48px', height: '48px', backgroundColor: '#f3e8ff' }}>
                  <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#8A6BC1" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ width: '24px', height: '24px' }}>
                    <path d="M12 7v14"></path>
                    <path d="M3 18a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1h5a4 4 0 0 1 4 4 4 4 0 0 1 4-4h5a1 1 0 0 1 1 1v13a1 1 0 0 1-1 1h-6a3 3 0 0 0-3 3 3 3 0 0 0-3-3z"></path>
                  </svg>
                </div>
                <h3 className="h4 mb-3">Smart Course Planning</h3>
                <p className="text-muted">Get personalized course recommendations based on your interests, major requirements, and career goals.</p>
              </div>
            </Col>
            <Col md={4} className="mb-4">
              <div className="bg-light p-4 rounded h-100">
                <div className="bg-purple-100 p-3 rounded-circle d-inline-flex align-items-center justify-content-center mb-3" style={{ width: '48px', height: '48px', backgroundColor: '#f3e8ff' }}>
                  <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#8A6BC1" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ width: '24px', height: '24px' }}>
                    <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"></path>
                    <circle cx="9" cy="7" r="4"></circle>
                    <path d="M22 21v-2a4 4 0 0 0-3-3.87"></path>
                    <path d="M16 3.13a4 4 0 0 1 0 7.75"></path>
                  </svg>
                </div>
                <h3 className="h4 mb-3">Club Involvement</h3>
                <p className="text-muted">Discover student organizations that align with your interests and enhance your college experience.</p>
              </div>
            </Col>
            <Col md={4} className="mb-4">
              <div className="bg-light p-4 rounded h-100">
                <div className="bg-purple-100 p-3 rounded-circle d-inline-flex align-items-center justify-content-center mb-3" style={{ width: '48px', height: '48px', backgroundColor: '#f3e8ff' }}>
                  <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#8A6BC1" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ width: '24px', height: '24px' }}>
                    <rect x="16" y="16" width="6" height="6" rx="1"></rect>
                    <rect x="2" y="16" width="6" height="6" rx="1"></rect>
                    <rect x="9" y="2" width="6" height="6" rx="1"></rect>
                    <path d="M5 16v-3a1 1 0 0 1 1-1h12a1 1 0 0 1 1 1v3"></path>
                    <path d="M12 12V8"></path>
                  </svg>
                </div>
                <h3 className="h4 mb-3">Alumni Connections</h3>
                <p className="text-muted">Connect with alumni in your field of interest for mentorship, advice, and career opportunities.</p>
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
            <Col md={6}>
              <div className="d-flex gap-4 justify-content-md-end">
                <a href="#" className="text-white text-decoration-none">About</a>
                <a href="#" className="text-white text-decoration-none">Privacy</a>
                <a href="#" className="text-white text-decoration-none">Terms</a>
                <a href="#" className="text-white text-decoration-none">Contact</a>
              </div>
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