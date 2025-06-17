import React, { useState, useEffect } from 'react';
import { Container, Row, Col, Card, Form, Button, Alert } from 'react-bootstrap';
import { useNavigate } from 'react-router-dom';
import { supabase } from '../lib/supabase';

const CreateDetailedProfile = () => {
  const navigate = useNavigate();
  const [form, setForm] = useState({
    major: '',
    college_interests: '',
    post_grad_goal: '',
    long_term_goal: '',
    graduationYear: new Date().getFullYear() + 4
  });
  const [majors, setMajors] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);

  useEffect(() => {
    // Fetch available majors
    fetch('http://localhost:5001/api/majors')
      .then(response => response.json())
      .then(data => setMajors(data))
      .catch(error => {
        console.error('Error fetching majors:', error);
        setError('Failed to load majors. Please try again later.');
      });
  }, []);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setForm(prev => ({
      ...prev,
      [name]: value
    }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSuccess('');
    setLoading(true);

    const { data: { user } } = await supabase.auth.getUser();
    if (!user) {
      setError('Not logged in');
      setLoading(false);
      return;
    }

    // Just insert, no need to check for existence
    const { error } = await supabase.from('detailed_profiles').insert([{
      user_id: user.id,
      major: form.major,
      college_interests: form.college_interests,
      post_grad_goal: form.post_grad_goal,
      long_term_goal: form.long_term_goal
    }]);

    if (error) {
      setError(error.message);
    } else {
      setSuccess('Profile saved!');
      setTimeout(() => navigate('/dashboard'), 1000);
    }
    setLoading(false);
  };

  return (
    <Container className="py-5">
      <Row className="justify-content-center">
        <Col md={8} lg={6}>
          <Card className="shadow-sm">
            <Card.Body className="p-4 p-md-5">
              <div className="text-center mb-4">
                <h1 className="h3 mb-3" style={{ fontFamily: 'Lora, serif' }}>Complete Your Profile</h1>
                <p className="text-muted">Tell us about yourself to get personalized recommendations</p>
              </div>

              {error && (
                <Alert variant="danger" className="mb-4">
                  {error}
                </Alert>
              )}

              {success && (
                <Alert variant="success" className="mb-4">
                  {success}
                </Alert>
              )}

              <Form onSubmit={handleSubmit}>
                <Form.Group className="mb-3">
                  <Form.Label>Major</Form.Label>
                  <Form.Select
                    name="major"
                    value={form.major}
                    onChange={handleChange}
                    required
                  >
                    <option value="">Select your major</option>
                    {majors.map(major => (
                      <option key={major} value={major}>
                        {major}
                      </option>
                    ))}
                  </Form.Select>
                </Form.Group>

                <Form.Group className="mb-3">
                  <Form.Label>Interests</Form.Label>
                  <Form.Control
                    as="textarea"
                    name="college_interests"
                    value={form.college_interests}
                    onChange={handleChange}
                    required
                    placeholder="Tell us about your interests and hobbies"
                    rows={3}
                  />
                </Form.Group>

                <Form.Group className="mb-3">
                  <Form.Label>Post-Grad Goal</Form.Label>
                  <Form.Control
                    type="text"
                    name="post_grad_goal"
                    value={form.post_grad_goal}
                    onChange={handleChange}
                    required
                  />
                </Form.Group>

                <Form.Group className="mb-3">
                  <Form.Label>Long-Term Goal</Form.Label>
                  <Form.Control
                    type="text"
                    name="long_term_goal"
                    value={form.long_term_goal}
                    onChange={handleChange}
                    required
                  />
                </Form.Group>

                <Form.Group className="mb-4">
                  <Form.Label>Expected Graduation Year</Form.Label>
                  <Form.Control
                    type="number"
                    name="graduationYear"
                    value={form.graduationYear}
                    onChange={handleChange}
                    required
                    min={new Date().getFullYear()}
                    max={new Date().getFullYear() + 8}
                  />
                </Form.Group>

                <Button
                  variant="primary"
                  type="submit"
                  className="w-100"
                  disabled={loading}
                >
                  {loading ? 'Saving...' : 'Complete Profile'}
                </Button>
              </Form>
            </Card.Body>
          </Card>
        </Col>
      </Row>
    </Container>
  );
}

export default CreateDetailedProfile; 