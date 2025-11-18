import React, { useState, useEffect } from 'react';
import { Container, Form, Button, Card, ProgressBar, Alert } from 'react-bootstrap';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { apiClient } from '../lib/api';
import InitLoadingOverlay from './InitLoadingOverlay';
import 'bootstrap/dist/css/bootstrap.min.css';

// Custom styles for enhanced onboarding wizard
const onboardingStyles = `
  .custom-progress-bar .progress-bar {
    background-color: #00693E !important;
    transition: width 0.4s ease;
  }

  .onboarding-card {
    backdrop-filter: blur(10px);
    background: rgba(255, 255, 255, 0.98) !important;
  }

  .question-title {
    font-size: 20px;
    font-weight: 500;
    line-height: 1.3;
    color: #00693E;
    margin-bottom: 5px;
  }

  .question-description {
    color: #7a7a7a;
    font-size: 14px;
    line-height: 1.6;
  }

  .step-indicator {
    font-family: 'Lora', serif;
    font-size: 13px;
    color: #666;
    text-align: center;
    margin-top: 8px;
    font-weight: 400;
  }
  .profile-text-input {
    borderRadius: 10,
    border: '2px solid #e8e0f5',
    padding: '14px 16px',
    fontSize: '15px',
    lineHeight: '1.6'
  }

  .profile-text-input::placeholder {
    color:rgb(160, 155, 171) !important;
    font-style: italic;
  }

  .helper-text {
    color: #7a7a7a;
    font-size: 14px;
    line-height: 1.6;
    text-align: center;
  }

  .form-control:focus, .form-select:focus {
    border-color: #8A6BC1 !important;
    box-shadow: 0 0 0 0.2rem rgba(138, 107, 193, 0.15) !important;
  }

  .major-input {
    font-family: 'Lora', serif !important;
    color: #8A6BC1 !important;
  }

  .major-input::placeholder {
    color: #d6cdea !important;
    font-family: 'Lora', serif !important;
  }

  .autocomplete-dropdown {
    position: absolute;
    top: 100%;
    left: 0;
    right: 0;
    background: white;
    border: 2px solid #e8e0f5;
    border-top: none;
    border-radius: 0 0 10px 10px;
    max-height: 250px;
    overflow-y: auto;
    z-index: 1000;
    box-shadow: 0 4px 12px rgba(138, 107, 193, 0.15);
  }

  .autocomplete-item {
    padding: 12px 16px;
    cursor: pointer;
    font-family: 'Lora', serif;
    color: #444;
    font-size: 15px;
    transition: all 0.2s ease;
    border-bottom: 1px solid #f5f0fa;
  }

  .autocomplete-item:last-child {
    border-bottom: none;
  }

  .autocomplete-item:hover {
    background: linear-gradient(135deg, #f8f6fb 0%, #f5f8fc 100%);
    color: #8A6BC1;
  }

  .autocomplete-item.selected {
    background: linear-gradient(135deg, #8A6BC1 0%, #6B8FC7 100%);
    color: white;
  }

  .autocomplete-empty {
    padding: 12px 16px;
    color: #999;
    font-style: italic;
    font-size: 14px;
    text-align: center;
  }

  .review-section {
    background: linear-gradient(135deg, #f8f6fb 0%, #f5f8fc 100%);
    padding: 24px;
    border-radius: 12px;
    border: 1px solid #e8e0f5;
  }

  .review-label {
    font-family: 'Lora', serif;
    font-size: 16px;
    font-weight: 600;
    color: #6A4C93;
    margin-bottom: 8px;
  }

  .review-content {
    color: #444;
    font-size: 15px;
    line-height: 1.6;
    margin-bottom: 0;
  }
`;

/**
 * Onboarding - Multi-step wizard for new users
 *
 * Collects profile information and triggers course path initialization
 * Steps: Major → Interests → Post-grad Goals → Career Goals → Review
 */
