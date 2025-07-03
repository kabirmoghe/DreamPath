import React, { useState } from 'react';
import { Modal, Button, Form, Row, Col, Card } from 'react-bootstrap';
import { Gear, X } from 'react-bootstrap-icons';

const ParameterWeightsSettings = ({ show, onHide, onSave, currentWeights }) => {
  const [courseWeights, setCourseWeights] = useState({
    college_interests: currentWeights?.course_parameter_weights?.college_interests || 1.0,
    post_grad_goal: currentWeights?.course_parameter_weights?.post_grad_goal || 1.0,
    long_term_goal: currentWeights?.course_parameter_weights?.long_term_goal || 0.5
  });

  const [clubWeights, setClubWeights] = useState({
    college_interests: currentWeights?.club_parameter_weights?.college_interests || 1.0,
    post_grad_goal: currentWeights?.club_parameter_weights?.post_grad_goal || 1.0,
    long_term_goal: currentWeights?.club_parameter_weights?.long_term_goal || 0.5
  });

  // Validation functions
  const validateWeights = (weights) => {
    return Object.values(weights).some(weight => weight > 0);
  };

  const isCourseWeightsValid = validateWeights(courseWeights);
  const isClubWeightsValid = validateWeights(clubWeights);
  const isFormValid = isCourseWeightsValid && isClubWeightsValid;

  const handleCourseWeightChange = (parameter, value) => {
    setCourseWeights(prev => ({
      ...prev,
      [parameter]: parseFloat(value)
    }));
  };

  const handleClubWeightChange = (parameter, value) => {
    setClubWeights(prev => ({
      ...prev,
      [parameter]: parseFloat(value)
    }));
  };

  const handleSave = () => {
    if (!isFormValid) {
      return; // Prevent save if validation fails
    }
    onSave({
      course_parameter_weights: courseWeights,
      club_parameter_weights: clubWeights
    });
    onHide();
  };

  const handleReset = () => {
    setCourseWeights({
      college_interests: 1.0,
      post_grad_goal: 1.0,
      long_term_goal: 0.5
    });
    setClubWeights({
      college_interests: 1.0,
      post_grad_goal: 1.0,
      long_term_goal: 0.5
    });
  };

  const formatParameterName = (parameter) => {
    switch (parameter) {
      case 'college_interests':
        return 'College Interests';
      case 'post_grad_goal':
        return 'Post-Grad Goal';
      case 'long_term_goal':
        return 'Long-Term Goal';
      default:
        return parameter;
    }
  };

  const getWeightColor = (weight) => {
    if (weight === 0) return '#e9ecef';
    if (weight <= 0.3) return '#ff6b6b';
    if (weight <= 0.6) return '#ffd93d';
    return '#6bcf7f';
  };

  return (
    <Modal show={show} onHide={onHide} size="lg" centered>
      <Modal.Header style={{ borderBottom: '1px solid #e9ecef', background: '#f8f9fa' }}>
        <Modal.Title className="d-flex align-items-center">
          <Gear className="me-2" />
          Recommendation Settings
        </Modal.Title>
        <Button variant="link" onClick={onHide} className="p-0 ms-auto">
          <X size={20} />
        </Button>
      </Modal.Header>
      
      <Modal.Body className="p-4">
        <div className="mb-4">
          <p className="text-muted mb-3">
            Adjust the importance of each parameter for course and club recommendations. 
            Higher weights mean that parameter will have more influence on your recommendations.
          </p>
        </div>

        <Row>
          {/* Course Weights */}
          <Col md={6}>
            <Card className="h-100" style={{ 
              border: isCourseWeightsValid ? '1px solid #e9ecef' : '1px solid #dc3545',
              borderRadius: 12 
            }}>
              <Card.Header style={{ 
                background: isCourseWeightsValid 
                  ? 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)' 
                  : 'linear-gradient(135deg, #dc3545 0%, #c82333 100%)',
                color: 'white', 
                border: 'none', 
                borderRadius: '7px 7px 0 0' 
              }}>
                <div className="d-flex justify-content-between align-items-center">
                  <h5 className="mb-0">Course Recommendations</h5>
                  {!isCourseWeightsValid && (
                    <span className="badge bg-light text-danger" style={{ fontSize: '10px' }}>
                      Invalid
                    </span>
                  )}
                </div>
              </Card.Header>
              <Card.Body className="p-3">
                {Object.entries(courseWeights).map(([parameter, weight]) => (
                  <div key={parameter} className="mb-3">
                    <div className="d-flex justify-content-between align-items-center mb-2">
                      <label className="form-label mb-0" style={{ fontSize: '14px', fontWeight: 500 }}>
                        {formatParameterName(parameter)}
                      </label>
                      <span 
                        className="badge" 
                        style={{ 
                          backgroundColor: getWeightColor(weight),
                          color: weight === 0 ? '#6c757d' : 'white',
                          fontSize: '12px',
                          padding: '4px 8px'
                        }}
                      >
                        {weight.toFixed(1)}
                      </span>
                    </div>
                    <Form.Range
                      min="0"
                      max="1"
                      step="0.1"
                      value={weight}
                      onChange={(e) => handleCourseWeightChange(parameter, e.target.value)}
                      style={{
                        '--bs-range-thumb-bg': getWeightColor(weight),
                        '--bs-range-track-bg': '#e9ecef'
                      }}
                    />
                  </div>
                ))}
                {!isCourseWeightsValid && (
                  <div className="text-danger mt-2" style={{ fontSize: '12px' }}>
                    ⚠️ At least one parameter must be greater than 0
                  </div>
                )}
              </Card.Body>
            </Card>
          </Col>

          {/* Club Weights */}
          <Col md={6}>
            <Card className="h-100" style={{ 
              border: isClubWeightsValid ? '1px solid #e9ecef' : '1px solid #dc3545',
              borderRadius: 7
            }}>
              <Card.Header style={{ 
                background: isClubWeightsValid 
                  ? 'linear-gradient(135deg,rgb(91, 193, 133) 0%,rgb(47, 154, 102) 100%)' 
                  : 'linear-gradient(135deg, #dc3545 0%, #c82333 100%)',
                color: 'white', 
                border: 'none', 
                borderRadius: '7px 7px 0 0' 
              }}>
                <div className="d-flex justify-content-between align-items-center">
                  <h5 className="mb-0">Club Recommendations</h5>
                  {!isClubWeightsValid && (
                    <span className="badge bg-light text-danger" style={{ fontSize: '10px' }}>
                      Invalid
                    </span>
                  )}
                </div>
              </Card.Header>
              <Card.Body className="p-3">
                {Object.entries(clubWeights).map(([parameter, weight]) => (
                  <div key={parameter} className="mb-3">
                    <div className="d-flex justify-content-between align-items-center mb-2">
                      <label className="form-label mb-0" style={{ fontSize: '14px', fontWeight: 500 }}>
                        {formatParameterName(parameter)}
                      </label>
                      <span 
                        className="badge" 
                        style={{ 
                          backgroundColor: getWeightColor(weight),
                          color: weight === 0 ? '#6c757d' : 'white',
                          fontSize: '12px',
                          padding: '4px 8px'
                        }}
                      >
                        {weight.toFixed(1)}
                      </span>
                    </div>
                    <Form.Range
                      min="0"
                      max="1"
                      step="0.1"
                      value={weight}
                      onChange={(e) => handleClubWeightChange(parameter, e.target.value)}
                      style={{
                        '--bs-range-thumb-bg': getWeightColor(weight),
                        '--bs-range-track-bg': '#e9ecef'
                      }}
                    />
                  </div>
                ))}
                {!isClubWeightsValid && (
                  <div className="text-danger mt-2" style={{ fontSize: '12px' }}>
                    ⚠️ At least one parameter must be greater than 0
                  </div>
                )}
              </Card.Body>
            </Card>
          </Col>
        </Row>
      </Modal.Body>

      <Modal.Footer style={{ borderTop: '1px solid #e9ecef', background: '#f8f9fa' }}>
        {!isFormValid && (
          <div className="text-danger me-auto" style={{ fontSize: '12px' }}>
            ⚠️ Please ensure at least one parameter is greater than 0 for both courses and clubs
          </div>
        )}
        <Button variant="outline-secondary" onClick={handleReset}>
          Reset to Defaults
        </Button>
        <div className="ms-auto">
          <Button variant="secondary" onClick={onHide} className="me-2">
            Cancel
          </Button>
          <Button 
            variant="primary" 
            onClick={handleSave}
            disabled={!isFormValid}
            style={{ 
              opacity: isFormValid ? 1 : 0.6,
              cursor: isFormValid ? 'pointer' : 'not-allowed'
            }}
          >
            Save Settings
          </Button>
        </div>
      </Modal.Footer>
    </Modal>
  );
};

export default ParameterWeightsSettings; 