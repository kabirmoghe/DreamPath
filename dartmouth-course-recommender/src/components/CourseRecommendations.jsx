import React, { useState } from 'react';
import { Card, Badge, Row, Col, Button, Nav, Tab, Container } from 'react-bootstrap';

function CourseRecommendations({ recommendations }) {
  const [expandedCourse, setExpandedCourse] = useState(null);
  const [activeTab, setActiveTab] = useState('coursePath');
  
  // Extract the different types of recommendations
  const majorRecommendations = recommendations.majorRecommendations || [];
  const complementaryRecommendations = recommendations.complementaryRecommendations || [];
  const coursePath = recommendations.coursePath || [];

  const toggleCourse = (courseCode) => {
    setExpandedCourse(expandedCourse === courseCode ? null : courseCode);
  };

  // Find the maximum score for scaling (across both recommendation types)
  const allScores = [...majorRecommendations, ...complementaryRecommendations].map(course => course.totalScore);
  const maxScore = allScores.length > 0 ? Math.max(...allScores.filter(score => !isNaN(score))) : 1;

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
                  {expandedCourse === course.courseCode ? 'Show Less' : 'Show More'}
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
    
    return (
      <Card className="h-100 course-path-card">
        <Card.Header className="d-flex justify-content-between align-items-center">
          <span className="fw-bold">{course}</span>
        </Card.Header>
        <Card.Body className="text-center">
          <Button 
            variant="outline-primary" 
            size="sm" 
            onClick={() => toggleCourse(course)}
          >
            {expandedCourse === course ? 'Hide Details' : 'View Details'}
          </Button>
        </Card.Body>
      </Card>
    );
  };

  const renderCoursePath = () => {
    if (!coursePath || coursePath.length === 0) {
      return <p>No course path available.</p>;
    }

    return (
      <div className="course-path-container">
        <div className="course-path-scroll">
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
        
        {expandedCourse && (
          <div className="course-details mt-4">
            <h4>Course Details</h4>
            <Card>
              <Card.Body>
                <Card.Title>{expandedCourse}</Card.Title>
                <p>To see full course details, find this course in the Major or Complementary tabs.</p>
              </Card.Body>
            </Card>
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="recommendations-container">
      <h2 className="mb-4">Your Courses</h2>
      
      <Tab.Container activeKey={activeTab} onSelect={(k) => setActiveTab(k)}>
        <Nav variant="tabs" className="mb-4 recommendation-tabs">
          <Nav.Item>
            <Nav.Link eventKey="coursePath" className="recommendation-tab">
              <span className="tab-icon path-icon">🗓️</span> DreamPath
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
              <p>This is your recommended course path across 12 terms.</p>
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