function Onboarding() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [currentStep, setCurrentStep] = useState(1);
  const [isInitializing, setIsInitializing] = useState(false);
  const [initStatus, setInitStatus] = useState(null);
  const [error, setError] = useState('');
  const [majors, setMajors] = useState([]);
  const [loadingMajors, setLoadingMajors] = useState(true);

  // Autocomplete state
  const [majorInputValue, setMajorInputValue] = useState('');
  const [showMajorDropdown, setShowMajorDropdown] = useState(false);
  const [filteredMajors, setFilteredMajors] = useState([]);

  // Form data
  const [formData, setFormData] = useState({
    major: '',
    interests: '',
    postGradGoals: '',
    careerGoals: '',
  });

  // Check if user already has a profile - redirect to dashboard if so
  // Use ref to ensure this only runs once
  const profileChecked = React.useRef(false);

  useEffect(() => {
    const checkProfile = async () => {
      if (!user?.id || profileChecked.current) return;

      profileChecked.current = true;

      try {
        const profile = await apiClient.getProfile(String(user.id));
        if (profile) {
          // User already has profile, redirect to dashboard
          navigate('/dashboard');
        }
      } catch (err) {
        // Profile doesn't exist, that's fine - user should complete onboarding
        console.log('No existing profile, continuing with onboarding');
      }
    };

    checkProfile();
  }, [user?.id, navigate]);

  // Fetch majors from backend on mount
  useEffect(() => {
    const fetchMajors = async () => {
      try {
        const majorsList = await apiClient.getMajors();
        // Extract just the major names
        const majorNames = majorsList.map(m => m.major);
        setMajors(majorNames);
        setLoadingMajors(false);
      } catch (err) {
        console.error('Failed to fetch majors:', err);
        // Fallback to basic list if fetch fails
        setMajors([
          'Computer Science',
          'Economics',
          'Mathematics',
          'Engineering',
          'Biology',
          'Psychology',
          'Other',
        ]);
        setLoadingMajors(false);
      }
    };

    fetchMajors();
  }, []);

  // Filter majors based on input
  useEffect(() => {
    if (majorInputValue.trim() === '') {
      setFilteredMajors(majors);
    } else {
      const filtered = majors.filter(major =>
        major.toLowerCase().includes(majorInputValue.toLowerCase())
      );
      setFilteredMajors(filtered);
    }
  }, [majorInputValue, majors]);

  // Handle major selection
  const handleMajorSelect = (major) => {
    setFormData({ ...formData, major });
    setMajorInputValue(major);
    setShowMajorDropdown(false);
  };

  // Handle major input change
  const handleMajorInputChange = (e) => {
    const value = e.target.value;
    setMajorInputValue(value);
    setFormData({ ...formData, major: value });
    setShowMajorDropdown(true);
  };

  const totalSteps = 5;
  const progress = (currentStep / totalSteps) * 100;

  const handleNext = () => {
    // Validation
    if (currentStep === 1 && !formData.major) {
      setError('Please select your major');
      return;
    }
    if (currentStep === 2 && !formData.interests.trim()) {
      setError('Please enter your college interests');
      return;
    }
    if (currentStep === 3 && !formData.postGradGoals.trim()) {
      setError('Please enter your post-graduation goals');
      return;
    }
    if (currentStep === 4 && !formData.careerGoals.trim()) {
      setError('Please enter your career goals');
      return;
    }

    setError('');
    setCurrentStep(currentStep + 1);
  };

  const handleBack = () => {
    setError('');
    setCurrentStep(currentStep - 1);
  };

  const handleBuildDreamPath = async () => {
    setError('');

    if (!user?.id) {
      setError('User not authenticated');
      return;
    }

    try {
      // 1. Save profile to backend - WAITS for completion
      console.log('Creating profile...');
      await apiClient.createProfile({
        user_id: String(user.id),
        name: user.user_metadata?.full_name || user.email?.split('@')[0] || 'Student',
        major: formData.major,
        college_interests: formData.interests,
        post_grad_goals: formData.postGradGoals,
        career_goals: formData.careerGoals,
      });
      console.log('Profile created successfully');

      // 2. Show loading overlay (only after profile saved)
      setIsInitializing(true);

      // 3. Stream init via /init endpoint (only after steps 1 & 2)
      console.log('Starting init stream...');
      let capturedThreadId = null;

      for await (const chunk of apiClient.initCoursePath(String(user.id))) {
        console.log('Init chunk received:', chunk);

        // Capture thread_id when it arrives
        if (chunk.type === 'thread_id') {
          capturedThreadId = chunk.thread_id;
          console.log('Captured thread_id:', capturedThreadId);
        } else if (chunk.custom_data?.event_type === 'node_status') {
          setInitStatus(chunk.custom_data);
        }
      }
      console.log('Init stream complete');

      // 4. Set current thread ID in localStorage if we got a thread_id
      // (Thread was already created in database by the backend)
      if (capturedThreadId) {
        console.log('Setting current thread ID in localStorage:', capturedThreadId);
        apiClient.setCurrentThreadId(String(user.id), capturedThreadId);
        console.log('Current thread ID set successfully');
      }

      // 5. Hide overlay
      setIsInitializing(false);

      // 6. Success - redirect to dashboard
      console.log('Redirecting to dashboard...');
      navigate('/dashboard');
    } catch (err) {
      console.error('Init failed:', err);
      setError(err.message || 'Failed to build your DreamPath. Please try again.');
      setIsInitializing(false);
    }
  };

  const renderStep = () => {
    switch (currentStep) {
      case 1:
        return (
          <div>
            <h2 className="question-title" style={{ fontFamily: 'Lora, serif' }}>
              What's your major?
            </h2>
            <p className="question-description mb-4">
              Choose your primary field of study. This helps us tailor your academic journey.
            </p>
            <Form.Group style={{ position: 'relative' }}>
              <Form.Control
                type="text"
                size="lg"
                value={majorInputValue}
                onChange={handleMajorInputChange}
                onFocus={() => setShowMajorDropdown(true)}
                onBlur={() => setTimeout(() => setShowMajorDropdown(false), 200)}
                placeholder={loadingMajors ? 'Loading majors...' : 'ex. Government'}
                className="major-input"
                style={{
                  borderRadius: showMajorDropdown ? '10px 10px 0 0' : '10px',
                  border: '2px solid #e8e0f5',
                  padding: '14px 16px',
                  fontSize: '16px'
                }}
                disabled={loadingMajors}
              />
              {showMajorDropdown && filteredMajors.length > 0 && (
                <div className="autocomplete-dropdown">
                  {filteredMajors.map((major, index) => (
                    <div
                      key={`${major}-${index}`}
                      className="autocomplete-item"
                      onClick={() => handleMajorSelect(major)}
                    >
                      {major}
                    </div>
                  ))}
                </div>
              )}
              {showMajorDropdown && filteredMajors.length === 0 && majorInputValue.trim() !== '' && (
                <div className="autocomplete-dropdown">
                  <div className="autocomplete-empty">
                    No majors found matching "{majorInputValue}"
                  </div>
                </div>
              )}
            </Form.Group>
          </div>
        );

      case 2:
        return (
          <div>
            <h2 className="question-title" style={{ fontFamily: 'Lora, serif' }}>
              What are your college interests?
            </h2>
            <p className="question-description mb-4">
              Share your academic passions, clubs, activities, or areas you'd like to explore during your time here.
            </p>
            <Form.Group>
              <Form.Control
                as="textarea"
                rows={6}
                placeholder="e.g., Machine learning research, debate team, entrepreneurship, community service"
                value={formData.interests}
                onChange={(e) => setFormData({ ...formData, interests: e.target.value })}
                className="profile-text-input"
                style={{
                  borderRadius: 10,
                  border: '2px solid #e8e0f5',
                  padding: '14px 16px',
                  fontSize: '15px',
                  lineHeight: '1.6'
                }}
              />
              <Form.Text className="helper-text" style={{ marginTop: '8px', display: 'block' }}>
                💡 The more specific you are, the better we can personalize your journey
              </Form.Text>
            </Form.Group>
          </div>
        );

      case 3:
        return (
          <div>
            <h2 className="question-title" style={{ fontFamily: 'Lora, serif' }}>
              What are your post-graduation goals?
            </h2>
            <p className="question-description mb-4">
              Tell us what you envision for yourself after graduation. Your aspirations guide our recommendations.
            </p>
            <Form.Group>
              <Form.Control
                as="textarea"
                rows={6}
                placeholder="e.g., Pursue a PhD in computational biology, join a tech startup, attend medical school..."
                value={formData.postGradGoals}
                onChange={(e) => setFormData({ ...formData, postGradGoals: e.target.value })}
                style={{
                  borderRadius: 10,
                  border: '2px solid #e8e0f5',
                  padding: '14px 16px',
                  fontSize: '15px',
                  lineHeight: '1.6'
                }}
              />
              <Form.Text className="helper-text" style={{ marginTop: '8px', display: 'block' }}>
                🎓 We'll align your academic path with your aspirations
              </Form.Text>
            </Form.Group>
          </div>
        );

      case 4:
        return (
          <div>
            <h2 className="question-title" style={{ fontFamily: 'Lora, serif' }}>
              What are your career goals?
            </h2>
            <p className="question-description mb-4">
              Describe the career paths or industries that excite you. Think about where you see yourself thriving.
            </p>
            <Form.Group>
              <Form.Control
                as="textarea"
                rows={6}
                placeholder="e.g., mechanical engineer, strategy consultant, academic researcher, social entrepreneur..."
                value={formData.careerGoals}
                onChange={(e) => setFormData({ ...formData, careerGoals: e.target.value })}
                style={{
                  borderRadius: 10,
                  border: '2px solid #e8e0f5',
                  padding: '14px 16px',
                  fontSize: '15px',
                  lineHeight: '1.6'
                }}
              />
              <Form.Text className="helper-text" style={{ marginTop: '8px', display: 'block' }}>
                🌟 Your career vision shapes your academic roadmap
              </Form.Text>
            </Form.Group>
          </div>
        );

      case 5:
        return (
          <div>
            <h2 className="question-title" style={{ fontFamily: 'Lora, serif' }}>
              Review your profile
            </h2>
            <p className="question-description mb-4">
              Take a moment to review your information. You can always update this later.
            </p>
            <div className="review-section mb-4">
              <div className="mb-4">
                <div className="review-label">Major</div>
                <p className="review-content">{formData.major}</p>
              </div>
              <div className="mb-4">
                <div className="review-label">College Interests</div>
                <p className="review-content">{formData.interests}</p>
              </div>
              <div className="mb-4">
                <div className="review-label">Post-Graduation Goals</div>
                <p className="review-content">{formData.postGradGoals}</p>
              </div>
              <div className="mb-0">
                <div className="review-label">Career Goals</div>
                <p className="review-content">{formData.careerGoals}</p>
              </div>
            </div>
            <Button
              onClick={handleBuildDreamPath}
              style={{
                width: '100%',
                padding: '18px',
                borderRadius: 12,
                background: 'linear-gradient(135deg, #8A6BC1 0%, #6B8FC7 100%)',
                border: 'none',
                fontWeight: 600,
                fontFamily: 'Lora, serif',
                fontSize: '18px',
                boxShadow: '0 4px 15px rgba(138, 107, 193, 0.3)',
                transition: 'all 0.3s ease'
              }}
              onMouseEnter={(e) => {
                e.target.style.transform = 'translateY(-2px)';
                e.target.style.boxShadow = '0 6px 20px rgba(138, 107, 193, 0.4)';
              }}
              onMouseLeave={(e) => {
                e.target.style.transform = 'translateY(0)';
                e.target.style.boxShadow = '0 4px 15px rgba(138, 107, 193, 0.3)';
              }}
            >
              Build My DreamPath ✨
            </Button>
          </div>
        );

      default:
        return null;
    }
  };

  return (
    <>
      <style>{onboardingStyles}</style>
      <InitLoadingOverlay isOpen={isInitializing} nodeStatus={initStatus} />

      <div
        style={{
          minHeight: '100vh',
          background: 'linear-gradient(135deg, #8A6BC1 0%, #6B8FC7 100%)',
          display: 'flex',
          alignItems: 'center',
          padding: '60px 20px',
        }}
      >
        <Container>
          <div className="row justify-content-center">
            <div className="col-md-10 col-lg-8">
              <Card className="onboarding-card" style={{
                border: 'none',
                borderRadius: 20,
                boxShadow: '0 20px 60px rgba(0, 0, 0, 0.3)',
              }}>
                <Card.Body style={{ padding: '48px 56px' }}>
                  <div style={{ marginBottom: '1rem' }}>
                    <div className="text-center mb-2">
                      <h1
                        style={{
                          fontFamily: 'Lora, serif',
                          fontSize: '36px',
                          fontWeight: 600,
                          background: 'linear-gradient(135deg, #8A6BC1 0%, #6B8FC7 100%)',
                          WebkitBackgroundClip: 'text',
                          WebkitTextFillColor: 'transparent',
                          backgroundClip: 'text',
                          marginBottom: '12px'
                        }}
                      >
                        Welcome to DreamPath
                      </h1>
                      <p style={{
                        color: '#666',
                        fontSize: '16px',
                        fontWeight: 400,
                        marginBottom: '24px'
                      }}>
                        The journey from college to your dream career begins here.
                      </p>
                    </div>
                    <ProgressBar
                      now={progress}
                      style={{
                        height: '8px',
                        borderRadius: 4,
                        backgroundColor: '#e8e0f5'
                      }}
                      className="custom-progress-bar"
                    />
                    <div className="step-indicator">
                      Step {currentStep} of {totalSteps}
                    </div>
                  </div>

                  {error && <Alert variant="danger">{error}</Alert>}

                  {renderStep()}

                  {currentStep < 5 && (
                    <div className="d-flex justify-content-between mt-5">
                      <Button
                        variant="outline-secondary"
                        onClick={handleBack}
                        disabled={currentStep === 1}
                        style={{
                          padding: '12px 32px',
                          borderRadius: 10,
                          border: '2px solid #d6cdea',
                          color: '#8A6BC1',
                          fontWeight: 500,
                          backgroundColor: 'transparent',
                          opacity: currentStep === 1 ? 0.5 : 1
                        }}
                      >
                        ← Back
                      </Button>
                      <Button
                        onClick={handleNext}
                        style={{
                          padding: '12px 32px',
                          borderRadius: 10,
                          background: 'linear-gradient(135deg, #8A6BC1 0%, #6B8FC7 100%)',
                          border: 'none',
                          fontWeight: 500,
                          boxShadow: '0 4px 12px rgba(138, 107, 193, 0.25)'
                        }}
                      >
                        Next →
                      </Button>
                    </div>
                  )}

                  {currentStep === 5 && (
                    <div className="mt-4 text-center">
                      <Button
                        onClick={handleBack}
                        style={{
                          padding: '12px 32px',
                          borderRadius: 10,
                          border: '2px solid #d6cdea',
                          color: '#8A6BC1',
                          fontWeight: 500,
                          backgroundColor: 'white'
                        }}
                      >
                        ← Back to Edit
                      </Button>
                    </div>
                  )}
                </Card.Body>
              </Card>
            </div>
          </div>
        </Container>
      </div>
    </>
  );
}

export default Onboarding;
