import React, { useState } from 'react';
import { Card, Badge, Row, Col, Button, Nav, Tab } from 'react-bootstrap';

function CourseRecommendations({ recommendations }) {
  const [expandedCourse, setExpandedCourse] = useState(null);
  const [activeTab, setActiveTab] = useState('major');
  
  // Extract the two types of recommendations
  const majorRecommendations = recommendations.majorRecommendations || [];
  const otherRecommendations = recommendations.otherRecommendations || [];

  const toggleCourse = (courseCode) => {
    setExpandedCourse(expandedCourse === courseCode ? null : courseCode);
  };

  // Find the maximum score for scaling (across both recommendation types)
  const allScores = [...majorRecommendations, ...otherRecommendations].map(course => course.totalScore);
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

  return (
    <div className="recommendations-container">
      <h2 className="mb-4">Your Courses</h2>
      
      <Tab.Container activeKey={activeTab} onSelect={(k) => setActiveTab(k)}>
        <Nav variant="tabs" className="mb-4 recommendation-tabs">
          <Nav.Item>
            <Nav.Link eventKey="major" className="recommendation-tab">
              <span className="tab-icon major-icon">📚</span> Major Courses
              <Badge bg="primary" pill className="ms-2">{majorRecommendations.length}</Badge>
            </Nav.Link>
          </Nav.Item>
          <Nav.Item>
            <Nav.Link eventKey="other" className="recommendation-tab">
              <span className="tab-icon other-icon">🌟</span> Complementary Courses
              <Badge bg="info" pill className="ms-2">{otherRecommendations.length}</Badge>
            </Nav.Link>
          </Nav.Item>
        </Nav>
        
        <Tab.Content>
          <Tab.Pane eventKey="major">
            <div className="tab-description mb-3">
              <p>These courses within your major align with your interests and goals.</p>
            </div>
            {renderCourseList(majorRecommendations)}
          </Tab.Pane>
          <Tab.Pane eventKey="other">
            <div className="tab-description mb-3">
              <p>These courses from other departments complement your major and support your aspirations.</p>
            </div>
            {renderCourseList(otherRecommendations)}
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