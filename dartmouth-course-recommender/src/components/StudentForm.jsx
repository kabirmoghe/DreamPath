import React, { useState } from 'react';
import { Form, Button, Card, ProgressBar } from 'react-bootstrap';

function StudentForm({ majors, onSubmit }) {
  const [formData, setFormData] = useState({
    major: '',
    collegeInterests: '',
    postGradGoal: '',
    longTermGoal: ''
  });

  const [currentStep, setCurrentStep] = useState(1);
  const totalSteps = 5; // 5 steps including summary

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData(prevData => ({
      ...prevData,
      [name]: value
    }));
  };

  const nextStep = (e) => {
    // If this was triggered by an event, prevent default behavior
    if (e && e.preventDefault) {
      e.preventDefault();
    }
    setCurrentStep(prev => Math.min(prev + 1, totalSteps));
  };

  const prevStep = () => {
    setCurrentStep(prev => Math.max(prev - 1, 1));
  };

  const handleKeyDown = (e) => {
    // Prevent form submission when pressing Enter in text fields
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (isStepValid()) {
        nextStep();
      }
    }
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    // Only submit if we're on the summary page (step 5)
    if (currentStep === 5) {
      onSubmit(formData);
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

  const renderStepContent = () => {
    switch (currentStep) {
      case 1:
        return (
          <Form.Group className="mb-4">
            <h3 className="text-center form-question">What's your major?</h3>
            <Form.Select 
              name="major" 
              value={formData.major} 
              onChange={handleChange}
              className="form-control-lg"
              required
            >
              <option value="">Select Major</option>
              {majors.map(major => (
                <option key={major} value={major}>{major}</option>
              ))}
            </Form.Select>
          </Form.Group>
        );
      case 2:
        return (
          <Form.Group className="mb-4">
            <h3 className="text-center form-question">What interests you (in {formData.major} and beyond)?</h3>
            <Form.Control
              as="textarea"
              rows={4}
              name="collegeInterests"
              value={formData.collegeInterests}
              onChange={handleChange}
              placeholder="e.g., cybersecurity, cloud computing, artificial intelligence"
              className="form-control-lg"
              required
            />
          </Form.Group>
        );
      case 3:
        return (
          <Form.Group className="mb-4">
            <h3 className="text-center form-question">What are your post-graduation goals?</h3>
            <Form.Control
              as="textarea"
              rows={4}
              name="postGradGoal"
              value={formData.postGradGoal}
              onChange={handleChange}
              placeholder="e.g., data scientist and machine learning engineer"
              className="form-control-lg"
              required
            />
          </Form.Group>
        );
      case 4:
        return (
          <Form.Group className="mb-4">
            <h3 className="text-center form-question">What are your long-term career aspirations?</h3>
            <Form.Control
              as="textarea"
              rows={4}
              name="longTermGoal"
              value={formData.longTermGoal}
              onChange={handleChange}
              onKeyDown={handleKeyDown}
              placeholder="e.g., Lead the development of ethical, large-scale AI systems"
              className="form-control-lg"
              required
            />
          </Form.Group>
        );
      case 5:
        return (
          <>
            <h3 className="mb-4 text-center">Summary</h3>
            <div className="summary-box p-4 mb-4 bg-light rounded">
              <p><strong>Major:</strong> {formData.major}</p>
              <p><strong>Interests:</strong> {formData.collegeInterests}</p>
              <p><strong>Post-Graduation:</strong> {formData.postGradGoal}</p>
              <p><strong>Long-Term Aspirations:</strong> {formData.longTermGoal}</p>
            </div>
            <p className="text-center text-muted small">Review your information above and click "Find My Courses" when ready.</p>
          </>
        );
      default:
        return null;
    }
  };

  return (
    <Card className="form-card">
      <Card.Header as="h5">
        <div className="d-flex justify-content-between align-items-center">
          <span className="card-header-title"><span className="dream-text">Your DreamPath</span></span>
          <span className="badge bg-light text-dark">Step {currentStep} of {totalSteps}</span>
        </div>
      </Card.Header>
      <Card.Body>
        <ProgressBar 
          now={(currentStep / totalSteps) * 100} 
          className="mb-4"
        />
        
        <Form onSubmit={handleSubmit}>
          {renderStepContent()}
          
          <div className="d-flex justify-content-between mt-4">
            {currentStep > 1 && (
              <Button 
                variant="outline-secondary" 
                onClick={prevStep}
              >
                Back
              </Button>
            )}
            
            {currentStep < totalSteps ? (
              <Button 
                variant="primary" 
                onClick={(e) => nextStep(e)}
                disabled={!isStepValid()}
                className={currentStep === 1 ? "ms-auto" : ""}
                type="button"
              >
                Next
              </Button>
            ) : (
              <Button 
                variant="dartmouth" 
                type="submit"
                className="ms-auto"
              >
                Build DreamPath
              </Button>
            )}
          </div>
        </Form>
      </Card.Body>
    </Card>
  );
}

export default StudentForm; 