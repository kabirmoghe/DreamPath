import React, { useState, useEffect } from 'react';
import { Form, Button, Card, ProgressBar, Container, Row, Col } from 'react-bootstrap';
import './ModernStudentForm.css';

function ModernStudentForm({ majors, onSubmit }) {
  // Form state
  const [formData, setFormData] = useState({
    major: '',
    collegeInterests: '',
    postGradGoal: '',
    longTermGoal: ''
  });
  const [currentStep, setCurrentStep] = useState(1);
  const totalSteps = 5; // 5 steps including summary
  const [loading, setLoading] = useState(false);
  
  // Major selection state
  const [searchTerm, setSearchTerm] = useState('');
  const [filteredMajors, setFilteredMajors] = useState([]);
  const [selectedMajor, setSelectedMajor] = useState('');

  // Update filtered majors when search term changes
  useEffect(() => {
    if (searchTerm.trim() === '') {
      // Show no majors when search is empty
      setFilteredMajors([]);
    } else {
      // Filter majors based on search term and limit to 5 results
      const filtered = majors
        .filter(major => major.toLowerCase().includes(searchTerm.toLowerCase()))
        .slice(0, 5); // Limit to 5 results
      setFilteredMajors(filtered);
    }
  }, [searchTerm, majors]);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData(prevData => ({
      ...prevData,
      [name]: value
    }));
  };

  const handleMajorSelect = (major) => {
    // Just select the major, don't advance to next step yet
    setSelectedMajor(major);
    setFormData(prevData => ({
      ...prevData,
      major: major
    }));
  };

  const nextStep = (e) => {
    if (e && e.preventDefault) {
      e.preventDefault();
    }
    setCurrentStep(prev => Math.min(prev + 1, totalSteps));
  };

  const prevStep = () => {
    setCurrentStep(prev => Math.max(prev - 1, 1));
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (isStepValid()) {
        nextStep();
      }
    }
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    if (currentStep === 5) {
      setLoading(true);
      onSubmit(formData);
    } else {
      nextStep();
    }
  };

  const isStepValid = () => {
    switch (currentStep) {
      case 1:
        return formData.major !== '';
      case 2:
        return formData.collegeInterests !== '';
      case 3:
        return formData.postGradGoal !== '';
      case 4:
        return formData.longTermGoal !== '';
      case 5:
        return true; // Summary page is always valid
      default:
        return false;
    }
  };

  // Render the major selection step
  const renderMajorTiles = () => (
    <div className="major-selection">
      <h3 className="text-center form-question mb-4">What's your major?</h3>
      
      <div className="search-container mb-4">
        <Form.Control
          type="text"
          placeholder="Type to find your major..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          className="major-search-input"
          autoFocus
        />
      </div>
      
      <div className="major-cloud-container">
        {filteredMajors.length > 0 && (
          <div className="major-results-group">
            {filteredMajors.map(major => (
              <div 
                key={major} 
                className={`major-cloud-tile ${formData.major === major ? 'selected' : ''}`}
                onClick={() => handleMajorSelect(major)}
              >
                {major}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );

  // Render the appropriate step content
  const renderStepContent = () => {
    switch (currentStep) {
      case 1:
        return renderMajorTiles();
      case 2:
        return (
          <div className="form-step">
            <h3 className="text-center form-question">What interests you (in {formData.major} and beyond)?</h3>
            <Form.Control
              as="textarea"
              rows={4}
              name="collegeInterests"
              value={formData.collegeInterests}
              onChange={handleChange}
              onKeyDown={handleKeyDown}
              placeholder="e.g., cybersecurity, cloud computing, artificial intelligence"
              className="modern-input"
              required
            />
          </div>
        );
      case 3:
        return (
          <div className="form-step">
            <h3 className="text-center form-question">What are your post-graduation goals?</h3>
            <Form.Control
              as="textarea"
              rows={4}
              name="postGradGoal"
              value={formData.postGradGoal}
              onChange={handleChange}
              onKeyDown={handleKeyDown}
              placeholder="e.g., data scientist and machine learning engineer"
              className="modern-input"
              required
            />
          </div>
        );
      case 4:
        return (
          <div className="form-step">
            <h3 className="text-center form-question">What are your long-term career aspirations?</h3>
            <Form.Control
              as="textarea"
              rows={4}
              name="longTermGoal"
              value={formData.longTermGoal}
              onChange={handleChange}
              onKeyDown={handleKeyDown}
              placeholder="e.g., CTO of a tech company, research scientist, entrepreneur"
              className="modern-input"
              required
            />
          </div>
        );
      case 5:
        return (
          <div className="summary-step">
            <h3 className="text-center form-question">Review Your Information</h3>
            <div className="summary-box">
              <p><strong>Major:</strong> {formData.major}</p>
              <p><strong>Interests:</strong> {formData.collegeInterests}</p>
              <p><strong>Post-Graduation Goals:</strong> {formData.postGradGoal}</p>
              <p><strong>Long-Term Aspirations:</strong> {formData.longTermGoal}</p>
            </div>
          </div>
        );
      default:
        return null;
    }
  };

  // Calculate progress percentage
  const progressPercentage = (currentStep / totalSteps) * 100;

  return (
    <Container className="modern-form-container">
      <Card className="modern-form-card">
        <Card.Body>
          <div className="progress-container mb-4">
            <ProgressBar 
              now={progressPercentage} 
              className="modern-progress"
            />
            <div className="step-indicator">Step {currentStep} of {totalSteps}</div>
          </div>
          
          <Form onSubmit={handleSubmit}>
            <div className="step-content">
              {renderStepContent()}
            </div>
            
            <div className="d-flex justify-content-between mt-4">
              {currentStep > 1 && (
                <Button 
                  variant="outline-secondary" 
                  onClick={prevStep}
                  className="modern-btn-back"
                >
                  Back
                </Button>
              )}
              
              {currentStep < 5 ? (
                <Button 
                  variant="primary" 
                  onClick={nextStep}
                  disabled={!isStepValid()}
                  className="modern-btn-next ms-auto"
                >
                  Next
                </Button>
              ) : (
                <Button 
                  variant="success" 
                  type="submit"
                  className="modern-btn-submit ms-auto"
                  disabled={loading}
                >
                  {loading ? 'Submitting...' : 'Build DreamPath'}
                </Button>
              )}
            </div>
          </Form>
        </Card.Body>
      </Card>
    </Container>
  );
}

export default ModernStudentForm; 