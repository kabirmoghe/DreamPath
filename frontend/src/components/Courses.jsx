import React, { useState, useEffect, useRef } from 'react';
import { Card, Badge, Row, Col, Button, Nav, Tab, Container, Spinner, CloseButton } from 'react-bootstrap';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { useAuth } from '../contexts/AuthContext';
import { apiClient } from '../lib/api';
import DashboardNavbar from './DashboardNavbar';
import LeftSidebar from './LeftSidebar';
import ChatWindow from './ChatWindow';
import { Calendar, CheckSquare, Lightbulb, Lock } from 'react-bootstrap-icons';

/**
 * Courses - Course path visualization and management
 *
 * Fetches course path from backend API, which returns:
 * - course_path: List[List[str]] - Term-by-term course codes
 * - course_bank: Dict[str, Course] - Full course objects
 * - Other metadata (curr_window_start, recommended_courses, etc.)
 */
function Courses() {
  const { user, signOut } = useAuth();
  const navigate = useNavigate();

  // React Query for course path data
  const {
    data: coursePathData,
    isLoading: loading,
    error: queryError,
    refetch: fetchCoursePath
  } = useQuery({
    queryKey: ['coursePath', user?.id ? String(user.id) : null],
    queryFn: async () => {
      if (!user?.id) return null;
      const data = await apiClient.getCoursePath(String(user.id));
      return data;
    },
    enabled: !!user?.id, // Only run query if user exists
    staleTime: 1000 * 30, // Consider fresh for 30 seconds
  });

  const error = queryError?.message || null;

  const [activeTab, setActiveTab] = useState('coursePath');
  const [expandedCourse, setExpandedCourse] = useState(null);
  const [detailsPanelVisible, setDetailsPanelVisible] = useState(false);
  const [isChatOpen, setIsChatOpen] = useState(false);
  const detailsPanelRef = useRef(null);
  const scrollContainerRef = useRef(null);

  useEffect(() => {
    if (!user) {
      navigate('/login');
      return;
    }
  }, [user, navigate]);

  const handleTabChange = (tab) => setActiveTab(tab);

  const handleSignOut = async () => {
    await signOut();
    navigate('/login');
  };

  // Get course details from course_bank
  const getCourseDetails = (courseCode) => {
    if (!coursePathData || !coursePathData.course_bank) return null;
    return coursePathData.course_bank[courseCode] || { course_code: courseCode };
  };

  // Render a course card for the term-by-term view
  const renderCoursePathCard = (courseCode, termIdx) => {
    const course = getCourseDetails(courseCode);
    const isMajor = course.course_type === 'major';
    const isComplementary = course.course_type === 'complementary';
    const isPrereq = course.is_prereq || false;
    const hasWindow = course.must_have_window && course.must_have_window.length > 0;

    let borderClass = 'course-path-card';
    if (isMajor) borderClass += ' border-primary';
    else if (isComplementary) borderClass += ' border-info';
    else borderClass += ' border-secondary';

    return (
      <Card className={borderClass} key={`${termIdx}-${courseCode}`} style={{ position: 'relative' }}>
        <Card.Header className="d-flex justify-content-between align-items-center p-2">
          <span className="fw-bold">{courseCode}</span>
          <div className="ms-auto d-flex gap-1">
            {isPrereq && <Badge bg="secondary" pill className="prereq-badge">Prereq</Badge>}
            {isMajor && <Badge bg="primary" pill>Major</Badge>}
            {isComplementary && <Badge bg="info" pill>Comp</Badge>}
          </div>
        </Card.Header>
        <Card.Body className="p-2">
          {course.course_title && (
            <p className="small mb-2 text-truncate" title={course.course_title}>{course.course_title}</p>
          )}
          <div className="text-center">
            <Button
              variant="outline-secondary"
              size="sm"
              className="view-details-btn"
              onClick={e => {
                e.preventDefault();
                e.stopPropagation();
                setExpandedCourse(courseCode);
                setDetailsPanelVisible(true);
              }}
            >
              Details
            </Button>
          </div>
        </Card.Body>
        {hasWindow && (
          <div
            style={{
              position: 'absolute',
              bottom: '6px',
              right: '6px',
              backgroundColor: '#ffe0e0',
              borderRadius: '50%',
              width: '22px',
              height: '22px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              zIndex: 1
            }}
          >
            <Lock size={11} color="#d32f2f" />
          </div>
        )}
      </Card>
    );
  };

  // Term-by-term course path visualization
  function renderCoursePath() {
    if (!coursePathData || !coursePathData.course_path || coursePathData.course_path.length === 0) {
      return (
        <div className="text-center text-muted">
          <p>No course path available.</p>
          <p className="small">Use the chat assistant to build your course path.</p>
        </div>
      );
    }

    const scrollLeft = () => {
      if (scrollContainerRef.current) {
        scrollContainerRef.current.scrollBy({ left: -450, behavior: 'smooth' });
      }
    };

    const scrollRight = () => {
      if (scrollContainerRef.current) {
        scrollContainerRef.current.scrollBy({ left: 450, behavior: 'smooth' });
      }
    };

    return (
      <>
        <div className="tab-description" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0px' }}>
          <p style={{ margin: 0 }}>Your recommended course trajectory, term by term.</p>
          <div className="course-path-navigation">
            <button className="term-nav-button" onClick={scrollLeft}>← Previous Terms</button>
            <button className="term-nav-button" onClick={scrollRight}>Next Terms →</button>
          </div>
        </div>
        <div className="course-path-container">
          <div className="course-path-scroll" ref={scrollContainerRef}>
          {coursePathData.course_path.map((termCourses, termIndex) => (
            <div key={`term-${termIndex}`} className="term-container">
              <h5 className="term-header">Term {termIndex + 1}</h5>
              <div className="term-courses">
                {termCourses.map((courseCode) => (
                  <div key={`${termIndex}-${courseCode}`} className="term-course">
                    {renderCoursePathCard(courseCode, termIndex)}
                  </div>
                ))}
                {termCourses.length === 0 && <p className="no-courses" style={{ color: '#888' }}>No courses</p>}
              </div>
            </div>
          ))}
        </div>
      </div>
      </>
    );
  }

  // Details panel for expanded course
  function renderDetailsPanel() {
    const courseDetails = expandedCourse ? getCourseDetails(expandedCourse) : null;
    const isPrerequisite = courseDetails?.is_prereq || false;

    // Check if course is in recommended_courses
    const isRecommended = coursePathData?.recommended_courses?.includes(expandedCourse);

    // Only show prereq message if it's a prerequisite AND not a recommended course
    const showPrereqMessage = isPrerequisite && activeTab === 'coursePath' && !isRecommended;

    return (
      <>
        <div className={`panel-overlay ${detailsPanelVisible ? 'visible' : ''}`} onClick={() => handleClosePanel()}></div>
        <div className={`course-details-panel ${detailsPanelVisible ? 'visible' : ''}`} ref={detailsPanelRef}>
          <div className="details-header d-flex justify-content-between align-items-center mb-3">
            <h4 className="mb-0">Course Details</h4>
            <CloseButton onClick={() => handleClosePanel()} />
          </div>
          <div className="details-content">
            {courseDetails ? (
              <>
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '8px' }}>
                  <h5 style={{ margin: 0 }}>{courseDetails.course_code}</h5>
                  {courseDetails.must_have_window && courseDetails.must_have_window.length > 0 && (
                    <span
                      style={{
                        background: 'rgba(255, 82, 82, 0.08)',
                        padding: '4px 10px',
                        borderRadius: '4px',
                        border: '1px solid rgba(255, 82, 82, 0.2)',
                        fontSize: '12px',
                        fontWeight: 'normal',
                        whiteSpace: 'nowrap',
                        width: 'fit-content',
                        color: '#b22727',
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: '6px',
                      }}
                    >
                      <Lock size={11} color="#d32f2f" />
                      {(() => {
                        const window = courseDetails.must_have_window;
                        const startTerm = Math.min(...window) + 1;
                        const endTerm = Math.max(...window) + 1;

                        if (startTerm === endTerm) {
                          return `Prioritized for term ${startTerm}`;
                        } else {
                          return `Prioritized between terms ${startTerm} ➞ ${endTerm}`;
                        }
                      })()}
                    </span>
                  )}
                </div>
                <h6 className="mb-3">{courseDetails.course_title || 'No title available'}</h6>
                <div className="course-type-badges mb-3">
                  {courseDetails.course_type === 'major' && <Badge bg="primary" className="me-2">Major Course</Badge>}
                  {courseDetails.course_type === 'complementary' && <Badge bg="info" className="me-2">Complementary Course</Badge>}
                  {courseDetails.is_prereq && <Badge bg="secondary">Prerequisite</Badge>}
                </div>
                {showPrereqMessage && (
                  <div className="text-muted" style={{ fontStyle: 'italic', fontSize: 15, marginBottom: 8 }}>
                    Recommended for prerequisite completion.
                  </div>
                )}
                <div className="mb-3">
                  <h6 className="fw-bold">Description</h6>
                  {courseDetails.course_description ? (
                    <p className="small">{courseDetails.course_description}</p>
                  ) : (
                    <p className="text-muted small">No description available</p>
                  )}
                </div>
                {courseDetails.term_idx !== null && courseDetails.term_idx !== undefined && (
                  <div className="mb-3">
                    <h6 className="fw-bold">Scheduled Term</h6>
                    <p className="small">Term {courseDetails.term_idx + 1}</p>
                  </div>
                )}
              </>
            ) : (
              <div className="text-center text-muted">
                <p>No course details available</p>
              </div>
            )}
          </div>
        </div>
      </>
    );
  }

  // Helper to close panel with animation
  function handleClosePanel() {
    setDetailsPanelVisible(false);
    setTimeout(() => setExpandedCourse(null), 300);
  }

  // Get major and complementary courses from course_bank
  const getMajorCourses = () => {
    if (!coursePathData || !coursePathData.course_bank) return [];
    return Object.values(coursePathData.course_bank).filter(
      course => course.course_type === 'major' && !course.is_prereq
    );
  };

  const getComplementaryCourses = () => {
    if (!coursePathData || !coursePathData.course_bank) return [];
    return Object.values(coursePathData.course_bank).filter(
      course => course.course_type === 'complementary' && !course.is_prereq
    );
  };

  // Render course list (for major/complementary tabs)
  function renderCourseList(courses, tab) {
    if (!courses || courses.length === 0) {
      return <p className="text-muted">No course recommendations available.</p>;
    }

    // Sort courses: scheduled courses first, then unscheduled
    const sortedCourses = [...courses].sort((a, b) => {
      const aScheduled = a.term_idx !== null && a.term_idx !== undefined;
      const bScheduled = b.term_idx !== null && b.term_idx !== undefined;
      if (aScheduled && !bScheduled) return -1;
      if (!aScheduled && bScheduled) return 1;
      return 0;
    });

    return (
      <Row xs={1} md={2} className="g-4">
        {sortedCourses.map((course, idx) => {
          const rankBadgeClass = tab === 'major' ? 'rank-badge-major' : 'rank-badge-complementary';
          return (
            <Col key={course.course_code}>
              <Card className="h-100 shadow-sm border-0" style={{ background: '#fff', borderRadius: 14, marginBottom: 12 }}>
                <Card.Header className="d-flex justify-content-between align-items-center bg-white border-0" style={{ borderRadius: 14 }}>
                  <Badge pill className={rankBadgeClass}>{idx + 1}</Badge>
                  <span className="ms-2 fw-bold" style={{ fontSize: 18 }}>{course.course_code}</span>
                </Card.Header>
                <Card.Body>
                  <Card.Title style={{ fontSize: 20, fontWeight: 500 }}>{course.course_title}</Card.Title>
                  <Card.Text style={{ color: '#555', fontSize: 15 }}>
                    {course.course_description ?
                      course.course_description.substring(0, 180) + (course.course_description.length > 180 ? '...' : '')
                      : 'No description available.'}
                  </Card.Text>
                  {course.term_idx !== null && course.term_idx !== undefined && (
                    <div className="mb-2">
                      <span
                        className="small"
                        style={{
                          padding: '4px 10px',
                          borderRadius: '6px',
                          background: 'rgba(76, 175, 80, 0.1)',
                          border: '1px solid rgba(76, 175, 80, 0.3)',
                          color: '#2e7d32',
                          fontWeight: 500,
                          display: 'inline-block'
                        }}
                      >
                        Scheduled: Term {course.term_idx + 1}
                      </span>
                    </div>
                  )}
                  <div className="text-center mt-2">
                    <Button
                      variant="outline-secondary"
                      size="sm"
                      className="view-details-btn"
                      onClick={e => {
                        e.preventDefault();
                        e.stopPropagation();
                        setExpandedCourse(course.course_code);
                        setDetailsPanelVisible(true);
                      }}
                    >
                      Details
                    </Button>
                  </div>
                </Card.Body>
              </Card>
            </Col>
          );
        })}
      </Row>
    );
  }

  // Main render
  return (
    <div style={{ minHeight: '100vh', background: 'linear-gradient(135deg, #ede9f5 0%, #e5ebf8 100%)' }}>
      <DashboardNavbar onSignOut={handleSignOut} />
      <LeftSidebar />
      <div className="content-with-sidebar">
        <Container className="py-4">
        <h2 className="mb-4" style={{ fontFamily: 'Lora, serif', fontWeight: 400, fontSize: 32, letterSpacing: 0.5, color: '#7b7b93' }}>Courses</h2>
        <Card className="shadow-sm border-0" style={{ borderRadius: 18, background: '#fff', padding: 0 }}>
          <Card.Body style={{ padding: '1rem' }}>
            {loading ? (
              <div className="d-flex flex-column align-items-center justify-content-center" style={{ minHeight: 200 }}>
                <Spinner animation="border" variant="secondary" />
                <span className="mt-3 text-muted">Loading your course path...</span>
              </div>
            ) : error ? (
              <div className="alert alert-danger">{error}</div>
            ) : !coursePathData ? (
              <div className="text-center text-muted">
                <p>No course path found.</p>
                <p className="small">Build and tweak your DreamPath using Compass.</p>
                <Button variant="primary" onClick={() => navigate('/dashboard')} className="mt-3">
                  Go to Dashboard
                </Button>
              </div>
            ) : (
              <Tab.Container activeKey={activeTab} onSelect={handleTabChange}>
                <Nav variant="tabs" className="recommendation-tabs">
                  <Nav.Item>
                    <Nav.Link
                      eventKey="coursePath"
                      className="recommendation-tab"
                      style={{
                        color: activeTab === 'coursePath' ? '#888' : '#888',
                        fontWeight: activeTab === 'coursePath' ? 600 : 500,
                        background: activeTab === 'coursePath' ? '#f3f3f3' : '#fff'
                      }}
                    >
                      <Calendar className="tab-icon me-1" style={{ color: activeTab === 'coursePath' ? '#888' : '#888' }} /> CoursePath
                    </Nav.Link>
                  </Nav.Item>
                  <Nav.Item>
                    <Nav.Link
                      eventKey="major"
                      className="recommendation-tab"
                      style={{
                        color: activeTab === 'major' ? '#8A6BC1' : '#888',
                        fontWeight: activeTab === 'major' ? 600 : 500,
                        background: activeTab === 'major' ? '#f7f0fa' : '#fff'
                      }}
                    >
                      <CheckSquare className="tab-icon me-1" style={{ color: activeTab === 'major' ? '#8A6BC1' : '#888' }} /> Major Courses
                      <Badge bg="primary" pill className="ms-2">{getMajorCourses().length}</Badge>
                    </Nav.Link>
                  </Nav.Item>
                  <Nav.Item>
                    <Nav.Link
                      eventKey="complementary"
                      className="recommendation-tab"
                      style={{
                        color: activeTab === 'complementary' ? '#3873a0' : '#888',
                        fontWeight: activeTab === 'complementary' ? 600 : 500,
                        background: activeTab === 'complementary' ? '#f0f3fa' : '#fff'
                      }}
                    >
                      <Lightbulb className="tab-icon me-1" style={{ color: activeTab === 'complementary' ? '#3873a0' : '#888' }} /> Complementary Courses
                      <Badge bg="info" pill className="ms-2">{getComplementaryCourses().length}</Badge>
                    </Nav.Link>
                  </Nav.Item>
                </Nav>
                <Tab.Content>
                  <Tab.Pane eventKey="coursePath">
                    {renderCoursePath()}
                  </Tab.Pane>
                  <Tab.Pane eventKey="major">
                    <div className="tab-description">
                      <p style={{ margin: 0 }}>Personalized major courses in your course path.</p>
                    </div>
                    {renderCourseList(getMajorCourses(), 'major')}
                  </Tab.Pane>
                  <Tab.Pane eventKey="complementary">
                    <div className="tab-description">
                      <p style={{ margin: 0 }}>Complementary courses from other departments.</p>
                    </div>
                    {renderCourseList(getComplementaryCourses(), 'complementary')}
                  </Tab.Pane>
                </Tab.Content>
              </Tab.Container>
            )}
          </Card.Body>
        </Card>
        {renderDetailsPanel()}
        </Container>
      </div>

      {/* Styles for courses */}
      <style>{`
        .tab-description {
          min-height: 40px !important;
          display: flex;
          align-items: center;
        }

        .course-path-container {
          width: 100%;
          overflow: hidden;
          padding-bottom: 0px;
        }

        .course-path-scroll {
          display: flex;
          gap: 20px;
          overflow-x: auto;
          padding: 20px 0;
          scroll-behavior: smooth;
        }

        .course-path-scroll::-webkit-scrollbar {
          height: 8px;
        }

        .course-path-scroll::-webkit-scrollbar-track {
          background: #f1f1f1;
          border-radius: 10px;
        }

        .course-path-scroll::-webkit-scrollbar-thumb {
          background: #8A6BC1;
          border-radius: 10px;
        }

        .term-container {
          min-width: 250px;
          flex-shrink: 0;
        }

        .term-header {
          font-size: 16px;
          font-weight: 600;
          margin-bottom: 12px;
          color: #333;
        }

        .term-courses {
          display: flex;
          flex-direction: column;
          gap: 10px;
        }

        .term-course {
          width: 100%;
        }

        .course-path-card {
          border-radius: 8px;
          transition: all 0.2s;
        }

        .course-path-card-old {
          border-radius: 8px;
          border: 2px solid #e0e0e0;
          transition: all 0.2s;
        }

        .course-path-card:hover {
          box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }

        .course-path-card.border-primary {
          border-color: #8A6BC1;
        }

        .course-path-card.border-info {
          border-color: #6B8FC7;
        }

        .course-path-navigation {
          display: flex;
          gap: 12px;
          justify-content: center;
        }

        .term-nav-button {
          padding: 8px 16px;
          border: 1px solid #8A6BC1;
          background: white;
          color: #8A6BC1;
          border-radius: 8px;
          cursor: pointer;
          font-size: 14px;
          transition: all 0.2s;
        }

        .term-nav-button:hover {
          background: #8A6BC1;
          color: white;
        }

        .panel-overlay {
          position: fixed;
          top: 0;
          left: 0;
          width: 100%;
          height: 100%;
          background: rgba(0, 0, 0, 0.5);
          z-index: 998;
          opacity: 0;
          visibility: hidden;
          transition: all 0.3s;
        }

        .panel-overlay.visible {
          opacity: 1;
          visibility: visible;
        }

        .course-details-panel {
          position: fixed;
          right: -400px;
          top: var(--navbar-height, 68px);
          width: 400px;
          height: calc(100vh - var(--navbar-height, 68px));
          background: white;
          box-shadow: -4px 0 10px rgba(0,0,0,0.1);
          z-index: 999;
          padding: 24px;
          overflow-y: auto;
          transition: right 0.3s;
          border-top: none;
        }

        .course-details-panel.visible {
          right: 0;
        }

        .rank-badge-major {
          background: linear-gradient(135deg, #8A6BC1 0%, #6B8FC7 100%);
        }

        .rank-badge-complementary {
          background: linear-gradient(135deg, #6B8FC7 0%, #5A9FC7 100%);
        }

        .prereq-badge {
          font-size: 0.7rem;
        }

        .no-courses {
          text-align: center;
          padding: 20px;
          color: #888;
          font-style: italic;
        }
      `}</style>

      {/* Compass Chat Window */}
      <ChatWindow
        userId={user?.id ? String(user.id) : null}
        isOpen={isChatOpen}
        onToggle={() => setIsChatOpen(!isChatOpen)}
      />
    </div>
  );
}

export default Courses;
