import React, { useState, useRef, useEffect } from 'react';
import { Card, Badge, Row, Col, Button, Nav, Tab, Container, CloseButton } from 'react-bootstrap';

function CourseRecommendations({ recommendations }) {
  const [expandedCourse, setExpandedCourse] = useState(null);
  const [activeTab, setActiveTab] = useState('coursePath');
  const [detailsPanelVisible, setDetailsPanelVisible] = useState(false);
  const detailsPanelRef = useRef(null);
  
  // Extract the different types of recommendations
  const majorRecommendations = recommendations.majorRecommendations || [];
  const complementaryRecommendations = recommendations.complementaryRecommendations || [];
  const coursePath = recommendations.coursePath || [];
  
  // Handle tab changes
  const handleTabChange = (newTab) => {
    setActiveTab(newTab);
    setExpandedCourse(null);
    setDetailsPanelVisible(false);
  };
  
  // Handle clicking outside the details panel to close it
  useEffect(() => {
    function handleClickOutside(event) {
      if (detailsPanelRef.current && 
          !detailsPanelRef.current.contains(event.target) && 
          !event.target.closest('.view-details-btn')) {
        setDetailsPanelVisible(false);
      }
    }
    
    document.addEventListener("mousedown", handleClickOutside);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [detailsPanelRef]);

  // Toggle course details for major and complementary tabs
  const toggleCourse = (courseCode) => {
    if (activeTab === 'coursePath') {
      // For course path tab, show the details panel
      setExpandedCourse(courseCode);
      setDetailsPanelVisible(true);
    } else {
      // For major and complementary tabs, just toggle the expanded state
      setExpandedCourse(expandedCourse === courseCode ? null : courseCode);
    }
  };

  // Close button handler for the slide-out panel
  const handleClosePanel = () => {
    setDetailsPanelVisible(false);
  };

  // Find the maximum score for scaling
  const allScores = [...majorRecommendations, ...complementaryRecommendations].map(course => course.totalScore);
  const maxScore = allScores.length > 0 ? Math.max(...allScores.filter(score => !isNaN(score))) : 1;

  // Find course details across all sources
  const findCourseDetails = (courseCode) => {
    // First check in course path
    for (const term of coursePath) {
      for (const course of term) {
        if (typeof course === 'object' && course.courseCode === courseCode) {
          return course;
        }
      }
    }
    
    // Check in major recommendations
    const majorCourse = majorRecommendations.find(
      course => course.courseCode === courseCode
    );
    
    // Check in complementary recommendations
    const complementaryCourse = complementaryRecommendations.find(
      course => course.courseCode === courseCode
    );
    
    // If found in both, merge the details
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
    
    // If found in only one, return that with appropriate flags
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
    
    // If not found anywhere, return a basic object with the course code
    return { courseCode };
  };

  const renderCourseList = (courses) => {
    if (courses.length === 0) {
      return <p>No course recommendations available.</p>;
    }

    return (
      <Row xs={1} md={2} className="g-4">
        {courses.map((course, index) => (
          <Col key={course.courseCode}>
            <Card className="h-100 course-card">
              <Card.Header className="d-flex justify-content-between align-items-center">
                <Badge bg="primary" pill className="course-number">
                  {index + 1}
                </Badge>
                <span className="ms-2 fw-bold">{course.courseCode}</span>
                <Badge 
                  bg="info" 
                  pill 
                  className="ms-auto"
                  title="Recommendation score"
                >
                  {isNaN(course.totalScore) ? "--" : course.totalScore.toFixed(1)}
                </Badge>
              </Card.Header>
              
              <Card.Body>
                <Card.Title>{course.courseTitle}</Card.Title>
                <Card.Text>
                  {expandedCourse === course.courseCode 
                    ? course.description 
                    : `${course.description?.substring(0, 150) || "No description available"}${course.description?.length > 150 ? '...' : ''}`}
                </Card.Text>
                
                {expandedCourse === course.courseCode && (
                  <>
                    {course.prerequisites && (
                      <div className="mb-3">
                        <h6 className="fw-bold">Prerequisites</h6>
                        <p className="small">{course.prerequisites}</p>
                      </div>
                    )}
                    
                    {course.degreeReq && (
                      <div className="mb-3">
                        <h6 className="fw-bold">Degree Requirements</h6>
                        <p className="small">{course.degreeReq}</p>
                      </div>
                    )}
                    
                    <h6 className="fw-bold">Recommendation Factors</h6>
                    <div className="score-breakdown">
                      {Object.entries(course.parameterScores || {}).map(([parameter, score]) => (
                        <div key={parameter} className="d-flex justify-content-between small mb-1">
                          <span>{formatParameterName(parameter)}</span>
                          <span>{isNaN(score) || score <= 0 ? "--" : score.toFixed(1)}</span>
                        </div>
                      ))}
                    </div>
                  </>
                )}
              </Card.Body>
              
              <Card.Footer className="text-center">
                <Button 
                  variant={expandedCourse === course.courseCode ? "outline-secondary" : "outline-primary"} 
                  size="sm"
                  onClick={() => toggleCourse(course.courseCode)}
                >
                  {expandedCourse === course.courseCode ? "Show Less" : "Show More"}
                </Button>
              </Card.Footer>
            </Card>
          </Col>
        ))}
      </Row>
    );
  };

  const renderCoursePathCard = (course) => {
    if (!course) return null;
    
    // Check if course is a string (old format) or an object (new format)
    const courseCode = typeof course === 'string' ? course : course.courseCode;
    
    // Get course properties
    const isMajor = course.isMajor || false;
    const isComplementary = course.isComplementary || false;
    const isPrerequisite = course.isPrerequisite || false;
    
    // Determine the left border color based on priority (major > complementary > prerequisite)
    let borderClass = "course-path-card";
    if (isMajor) {
      borderClass += " border-primary"; // Purple for major
    } else if (isComplementary) {
      borderClass += " border-info"; // Teal for complementary
    } else {
      borderClass += " border-secondary"; // Gray for prerequisite
    }
    
    return (
      <Card className={borderClass}>
        <Card.Header className="d-flex justify-content-between align-items-center p-2">
          <span className="fw-bold">{courseCode}</span>
          <div className="ms-auto d-flex gap-1">
            {isPrerequisite && (
              <Badge 
                bg="secondary" 
                pill
                className="prereq-badge"
              >
                Prereq
              </Badge>
            )}
            {isMajor && (
              <Badge 
                bg="primary" 
                pill
              >
                Major
              </Badge>
            )}
            {isComplementary && (
              <Badge 
                bg="info" 
                pill
              >
                Comp
              </Badge>
            )}
          </div>
        </Card.Header>
        <Card.Body className="p-2">
          {course.courseTitle && (
            <p className="small mb-2 text-truncate" title={course.courseTitle}>
              {course.courseTitle}
            </p>
          )}
          
          <div className="text-center">
            <Button 
              variant="outline-secondary" 
              size="sm" 
              className="view-details-btn"
              onClick={(e) => {
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

  const renderCoursePath = () => {
    if (!coursePath || coursePath.length === 0) {
      return <p>No course path available.</p>;
    }

    // Reference for scrolling
    const scrollContainerRef = useRef(null);
    
    // Navigation buttons
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
          {coursePath.map((termCourses, termIndex) => (
            <div key={`term-${termIndex}`} className="term-container">
              <h5 className="term-header">Term {termIndex + 1}</h5>
              <div className="term-courses">
                {termCourses.map((course, courseIndex) => (
                  <div key={`${termIndex}-${courseIndex}`} className="term-course">
                    {renderCoursePathCard(course)}
                  </div>
                ))}
                {termCourses.length === 0 && (
                  <p className="no-courses">No courses</p>
                )}
              </div>
            </div>
          ))}
        </div>
        
        {/* Navigation controls at the bottom */}
        <div className="course-path-navigation mt-3">
          <button className="term-nav-button" onClick={scrollLeft}>
            ← Previous Terms
          </button>
          <button className="term-nav-button" onClick={scrollRight}>
            Next Terms →
          </button>
        </div>
      </div>
    );
  };

  const renderDetailsPanel = () => {
    // Only render when a course is expanded and panel is visible
    if (!detailsPanelVisible || !expandedCourse) return null;
    
    // Find the course details across all sources
    const courseDetails = findCourseDetails(expandedCourse);
    if (!courseDetails) return null;
    
    // Extract scores for display - add null checks
    const majorScore = courseDetails.majorTotalScore;
    const complementaryScore = courseDetails.complementaryTotalScore;
    
    // Combine parameter scores for display - add null checks
    const majorParameterScores = courseDetails.majorParameterScores || {};
    const complementaryParameterScores = courseDetails.complementaryParameterScores || {};
    
    return (
      <>
        <div 
          className={`panel-overlay ${detailsPanelVisible ? 'visible' : ''}`}
          onClick={handleClosePanel}
        ></div>
        
        <div 
          className={`course-details-panel ${detailsPanelVisible ? 'visible' : ''}`}
          ref={detailsPanelRef}
        >
          <div className="details-header d-flex justify-content-between align-items-center mb-3">
            <h4 className="mb-0">Course Details</h4>
            <CloseButton onClick={handleClosePanel} />
          </div>
          
          <div className="details-content">
            <h5>{courseDetails.courseCode}</h5>
            <h6 className="mb-3">{courseDetails.courseTitle || "No title available"}</h6>
            
            {/* Course type badges */}
            <div className="course-type-badges mb-3">
              {courseDetails.isMajor && <Badge bg="primary" className="me-2">Major Course</Badge>}
              {courseDetails.isComplementary && <Badge bg="info" className="me-2">Complementary Course</Badge>}
              {courseDetails.isPrerequisite && <Badge bg="secondary">Prerequisite</Badge>}
            </div>
            
            {/* Course scores section - with null checks */}
            {(majorScore !== undefined || complementaryScore !== undefined) && (
              <div className="course-scores mb-3">
                <h6 className="fw-bold">Course Scores</h6>
                <div className="score-breakdown">
                  {majorScore !== undefined && (
                    <div className="d-flex justify-content-between small mb-1">
                      <span>Major Score</span>
                      <span className="fw-bold">
                        {majorScore === null || isNaN(majorScore) ? "--" : majorScore.toFixed(1)}
                      </span>
                    </div>
                  )}
                  {complementaryScore !== undefined && (
                    <div className="d-flex justify-content-between small mb-1">
                      <span>Complementary Score</span>
                      <span className="fw-bold">
                        {complementaryScore === null || isNaN(complementaryScore) ? "--" : complementaryScore.toFixed(1)}
                      </span>
                    </div>
                  )}
                </div>
              </div>
            )}
            
            {/* Course description */}
            <div className="mb-3">
              <h6 className="fw-bold">Description</h6>
              {courseDetails.description ? (
                <p className="small">{courseDetails.description}</p>
              ) : (
                <p className="text-muted small">No description available</p>
              )}
            </div>
            
            {/* Prerequisites */}
            {courseDetails.prerequisites && (
              <div className="mb-3">
                <h6 className="fw-bold">Prerequisites</h6>
                <p className="small">{courseDetails.prerequisites}</p>
              </div>
            )}
            
            {/* Degree Requirements */}
            {courseDetails.degreeReq && (
              <div className="mb-3">
                <h6 className="fw-bold">Degree Requirements</h6>
                <p className="small">{courseDetails.degreeReq}</p>
              </div>
            )}
            
            {/* Major Recommendation Factors - with null checks */}
            {courseDetails.isMajor && majorParameterScores && 
             Object.entries(majorParameterScores).some(([_, score]) => score !== null && !isNaN(score) && score > 0) && (
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
            
            {/* Complementary Recommendation Factors - with null checks */}
            {courseDetails.isComplementary && complementaryParameterScores && 
             Object.entries(complementaryParameterScores).some(([_, score]) => score !== null && !isNaN(score) && score > 0) && (
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
          </div>
        </div>
      </>
    );
  };

  return (
    <div className="recommendations-container">
      <Tab.Container activeKey={activeTab} onSelect={handleTabChange}>
        <Nav variant="tabs" className="mb-4 recommendation-tabs">
          <Nav.Item>
            <Nav.Link eventKey="coursePath" className="recommendation-tab">
              <span className="tab-icon path-icon">🗓️</span> Course Path
            </Nav.Link>
          </Nav.Item>
          <Nav.Item>
            <Nav.Link eventKey="major" className="recommendation-tab">
              <span className="tab-icon major-icon">📚</span> Major Courses
              <Badge bg="primary" pill className="ms-2">{majorRecommendations.length}</Badge>
            </Nav.Link>
          </Nav.Item>
          <Nav.Item>
            <Nav.Link eventKey="complementary" className="recommendation-tab">
              <span className="tab-icon complementary-icon">🌟</span> Complementary Courses
              <Badge bg="info" pill className="ms-2">{complementaryRecommendations.length}</Badge>
            </Nav.Link>
          </Nav.Item>
        </Nav>
        
        <Tab.Content>
          <Tab.Pane eventKey="coursePath">
            <div className="tab-description mb-3">
              <p>Your recommended course trajectory.</p>
            </div>
            <div className="course-path-legend">
              <div className="legend-item">
                <div className="legend-color major"></div>
                <span>Major Courses</span>
              </div>
              <div className="legend-item">
                <div className="legend-color complementary"></div>
                <span>Complementary Courses</span>
              </div>
              <div className="legend-item">
                <div className="legend-color prerequisite"></div>
                <span>Prerequisites</span>
              </div>
            </div>
            {renderCoursePath()}
          </Tab.Pane>
          <Tab.Pane eventKey="major">
            <div className="tab-description mb-3">
              <p>These courses within your major align with your interests and goals.</p>
            </div>
            {renderCourseList(majorRecommendations)}
          </Tab.Pane>
          <Tab.Pane eventKey="complementary">
            <div className="tab-description mb-3">
              <p>These courses from other departments complement your major and support your aspirations.</p>
            </div>
            {renderCourseList(complementaryRecommendations)}
          </Tab.Pane>
        </Tab.Content>
      </Tab.Container>
      
      {renderDetailsPanel()}
    </div>
  );
}

// Helper functions
function formatParameterName(parameter) {
  switch(parameter) {
    case 'college_interests':
      return 'College Interests';
    case 'post_grad_goal':
      return 'Post-Graduation Goal';
    case 'long_term_goal':
      return 'Long-Term Aspirations';
    default:
      return parameter.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
  }
}

export default CourseRecommendations;