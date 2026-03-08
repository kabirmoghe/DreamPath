import React, { useState, useEffect } from 'react';
import { Container, Row, Col, Card, Button, Form } from 'react-bootstrap';
import { useNavigate } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useAuth } from '../contexts/AuthContext';
import { apiClient } from '../lib/api';
import DashboardNavbar from './DashboardNavbar';
import LeftSidebar from './LeftSidebar';
import ChatWindow from './ChatWindow';
import WelcomeOverlay from './WelcomeOverlay';
import { BookIcon, PeopleIcon, NetworkIcon } from './icons/DreamPathIcons';
import 'bootstrap/dist/css/bootstrap.min.css';

/**
 * Dashboard - Main dashboard with chat window integration
 *
 * Features:
 * - Chat window with AI agent integration
 * - Student profile management
 * - Quick navigation tabs to Courses, Clubs, Career
 * - Uses AuthContext for authentication
 */
function Dashboard() {
  const navigate = useNavigate();
  const { user, signOut } = useAuth();
  const queryClient = useQueryClient();

  // React Query for profile data
  const {
    data: profile,
    isLoading: profileLoading,
    error: profileError
  } = useQuery({
    queryKey: ['profile', user?.id ? String(user.id) : null],
    queryFn: async () => {
      if (!user?.id) return null;
      const data = await apiClient.getProfile(String(user.id));
      return data;
    },
    enabled: !!user?.id,
    staleTime: 1000 * 60, // Consider fresh for 1 minute
  });

  // React Query for course path data
  const {
    data: coursePathData,
    isLoading: coursePathLoading
  } = useQuery({
    queryKey: ['coursePath', user?.id ? String(user.id) : null],
    queryFn: async () => {
      if (!user?.id) return null;
      const data = await apiClient.getCoursePath(String(user.id));
      return data;
    },
    enabled: !!user?.id,
    staleTime: 1000 * 30,
  });

  // React Query for club path data
  const {
    data: clubPathData,
    isLoading: clubPathLoading
  } = useQuery({
    queryKey: ['clubPath', user?.id ? String(user.id) : null],
    queryFn: async () => {
      if (!user?.id) return null;
      const data = await apiClient.getClubPath(String(user.id));
      return data;
    },
    enabled: !!user?.id,
    staleTime: 1000 * 30,
  });

  const [editProfile, setEditProfile] = useState(null);
  const [isEditing, setIsEditing] = useState(false);
  const [isChatOpen, setIsChatOpen] = useState(false);
  const [typedText, setTypedText] = useState('');
  const [showCursor, setShowCursor] = useState(true);
  const [showWelcome, setShowWelcome] = useState(false);

  // Get first name from profile (from DB) instead of AuthContext
  const fullName = profile?.name || '';
  const firstName = fullName.split(' ')[0] || 'Student';

  useEffect(() => {
    if (!user) {
      navigate('/login');
      return;
    }
  }, [user, navigate]);

  // Redirect to onboarding if profile doesn't exist (incomplete onboarding)
  useEffect(() => {
    if (!profileLoading && !profileError && profile === null) {
      // Profile doesn't exist - user needs to complete onboarding
      console.log('No profile found, redirecting to onboarding');
      navigate('/onboarding');
    }
  }, [profile, profileLoading, profileError, navigate]);

  // Sync editProfile when profile changes (including after agent updates)
  // Map backend fields to frontend field names
  useEffect(() => {
    if (profile) {
      // Only update if not currently editing to avoid overwriting user's changes
      if (!isEditing) {
        setEditProfile({
          ...profile,
          long_term_goal: profile.career_goals, // Map career_goals to long_term_goal for frontend
        });
      }
    }
  }, [profile, isEditing]);

  // Welcome flow for first-time users (after init)
  useEffect(() => {
    if (!user?.id || !coursePathData) return;

    const hasSeenWelcome = localStorage.getItem(`welcome_shown_${user.id}`);
    if (!hasSeenWelcome) {
      setShowWelcome(true);
      localStorage.setItem(`welcome_shown_${user.id}`, 'true');

      // Auto-hide after 8 seconds
      setTimeout(() => setShowWelcome(false), 8000);
    }
  }, [user?.id, coursePathData]);

  // Typing animation effect
  useEffect(() => {
    const fullText = `Welcome, ${firstName}`;
    let currentIndex = 0;
    setTypedText(''); // Reset on firstName change
    setShowCursor(true); // Reset cursor visibility

    // Cursor blinking effect
    const cursorInterval = setInterval(() => {
      setShowCursor((prev) => !prev);
    }, 500);

    const typingInterval = setInterval(() => {
      if (currentIndex <= fullText.length) {
        setTypedText(fullText.slice(0, currentIndex));
        currentIndex++;
      } else {
        clearInterval(typingInterval);
        // Let cursor blink for 1.5 seconds, then stop and hide
        setTimeout(() => {
          clearInterval(cursorInterval);
          setShowCursor(false);
        }, 1500);
      }
    }, 50); // 50ms per character

    return () => {
      clearInterval(typingInterval);
      clearInterval(cursorInterval);
    };
  }, [firstName]);

  const handleEditChange = (e) => {
    setEditProfile({ ...editProfile, [e.target.name]: e.target.value });
  };

  const handleSaveProfile = async () => {
    try {
      // Save profile to PostgreSQL backend
      await apiClient.updateProfile(String(user.id), {
        major: editProfile.major,
        college_interests: editProfile.college_interests,
        post_grad_goal: editProfile.post_grad_goal,
        career_goals: editProfile.long_term_goal,
        minors: editProfile.minors,
      });

      // Invalidate query to refetch fresh data
      queryClient.invalidateQueries(['profile', String(user.id)]);
      setIsEditing(false);
    } catch (error) {
      console.error('Failed to save profile:', error);
      alert('Failed to save profile. Please try again.');
    }
  };

  const handleSignOut = async () => {
    await signOut();
    navigate('/login');
  };

  // Helper: Get sample courses for timeline (3-4 courses from different terms)
  const getSampleCourses = () => {
    if (!coursePathData || !coursePathData.course_path || !coursePathData.course_bank) {
      return [];
    }

    const courses = [];
    const maxCourses = 4;
    const coursePath = coursePathData.course_path;

    // Try to get courses from different terms, spread evenly
    const termStep = Math.max(1, Math.floor(coursePath.length / maxCourses));

    for (let i = 0; i < coursePath.length && courses.length < maxCourses; i += termStep) {
      const termCourses = coursePath[i];
      if (termCourses && termCourses.length > 0) {
        const courseCode = termCourses[0]; // Take first course from the term
        const courseDetails = coursePathData.course_bank[courseCode];
        if (courseDetails) {
          courses.push({
            ...courseDetails,
            termIndex: i
          });
        }
      }
    }

    return courses;
  };

  if (profileLoading || !profile) {
    return (
      <div style={{ minHeight: '100vh', background: 'linear-gradient(135deg, #ede9f5 0%, #e5ebf8 100%)' }}>
        <DashboardNavbar onSignOut={handleSignOut} />
        <LeftSidebar />
        <div className="content-with-sidebar">
          <Container className="py-5 text-center">
            <p>Loading profile...</p>
          </Container>
        </div>
      </div>
    );
  }

  if (profileError) {
    return (
      <div style={{ minHeight: '100vh', background: 'linear-gradient(135deg, #ede9f5 0%, #e5ebf8 100%)' }}>
        <DashboardNavbar onSignOut={handleSignOut} />
        <LeftSidebar />
        <div className="content-with-sidebar">
          <Container className="py-5 text-center">
            <p className="text-danger">Failed to load profile. Please try refreshing.</p>
          </Container>
        </div>
      </div>
    );
  }

  return (
    <div style={{ minHeight: '100vh', background: 'linear-gradient(135deg, #ede9f5 0%, #e5ebf8 100%)' }}>
      <DashboardNavbar onSignOut={handleSignOut} />
      <LeftSidebar />
      <div className="content-with-sidebar">
        <Container className="py-4">
        <Row className="mb-4">
          <Col>
            <div className="d-flex justify-content-between align-items-center">
              <h1
                className="h2 mb-0"
                style={{ fontFamily: 'Lora, serif', fontWeight: 300, color: '#7b7b93' }}
              >
                {typedText}
                <span style={{ opacity: showCursor ? 1 : 0, transition: 'opacity 0.1s' }}>|</span>
              </h1>
            </div>
          </Col>
        </Row>

        <Row>
          {/* Left Column - Profile */}
          <Col md={6} className="h-100" style={{ width: '45%' }}>
            <Card
              className="mb-4 h-100"
              style={{ background: '#faf9fb', border: 'none', borderRadius: 16 }}
            >
              <Card.Body
                style={{
                  height: '100%',
                  display: 'flex',
                  flexDirection: 'column',
                  justifyContent: 'center',
                }}
              >
                <div className="d-flex justify-content-between align-items-center mb-3">
                  <h3 className="h5 mb-0">Your Profile</h3>
                  {!isEditing && (
                    <Button
                      variant="outline-primary"
                      size="sm"
                      onClick={() => setIsEditing(true)}
                      style={{
                        fontFamily: 'Lora, serif',
                        border: '1px solid #8A6BC1',
                        color: '#8A6BC1',
                        background: 'transparent',
                        borderRadius: 8,
                        transition: 'all 0.2s ease',
                      }}
                      onMouseEnter={(e) => {
                        e.currentTarget.style.background = '#8A6BC1';
                        e.currentTarget.style.color = 'white';
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.background = 'transparent';
                        e.currentTarget.style.color = '#8A6BC1';
                      }}
                    >
                      Edit
                    </Button>
                  )}
                </div>

                <Form>
                  <Form.Group className="mb-3">
                    <Form.Label style={{ fontWeight: 500 }}>Major</Form.Label>
                    {isEditing ? (
                      <Form.Control
                        type="text"
                        name="major"
                        value={editProfile?.major || ''}
                        onChange={handleEditChange}
                        style={{
                          background: '#eeeefa',
                          border: '0.5px solid #d6cdea',
                          boxShadow: 'none',
                          borderRadius: 8,
                          padding: '8px 12px',
                          fontFamily: 'Lora, serif',
                          fontSize: '14px',
                          fontWeight: 450,
                          color: '#504762',
                        }}
                      />
                    ) : (
                      <Form.Control
                        plaintext
                        readOnly
                        value={editProfile?.major || ''}
                        style={{
                          background: '#eeeefa',
                          border: 'none',
                          color: '#504762',
                          borderRadius: 8,
                          padding: '8px 12px',
                          fontFamily: 'Lora, serif',
                          fontSize: '14px',
                          fontWeight: 450,
                        }}
                      />
                    )}
                  </Form.Group>

                  <Form.Group className="mb-3">
                    <Form.Label style={{ fontWeight: 500 }}>College Interests</Form.Label>
                    {isEditing ? (
                      <Form.Control
                        as="textarea"
                        rows={3}
                        style={{
                          resize: 'none',
                          overflowY: 'auto',
                          minHeight: 80,
                          maxHeight: 80,
                          background: '#eeeefa',
                          border: '0.5px solid #d6cdea',
                          boxShadow: 'none',
                          borderRadius: 8,
                          padding: '8px 12px',
                          fontFamily: 'Lora, serif',
                          fontSize: '14px',
                          color: '#504762',
                          fontWeight: 450,
                        }}
                        name="college_interests"
                        value={editProfile?.college_interests || ''}
                        onChange={handleEditChange}
                      />
                    ) : (
                      <Form.Control
                        plaintext
                        readOnly
                        as="textarea"
                        rows={3}
                        value={editProfile?.college_interests || ''}
                        style={{
                          background: '#eeeefa',
                          border: 'none',
                          color: '#504762',
                          resize: 'none',
                          minHeight: 80,
                          maxHeight: 80,
                          borderRadius: 8,
                          padding: '8px 12px',
                          fontFamily: 'Lora, serif',
                          fontSize: '14px',
                          fontWeight: 450,
                        }}
                      />
                    )}
                  </Form.Group>

                  <Form.Group className="mb-3">
                    <Form.Label style={{ fontWeight: 500 }}>Post-Graduation Goals</Form.Label>
                    {isEditing ? (
                      <Form.Control
                        as="textarea"
                        rows={3}
                        style={{
                          resize: 'none',
                          overflowY: 'auto',
                          minHeight: 80,
                          maxHeight: 80,
                          background: '#eeeefa',
                          border: '0.5px solid #d6cdea',
                          boxShadow: 'none',
                          borderRadius: 8,
                          padding: '8px 12px',
                          fontFamily: 'Lora, serif',
                          fontSize: '14px',
                          fontWeight: 450,
                          color: '#504762',
                        }}
                        name="post_grad_goal"
                        value={editProfile?.post_grad_goal || ''}
                        onChange={handleEditChange}
                      />
                    ) : (
                      <Form.Control
                        plaintext
                        readOnly
                        as="textarea"
                        rows={3}
                        value={editProfile?.post_grad_goal || ''}
                        style={{
                          background: '#eeeefa',
                          border: 'none',
                          color: '#504762',
                          resize: 'none',
                          minHeight: 80,
                          maxHeight: 80,
                          borderRadius: 8,
                          padding: '8px 12px',
                          fontFamily: 'Lora, serif',
                          fontSize: '14px',
                          fontWeight: 450,
                        }}
                      />
                    )}
                  </Form.Group>

                  <Form.Group className="mb-3">
                    <Form.Label style={{ fontWeight: 500 }}>Career Goals</Form.Label>
                    {isEditing ? (
                      <Form.Control
                        as="textarea"
                        rows={3}
                        style={{
                          resize: 'none',
                          overflowY: 'auto',
                          minHeight: 80,
                          maxHeight: 80,
                          background: '#eeeefa',
                          border: '0.5px solid #d6cdea',
                          boxShadow: 'none',
                          borderRadius: 8,
                          padding: '8px 12px',
                          fontFamily: 'Lora, serif',
                          fontSize: '14px',
                          fontWeight: 450,
                          color: '#504762',
                        }}
                        name="long_term_goal"
                        value={editProfile?.long_term_goal || ''}
                        onChange={handleEditChange}
                      />
                    ) : (
                      <Form.Control
                        plaintext
                        readOnly
                        as="textarea"
                        rows={3}
                        value={editProfile?.long_term_goal || ''}
                        style={{
                          background: '#eeeefa',
                          border: 'none',
                          color: '#504762',
                          resize: 'none',
                          minHeight: 80,
                          maxHeight: 80,
                          borderRadius: 8,
                          padding: '8px 12px',
                          fontFamily: 'Lora, serif',
                          fontSize: '14px',
                          fontWeight: 450,
                        }}
                      />
                    )}
                  </Form.Group>

                  {isEditing && (
                    <div className="d-flex justify-content-end gap-2">
                      <Button
                        variant="outline-secondary"
                        onClick={() => {
                          setEditProfile(profile);
                          setIsEditing(false);
                        }}
                        style={{
                          minWidth: 100,
                          fontFamily: 'Lora, serif',
                          border: '1px solid #d6cdea',
                          color: '#7b7b93',
                          background: 'transparent',
                          borderRadius: 8,
                          transition: 'all 0.2s ease',
                        }}
                        onMouseEnter={(e) => {
                          e.currentTarget.style.background = '#f5f3f8';
                          e.currentTarget.style.borderColor = '#c4b8d9';
                        }}
                        onMouseLeave={(e) => {
                          e.currentTarget.style.background = 'transparent';
                          e.currentTarget.style.borderColor = '#d6cdea';
                        }}
                      >
                        Cancel
                      </Button>
                      <Button
                        onClick={handleSaveProfile}
                        style={{
                          minWidth: 100,
                          fontFamily: 'Lora, serif',
                          background: '#8A6BC1',
                          border: 'none',
                          borderRadius: 8,
                          transition: 'all 0.2s ease',
                        }}
                        onMouseEnter={(e) => {
                          e.currentTarget.style.background = '#7559a8';
                        }}
                        onMouseLeave={(e) => {
                          e.currentTarget.style.background = '#8A6BC1';
                        }}
                      >
                        Save
                      </Button>
                    </div>
                  )}
                </Form>
              </Card.Body>
            </Card>
          </Col>

          {/* Right Column - Dashboard Overview */}
          <Col md={6} className="h-100" style={{ width: '55%' }}>
            <Card
              className="mb-4"
              style={{ background: '#faf9fb', border: 'none', borderRadius: 16 }}
            >
              <Card.Body style={{ padding: '20px' }}>
                {/* Dashboard Header */}
                <div style={{ marginBottom: '20px' }}>
                  <h3 className="h5 mb-0">Dashboard</h3>
                </div>

                {/* Courses Section */}
                <div
                  onClick={() => navigate('/courses')}
                  style={{
                    background: 'linear-gradient(135deg, #f5f0fa 0%, #f9f6fc 100%)',
                    borderRadius: '12px',
                    padding: '16px',
                    marginBottom: '16px',
                    border: '1px solid #e8dff5',
                    cursor: 'pointer',
                    transition: 'all 0.2s ease',
                    boxShadow: '0 2px 4px rgba(0,0,0,0.05)'
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.boxShadow = '0 4px 12px rgba(138, 107, 193, 0.15)';
                    e.currentTarget.style.transform = 'translateY(-2px)';
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.boxShadow = '0 2px 4px rgba(0,0,0,0.05)';
                    e.currentTarget.style.transform = 'translateY(0)';
                  }}
                >
                  <h4 style={{ fontSize: '15px', fontWeight: '600', color: '#8A6BC1', marginBottom: '12px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <BookIcon size={16} />
                    Courses
                  </h4>
                  {coursePathLoading ? (
                    <div className="text-center py-2">
                      <p className="text-muted" style={{ fontSize: 13 }}>Loading...</p>
                    </div>
                  ) : getSampleCourses().length > 0 ? (
                    <div>
                      {getSampleCourses().map((course, idx) => (
                        <div
                          key={course.course_code}
                          style={{
                            display: 'flex',
                            alignItems: 'flex-start',
                            marginBottom: idx < getSampleCourses().length - 1 ? '12px' : '0',
                            position: 'relative'
                          }}
                        >
                          {/* Timeline dot and line */}
                          <div style={{
                            display: 'flex',
                            flexDirection: 'column',
                            alignItems: 'center',
                            marginRight: '10px',
                            position: 'relative'
                          }}>
                            <div style={{
                              width: '10px',
                              height: '10px',
                              borderRadius: '50%',
                              background: course.course_type === 'major' ? '#8A6BC1' : '#6B8FC7',
                              border: '2px solid white',
                              boxShadow: '0 0 0 1px #d6cdea',
                              zIndex: 1
                            }} />
                            {idx < getSampleCourses().length - 1 && (
                              <div style={{
                                width: '2px',
                                height: '32px',
                                background: '#d6cdea',
                                marginTop: '3px'
                              }} />
                            )}
                          </div>

                          {/* Course info */}
                          <div style={{ flex: 1 }}>
                            <div style={{
                              fontSize: '11px',
                              color: '#8A6BC1',
                              fontWeight: '600',
                              marginBottom: '1px'
                            }}>
                              Term {course.termIndex + 1}
                            </div>
                            <div style={{
                              fontSize: '13px',
                              fontWeight: '600',
                              color: '#333',
                              marginBottom: '1px'
                            }}>
                              {course.course_code}
                            </div>
                            <div style={{
                              fontSize: '11px',
                              color: '#666',
                              lineHeight: '1.3'
                            }}>
                              {course.course_title}
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="text-center py-2">
                      <p style={{ color: '#888', fontSize: 13, marginBottom: '4px' }}>
                        Build your course path
                      </p>
                      <p className="text-muted" style={{ fontSize: 11, margin: 0 }}>
                        Try: "Add COSC 50"
                      </p>
                    </div>
                  )}
                </div>

                {/* Clubs and Alumni - Side by Side */}
                <Row>
                  <Col md={6}>
                    {/* Clubs Section */}
                    <div
                      onClick={() => navigate('/clubs')}
                      style={{
                        background: 'linear-gradient(135deg, #f0f9f4 0%, #f6fcf9 100%)',
                        borderRadius: '12px',
                        padding: '16px',
                        border: '1px solid #d4ede0',
                        height: '100%',
                        cursor: 'pointer',
                        transition: 'all 0.2s ease',
                        boxShadow: '0 2px 4px rgba(0,0,0,0.05)',
                      }}
                      onMouseEnter={(e) => {
                        e.currentTarget.style.boxShadow = '0 4px 12px rgba(74, 157, 110, 0.15)';
                        e.currentTarget.style.transform = 'translateY(-2px)';
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.boxShadow = '0 2px 4px rgba(0,0,0,0.05)';
                        e.currentTarget.style.transform = 'translateY(0)';
                      }}
                    >
                      <h4 style={{ fontSize: '15px', fontWeight: '600', color: '#4a9d6e', marginBottom: '12px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <PeopleIcon size={16} />
                        Clubs
                      </h4>
                      {clubPathLoading ? (
                        <div className="text-center py-2">
                          <p className="text-muted" style={{ fontSize: 13 }}>Loading...</p>
                        </div>
                      ) : clubPathData?.activities?.length > 0 ? (
                        <div>
                          {clubPathData.activities.slice(0, 2).map((activity, idx) => (
                            <div key={activity.activity_slug} style={{
                              background: 'white',
                              borderRadius: '8px',
                              padding: '7px 12px',
                              marginBottom: idx < Math.min(clubPathData.activities.length, 2) - 1 ? '8px' : '0',
                              border: '1px solid #e8f5ed',
                              boxShadow: '0 1px 2px rgba(0,0,0,0.03)',
                            }}>
                              <div style={{ fontSize: '13px', fontWeight: '500', color: '#333', marginBottom: '3px' }}>
                                {activity.display_name}
                              </div>
                              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
                                {activity.activity_type && (
                                  <span style={{
                                    fontSize: '10px', color: '#5a9e5e', background: 'rgba(90, 158, 94, 0.08)',
                                    padding: '1px 7px', borderRadius: '10px', fontWeight: 500,
                                  }}>{activity.activity_type}</span>
                                )}
                                {activity.domain && (
                                  <span style={{
                                    fontSize: '10px', color: '#6a8e5e', background: 'rgba(90, 158, 94, 0.06)',
                                    padding: '1px 7px', borderRadius: '10px', fontWeight: 500,
                                  }}>{activity.domain}</span>
                                )}
                              </div>
                            </div>
                          ))}
                          {clubPathData.activities.length > 2 && (
                            <div style={{ fontSize: '11px', color: '#888', textAlign: 'center', marginTop: '6px' }}>
                              +{clubPathData.activities.length - 2} more
                            </div>
                          )}
                        </div>
                      ) : (
                        <div className="text-center py-2">
                          <p style={{ color: '#888', fontSize: 13, marginBottom: '4px' }}>
                            Build your club path
                          </p>
                          <p className="text-muted" style={{ fontSize: 11, margin: 0 }}>
                            Try: "Find clubs for me"
                          </p>
                        </div>
                      )}
                    </div>
                  </Col>

                  <Col md={6}>
                    {/* Alumni Section */}
                    <div
                      style={{
                        background: 'linear-gradient(135deg, #fef5f5 0%, #fefafa 100%)',
                        borderRadius: '12px',
                        padding: '16px',
                        border: '1px solid #f5e0e0',
                        height: '100%',
                        opacity: 0.7,
                        cursor: 'not-allowed'
                      }}
                    >
                      <h4 style={{ fontSize: '15px', fontWeight: '600', color: '#c95d5d', marginBottom: '12px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <NetworkIcon size={16} />
                        Action Items
                      </h4>
                      <div>
                        <div style={{
                          background: 'white',
                          borderRadius: '8px',
                          padding: '7px 12px',
                          marginBottom: '8px',
                          display: 'flex',
                          alignItems: 'center',
                          border: '1px solid #fce8e8',
                          boxShadow: '0 1px 2px rgba(0,0,0,0.03)'
                        }}>
                          <span style={{ fontSize: '13px', color: '#c95d5d', marginRight: '8px' }}>→</span>
                          <span style={{ fontSize: '13px', color: '#333' }}>
                            Connect with {'  '}
                            <span style={{
                              display: 'inline-block',
                              background: '#e8e8e8',
                              borderRadius: '3px',
                              width: '50px',
                              height: '12px',
                              verticalAlign: 'middle'
                            }}></span>
                          </span>
                        </div>
                        <div style={{
                          background: 'white',
                          borderRadius: '8px',
                          padding: '7px 12px',
                          display: 'flex',
                          alignItems: 'center',
                          border: '1px solid #fce8e8',
                          boxShadow: '0 1px 2px rgba(0,0,0,0.03)'
                        }}>
                          <span style={{ fontSize: '13px', color: '#c95d5d', marginRight: '8px' }}>→</span>
                          <span style={{ fontSize: '13px', color: '#333' }}>
                            Reach out to {' '}
                            <span style={{
                              display: 'inline-block',
                              background: '#e8e8e8',
                              borderRadius: '3px',
                              width: '50px',
                              height: '12px',
                              verticalAlign: 'middle'
                            }}></span>
                            {' '}
                          </span>
                        </div>
                      </div>
                    </div>
                  </Col>
                </Row>
              </Card.Body>
            </Card>
          </Col>
        </Row>
        </Container>
      </div>

      {/* Welcome Overlay for first-time users */}
      <WelcomeOverlay show={showWelcome} onClose={() => setShowWelcome(false)} />

      {/* Chat Window */}
      <ChatWindow
        userId={user?.id ? String(user.id) : null}
        isOpen={isChatOpen}
        onToggle={() => setIsChatOpen(!isChatOpen)}
      />
    </div>
  );
}

export default Dashboard;
