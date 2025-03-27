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
  
  // Handle tab changes with synchronized panel closing
  const handleTabChange = (newTab) => {
    if (activeTab === 'coursePath' && detailsPanelVisible) {
      // First hide the panel
      setDetailsPanelVisible(false);
      
      // Then change the tab after the panel transition completes
      setTimeout(() => {
        setActiveTab(newTab);
        setExpandedCourse(null);
      }, 300); // Match the CSS transition time
    } else {
      // If panel isn't visible, just change tabs immediately
      setActiveTab(newTab);
      setExpandedCourse(null);
    }
  };
  
  // Handle clicking outside the details panel to close it
  useEffect(() => {
    function handleClickOutside(event) {
      if (detailsPanelRef.current && !detailsPanelRef.current.contains(event.target) && 
          !event.target.closest('.view-details-btn')) {
        setDetailsPanelVisible(false);
      }
    }
    
    document.addEventListener("mousedown", handleClickOutside);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [detailsPanelRef]);

  // Toggle course details - different behavior based on active tab
  const toggleCourse = (courseCode) => {
    if (activeTab === 'coursePath') {
      // For course path tab, use the slide-out panel
      if (expandedCourse === courseCode) {
        setExpandedCourse(null);
        setDetailsPanelVisible(false);
      } else {
        // If we're already showing a course and just switching to another
        if (detailsPanelVisible) {
          setExpandedCourse(courseCode);
        } else {
          setExpandedCourse(courseCode);
          setDetailsPanelVisible(true);
        }
      }
    } else {
      // For major and complementary tabs, just toggle the expanded state
      setExpandedCourse(expandedCourse === courseCode ? null : courseCode);
    }
  };

  // Close button handler for the slide-out panel
  const handleClosePanel = () => {
    setDetailsPanelVisible(false);
    setTimeout(() => {
      if (!detailsPanelVisible) {
        setExpandedCourse(null);
      }
    }, 300);
  };

  // Find the maximum score for scaling
  const allScores = [...majorRecommendations, ...complementaryRecommendations].map(course => course.totalScore);
  const maxScore = allScores.length > 0 ? Math.max(...allScores.filter(score => !isNaN(score))) : 1;

  // Find course details across all recommendation types
  const findCourseDetails = (courseCode) => {
    // Look through all terms in the course path
    for (const term of coursePath) {
      for (const course of term) {
        if (typeof course === 'object' && course.courseCode === courseCode) {
          return course;
        }
      }
    }
    
    // If not found in course path, check major recommendations
    const majorCourse = majorRecommendations.find(c => c.courseCode === courseCode);
    if (majorCourse) return majorCourse;
    
    // If not found in major, check complementary recommendations
    const compCourse = complementaryRecommendations.find(c => c.courseCode === courseCode);
    if (compCourse) return compCourse;
    
    // If not found anywhere, return basic info
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
                  variant="outline-primary" 
                  size="sm" 
                  onClick={() => toggleCourse(course.courseCode)}
                >
                  {expandedCourse === course.courseCode ? 'Show Less' : 'View More'}
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
              variant="outline-primary" 
              size="sm" 
              onClick={() => toggleCourse(courseCode)}
              className="view-details-btn"
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
    // Only render for course path tab and when a course is expanded
    if (activeTab !== 'coursePath' || !detailsPanelVisible || !expandedCourse) return null;
    
    const courseDetails = findCourseDetails(expandedCourse);
    
    return (
      <div 
        className="course-details-panel visible"
        ref={detailsPanelRef}
      >
        <div className="details-header">
          <h4>Course Details</h4>
          <CloseButton onClick={handleClosePanel} />
        </div>
        
        <div className="details-content">
          <h5>{courseDetails.courseCode}</h5>
          <h6>{courseDetails.courseTitle}</h6>
          
          {courseDetails.description ? (
            <div className="mb-3">
              <p className="small">{courseDetails.description}</p>
            </div>
          ) : (
            <p className="text-muted small">No description available</p>
          )}
          
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
          
          {courseDetails.parameterScores && Object.keys(courseDetails.parameterScores).length > 0 && (
            <>
              <h6 className="fw-bold">Recommendation Factors</h6>
              <div className="score-breakdown">
                {Object.entries(courseDetails.parameterScores).map(([parameter, score]) => (
                  <div key={parameter} className="d-flex justify-content-between small mb-1">
                    <span>{formatParameterName(parameter)}</span>
                    <span>{isNaN(score) || score <= 0 ? "--" : score.toFixed(1)}</span>
                  </div>
                ))}
              </div>
            </>
          )}
        </div>
      </div>
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