import React, { useState, useEffect } from 'react';
import { Container, Form, Button, Card, ProgressBar, Alert } from 'react-bootstrap';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { apiClient } from '../lib/api';
import InitLoadingOverlay from './InitLoadingOverlay';
import { Handshake, Rocket, Brain, Shield, Building2, Map, Users, HelpCircle, ChevronLeft, ChevronRight } from 'lucide-react';
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

  /* Intro Slide Styles */
  .intro-slide-container {
    position: relative;
    overflow: hidden;
    min-height: 320px;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
  }

  .intro-slide {
    display: flex;
    flex-direction: column;
    align-items: center;
    text-align: center;
    padding: 20px;
    animation: fadeSlideIn 0.4s ease-out;
  }

  .intro-slide.slide-left {
    animation: slideOutLeft 0.3s ease-in forwards;
  }

  .intro-slide.slide-right {
    animation: slideOutRight 0.3s ease-in forwards;
  }

  @keyframes fadeSlideIn {
    from {
      opacity: 0;
      transform: translateX(30px);
    }
    to {
      opacity: 1;
      transform: translateX(0);
    }
  }

  @keyframes slideOutLeft {
    from {
      opacity: 1;
      transform: translateX(0);
    }
    to {
      opacity: 0;
      transform: translateX(-30px);
    }
  }

  @keyframes slideOutRight {
    from {
      opacity: 1;
      transform: translateX(0);
    }
    to {
      opacity: 0;
      transform: translateX(30px);
    }
  }

  .intro-icon {
    display: flex;
    align-items: center;
    justify-content: center;
    margin-bottom: 24px;
  }

  .intro-icon svg {
    width: 40px;
    height: 40px;
    color: #8A6BC1;
    stroke-width: 1.5;
  }

  .intro-logo {
    width: 80px;
    height: 80px;
    margin-bottom: 28px;
  }

  .intro-logo img {
    width: 100%;
    height: 100%;
    object-fit: contain;
  }

  .intro-compass {
    width: 48px;
    height: 48px;
    margin-bottom: 24px;
  }

  .intro-compass img {
    width: 100%;
    height: 100%;
    object-fit: contain;
  }

  .intro-content {
    font-family: 'Lora', serif;
    font-size: 21px;
    line-height: 1.7;
    color: #6a6a7a;
    max-width: 500px;
    font-weight: 400;
    letter-spacing: -0.01em;
  }

  .intro-content strong {
    color: #8A6BC1;
    font-weight: 600;
  }

  .intro-feature-box {
    display: flex;
    gap: 24px;
    margin-top: 16px;
    flex-wrap: wrap;
    justify-content: center;
  }

  .intro-feature {
    flex: 1;
    min-width: 200px;
    max-width: 220px;
    background: linear-gradient(135deg, #f8f6fb 0%, #f5f8fc 100%);
    border-radius: 12px;
    padding: 20px;
    text-align: center;
    border: 1px solid #e8e0f5;
  }

  .intro-feature-icon {
    width: 48px;
    height: 48px;
    border-radius: 50%;
    background: white;
    display: flex;
    align-items: center;
    justify-content: center;
    margin: 0 auto 12px;
    box-shadow: 0 2px 8px rgba(138, 107, 193, 0.15);
  }

  .intro-feature-icon svg {
    width: 24px;
    height: 24px;
    color: #8A6BC1;
    stroke-width: 1.5;
  }

  .intro-feature-title {
    font-family: 'Lora', serif;
    font-size: 16px;
    font-weight: 600;
    color: #8A6BC1;
    margin-bottom: 6px;
  }

  .intro-feature-desc {
    font-family: 'Lora', serif;
    font-size: 13px;
    color: #666;
    line-height: 1.5;
  }

  .intro-progress-dots {
    display: flex;
    gap: 8px;
    justify-content: center;
    margin-top: 32px;
  }

  .intro-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: #d6cdea;
    transition: all 0.3s ease;
  }

  .intro-dot.active {
    width: 20px;
    border-radius: 3px;
    background: linear-gradient(135deg, #8A6BC1 0%, #7B8FC7 100%);
  }

  .intro-nav {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-top: 32px;
    width: 100%;
    max-width: 400px;
    margin-left: auto;
    margin-right: auto;
  }

  .intro-nav-btn {
    width: 48px;
    height: 48px;
    border-radius: 50%;
    border: 2px solid #e8e0f5;
    background: white;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    transition: all 0.2s ease;
  }

  .intro-nav-btn:hover:not(:disabled) {
    border-color: #8A6BC1;
    background: linear-gradient(135deg, #f8f6fb 0%, #f5f8fc 100%);
  }

  .intro-nav-btn:disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }

  .intro-nav-btn svg {
    width: 20px;
    height: 20px;
    color: #8A6BC1;
  }

  .intro-skip-link {
    position: absolute;
    top: 20px;
    right: 24px;
    font-family: 'Lora', serif;
    font-size: 14px;
    color: #a8a8a8;
    cursor: pointer;
    transition: color 0.2s ease;
    text-decoration: none;
    font-style: italic;
  }

  .intro-skip-link:hover {
    color: #8A6BC1;
  }

  .intro-ready-btn {
    padding: 16px 48px;
    border-radius: 12px;
    background: linear-gradient(135deg, #8A6BC1 0%, #6B8FC7 100%);
    border: none;
    color: white;
    font-weight: 600;
    font-family: 'Lora', serif;
    font-size: 18px;
    box-shadow: 0 4px 15px rgba(138, 107, 193, 0.3);
    cursor: pointer;
    transition: all 0.3s ease;
    margin-top: 24px;
  }

  .intro-ready-btn:hover {
    transform: translateY(-2px);
    box-shadow: 0 6px 20px rgba(138, 107, 193, 0.4);
  }
`;

/**
 * Onboarding - Multi-step wizard for new users
 *
 * Collects profile information and triggers course path initialization
 * Steps: Major → Interests → Post-grad Goals → Career Goals → Review
 */
// Intro slides data
const introSlides = [
  {
    icon: null,
    isLogoSlide: true,
    content: "Hi, there! Welcome to <strong>DreamPath</strong>."
  },
  {
    icon: Handshake,
    content: "DreamPath is a tool dedicated to helping you succeed with whatever you hope to do, taking you from curious student to your <strong>dream career</strong>."
  },
  {
    icon: Rocket,
    content: "DreamPath transforms college into your personalized <strong>launchpad</strong> for strategic exploration and career success."
  },
  {
    icon: Brain,
    content: "Powered by an intelligent AI system that's knowledgeable about emerging careers and changing market landscapes, DreamPath stays <strong>up to date</strong> about how the professional world is changing."
  },
  {
    icon: Shield,
    content: "Worried about the impact of AI automation, or new qualifications for a once tried-and-true role? <strong>DreamPath's got you covered.</strong>"
  },
  {
    icon: Building2,
    content: "With this knowledge in hand, DreamPath is plugged into school resources in real time — every <strong>course</strong>, <strong>club</strong>, and <strong>research group</strong> you can think of."
  },
  {
    icon: null, // Special slide with two features
    isFeatureSlide: true,
    features: [
      {
        icon: Map,
        title: "CoursePath",
        description: "Your curated academic roadmap to equip you with the right knowledge and skills."
      },
      {
        icon: Users,
        title: "ClubPath",
        description: "Discover activities and groups that help you acquire valuable experience and interactions."
      }
    ]
  },
  {
    icon: HelpCircle,
    content: "Three terms, or even two years down the line, what if <strong>something changes</strong>? Or what if you need a course at a specific point in time?"
  },
  {
    icon: null,
    isCompassSlide: true,
    content: "Meet <strong>Compass</strong> — the conversational advising assistant that helps you brainstorm, make changes, and engage in structured career pivots."
  },
  {
    icon: null,
    content: "What's next? After telling us a bit about yourself, we'll build your personalized <strong>DreamPath</strong>.",
    isFinalSlide: true
  }
];

function Onboarding() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [currentStep, setCurrentStep] = useState(1);
  const [isInitializing, setIsInitializing] = useState(false);
  const [initStatus, setInitStatus] = useState(null);
  const [error, setError] = useState('');
  const [majors, setMajors] = useState([]);
  const [loadingMajors, setLoadingMajors] = useState(true);

  // Intro flow state
  const [introSlide, setIntroSlide] = useState(0);
  const [introComplete, setIntroComplete] = useState(false);
  const [slideDirection, setSlideDirection] = useState(null);

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
    if (currentStep === 1) {
      // Go back to intro slides (last slide)
      setIntroComplete(false);
      setIntroSlide(introSlides.length - 1);
    } else {
      setCurrentStep(currentStep - 1);
    }
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

  // Intro navigation handlers
  const handleIntroNext = () => {
    if (introSlide < introSlides.length - 1) {
      setSlideDirection('left');
      setTimeout(() => {
        setIntroSlide(introSlide + 1);
        setSlideDirection(null);
      }, 300);
    }
  };

  const handleIntroBack = () => {
    if (introSlide > 0) {
      setSlideDirection('right');
      setTimeout(() => {
        setIntroSlide(introSlide - 1);
        setSlideDirection(null);
      }, 300);
    }
  };

  const handleSkipIntro = () => {
    setIntroComplete(true);
  };

  const handleIntroComplete = () => {
    setIntroComplete(true);
  };

  // Render intro slide content
  const renderIntroSlide = () => {
    const slide = introSlides[introSlide];
    const slideClass = slideDirection === 'left' ? 'slide-left' : slideDirection === 'right' ? 'slide-right' : '';

    if (slide.isFeatureSlide) {
      return (
        <div className={`intro-slide ${slideClass}`}>
          <div className="intro-content" style={{ marginBottom: '8px' }}>
            These resources power your <strong>personalized journey</strong>:
          </div>
          <div className="intro-feature-box">
            {slide.features.map((feature, idx) => (
              <div key={idx} className="intro-feature">
                <div className="intro-feature-icon">
                  <feature.icon />
                </div>
                <div className="intro-feature-title">{feature.title}</div>
                <div className="intro-feature-desc">{feature.description}</div>
              </div>
            ))}
          </div>
        </div>
      );
    }

    const IconComponent = slide.icon;
    return (
      <div className={`intro-slide ${slideClass}`}>
        {slide.isLogoSlide ? (
          <div className="intro-logo">
            <img src="/logo.png" alt="DreamPath" />
          </div>
        ) : slide.isCompassSlide ? (
          <div className="intro-compass">
            <img src="/compass.svg" alt="Compass" />
          </div>
        ) : IconComponent ? (
          <div className="intro-icon">
            <IconComponent />
          </div>
        ) : null}
        <div
          className="intro-content"
          dangerouslySetInnerHTML={{ __html: slide.content }}
        />
        {slide.isFinalSlide && (
          <button className="intro-ready-btn" onClick={handleIntroComplete}>
            I'm Ready
          </button>
        )}
      </div>
    );
  };

  // Render the full intro flow
  const renderIntroFlow = () => {
    return (
      <>
        <style>{onboardingStyles}</style>
        <div
          style={{
            minHeight: '100vh',
            background: 'linear-gradient(145deg, #f5f0fa 0%, #e8e0f5 50%, #dfe8f5 100%)',
            display: 'flex',
            alignItems: 'center',
            padding: '60px 20px',
          }}
        >
          <Container>
            <div className="row justify-content-center">
              <div className="col-md-10 col-lg-8">
                <Card className="onboarding-card" style={{
                  border: '1px solid rgba(138, 107, 193, 0.12)',
                  borderRadius: 24,
                  boxShadow: '0 8px 40px rgba(138, 107, 193, 0.15)',
                  position: 'relative',
                }}>
                  <Card.Body style={{ padding: '52px 60px' }}>
                    <span className="intro-skip-link" onClick={handleSkipIntro}>
                      Skip intro →
                    </span>

                    <div className="text-center mb-4">
                      <h1
                        style={{
                          fontFamily: 'Lora, serif',
                          fontSize: '40px',
                          fontWeight: 600,
                          background: 'linear-gradient(135deg, #7B5BA6 0%, #5B7BB6 100%)',
                          WebkitBackgroundClip: 'text',
                          WebkitTextFillColor: 'transparent',
                          backgroundClip: 'text',
                          marginBottom: '4px',
                          letterSpacing: '-0.02em'
                        }}
                      >
                        DreamPath
                      </h1>
                      <p
                        style={{
                          fontFamily: 'Lora, serif',
                          fontSize: '15px',
                          color: '#8a8a9a',
                          fontStyle: 'italic',
                          marginBottom: 0
                        }}
                      >
                        Your journey starts here
                      </p>
                    </div>

                    <div className="intro-slide-container">
                      {renderIntroSlide()}
                    </div>

                    <div className="intro-progress-dots">
                      {introSlides.map((_, idx) => (
                        <div
                          key={idx}
                          className={`intro-dot ${idx === introSlide ? 'active' : ''}`}
                        />
                      ))}
                    </div>

                    {!introSlides[introSlide].isFinalSlide && (
                      <div className="intro-nav">
                        <button
                          className="intro-nav-btn"
                          onClick={handleIntroBack}
                          disabled={introSlide === 0}
                        >
                          <ChevronLeft />
                        </button>
                        <button
                          className="intro-nav-btn"
                          onClick={handleIntroNext}
                          disabled={introSlide === introSlides.length - 1}
                        >
                          <ChevronRight />
                        </button>
                      </div>
                    )}

                    {introSlides[introSlide].isFinalSlide && (
                      <div className="intro-nav" style={{ justifyContent: 'center' }}>
                        <button
                          className="intro-nav-btn"
                          onClick={handleIntroBack}
                        >
                          <ChevronLeft />
                        </button>
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
                The more specific you are, the better we can personalize your journey
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
                We'll align your academic path with your aspirations
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
                Your career vision shapes your academic roadmap
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

  // Show intro flow if not complete
  if (!introComplete) {
    return renderIntroFlow();
  }

  // Show profile creation steps
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
                        Build Your Profile
                      </h1>
                      <p style={{
                        color: '#666',
                        fontSize: '16px',
                        fontWeight: 400,
                        marginBottom: '24px'
                      }}>
                        Tell us about yourself so we can personalize your DreamPath.
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
                        style={{
                          padding: '12px 32px',
                          borderRadius: 10,
                          border: '2px solid #d6cdea',
                          color: '#8A6BC1',
                          fontWeight: 500,
                          backgroundColor: 'transparent',
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
