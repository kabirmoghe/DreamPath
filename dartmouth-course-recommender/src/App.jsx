import React, { useState, useEffect } from 'react';
import { Container, Row, Col } from 'react-bootstrap';
import 'bootstrap/dist/css/bootstrap.min.css';
import './App.css';
import StudentForm from './components/StudentForm';
import CourseRecommendations from './components/CourseRecommendations';
import LoadingSpinner from './components/LoadingSpinner';
import axios from 'axios';

function App() {
  const [majors, setMajors] = useState([]);
  const [recommendations, setRecommendations] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    // Fetch available majors when component mounts
    axios.get('http://localhost:5001/api/majors')
      .then(response => {
        setMajors(response.data);
      })
      .catch(err => {
        setError('Failed to load majors. Please try again later.');
        console.error('Error fetching majors:', err);
      });
  }, []);

  const handleSubmit = async (formData) => {
    setLoading(true);
    setError(null);
    setRecommendations([]);
    
    try {
      const response = await axios.post('http://localhost:5001/api/recommendations', formData);
      
      // Parse the response if it's a string
      let parsedRecommendations = response.data;
      if (typeof response.data === 'string') {
        try {
          parsedRecommendations = JSON.parse(response.data);
        } catch (parseError) {
          setError('Failed to parse recommendations data.');
          setLoading(false);
          return;
        }
      }
      
      setRecommendations(parsedRecommendations);
    } catch (err) {
      console.error('Error fetching recommendations:', err);
      setError('Failed to generate recommendations. Please try again later.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Container fluid className="app-container">
      <Row className="header">
        <Col>
          <h1><span className="dartmouth-text">Dartmouth</span> <span className="dream-text">DreamPath</span></h1>
          <p className="lead">
          Plan smarter. Graduate with purpose.
          </p>
        </Col>
      </Row>
      
      <Row>
        <Col md={4}>
          <StudentForm majors={majors} onSubmit={handleSubmit} />
        </Col>
        <Col md={8}>
          {loading ? (
            <LoadingSpinner message="Generating course recommendations..." />
          ) : error ? (
            <div className="error-message">{error}</div>
          ) : recommendations.majorRecommendations ? (
            <CourseRecommendations recommendations={recommendations} />
          ) : (
            <div className="placeholder-message">
              <p>
                Get a personalized course plan based on your interests and goals.
              </p>
              <div className="steps">
                <div className="step">
                  <div className="step-number">1</div>
                  <div className="step-text">Select your major and areas of interest</div>
                </div>
                <div className="step">
                  <div className="step-number">2</div>
                  <div className="step-text">Tell us about your goals</div>
                </div>
                <div className="step">
                  <div className="step-number">3</div>
                  <div className="step-text">Build your DreamPath</div>
                </div>
              </div>
            </div>
          )}
        </Col>
      </Row>
    </Container>
  );
}

export default App; 