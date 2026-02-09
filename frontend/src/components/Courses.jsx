import React, { useState, useEffect, useRef } from 'react';
import { Card, Badge, Row, Col, Button, Nav, Tab, Container, Spinner, CloseButton } from 'react-bootstrap';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { useAuth } from '../contexts/AuthContext';
import { apiClient } from '../lib/api';
import DashboardNavbar from './DashboardNavbar';
import LeftSidebar from './LeftSidebar';
import ChatWindow from './ChatWindow';
import { Calendar, CheckSquare, Lightbulb, Lock, BoxArrowUpRight, PeopleFill, CheckCircleFill } from 'react-bootstrap-icons';

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
  const [isUpdatingTerm, setIsUpdatingTerm] = useState(false);
  const [typedText, setTypedText] = useState('');
  const [showCursor, setShowCursor] = useState(true);
  const detailsPanelRef = useRef(null);
  const scrollContainerRef = useRef(null);
  const hasAutoScrolled = useRef(false);

  // Get current term from course path data
  const currentTermIndex = coursePathData?.curr_window_start ?? 0;

  // Handle setting a new current term
  const handleSetCurrentTerm = async (termIndex) => {
    if (!user?.id || termIndex === currentTermIndex || isUpdatingTerm) return;

    setIsUpdatingTerm(true);
    try {
      await apiClient.updateCurrentTerm(String(user.id), termIndex);
      // Refetch to get updated data
      await fetchCoursePath();
    } catch (error) {
      console.error('Failed to update current term:', error);
    } finally {
      setIsUpdatingTerm(false);
    }
  };

  useEffect(() => {
    if (!user) {
      navigate('/login');
      return;
    }
  }, [user, navigate]);

  // Auto-scroll to current term on initial page load only
  useEffect(() => {
    if (coursePathData?.course_path && scrollContainerRef.current && !hasAutoScrolled.current) {
      hasAutoScrolled.current = true;

      // Term width (250px) + gap (20px) = 270px per term
      const termWidth = 270;
      const scrollPosition = currentTermIndex * termWidth;

      // Small delay to ensure DOM is rendered
      setTimeout(() => {
        scrollContainerRef.current?.scrollTo({
          left: scrollPosition,
          behavior: 'smooth'
        });
      }, 100);
    }
  }, [coursePathData, currentTermIndex]);

  // Prevent body scroll when modal is open
  useEffect(() => {
    if (detailsPanelVisible) {
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = '';
    }
    // Cleanup on unmount
    return () => {
      document.body.style.overflow = '';
    };
  }, [detailsPanelVisible]);

  // Typing animation effect
  useEffect(() => {
    const fullText = 'Courses';
    let currentIndex = 0;
    setTypedText(''); // Reset
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
  }, []);

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
            {isPrereq && <Badge bg="secondary" pill className="mini-type-badge">Prereq</Badge>}
            {isMajor && <Badge bg="primary" pill className="mini-type-badge">Major</Badge>}
            {isComplementary && <Badge bg="info" pill className="mini-type-badge">Comp</Badge>}
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
        {hasWindow && (() => {
          const window = course.must_have_window;
          const startTerm = Math.min(...window) + 1;
          const endTerm = Math.max(...window) + 1;
          const tooltipText = startTerm === endTerm
            ? `Prioritized for Term ${startTerm}`
            : `Prioritized for Terms ${startTerm} – ${endTerm}`;
          return (
            <div
              className="course-path-lock-circle"
              data-tooltip={tooltipText}
            >
              <Lock size={11} color="#d32f2f" />
            </div>
          );
        })()}
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
        <div className="tab-description course-path-header">
          <div className="course-path-spacer" />
          <p className="course-path-subtitle">Your recommended course trajectory, term by term.</p>
          <div className="course-path-navigation">
            <button className="term-nav-button" onClick={scrollLeft}>← Previous Terms</button>
            <button className="term-nav-button" onClick={scrollRight}>Next Terms →</button>
          </div>
        </div>
        <div className="course-path-container">
          <div className="course-path-scroll" ref={scrollContainerRef}>
          {coursePathData.course_path.map((termCourses, termIndex) => {
            const isPast = termIndex < currentTermIndex;
            const isCurrent = termIndex === currentTermIndex;
            const termStateClass = isPast ? 'term-past' : isCurrent ? 'term-current' : 'term-future';
            const showYearDivider = (termIndex + 1) % 3 === 0 && termIndex < coursePathData.course_path.length - 1;

            return (
              <React.Fragment key={`term-${termIndex}`}>
                <div className={`term-container ${termStateClass}`}>
                  <div
                    className={`term-header-wrapper ${isUpdatingTerm ? 'updating' : ''}`}
                    onClick={() => handleSetCurrentTerm(termIndex)}
                    title={isCurrent ? 'Current term' : `Click to set as current term`}
                  >
                    <h5 className="term-header">
                      {isPast && <CheckCircleFill className="term-check-icon" size={14} />}
                      Term {termIndex + 1}
                    </h5>
                    {isCurrent && <Badge bg="secondary" className="current-term-badge">Current</Badge>}
                  </div>
                  <div className="term-courses">
                    {termCourses.map((courseCode) => (
                      <div key={`${termIndex}-${courseCode}`} className="term-course">
                        {renderCoursePathCard(courseCode, termIndex)}
                      </div>
                    ))}
                    {termCourses.length < 3 && (
                      <>
                        {Array.from({ length: 3 - termCourses.length }, (_, i) => (
                          <div key={`empty-${termIndex}-${i}`} className="term-course">
                            <Card className="empty-course-slot">
                              <Card.Header className="d-flex justify-content-between align-items-center p-2">
                                <span className="fw-bold">&nbsp;</span>
                              </Card.Header>
                              <Card.Body className="p-2">
                                <p className="small mb-2">&nbsp;</p>
                                <div className="text-center">
                                  <Button variant="outline-secondary" size="sm" className="invisible">Details</Button>
                                </div>
                              </Card.Body>
                            </Card>
                          </div>
                        ))}
                      </>
                    )}
                  </div>
                </div>
                {showYearDivider && <div className="year-divider" />}
              </React.Fragment>
            );
          })}
        </div>
      </div>
      </>
    );
  }

  // Render a percentile bar for metrics
  const renderPercentileBar = (percentile, classification, isDifficulty = false) => {
    if (percentile === null || percentile === undefined) return null;

    // Color based on classification and type
    let barColor = '#8A6BC1'; // default purple
    if (isDifficulty) {
      if (classification === 'Low') barColor = '#4caf50';
      else if (classification === 'Medium') barColor = '#ff9800';
      else if (classification === 'High') barColor = '#f44336';
    } else {
      // Learning value - higher is better
      if (classification === 'High') barColor = '#4caf50';
      else if (classification === 'Medium') barColor = '#ff9800';
      else if (classification === 'Low') barColor = '#f44336';
    }

    return (
      <div className="percentile-bar-container">
        <div className="percentile-bar-bg">
          <div
            className="percentile-bar-fill"
            style={{ width: `${percentile}%`, backgroundColor: barColor }}
          />
        </div>
        <span className="percentile-label">{Math.round(percentile)}%</span>
      </div>
    );
  };

  // Render aligned parameters with icons
  const renderAlignedParameters = (alignedParams) => {
    if (!alignedParams || alignedParams.length === 0) return null;

    const paramConfig = {
      'interests': { icon: '/interests_icon.svg', label: 'Interests' },
      'post_grad': { icon: '/post_grad_goal_icon.svg', label: 'Post-Grad Goals' },
      'career': { icon: '/career_goal_icon.svg', label: 'Career Goals' }
    };

    return (
      <div className="aligned-params-container">
        {alignedParams.map(param => {
          const config = paramConfig[param];
          if (!config) return null;
          return (
            <div key={param} className="aligned-param-badge">
              <img src={config.icon} alt={config.label} className="aligned-param-icon" />
              <span>{config.label}</span>
            </div>
          );
        })}
      </div>
    );
  };

  // Details modal for expanded course
  function renderDetailsModal() {
    const courseDetails = expandedCourse ? getCourseDetails(expandedCourse) : null;
    const isPrerequisite = courseDetails?.is_prereq || false;

    // Check if course is in recommended_courses
    const isRecommended = coursePathData?.recommended_courses?.includes(expandedCourse);

    // Only show prereq message if it's a prerequisite AND not a recommended course
    const showPrereqMessage = isPrerequisite && activeTab === 'coursePath' && !isRecommended;

    // Check if any metrics are available
    const hasDifficultyMetrics = courseDetails?.global_difficulty_percentile !== null && courseDetails?.global_difficulty_percentile !== undefined;
    const hasValueMetrics = courseDetails?.global_value_percentile !== null && courseDetails?.global_value_percentile !== undefined;
    const hasTargetAudience = courseDetails?.target_audience_blurb;
    // Only show aligned params for courses that are actually recommended (not prereqs that lost recommendation status)
    const hasAlignedParams = courseDetails?.aligned_parameters && courseDetails.aligned_parameters.length > 0 && isRecommended;

    return (
      <>
        <div className={`modal-overlay ${detailsPanelVisible ? 'visible' : ''}`} onClick={() => handleClosePanel()}></div>
        <div className={`course-details-modal ${detailsPanelVisible ? 'visible' : ''}`} ref={detailsPanelRef}>
          {/* Side Schedule Tab - outside left edge */}
          {courseDetails && ((courseDetails.term_idx !== null && courseDetails.term_idx !== undefined) || (courseDetails.must_have_window && courseDetails.must_have_window.length > 0)) && (
            <div className="side-schedule-tab">
              {courseDetails.term_idx !== null && courseDetails.term_idx !== undefined && (
                <div className="side-tab-row">
                  <span className="side-term-badge">
                    <span className="term-short">T: {courseDetails.term_idx + 1}</span>
                    <span className="term-full">Scheduled in Term {courseDetails.term_idx + 1}</span>
                  </span>
                </div>
              )}
              {courseDetails.must_have_window && courseDetails.must_have_window.length > 0 && (
                <div className="side-tab-row">
                  <span className="side-lock-pill">
                    <Lock size={11} color="#d32f2f" />
                    {(() => {
                      const window = courseDetails.must_have_window;
                      const startTerm = Math.min(...window) + 1;
                      const endTerm = Math.max(...window) + 1;
                      const shortText = startTerm === endTerm ? `${startTerm}` : `${startTerm} ↔ ${endTerm}`;
                      const fullText = startTerm === endTerm
                        ? `Prioritized for Term ${startTerm}`
                        : `Prioritized for Terms ${startTerm} ↔ ${endTerm}`;
                      return (
                        <>
                          <span className="priority-short">{shortText}</span>
                          <span className="priority-full">{fullText}</span>
                        </>
                      );
                    })()}
                  </span>
                </div>
              )}
            </div>
          )}

          <div className="modal-header-row">
            {courseDetails ? (
              <div className="modal-header-content">
                <div className="course-code-row">
                  <h5 className="course-code">{courseDetails.course_code}</h5>
                  {courseDetails.course_type === 'major' && <Badge bg="primary">Major Course</Badge>}
                  {courseDetails.course_type === 'complementary' && <Badge bg="info">Complementary Course</Badge>}
                  {courseDetails.is_prereq && <Badge bg="secondary">Prerequisite</Badge>}
                </div>
                <h6 className="course-title">{courseDetails.course_title || 'No title available'}</h6>
              </div>
            ) : (
              <h4 className="modal-title">Course Details</h4>
            )}
            <CloseButton onClick={() => handleClosePanel()} />
          </div>
          <div className="modal-content-scroll">
            {courseDetails ? (
              <>
                {showPrereqMessage && (
                  <div className="prereq-message">
                    Recommended for prerequisite completion
                  </div>
                )}

                {/* Aligned Parameters */}
                {hasAlignedParams && (
                  <div className="modal-section aligned-section">
                    <h6 className="section-title">Alignment</h6>
                    {renderAlignedParameters(courseDetails.aligned_parameters)}
                  </div>
                )}

                {/* Description */}
                <div className="modal-section">
                  <div className="section-title-row">
                    <h6 className="section-title">Description</h6>
                    {courseDetails.course_url && (
                      <a href={courseDetails.course_url} target="_blank" rel="noopener noreferrer" className="course-link">
                        <BoxArrowUpRight size={14} />
                      </a>
                    )}
                  </div>
                  {courseDetails.course_description ? (
                    <p className="description-text">{courseDetails.course_description}</p>
                  ) : (
                    <p className="no-data-text">No description available</p>
                  )}
                </div>

                {/* Learning Value Metrics */}
                {hasValueMetrics && (
                  <div className="modal-section metrics-section">
                    <h6 className="section-title">Learning Value</h6>
                    <div className="metric-row">
                      <div className="metric-header">
                        <span className="metric-label">Overall</span>
                        <span className={`classification-badge value-${courseDetails.global_value_classification?.toLowerCase()}`}>
                          {courseDetails.global_value_classification}
                        </span>
                      </div>
                      {renderPercentileBar(courseDetails.global_value_percentile, courseDetails.global_value_classification, false)}
                    </div>
                    {courseDetails.dept_value_percentile !== null && courseDetails.dept_value_percentile !== undefined && (
                      <div className="metric-row">
                        <div className="metric-header">
                          <span className="metric-label">Within {courseDetails.department || 'Dept'}</span>
                          <span className={`classification-badge value-${courseDetails.dept_value_classification?.toLowerCase()}`}>
                            {courseDetails.dept_value_classification}
                          </span>
                        </div>
                        {renderPercentileBar(courseDetails.dept_value_percentile, courseDetails.dept_value_classification, false)}
                      </div>
                    )}
                    {courseDetails.learning_value_blurb && (
                      <p className="metric-blurb">{courseDetails.learning_value_blurb}</p>
                    )}
                  </div>
                )}

                {/* Difficulty Metrics */}
                {hasDifficultyMetrics && (
                  <div className="modal-section metrics-section">
                    <h6 className="section-title">Difficulty</h6>
                    <div className="metric-row">
                      <div className="metric-header">
                        <span className="metric-label">Overall</span>
                        <span className={`classification-badge difficulty-${courseDetails.global_difficulty_classification?.toLowerCase()}`}>
                          {courseDetails.global_difficulty_classification}
                        </span>
                      </div>
                      {renderPercentileBar(courseDetails.global_difficulty_percentile, courseDetails.global_difficulty_classification, true)}
                    </div>
                    {courseDetails.dept_difficulty_percentile !== null && courseDetails.dept_difficulty_percentile !== undefined && (
                      <div className="metric-row">
                        <div className="metric-header">
                          <span className="metric-label">Within {courseDetails.department || 'Dept'}</span>
                          <span className={`classification-badge difficulty-${courseDetails.dept_difficulty_classification?.toLowerCase()}`}>
                            {courseDetails.dept_difficulty_classification}
                          </span>
                        </div>
                        {renderPercentileBar(courseDetails.dept_difficulty_percentile, courseDetails.dept_difficulty_classification, true)}
                      </div>
                    )}
                    {courseDetails.difficulty_blurb && (
                      <p className="metric-blurb">{courseDetails.difficulty_blurb}</p>
                    )}
                  </div>
                )}

                {/* Target Audience */}
                {hasTargetAudience && (
                  <div className="modal-section">
                    <h6 className="section-title">Target Audience</h6>
                    <p className="description-text">{courseDetails.target_audience_blurb}</p>
                    {courseDetails.total_reviews !== null && courseDetails.total_reviews !== undefined && (
                      <div className="reviews-count" data-tooltip={`Sentiment from ${courseDetails.total_reviews >= 25 ? '25+' : courseDetails.total_reviews} students`}>
                        <PeopleFill size={14} color="#666" />
                        <span>{courseDetails.total_reviews >= 25 ? '25+' : courseDetails.total_reviews}</span>
                      </div>
                    )}
                  </div>
                )}

                {/* Additional Info - Prerequisites */}
                {(() => {
                  // Check if prereq_tree exists and has content
                  const prereqTree = courseDetails.prereq_tree;
                  const courseCode = courseDetails.course_code;

                  if (prereqTree && courseCode && prereqTree[courseCode]) {
                    // Extract direct children from prereq_tree
                    const directChildren = prereqTree[courseCode];
                    if (Array.isArray(directChildren) && directChildren.length > 0) {
                      // Each child is an object like { "COSC10": [...] }
                      const prereqItems = directChildren
                        .map(child => {
                          const code = Object.keys(child)[0];
                          if (!code) return null;
                          const prereqCourse = coursePathData?.course_bank?.[code];
                          if (prereqCourse && prereqCourse.term_idx !== null && prereqCourse.term_idx !== undefined) {
                            return {
                              code,
                              termIdx: prereqCourse.term_idx,
                              courseType: prereqCourse.course_type || 'other'
                            };
                          }
                          return null;
                        })
                        .filter(Boolean);

                      if (prereqItems.length > 0) {
                        return (
                          <div className="modal-section additional-info">
                            <div className="info-item prereq-badges-row">
                              <span className="info-label">Scheduled Prerequisites:</span>
                              <span className="prereq-badges">
                                {prereqItems.map((item, idx) => (
                                  <span
                                    key={item.code}
                                    className={`prereq-badge prereq-badge-${item.courseType}`}
                                    data-tooltip={`Scheduled in Term ${item.termIdx + 1}`}
                                  >
                                    {item.code}
                                  </span>
                                ))}
                              </span>
                            </div>
                          </div>
                        );
                      }
                    }
                  }

                  // Fallback: show raw prerequisites text if available
                  if (courseDetails.prerequisites) {
                    return (
                      <div className="modal-section additional-info">
                        <div className="info-item">
                          <span className="info-label">Prerequisites:</span>
                          <span className="info-value">{courseDetails.prerequisites}</span>
                        </div>
                      </div>
                    );
                  }

                  return null;
                })()}
              </>
            ) : (
              <div className="no-details">
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

  // Get major and complementary courses from recommended_courses (source of truth)
  const getRecommendedByType = (type) => {
    if (!coursePathData?.recommended_courses || !coursePathData?.course_bank) return [];
    return coursePathData.recommended_courses
      .map(code => coursePathData.course_bank[code])
      .filter(course => course && course.course_type === type);
  };

  const getMajorCourses = () => getRecommendedByType('major');
  const getComplementaryCourses = () => getRecommendedByType('complementary');

  // Render course list (for major/complementary tabs)
  function renderCourseList(courses, tab) {
    if (!courses || courses.length === 0) {
      return <p className="text-muted">No course recommendations available.</p>;
    }

    // Priority scoring based on aligned_parameters (same as rebuild node)
    // 2 points: both interests AND post_grad
    // 1 point: either interests OR post_grad
    // 0 points: only career or no alignment
    const getPriorityScore = (course) => {
      const aligned = course.aligned_parameters || [];
      const hasInterests = aligned.includes('interests');
      const hasPostGrad = aligned.includes('post_grad');
      if (hasInterests && hasPostGrad) return 2;
      if (hasInterests || hasPostGrad) return 1;
      return 0;
    };

    // Sort: scheduled first, then by priority score within each group
    const sortedCourses = [...courses].sort((a, b) => {
      // Primary: scheduled courses on top
      const aScheduled = a.term_idx !== null && a.term_idx !== undefined;
      const bScheduled = b.term_idx !== null && b.term_idx !== undefined;
      if (aScheduled && !bScheduled) return -1;
      if (!aScheduled && bScheduled) return 1;

      // Secondary: sort by priority score within each group
      const aScore = getPriorityScore(a);
      const bScore = getPriorityScore(b);
      return bScore - aScore;
    });

    return (
      <Row xs={1} md={2} className="g-4">
        {sortedCourses.map((course, idx) => {
          const rankBadgeClass = tab === 'major' ? 'rank-badge-major' : 'rank-badge-complementary';
          const hasWindow = course.must_have_window && course.must_have_window.length > 0;

          // Compute window text if exists
          let windowText = null;
          if (hasWindow) {
            const startTerm = Math.min(...course.must_have_window) + 1;
            const endTerm = Math.max(...course.must_have_window) + 1;
            windowText = startTerm === endTerm ? `${startTerm}` : `${startTerm} ↔ ${endTerm}`;
          }

          return (
            <Col key={course.course_code}>
              <Card className="h-100 shadow-sm border-0" style={{ background: '#fff', borderRadius: 14, marginBottom: 12, position: 'relative' }}>
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
                {/* Bottom right badges: scheduled term + lock pill */}
                {((course.term_idx !== null && course.term_idx !== undefined) || hasWindow) && (
                  <div className="course-card-bottom-badges">
                    {course.term_idx !== null && course.term_idx !== undefined && (
                      <span className="course-card-term-badge">
                        Term {course.term_idx + 1}
                      </span>
                    )}
                    {hasWindow && (
                      <span className="course-card-lock-pill">
                        <Lock size={11} color="#d32f2f" />
                        <span>{windowText}</span>
                      </span>
                    )}
                  </div>
                )}
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
        <h2 className="mb-4" style={{ fontFamily: 'Lora, serif', fontWeight: 400, fontSize: 32, letterSpacing: 0.5, color: '#7b7b93' }}>
          {typedText}
          <span style={{ opacity: showCursor ? 1 : 0, transition: 'opacity 0.1s' }}>|</span>
        </h2>
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
                      <Badge bg="primary" pill className="ms-2 tab-count-badge">{getMajorCourses().length}</Badge>
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
                      <Badge bg="info" pill className="ms-2 tab-count-badge">{getComplementaryCourses().length}</Badge>
                    </Nav.Link>
                  </Nav.Item>
                </Nav>
                <Tab.Content>
                  <Tab.Pane eventKey="coursePath">
                    {renderCoursePath()}
                  </Tab.Pane>
                  <Tab.Pane eventKey="major">
                    <div className="tab-description">
                      <p style={{ margin: 0, textAlign: 'center', width: '100%' }}>Personalized major courses in your CoursePath.</p>
                    </div>
                    {renderCourseList(getMajorCourses(), 'major')}
                  </Tab.Pane>
                  <Tab.Pane eventKey="complementary">
                    <div className="tab-description">
                      <p style={{ margin: 0, textAlign: 'center', width: '100%' }}>Complementary courses from other departments.</p>
                    </div>
                    {renderCourseList(getComplementaryCourses(), 'complementary')}
                  </Tab.Pane>
                </Tab.Content>
              </Tab.Container>
            )}
          </Card.Body>
        </Card>
        {renderDetailsModal()}
        </Container>
      </div>

      {/* Styles for courses */}
      <style>{`
        .tab-description {
          min-height: 40px !important;
          display: flex;
          align-items: center;
          font-family: 'Lora', serif;
          margin-bottom: 20px;
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
          transition: opacity 0.2s ease;
        }

        /* Past term styling */
        .term-container.term-past {
          opacity: 0.6;
        }

        .term-container.term-past .course-path-card {
          background: #f5f5f5;
        }

        .term-container.term-past .term-header-wrapper {
          background: rgba(0, 0, 0, 0.04);
        }

        /* Current term styling */
        .term-container.term-current {
          position: relative;
        }

        .term-container.term-current .term-header-wrapper {
          background: linear-gradient(135deg, rgba(138, 107, 193, 0.12) 0%, rgba(107, 143, 199, 0.12) 100%);
        }

        .term-container.term-current .term-header {
          color: #6B4FA0;
        }

        /* Future term styling - default */
        .term-container.term-future .term-header-wrapper:hover {
          background: rgba(138, 107, 193, 0.06);
        }

        /* Year divider - vertical line between every 3 terms */
        .year-divider {
          width: 3px;
          background: linear-gradient(to bottom, transparent 0%, #d6cdea 20%, #d6cdea 80%, transparent 100%);
          margin: 0 10px;
          flex-shrink: 0;
          align-self: stretch;
        }

        /* Term header wrapper - clickable */
        .term-header-wrapper {
          display: flex;
          align-items: center;
          gap: 8px;
          padding: 8px 12px;
          border-radius: 8px;
          margin-bottom: 12px;
          cursor: pointer;
          transition: background 0.2s ease, transform 0.1s ease;
          user-select: none;
        }

        .term-header-wrapper:hover {
          transform: translateY(-1px);
        }

        .term-header-wrapper:active {
          transform: translateY(0);
        }

        .term-header-wrapper.updating {
          pointer-events: none;
          opacity: 0.7;
        }

        .term-check-icon {
          color: #78976e;
          flex-shrink: 0;
        }

        .current-term-badge {
          font-size: 10px;
          padding: 4px 8px;
          background: linear-gradient(135deg, #8A6BC1 0%, #6B8FC7 100%) !important;
          border-radius: 4px;
          border: none;
        }

        .term-header {
          font-size: 16px;
          font-weight: 600;
          margin: 0;
          color: #333;
          display: flex;
          align-items: center;
          gap: 6px;
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

        .course-path-header {
          display: flex;
          align-items: center;
          justify-content: space-between;
        }

        .course-path-spacer {
          flex: 1;
        }

        .course-path-subtitle {
          margin: 0;
          text-align: center;
          flex-shrink: 0;
        }

        .course-path-navigation {
          display: flex;
          gap: 12px;
          flex: 1;
          justify-content: flex-end;
        }

        @media (max-width: 768px) {
          .course-path-spacer {
            display: none;
          }

          .course-path-header {
            flex-direction: column;
            gap: 10px;
          }

          .course-path-navigation {
            order: -1;
            flex: none;
            align-self: flex-end;
          }
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

        /* Modal Overlay */
        .modal-overlay {
          position: fixed;
          top: 0;
          left: 0;
          width: 100vw;
          height: 100vh;
          background: rgba(0, 0, 0, 0.6);
          z-index: 2000;
          opacity: 0;
          visibility: hidden;
          transition: opacity 0.25s ease-out;
        }

        .modal-overlay.visible {
          opacity: 1;
          visibility: visible;
        }

        /* Course Details Modal */
        .course-details-modal {
          font-family: 'Lora', serif;
          position: fixed;
          top: 50%;
          left: 50%;
          transform: translate(-50%, -50%) scale(0.95);
          width: 580px;
          max-width: 90vw;
          max-height: 85vh;
          background: white;
          border-radius: 10px;
          box-shadow: 0 20px 60px rgba(0, 0, 0, 0.25);
          z-index: 2001;
          opacity: 0;
          visibility: hidden;
          transition: all 0.3s ease-out;
          display: flex;
          flex-direction: column;
          overflow: visible;
        }

        .course-details-modal.visible {
          opacity: 1;
          visibility: visible;
          transform: translate(-50%, -50%) scale(1);
        }

        .modal-header-row {
          display: flex;
          justify-content: space-between;
          align-items: flex-start;
          padding: 25px 25px 20px;
          border-bottom: 1px solid #f0f0f0;
          flex-shrink: 0;
          gap: 16px;
        }

        .modal-header-content {
          flex: 1;
          min-width: 0;
        }

        .modal-header-content .course-code-row {
          margin-bottom: 8px;
        }

        .modal-header-content .course-title {
          margin: 0;
          color: #555;
        }

        .modal-title {
          margin: 0;
          font-size: 1.25rem;
          font-weight: 600;
          color: #333;
        }

        .modal-content-scroll {
          flex: 1;
          overflow-y: auto;
          overflow-x: hidden;
          padding: 0px 24px 24px;
          scrollbar-width: none;
          -ms-overflow-style: none;
          border-radius: 0 0 20px 20px;
        }

        .modal-content-scroll::-webkit-scrollbar {
          display: none;
        }

        /* Side Schedule Tab - outside left edge like a physical tab */
        .side-schedule-tab {
          position: absolute;
          top: 8%;
          right: 100%;
          transform: translateY(-50%);
          z-index: 10;
          background: white;
          border-radius: 8px 0 0 8px;
          box-shadow: -4px 2px 12px rgba(0, 0, 0, 0.1);
          cursor: default;
          transition: all 0.35s ease-out;
          border: 1px solid #e0e0e0;
          border-right: none;
          overflow: hidden;
        }

        .side-schedule-tab {
          display: flex;
          flex-direction: column;
          gap: 6px;
          padding: 10px 8px;
        }

        .side-tab-row {
          display: flex;
          align-items: center;
          gap: 8px;
          white-space: nowrap;
        }

        .side-tab-text {
          max-width: 0;
          overflow: hidden;
          opacity: 0;
          transition: max-width 0.3s ease-out, opacity 0.25s ease-out;
        }

        .side-schedule-tab:hover .side-tab-text {
          max-width: 200px;
          opacity: 1;
          transition: max-width 0.35s ease-out, opacity 0.3s ease-out 0.1s;
        }

        .side-schedule-tab:hover {
          box-shadow: -4px 4px 16px rgba(0, 0, 0, 0.15);
          padding: 10px 12px;
        }

        .side-term-badge {
          font-size: 12px;
          font-weight: 600;
          color: #2e7d32;
          background: rgba(76, 175, 80, 0.15);
          padding: 4px 8px;
          border-radius: 4px;
          line-height: 1.2;
          flex-shrink: 0;
        }

        .term-full {
          display: none;
        }

        .side-schedule-tab:hover .term-short {
          display: none;
        }

        .side-schedule-tab:hover .term-full {
          display: inline;
        }

        .side-lock-pill {
          display: flex;
          align-items: center;
          justify-content: center;
          gap: 5px;
          background-color: #ffe0e0;
          border-radius: 12px;
          padding: 4px 8px;
          min-height: 22px;
          flex-shrink: 0;
        }

        .priority-short,
        .priority-full {
          font-size: 12px;
          color: #d32f2f;
          font-weight: 500;
          line-height: 1.2;
        }

        .priority-full {
          display: none;
        }

        .side-schedule-tab:hover .priority-short {
          display: none;
        }

        .side-schedule-tab:hover .priority-full {
          display: inline;
        }

        .course-path-lock-circle {
          position: absolute;
          bottom: 6px;
          right: 6px;
          background-color: #ffe0e0;
          border-radius: 50%;
          width: 22px;
          height: 22px;
          display: flex;
          align-items: center;
          justify-content: center;
          z-index: 1;
          cursor: default;
        }

        .course-path-lock-circle::after {
          content: attr(data-tooltip);
          position: absolute;
          left: 100%;
          top: 50%;
          transform: translateY(-50%);
          margin-left: 8px;
          padding: 5px 10px;
          background: #333;
          color: #fff;
          font-family: 'Lora', serif;
          font-size: 11px;
          font-weight: 500;
          white-space: nowrap;
          border-radius: 4px;
          opacity: 0;
          visibility: hidden;
          transition: opacity 0.2s, visibility 0.2s;
          pointer-events: none;
          z-index: 10;
        }

        .course-path-lock-circle:hover::after {
          opacity: 1;
          visibility: visible;
        }

        /* Course Header Section */
        .course-header-section {
          margin-bottom: 20px;
        }

        .course-code-row {
          display: flex;
          align-items: center;
          gap: 12px;
          flex-wrap: wrap;
          margin-bottom: 6px;
        }

        .course-code {
          margin: 0;
          font-size: 1.3rem;
          font-weight: 700;
          color: #333;
        }

        .priority-badge {
          background: rgba(255, 82, 82, 0.08);
          padding: 4px 10px;
          border-radius: 6px;
          border: 1px solid rgba(255, 82, 82, 0.2);
          font-size: 12px;
          color: #b22727;
          display: inline-flex;
          align-items: center;
          gap: 6px;
        }

        .course-title {
          margin: 0 0 12px;
          font-size: 1rem;
          font-weight: 500;
          color: #555;
        }

        .course-type-badges {
          margin-bottom: 10px;
        }

        .prereq-message {
          font-style: italic;
          font-size: 14px;
          color: #666;
          font-weight: 400;
          padding-top: 15px;
        }

        .schedule-badges-row {
          display: flex;
          align-items: center;
          gap: 10px;
          flex-wrap: wrap;
        }

        .scheduled-term-badge {
          display: inline-flex;
          align-items: center;
          padding: 4px 12px;
          border-radius: 6px;
          background: rgba(76, 175, 80, 0.1);
          border: 1px solid rgba(76, 175, 80, 0.3);
          color: #2e7d32;
          font-weight: 500;
          font-size: 13px;
        }

        /* Modal Sections */
        .modal-section {
          margin-bottom: 20px;
          padding: 16px 0px;
          border-bottom: 1px solid #f5f5f5;
        }

        .modal-section:last-child {
          border-bottom: none;
          margin-bottom: 0;
        }

        .section-title {
          margin: 0 0 10px;
          font-size: 0.9rem;
          font-weight: 600;
          color: #444;
          text-transform: uppercase;
          letter-spacing: 0.5px;
        }

        .section-title-row {
          display: flex;
          align-items: center;
          gap: 8px;
          margin-bottom: 10px;
        }

        .section-title-row .section-title {
          margin-bottom: 0;
        }

        .course-link {
          color: #555;
          opacity: 0.7;
          transition: opacity 0.2s;
          display: inline-flex;
          align-items: center;
          position: relative;
          top: -1px;
        }

        .course-link:hover {
          opacity: 1;
          color: #6B4FA0;
        }

        .description-text {
          margin: 0;
          font-size: 14px;
          line-height: 1.6;
          color: #555;
        }

        .reviews-count {
          display: inline-flex;
          align-items: center;
          gap: 6px;
          margin-top: 10px;
          font-size: 13px;
          color: #666;
          position: relative;
          cursor: default;
        }

        .reviews-count::after {
          content: attr(data-tooltip);
          position: absolute;
          left: 100%;
          top: 50%;
          transform: translateY(-50%);
          margin-left: 8px;
          padding: 5px 10px;
          background: #333;
          color: #fff;
          font-size: 11px;
          white-space: nowrap;
          border-radius: 4px;
          opacity: 0;
          visibility: hidden;
          transition: opacity 0.2s, visibility 0.2s;
          pointer-events: none;
        }

        .reviews-count:hover::after {
          opacity: 1;
          visibility: visible;
        }

        .no-data-text {
          margin: 0;
          font-size: 14px;
          color: #999;
          font-style: italic;
        }

        /* Aligned Parameters */
        .aligned-section {
          background: linear-gradient(135deg, rgb(239 232 249) 0%, rgba(107, 143, 199, 0.06) 100%);
          margin: -4px -24px 5px;
          padding: 16px 24px;
          border-bottom: none;
        }

        .aligned-params-container {
          display: flex;
          gap: 10px;
          flex-wrap: wrap;
        }

        .aligned-param-badge {
          display: flex;
          align-items: center;
          gap: 3px;
          padding: 6px 12px;
          background: white;
          border-radius: 10px;
          box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
          font-size: 13px;
          font-weight: 500;
          font-spacing: 0.5px;
          font-style: italic;
          color: #555;
        }
          /*    background: #e8f4e9;
    padding: 1px 6px;
    border-radius: 4px;*/

        .aligned-param-icon {
          width: 22px;
          height: 22px;
          object-fit: contain;
        }

        /* Metrics Styling */
        .metrics-section {
          margin: 0 -24px 20px;
          padding: 16px 24px;
          border-radius: 0;
          border-bottom: none;
        }

        .metric-row {
          margin-bottom: 12px;
        }

        .metric-row:last-of-type {
          margin-bottom: 8px;
        }

        .metric-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 6px;
        }

        .metric-label {
          font-size: 13px;
          color: #666;
        }

        .classification-badge {
          padding: 2px 10px;
          border-radius: 12px;
          font-size: 11px;
          font-weight: 600;
          text-transform: uppercase;
        }

        .classification-badge.difficulty-low,
        .classification-badge.value-high {
          background: rgba(76, 175, 80, 0.15);
          color: #2e7d32;
        }

        .classification-badge.difficulty-medium,
        .classification-badge.value-medium {
          background: rgba(255, 152, 0, 0.15);
          color: #e65100;
        }

        .classification-badge.difficulty-high,
        .classification-badge.value-low {
          background: rgba(244, 67, 54, 0.15);
          color: #c62828;
        }

        /* Percentile Bar */
        .percentile-bar-container {
          display: flex;
          align-items: center;
          gap: 10px;
        }

        .percentile-bar-bg {
          flex: 1;
          height: 8px;
          background: #e8e8e8;
          border-radius: 4px;
          overflow: hidden;
        }

        .percentile-bar-fill {
          height: 100%;
          border-radius: 4px;
          transition: width 0.4s ease-out;
        }

        .percentile-label {
          font-size: 12px;
          font-weight: 600;
          color: #666;
          min-width: 36px;
          text-align: right;
        }

        .metric-blurb {
          margin: 10px 0 0;
          font-size: 13px;
          line-height: 1.5;
          color: #666;
          font-style: italic;
        }

        /* Additional Info */
        .additional-info {
          margin: 0 -24px 0;
          padding: 5px 24px;
          border-bottom: none;
        }

        .info-item {
          display: flex;
          gap: 8px;
          margin-bottom: 8px;
          font-size: 13px;
        }

        .info-item:last-child {
          margin-bottom: 0;
        }

        .info-label {
          font-weight: 600;
          color: #555;
        }

        .info-value {
          color: #666;
        }

        /* Prerequisite badges */
        .prereq-badges-row {
          flex-wrap: wrap;
          align-items: center;
        }

        .prereq-badges {
          display: flex;
          gap: 6px;
          flex-wrap: wrap;
        }

        .prereq-badge {
          padding: 1px 5px;
          border-radius: 4px;
          font-size: 12px;
          font-weight: 500;
          position: relative;
          cursor: default;
        }

        .prereq-badge-major {
          background: #e8dced;
          color:rgb(77, 72, 86);
        }

        .prereq-badge-complementary {
          background: #dce8ed;
          color:rgb(66, 77, 84);
        }

        .prereq-badge-other {
          background: #e8e8e8;
          color: #555;
        }

        .prereq-badge::after {
          content: attr(data-tooltip);
          position: absolute;
          bottom: 100%;
          left: 50%;
          transform: translateX(-50%);
          margin-bottom: 6px;
          padding: 5px 10px;
          background: #333;
          color: #fff;
          font-size: 11px;
          white-space: nowrap;
          border-radius: 4px;
          opacity: 0;
          visibility: hidden;
          transition: opacity 0.2s, visibility 0.2s;
          pointer-events: none;
          z-index: 10;
        }

        .prereq-badge:hover::after {
          opacity: 1;
          visibility: visible;
        }

        .no-details {
          text-align: center;
          padding: 40px 20px;
          color: #999;
        }

        .rank-badge-major {
          font-family: 'Lora', serif;
          background: linear-gradient(135deg, #8A6BC1 0%, #6B8FC7 100%);
        }

        .rank-badge-complementary {
          font-family: 'Lora', serif;
          background: linear-gradient(135deg, #6B8FC7 0%, #5A9FC7 100%);
        }

        .mini-type-badge {
          font-size: 0.7rem;
          font-family: 'Lora', serif;
          border-radius: 8px !important;
        }

        .tab-count-badge {
          font-family: 'Lora', serif;
          border-radius: 5px !important;
          padding: 5px 8px !important;
        }

        .no-courses {
          text-align: center;
          padding: 20px;
          color: #888;
          font-style: italic;
        }

        .empty-course-slot {
          border: 1px dashed rgb(237, 232, 245) !important;
          border-radius: 8px;
          background: transparent !important;
          box-shadow: 0 4px 16px rgba(140, 110, 180, 0.13)
          margin: -0.5px 0px;
        }

        .empty-course-slot .card-header,
        .empty-course-slot .card-body {
          background: transparent !important;
          border: none !important;
        }

        /* Bottom badges for major/complementary course cards */
        .course-card-bottom-badges {
          position: absolute;
          bottom: 10px;
          right: 10px;
          display: flex;
          align-items: center;
          gap: 8px;
          z-index: 1;
        }

        .course-card-term-badge {
          font-size: 12px;
          font-weight: 600;
          color: #2e7d32;
          background: rgba(76, 175, 80, 0.15);
          padding: 4px 8px;
          border-radius: 4px;
          line-height: 1.2;
        }

        .course-card-lock-pill {
          display: flex;
          align-items: center;
          gap: 5px;
          background-color: #ffe0e0;
          border-radius: 12px;
          padding: 4px 8px;
        }

        .course-card-lock-pill span {
          font-size: 11px;
          color: #d32f2f;
          font-weight: 500;
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
