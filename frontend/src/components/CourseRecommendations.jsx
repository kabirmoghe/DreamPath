import React, { useState, useRef, useEffect } from 'react';
import { Card, Badge, Row, Col, Button, Nav, Tab, Container, CloseButton } from 'react-bootstrap';
import {
  Chart as ChartJS,
  RadialLinearScale,
  PointElement,
  LineElement,
  Filler,
  Tooltip,
  Legend,
} from 'chart.js';
import { Radar } from 'react-chartjs-2';

ChartJS.register(
  RadialLinearScale,
  PointElement,
  LineElement,
  Filler,
  Tooltip,
  Legend
);

function CourseRecommendations({ recommendations }) {
  const [expandedCourse, setExpandedCourse] = useState(null);
  const [expandedClub, setExpandedClub] = useState(null);
  const [activeTab, setActiveTab] = useState('coursePath');
  const [detailsPanelVisible, setDetailsPanelVisible] = useState(false);
  const detailsPanelRef = useRef(null);
  
  // Extract the different types of recommendations
  const majorRecommendations = recommendations.majorRecommendations || [];
  const complementaryRecommendations = recommendations.complementaryRecommendations || [];
  const coursePath = recommendations.coursePath || [];
  const clubRecommendations = recommendations.clubRecommendations || {};
  
  // Convert club recommendations object to array and sort by total score
  const clubRecommendationsArray = Object.values(clubRecommendations).sort((a, b) => b.totalScore - a.totalScore);
  
  // Create radar chart data for a club
  const createRadarData = (club) => {
    const parameterScores = club.parameterScores || {};
    
    // Extract the three main scores
    const collegeInterests = parameterScores.college_interests || 0;
    const postGradGoal = parameterScores.post_grad_goal || 0;
    const longTermGoal = parameterScores.long_term_goal || 0;
    
    // Check if all scores are zero or missing
    const hasAnyScores = collegeInterests > 0 || postGradGoal > 0 || longTermGoal > 0;
    
    return {
      labels: ['Interests', 'Post-Grad', 'Long-Term'],
      datasets: [
        {
          label: 'Match Score',
          data: hasAnyScores ? [collegeInterests, postGradGoal, longTermGoal] : [0, 0, 0],
          backgroundColor: hasAnyScores ? 'rgba(25, 135, 84, 0.2)' : 'rgba(128, 128, 128, 0.1)',
          borderColor: hasAnyScores ? 'rgba(25, 135, 84, 0.8)' : 'rgba(128, 128, 128, 0.3)',
          borderWidth: 2,
          pointBackgroundColor: hasAnyScores ? 'rgba(25, 135, 84, 1)' : 'transparent',
          pointBorderColor: hasAnyScores ? '#fff' : 'transparent',
          pointHoverBackgroundColor: hasAnyScores ? '#fff' : 'transparent',
          pointHoverBorderColor: hasAnyScores ? 'rgba(25, 135, 84, 1)' : 'transparent',
          pointRadius: hasAnyScores ? 3 : 0,
        },
      ],
    };
  };

  // Radar chart options for collapsed state
  const radarOptionsCollapsed = {
    responsive: true,
    maintainAspectRatio: true,
    layout: {
      padding: {
        top: 5,
        right: 20,
        bottom: 5,
        left: 20
      }
    },
    plugins: {
      legend: {
        display: false,
      },
      tooltip: {
        callbacks: {
          label: function(context) {
            const club = clubRecommendationsArray[context.datasetIndex];
            const parameterScores = club?.parameterScores || {};
            const labels = ['college_interests', 'post_grad_goal', 'long_term_goal'];
            const actualScore = parameterScores[labels[context.dataIndex]] || 0;
            return `${context.label}: ${actualScore.toFixed(3)}`;
          }
        }
      }
    },
    scales: {
      r: {
        angleLines: {
          display: true,
          color: 'rgba(0, 0, 0, 0.1)',
        },
        grid: {
          color: 'rgba(0, 0, 0, 0.1)',
        },
        pointLabels: {
          font: {
            size: 7,
            family: 'Lora, serif'
          },
          color: '#666',
          padding: 8
        },
        ticks: {
          display: false,
        },
        suggestedMin: 0,
        suggestedMax: 1,
      },
    },
  };

  // Radar chart options for expanded state
  const radarOptionsExpanded = {
    responsive: true,
    maintainAspectRatio: true,
    layout: {
      padding: {
        top: 25,
        right: 25,
        bottom: 25,
        left: 25
      }
    },
    plugins: {
      legend: {
        display: false,
      },
      tooltip: {
        callbacks: {
          label: function(context) {
            const club = clubRecommendationsArray[context.datasetIndex];
            const parameterScores = club?.parameterScores || {};
            const labels = ['college_interests', 'post_grad_goal', 'long_term_goal'];
            const actualScore = parameterScores[labels[context.dataIndex]] || 0;
            return `${context.label}: ${actualScore.toFixed(3)}`;
          }
        }
      }
    },
    scales: {
      r: {
        angleLines: {
          display: true,
          color: 'rgba(0, 0, 0, 0.1)',
        },
        grid: {
          color: 'rgba(0, 0, 0, 0.1)',
        },
        pointLabels: {
          font: {
            size: 8,
            family: 'Lora, serif'
          },
          color: '#666',
          padding: 12
        },
        ticks: {
          display: false,
        },
        suggestedMin: 0,
        suggestedMax: 1,
      },
    },
  };

  // Handle tab changes
  const handleTabChange = (newTab) => {
    setActiveTab(newTab);
    setExpandedCourse(null);
    setExpandedClub(null);
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

  // Toggle club details
  const toggleClub = (clubName) => {
    setExpandedClub(expandedClub === clubName ? null : clubName);
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
  
  const renderClubList = (clubs) => {
    if (clubs.length === 0) {
      return <p>No club recommendations available.</p>;
    }

    // Function to get category color
    const getCategoryColor = (category) => {
      const categoryColors = {
        'Multidisciplinary Research Initiatives': 'primary',           // Blue - general academic
        'Social Sciences and International Affairs Organizations': 'danger',               // Red - creative/liberal arts
        'STEM and Engineering Organizations': 'info',         // Green - sports/physical
        'Arts and Humanities Organizations': 'warning',          // Yellow/orange - cultural diversity
        'Greek Life': 'secondary',      // Gray - social organizations
        'Media': 'info',               // Light blue - communication/journalism
        'Professional': 'dark',         // Dark - career/business focused
        'Recreation': 'success',        // Green - leisure/outdoor activities
        'Service': 'warning',          // Yellow/orange - community service
        'Special Interest': 'info',     // Light blue - niche interests
        'Pre-Professional and Career-Focused Organizations': 'secondary' // Blue - leadership/governance
      };
      return categoryColors[category] || 'secondary';
    };

    return (
      <Row xs={1} md={2} className="g-4">
        {clubs.map((club, index) => (
          <Col key={club.clubName}>
            <Card className="h-100 club-card">
              <Card.Header className="d-flex justify-content-between align-items-start">
                <span className="fw-bold flex-grow-1 me-2" title={club.clubName} style={{wordWrap: 'break-word', overflowWrap: 'break-word'}}>
                  {club.clubName}
                </span>
                <Badge 
                  bg="success" 
                  pill 
                  className="flex-shrink-0"
                  title="Recommendation score"
                >
                  {isNaN(club.totalScore) ? "--" : club.totalScore.toFixed(2)}
                </Badge>
              </Card.Header>
              
              <Card.Body>
                {/* Collapsed state: Category, tags, and radar chart side by side */}
                {expandedClub !== club.clubName && (
                  <div className="row">
                    {/* Left column: Category and Tags */}
                    <div className="col-md-8">
                      {/* Category at the top */}
                      {club.clubCategory && (
                        <div className="mb-2">
                          <Badge bg={getCategoryColor(club.clubCategory)} className="category-badge">
                            {club.clubCategory}
                          </Badge>
                        </div>
                      )}
                      
                      {/* Tags beneath category */}
                      {club.tags && club.tags.length > 0 && (
                        <div className="mb-3">
                          <div className="d-flex flex-wrap gap-1">
                            {club.tags.slice(0, 3).map((tag, tagIndex) => (
                              <Badge key={tagIndex} bg="light" text="dark" className="tag-badge">
                                {tag}
                              </Badge>
                            ))}
                            {club.tags.length > 3 && (
                              <Badge bg="light" text="muted" className="tag-badge">
                                +{club.tags.length - 3} more
                              </Badge>
                            )}
                          </div>
                        </div>
                      )}
                    </div>
                    
                    {/* Right column: Radar Chart */}
                    <div className="col-md-4 d-flex justify-content-center align-items-start">
                      <div style={{ width: '140px', height: '140px' }}>
                        <Radar data={createRadarData(club)} options={radarOptionsCollapsed} />
                      </div>
                    </div>
                  </div>
                )}
                
                {/* Expanded state content */}
                {expandedClub === club.clubName && (
                  <>
                    {/* Category at the top */}
                    {club.clubCategory && (
                      <div className="mb-2">
                        <Badge bg={getCategoryColor(club.clubCategory)} className="category-badge">
                          {club.clubCategory}
                        </Badge>
                      </div>
                    )}
                    
                    {/* Tags beneath category */}
                    {club.tags && club.tags.length > 0 && (
                      <div className="mb-3">
                        <div className="d-flex flex-wrap gap-1">
                          {club.tags.map((tag, tagIndex) => (
                            <Badge key={tagIndex} bg="light" text="dark" className="tag-badge">
                              {tag}
                            </Badge>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Club Blurb - only visible when expanded */}
                    {club.clubBlurb && (
                      <div className="mb-3">
                        <p className="small text-muted" style={{ lineHeight: '1.4' }}>
                          {club.clubBlurb}
                        </p>
                      </div>
                    )}

                    {/* Two-column layout for expanded content */}
                    <h6 className="fw-bold">Recommendation Factors</h6>
                    <div className="row">
                      {/* Left column: Score breakdown only */}
                      <div className="col-md-8">
                        <div className="score-breakdown">
                          {Object.entries(club.parameterScores || {}).map(([parameter, score]) => (
                            <div key={parameter} className="d-flex justify-content-between small mb-1">
                              <span>{formatParameterName(parameter)}</span>
                              <span>{isNaN(score) || score <= 0 ? "--" : score.toFixed(3)}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                      
                      {/* Right column: Radar Chart */}
                      <div className="col-md-4 d-flex justify-content-center align-items-start">
                        <div style={{ width: '140px', height: '140px' }}>
                          <Radar data={createRadarData(club)} options={radarOptionsExpanded} />
                        </div>
                      </div>
                    </div>

                    {/* URLs */}
                    {club.urls && club.urls.length > 0 && (
                      <div className="mb-3 mt-3">
                        <h6 className="fw-bold">Links</h6>
                        <div className="d-flex flex-column gap-1">
                          {club.urls.map((url, urlIndex) => (
                            <a 
                              key={urlIndex} 
                              href={url} 
                              target="_blank" 
                              rel="noopener noreferrer"
                              className="small text-decoration-none"
                            >
                              🔗 {url.length > 50 ? `${url.substring(0, 50)}...` : url}
                            </a>
                          ))}
                        </div>
                      </div>
                    )}
                  </>
                )}
              </Card.Body>
              
              <Card.Footer className="text-center">
                <Button 
                  variant={expandedClub === club.clubName ? "outline-secondary" : "outline-primary"} 
                  size="sm"
                  onClick={() => toggleClub(club.clubName)}
                >
                  {expandedClub === club.clubName ? "Show Less" : "Show More"}
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
              <span className="tab-icon path-icon">🗓️</span> CoursePath
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
          <Nav.Item>
            <Nav.Link eventKey="clubs" className="recommendation-tab">
              <span className="tab-icon club-icon">🎯</span> Clubs
              <Badge bg="success" pill className="ms-2">{clubRecommendationsArray.length}</Badge>
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
          <Tab.Pane eventKey="clubs">
            <div className="tab-description mb-3">
              <p>These clubs align with your interests and goals.</p>
            </div>
            {renderClubList(clubRecommendationsArray)}
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