import React, { useState } from 'react';
import { Container, Form, Button, Card, Alert } from 'react-bootstrap';
import { useNavigate, Link } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import 'bootstrap/dist/css/bootstrap.min.css';

/**
 * Signup - User registration component
 *
 * Uses AuthContext for localStorage-based authentication
 * Redirects to onboarding after successful signup
 */
function Signup() {
  const navigate = useNavigate();
  const { signUp } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [fullName, setFullName] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [confirmationSent, setConfirmationSent] = useState(false);

  const handleSignup = async (e) => {
    e.preventDefault();
    setError('');

    // Validation
    if (!fullName.trim()) {
      setError('Please enter your full name');
      return;
    }

    if (!email.trim()) {
      setError('Please enter your email');
      return;
    }

    if (!email.toLowerCase().endsWith('@dartmouth.edu')) {
      setError('Only @dartmouth.edu addresses are accepted');
      return;
    }

    if (password.length < 6) {
      setError('Password must be at least 6 characters');
      return;
    }

    if (password !== confirmPassword) {
      setError('Passwords do not match');
      return;
    }

    setLoading(true);

    try {
      const { user, error, needsEmailConfirmation } = await signUp(email, password, fullName);

      if (error) {
        setError(error);
      } else if (user) {
        if (needsEmailConfirmation) {
          // Show confirmation message instead of redirecting
          setConfirmationSent(true);
        } else {
          // Email already confirmed (shouldn't happen with confirmation enabled)
          navigate('/onboarding');
        }
      }
    } catch (err) {
      setError(err.message || 'Failed to create account');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      style={{
        minHeight: '100vh',
        background: 'linear-gradient(135deg, #8A6BC1 0%, #6B8FC7 100%)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
      }}
    >
      <Container>
        <div className="row justify-content-center">
          <div className="col-md-6 col-lg-5">
            <Card className="shadow-lg border-0">
              <Card.Body className="p-5">
                <div className="text-center mb-4">
                  <h2
                    style={{
                      fontFamily: 'Lora, serif',
                      fontWeight: 600,
                      color: '#8A6BC1',
                    }}
                  >
                    Join DreamPath
                  </h2>
                  <p className="text-muted">
                    {confirmationSent ? 'Check your email' : 'Create your account to get started'}
                  </p>
                </div>

                {error && <Alert variant="danger">{error}</Alert>}

                {confirmationSent ? (
                  <div>
                    <div
                      style={{
                        background: 'linear-gradient(135deg, #e5f1d3 0%, #f0f8e8 100%)',
                        border: '2px solid #a8d5a8',
                        borderRadius: '12px',
                        padding: '30px',
                        textAlign: 'center',
                      }}
                    >
                      {/* Checkmark icon */}
                      <div style={{ marginBottom: '20px' }}>
                        <svg
                          width="60"
                          height="60"
                          viewBox="0 0 60 60"
                          fill="none"
                          xmlns="http://www.w3.org/2000/svg"
                          style={{ margin: '0 auto', display: 'block' }}
                        >
                          <circle cx="30" cy="30" r="30" fill="#a8d5a8" />
                          <path
                            d="M18 30L26 38L42 22"
                            stroke="#2d5f2d"
                            strokeWidth="4"
                            strokeLinecap="round"
                            strokeLinejoin="round"
                          />
                        </svg>
                      </div>

                      <h4
                        style={{
                          fontFamily: 'Lora, serif',
                          fontWeight: 700,
                          color: '#2d5f2d',
                          fontSize: '24px',
                          marginBottom: '15px',
                        }}
                      >
                        Check Your Email
                      </h4>

                      <p
                        style={{
                          fontFamily: 'Lora, serif',
                          color: '#4a5f4a',
                          fontSize: '15px',
                          lineHeight: '1.6',
                          marginBottom: '10px',
                        }}
                      >
                        If <strong style={{ color: '#2d5f2d' }}>{email}</strong> is not already registered,
                        we've sent a confirmation email.
                      </p>

                      <p
                        style={{
                          fontFamily: 'Lora, serif',
                          color: '#4a5f4a',
                          fontSize: '15px',
                          lineHeight: '1.6',
                          marginBottom: '20px',
                        }}
                      >
                        Please check your inbox and click the link to verify your account.
                      </p>

                      <div
                        style={{
                          borderTop: '1px solid rgba(168, 213, 168, 0.4)',
                          paddingTop: '20px',
                          marginTop: '10px',
                        }}
                      >
                        <p
                          style={{
                            fontFamily: 'Lora, serif',
                            color: '#5a6f5a',
                            fontSize: '14px',
                            fontStyle: 'italic',
                            marginBottom: 0,
                          }}
                        >
                          After confirming, you'll be redirected to complete your profile.
                        </p>
                      </div>
                    </div>

                    {/* Already have account warning */}
                    <Alert variant="info" className="mt-3" style={{
                      borderLeft: '4px solid #8A6BC1',
                      backgroundColor: '#f8f9fa'
                    }}>
                      <strong>Already have an account?</strong> If you don't receive an email within a few minutes,
                      you may already be registered. Try{' '}
                      <Link
                        to="/login"
                        style={{ color: '#8A6BC1', fontWeight: 600 }}
                      >
                        signing in
                      </Link>{' '}
                      instead.
                    </Alert>

                    <div className="text-center mt-4">
                      <Link
                        to="/login"
                        style={{
                          color: '#8A6BC1',
                          textDecoration: 'none',
                          fontWeight: 600,
                          fontFamily: 'Lora, serif',
                          fontSize: '15px',
                        }}
                      >
                        ← Back to Sign In
                      </Link>
                    </div>
                  </div>
                ) : (
                  <>
                    <Form onSubmit={handleSignup}>
                      <Form.Group className="mb-3" controlId="fullName">
                        <Form.Label>Full Name</Form.Label>
                        <Form.Control
                          type="text"
                          placeholder="Enter your full name"
                          value={fullName}
                          onChange={(e) => setFullName(e.target.value)}
                          required
                        />
                      </Form.Group>

                      <Form.Group className="mb-3" controlId="email">
                        <Form.Label>Email address</Form.Label>
                        <Form.Control
                          type="email"
                          placeholder="@dartmouth.edu"
                          value={email}
                          onChange={(e) => setEmail(e.target.value)}
                          required
                        />
                      </Form.Group>

                      <Form.Group className="mb-3" controlId="password">
                        <Form.Label>Password</Form.Label>
                        <Form.Control
                          type="password"
                          placeholder="Password"
                          value={password}
                          onChange={(e) => setPassword(e.target.value)}
                          required
                        />
                        <Form.Text className="text-muted">
                          Must be at least 6 characters
                        </Form.Text>
                      </Form.Group>

                      <Form.Group className="mb-3" controlId="confirmPassword">
                        <Form.Label>Confirm Password</Form.Label>
                        <Form.Control
                          type="password"
                          placeholder="Confirm password"
                          value={confirmPassword}
                          onChange={(e) => setConfirmPassword(e.target.value)}
                          required
                        />
                      </Form.Group>

                      <Button
                        variant="primary"
                        type="submit"
                        className="w-100"
                        disabled={loading}
                        style={{
                          background: 'linear-gradient(135deg, #8A6BC1 0%, #6B8FC7 100%)',
                          border: 'none',
                          padding: '12px',
                          fontWeight: 500,
                        }}
                      >
                        {loading ? 'Creating Account...' : 'Sign Up'}
                      </Button>
                    </Form>

                    <p className="text-center mt-3 mb-0">
                      Already have an account?{' '}
                      <Link
                        to="/login"
                        style={{ color: '#8A6BC1', textDecoration: 'none', fontWeight: 500 }}
                      >
                        Sign In
                      </Link>
                    </p>
                  </>
                )}
              </Card.Body>
            </Card>
          </div>
        </div>
      </Container>
    </div>
  );
}

export default Signup;
