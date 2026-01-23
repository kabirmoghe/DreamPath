import React, { useState } from 'react';
import { Container, Form, Button, Card, Alert } from 'react-bootstrap';
import { useNavigate, Link } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import 'bootstrap/dist/css/bootstrap.min.css';

/**
 * Login - User authentication component
 *
 * Uses AuthContext for localStorage-based authentication
 */
function Login() {
  const navigate = useNavigate();
  const { signIn } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleLogin = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const { user, error } = await signIn(email, password);

      if (error) {
        setError(error);
      } else if (user) {
        navigate('/dashboard');
      }
    } catch (err) {
      setError(err.message || 'Failed to sign in');
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
          <div className="col-md-6 col-lg-4">
            <Card
              style={{
                border: 'none',
                borderRadius: 16,
                boxShadow: '0 10px 40px rgba(0, 0, 0, 0.15)',
              }}
            >
              <Card.Body style={{ padding: '2rem' }}>
                <div className="text-center mb-4">
                  <h2
                    style={{
                      fontFamily: 'Lora, serif',
                      fontWeight: 400,
                      color: '#333',
                    }}
                  >
                    DreamPath
                  </h2>
                  <p className="text-muted">Sign in to your account</p>
                </div>

                {error && <Alert variant="danger">{error}</Alert>}

                <Form onSubmit={handleLogin}>
                  <Form.Group className="mb-3">
                    <Form.Label style={{ fontWeight: 400 }}>Email</Form.Label>
                    <Form.Control
                      type="email"
                      placeholder="@dartmouth.edu"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      required
                      style={{
                        borderRadius: 8,
                        border: '1px solid #d6cdea',
                        padding: '10px 14px',
                      }}
                    />
                  </Form.Group>

                  <Form.Group className="mb-3">
                    <Form.Label style={{ fontWeight: 400 }}>Password</Form.Label>
                    <Form.Control
                      type="password"
                      placeholder="Enter your password"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      required
                      style={{
                        borderRadius: 8,
                        border: '1px solid #d6cdea',
                        padding: '10px 14px',
                      }}
                    />
                  </Form.Group>

                  <Button
                    type="submit"
                    disabled={loading}
                    style={{
                      width: '100%',
                      padding: '12px',
                      borderRadius: 8,
                      background: 'linear-gradient(135deg, #8A6BC1 0%, #6B8FC7 100%)',
                      border: 'none',
                      fontWeight: 500,
                    }}
                  >
                    {loading ? 'Signing in...' : 'Sign In'}
                  </Button>
                </Form>

                <div className="text-center mt-3">
                  <p className="text-muted small">
                    Don't have an account?{' '}
                    <Link
                      to="/signup"
                      style={{ color: '#8A6BC1', textDecoration: 'none' }}
                    >
                      Sign up
                    </Link>
                  </p>
                </div>
              </Card.Body>
            </Card>
          </div>
        </div>
      </Container>
    </div>
  );
}

export default Login;
