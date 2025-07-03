import React, { useState, useEffect, useRef } from 'react';
import { Card, Badge, Row, Col, Button, Nav, Tab, Container, Spinner, CloseButton } from 'react-bootstrap';
import { supabase } from '../lib/supabase';
import DashboardNavbar from './DashboardNavbar';
import { useNavigate } from 'react-router-dom';
import { Calendar, BookmarkStar, Star } from 'react-bootstrap-icons';

// Courses Page: Tabbed interface for Course Path, Major, and Complementary Courses
function Courses() {
  const [user, setUser] = useState(null);
  const [recommendations, setRecommendations] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [activeTab, setActiveTab] = useState('coursePath');
  const navigate = useNavigate();
  const [expandedCourse, setExpandedCourse] = useState(null);
  const [detailsPanelVisible, setDetailsPanelVisible] = useState(false);
  const detailsPanelRef = useRef(null);
  const scrollContainerRef = useRef(null);

  // Fetch user and recommendations on mount
  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      try {
        // Get user session
        const { data: { session }, error: sessionError } = await supabase.auth.getSession();
        if (sessionError) throw sessionError;
        if (!session) {
          navigate('/login');
          return;
        }
        setUser(session.user);
        // Get most recent dreampath_iteration for user
        const { data: iterations, error: iterError } = await supabase
          .from('dreampath_iterations')
          .select('*')
          .eq('user_id', session.user.id)
          .order('created_at', { ascending: false });
        if (iterError) throw iterError;
        if (!iterations || iterations.length === 0) {
          setRecommendations(null);
          setLoading(false);
          return;
        }
        const iterationId = iterations[0].id;
        // Fetch recommendations for this iteration
        const recsResp = await fetch(`/api/recommendations/${iterationId}`);
        if (!recsResp.ok) throw new Error('Failed to fetch recommendations');
        const recsData = await recsResp.json();
        setRecommendations(recsData);
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, [navigate]);

  // Tab change handler
  const handleTabChange = (tab) => setActiveTab(tab);

  // Helper: Format parameter names
  function formatParameterName(parameter) {
    switch(parameter) {
      case 'college_interests': return 'College Interests';
      case 'post_grad_goal': return 'Post-Graduation Goal';
      case 'long_term_goal': return 'Long-Term Aspirations';
      default: return parameter.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
    }
  }

  // Helper to find course details across all sources
  const findCourseDetails = (courseCode) => {
    if (!recommendations) return null;
    // First check in course path
    for (const term of recommendations.coursePath || []) {
      for (const course of term) {
        if (typeof course === 'object' && course.courseCode === courseCode) {
          return course;
        }
      }
    }
    // Check in major recommendations
    const majorCourse = (recommendations.majorRecommendations || []).find(
      course => course.courseCode === courseCode
    );
    // Check in complementary recommendations
    const complementaryCourse = (recommendations.complementaryRecommendations || []).find(
      course => course.courseCode === courseCode
    );
    if (majorCourse && complementaryCourse) {
      return {
        ...majorCourse,
        ...complementaryCourse,
        isMajor: true,
        isComplementary: true,
        majorTotalScore: majorCourse.totalScore,
        complementaryTotalScore: complementaryCourse.totalScore,
        majorParameterScores: majorCourse.parameterScores,
        complementaryParameterScores: complementaryCourse.parameterScores
      };
    }
    if (majorCourse) {
      return {
        ...majorCourse,
        isMajor: true,
        isComplementary: false,
        majorTotalScore: majorCourse.totalScore,
        majorParameterScores: majorCourse.parameterScores
      };
    }
    if (complementaryCourse) {
      return {
        ...complementaryCourse,
        isMajor: false,
        isComplementary: true,
        complementaryTotalScore: complementaryCourse.totalScore,
        complementaryParameterScores: complementaryCourse.parameterScores
      };
    }
    return { courseCode };
  };

  // Card for each course in the course path
  const renderCoursePathCard = (course) => {
    if (!course) return null;
    const courseCode = typeof course === 'string' ? course : course.courseCode;
    const isMajor = course.isMajor || false;
    const isComplementary = course.isComplementary || false;
    const isPrerequisite = course.isPrerequisite || false;
    let borderClass = 'course-path-card';
    if (isMajor) borderClass += ' border-primary';
    else if (isComplementary) borderClass += ' border-info';
    else borderClass += ' border-secondary';
    return (
      <Card className={borderClass}>
        <Card.Header className="d-flex justify-content-between align-items-center p-2">
          <span className="fw-bold">{courseCode}</span>
          <div className="ms-auto d-flex gap-1">
            {isPrerequisite && <Badge bg="secondary" pill className="prereq-badge">Prereq</Badge>}
            {isMajor && <Badge bg="primary" pill>Major</Badge>}
            {isComplementary && <Badge bg="info" pill>Comp</Badge>}
          </div>
        </Card.Header>
        <Card.Body className="p-2">
          {course.courseTitle && (
            <p className="small mb-2 text-truncate" title={course.courseTitle}>{course.courseTitle}</p>
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
      </Card>
    );
  };

  // Term-by-term course path interface
  function renderCoursePath() {
    if (!recommendations || !recommendations.coursePath || recommendations.coursePath.length === 0) {
      return <p className="text-muted">No course path available.</p>;
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
      <div className="course-path-container">
        <div className="course-path-scroll" ref={scrollContainerRef}>
          {(recommendations.coursePath || []).map((termCourses, termIndex) => (
            <div key={`term-${termIndex}`} className="term-container">
              <h5 className="term-header">Term {termIndex + 1}</h5>
              <div className="term-courses">
                {termCourses.map((course, courseIndex) => (
                  <div key={`${termIndex}-${courseIndex}`} className="term-course">
                    {renderCoursePathCard(course)}
                  </div>
                ))}
                {termCourses.length === 0 && <p className="no-courses" style={{ color: '#888' }}>No courses</p>}
              </div>
            </div>
          ))}
        </div>
        <div className="course-path-navigation mt-3">
          <button className="term-nav-button" onClick={scrollLeft}>← Previous Terms</button>
          <button className="term-nav-button" onClick={scrollRight}>Next Terms →</button>
        </div>
      </div>
    );
  }

  // Details panel for expanded course
  function renderDetailsPanel() {
    const courseDetails = expandedCourse ? findCourseDetails(expandedCourse) : null;
    const majorScore = courseDetails?.majorTotalScore;
    const complementaryScore = courseDetails?.complementaryTotalScore;
    const majorParameterScores = courseDetails?.majorParameterScores || {};
    const complementaryParameterScores = courseDetails?.complementaryParameterScores || {};
    const isPrerequisite = courseDetails?.isPrerequisite;
    const showPrereqMessage = isPrerequisite && activeTab === 'coursePath';
    
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
                <h5>{courseDetails.courseCode}</h5>
                <h6 className="mb-3">{courseDetails.courseTitle || 'No title available'}</h6>
                <div className="course-type-badges mb-3">
                  {courseDetails.isMajor && <Badge bg="primary" className="me-2">Major Course</Badge>}
                  {courseDetails.isComplementary && <Badge bg="info" className="me-2">Complementary Course</Badge>}
                  {courseDetails.isPrerequisite && <Badge bg="secondary">Prerequisite</Badge>}
                </div>
                <div className="course-scores mb-3">
                  <h6 className="fw-bold">Course Scores</h6>
                  {showPrereqMessage ? (
                    <div className="text-muted" style={{ fontStyle: 'italic', fontSize: 15, marginBottom: 8 }}>
                      Recommended for prerequisite completion.
                    </div>
                  ) : (
                    <div className="score-breakdown">
                      {majorScore !== undefined && (
                        <div className="d-flex justify-content-between small mb-1">
                          <span>Major Score</span>
                          <span className="fw-bold">{majorScore === null || isNaN(majorScore) ? '--' : majorScore.toFixed(1)}</span>
                        </div>
                      )}
                      {complementaryScore !== undefined && (
                        <div className="d-flex justify-content-between small mb-1">
                          <span>Complementary Score</span>
                          <span className="fw-bold">{complementaryScore === null || isNaN(complementaryScore) ? '--' : complementaryScore.toFixed(1)}</span>
                        </div>
                      )}
                    </div>
                  )}
                </div>
                <div className="mb-3">
                  <h6 className="fw-bold">Description</h6>
                  {courseDetails.description ? (
                    <p className="small">{courseDetails.description}</p>
                  ) : (
                    <p className="text-muted small">No description available</p>
                  )}
                </div>
                {courseDetails.prerequisites && (
                  <div className="mb-3">
                    <h6 className="fw-bold">Prerequisites</h6>
                    <p className="small">{courseDetails.prerequisites}</p>
                  </div>
                )}
                {courseDetails.degreeReq && (
                  <div className="mb-3">
                    <h6 className="fw-bold">Degree Requirements</h6>
                    <p className="small">{courseDetails.degreeReq}</p>
                  </div>
                )}
                {!showPrereqMessage && courseDetails.isMajor && majorParameterScores && Object.entries(majorParameterScores).some(([_, score]) => score !== null && !isNaN(score) && score > 0) && (
                  <div className="mb-3">
                    <h6 className="fw-bold">Major Recommendation Factors</h6>
                    <div className="score-breakdown">
                      {Object.entries(majorParameterScores)
                        .filter(([_, score]) => score !== null && !isNaN(score) && score > 0)
                        .map(([parameter, score]) => (
                          <div key={`major-${parameter}`} className="d-flex justify-content-between small mb-1">
                            <span>{formatParameterName(parameter)}</span>
                            <span>{score.toFixed(1)}</span>
                          </div>
                        ))}
                    </div>
                  </div>
                )}
                {!showPrereqMessage && courseDetails.isComplementary && complementaryParameterScores && Object.entries(complementaryParameterScores).some(([_, score]) => score !== null && !isNaN(score) && score > 0) && (
                  <div className="mb-3">
                    <h6 className="fw-bold">Complementary Recommendation Factors</h6>
                    <div className="score-breakdown">
                      {Object.entries(complementaryParameterScores)
                        .filter(([_, score]) => score !== null && !isNaN(score) && score > 0)
                        .map(([parameter, score]) => (
                          <div key={`complementary-${parameter}`} className="d-flex justify-content-between small mb-1">
                            <span>{formatParameterName(parameter)}</span>
                            <span>{score.toFixed(1)}</span>
                          </div>
                        ))}
                    </div>
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
    setTimeout(() => setExpandedCourse(null), 300); // Wait for slide-out
  }

  // Render course cards (for major/complementary)
  function renderCourseList(courses, tab) {
    if (!courses || courses.length === 0) {
      return <p className="text-muted">No course recommendations available.</p>;
    }
    // Filter out prerequisites
    let filteredCourses = courses.filter(course => !course.isPrerequisite);
    if (filteredCourses.length === 0) {
      return <p className="text-muted">No course recommendations available.</p>;
    }
    // Sort by score descending
    filteredCourses = filteredCourses.sort((a, b) => {
      let aScore = a.totalScore;
      let bScore = b.totalScore;
      if (tab === 'major') {
        aScore = a.majorTotalScore !== undefined ? a.majorTotalScore : a.totalScore;
        bScore = b.majorTotalScore !== undefined ? b.majorTotalScore : b.totalScore;
      }
      if (tab === 'complementary') {
        aScore = a.complementaryTotalScore !== undefined ? a.complementaryTotalScore : a.totalScore;
        bScore = b.complementaryTotalScore !== undefined ? b.complementaryTotalScore : b.totalScore;
      }
      return (bScore || 0) - (aScore || 0);
    });
    return (
      <Row xs={1} md={2} className="g-4">
        {filteredCourses.map((course, idx) => {
          let score = course.totalScore;
          if (tab === 'major' && course.majorTotalScore !== undefined) score = course.majorTotalScore;
          if (tab === 'complementary' && course.complementaryTotalScore !== undefined) score = course.complementaryTotalScore;
          let rankBadgeClass = '';
          if (tab === 'major') rankBadgeClass = 'rank-badge-major';
          if (tab === 'complementary') rankBadgeClass = 'rank-badge-complementary';
          return (
            <Col key={course.courseCode}>
              <Card className="h-100 shadow-sm border-0" style={{ background: '#fff', borderRadius: 14, marginBottom: 12 }}>
                <Card.Header className="d-flex justify-content-between align-items-center bg-white border-0" style={{ borderRadius: 14 }}>
                  <Badge pill className={rankBadgeClass}>{idx + 1}</Badge>
                  <span className="ms-2 fw-bold" style={{ fontSize: 18 }}>{course.courseCode}</span>
                  <Badge pill className="ms-auto score-badge" title="Recommendation score">
                    {typeof score === 'number' && !isNaN(score) ? score.toFixed(1) : '--'}
                  </Badge>
                </Card.Header>
                <Card.Body>
                  <Card.Title style={{ fontSize: 20, fontWeight: 500 }}>{course.courseTitle}</Card.Title>
                  <Card.Text style={{ color: '#555', fontSize: 15 }}>
                    {course.description ? course.description.substring(0, 180) + (course.description.length > 180 ? '...' : '') : 'No description available.'}
                  </Card.Text>
                  {course.prerequisites && (
                    <div className="mb-2">
                      <span className="fw-bold small">Prerequisites: </span>
                      <span className="small">{course.prerequisites}</span>
                    </div>
                  )}
                  {course.degreeReq && (
                    <div className="mb-2">
                      <span className="fw-bold small">Degree Requirements: </span>
                      <span className="small">{course.degreeReq}</span>
                    </div>
                  )}
                  <div className="score-breakdown mt-2">
                    {course.parameterScores && Object.entries(course.parameterScores).map(([parameter, score]) => (
                      <div key={parameter} className="d-flex justify-content-between small mb-1">
                        <span>{formatParameterName(parameter)}</span>
                        <span>{isNaN(score) || score <= 0 ? '--' : score.toFixed(1)}</span>
                      </div>
                    ))}
                  </div>
                  <div className="text-center mt-2">
                    <Button
                      variant="outline-secondary"
                      size="sm"
                      className="view-details-btn"
                      onClick={e => {
                        e.preventDefault();
                        e.stopPropagation();
                        setExpandedCourse(course.courseCode);
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
    <div style={{ minHeight: '100vh', background: '#f8f6fc' }}>
      <DashboardNavbar />
      <Container className="py-4">
        <h2 className="mb-4" style={{ fontFamily: 'Lora, serif', fontWeight: 400, fontSize: 32, letterSpacing: 0.5 }}>Courses</h2>
        <Card className="shadow-sm border-0" style={{ borderRadius: 18, background: '#fff', padding: 0 }}>
          <Card.Body style={{ padding: '2.5rem 2rem 0 2rem' }}>
            {loading ? (
              <div className="d-flex flex-column align-items-center justify-content-center" style={{ minHeight: 200 }}>
                <Spinner animation="border" variant="secondary" />
                <span className="mt-3 text-muted">Loading your course recommendations...</span>
              </div>
            ) : error ? (
              <div className="alert alert-danger">{error}</div>
            ) : !recommendations ? (
              <div className="text-center text-muted">No recommendations found. Build your DreamPath on the dashboard first.</div>
            ) : (
              <Tab.Container activeKey={activeTab} onSelect={handleTabChange}>
                <Nav variant="tabs" className="mb-4 recommendation-tabs">
                  <Nav.Item>
                    <Nav.Link eventKey="coursePath" className="recommendation-tab" style={{ color: activeTab === 'coursePath' ? '#888' : '#888', fontWeight: activeTab === 'coursePath' ? 600 : 500, background: activeTab === 'coursePath' ? '#f3f3f3' : '#fff' }}>
                      <Calendar className="tab-icon me-1" style={{ color: activeTab === 'coursePath' ? '#888' : '#888' }} /> Course Path
                    </Nav.Link>
                  </Nav.Item>
                  <Nav.Item>
                    <Nav.Link eventKey="major" className="recommendation-tab" style={{ color: activeTab === 'major' ? '#8A6BC1' : '#888', fontWeight: activeTab === 'major' ? 600 : 500, background: activeTab === 'major' ? '#f7f0fa' : '#fff' }}>
                      <BookmarkStar className="tab-icon me-1" style={{ color: activeTab === 'major' ? '#8A6BC1' : '#888' }} /> Major Courses
                      <Badge bg="primary" pill className="ms-2">{(recommendations.majorRecommendations || []).length}</Badge>
                    </Nav.Link>
                  </Nav.Item>
                  <Nav.Item>
                    <Nav.Link eventKey="complementary" className="recommendation-tab" style={{ color: activeTab === 'complementary' ? '#3873a0' : '#888', fontWeight: activeTab === 'complementary' ? 600 : 500, background: activeTab === 'complementary' ? '#f0f3fa' : '#fff' }}>
                      <Star className="tab-icon me-1" style={{ color: activeTab === 'complementary' ? '#3873a0' : '#888' }} /> Complementary Courses
                      <Badge bg="info" pill className="ms-2">{(recommendations.complementaryRecommendations || []).length}</Badge>
                    </Nav.Link>
                  </Nav.Item>
                </Nav>
                <Tab.Content>
                  <Tab.Pane eventKey="coursePath">
                    <div className="tab-description">
                      <p>Your recommended course trajectory, term by term.</p>
                    </div>
                    {renderCoursePath()}
                  </Tab.Pane>
                  <Tab.Pane eventKey="major">
                    <div className="tab-description">
                      <p>Personalized major courses that support your interests and goals.</p>
                    </div>
                    {renderCourseList(recommendations.majorRecommendations || [], 'major')}
                  </Tab.Pane>
                  <Tab.Pane eventKey="complementary">
                    <div className="tab-description">
                      <p>Courses from other departments that support your aspirations.</p>
                    </div>
                    {renderCourseList(recommendations.complementaryRecommendations || [], 'complementary')}
                  </Tab.Pane>
                </Tab.Content>
              </Tab.Container>
            )}
          </Card.Body>
        </Card>
        {/* Always render details panel for animation */}
        {renderDetailsPanel()}
      </Container>
    </div>
  );
}

export default Courses; 