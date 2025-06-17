import React, { useState, useEffect } from 'react';
import { Container, Row, Col, Card, Button, Nav, Tab, Form, Spinner } from 'react-bootstrap';
import { supabase } from '../lib/supabase';
import { useNavigate } from 'react-router-dom';
import StudentForm from './StudentForm';
import ModernStudentForm from './ModernStudentForm';
import CourseRecommendations from './CourseRecommendations';
import axios from 'axios';
import DashboardNavbar from './DashboardNavbar';
import 'bootstrap/dist/css/bootstrap.min.css';
import { Hammer } from 'react-bootstrap-icons';
import CourseTimeline from './CourseTimeline';
import TopRecommendations from './TopRecommendations';

function Dashboard() {
  const navigate = useNavigate();
  const [user, setUser] = useState(null);
  const [profile, setProfile] = useState(null);
  const [editProfile, setEditProfile] = useState(null);
  const [isEditing, setIsEditing] = useState(false);
  const [saveLoading, setSaveLoading] = useState(false);
  const [saveError, setSaveError] = useState(null);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [majors, setMajors] = useState([]);
  const [recommendations, setRecommendations] = useState({});
  const [useModernForm, setUseModernForm] = useState(true);
  const [hasSubmittedOnce, setHasSubmittedOnce] = useState(false);
  const [formData, setFormData] = useState({
    major: '',
    collegeInterests: '',
    postGradGoal: '',
    longTermGoal: ''
  });
  const [buildLoading, setBuildLoading] = useState(false);
  const [iterations, setIterations] = useState([]);
  const [activeIteration, setActiveIteration] = useState(null);

  // Loader text animation state
  const loaderMessages = [
    'Finding courses that match your interests',
    'Discovering classes aligned with your post-grad goals',
    'Selecting courses for your career aspirations',
  ];
  const [loaderMsgIdx, setLoaderMsgIdx] = useState(0);
  const [fadeState, setFadeState] = useState('fade-in');
  const [ellipsis, setEllipsis] = useState('');

  const fullName = profile?.full_name || '';
  const firstName = fullName.split(' ')[0];

  useEffect(() => {
    checkUser();
  }, []);

  useEffect(() => {
    setEditProfile(profile);
  }, [profile]);

  useEffect(() => {
    if (!buildLoading) return;
    const msgInterval = setInterval(() => {
      setFadeState('fade-out');
      setTimeout(() => {
        setLoaderMsgIdx((idx) => (idx + 1) % loaderMessages.length);
        setFadeState('fade-in');
      }, 600); // 600ms fade
    }, 3500); // 3.5s per message
    return () => clearInterval(msgInterval);
  }, [buildLoading]);

  useEffect(() => {
    if (!buildLoading) return;
    let count = 0;
    const ellipsisInterval = setInterval(() => {
      setEllipsis('.'.repeat(count % 4)); // 0, 1, 2, 3 dots
      count++;
    }, 350);
    return () => clearInterval(ellipsisInterval);
  }, [buildLoading]);

  useEffect(() => {
    const fetchIterations = async () => {
      if (!user) return;
      const { data, error } = await supabase
        .from('dreampath_iterations')
        .select('*')
        .eq('user_id', user.id)
        .order('created_at', { ascending: false });
      if (!error && data && data.length > 0) {
        setIterations(data);
        setActiveIteration(data[0]);
        // Fetch recommendations for the most recent iteration
        const iterationId = data[0].id;
        const recsResp = await fetch(`/api/recommendations/${iterationId}`);
        if (recsResp.ok) {
          const recsData = await recsResp.json();
          setRecommendations(recsData);
        }
      } else {
        setIterations([]);
        setActiveIteration(null);
        setRecommendations({});
      }
    };
    fetchIterations();
  }, [user]);

  useEffect(() => {
    if (recommendations) {
      console.log('Recommendations:', recommendations);
    }
  }, [recommendations]);

  const checkUser = async () => {
    try {
      const { data: { session }, error: sessionError } = await supabase.auth.getSession();
      if (sessionError) throw sessionError;

      if (!session) {
        navigate('/login');
        return;
      }

      setUser(session.user);

      // Fetch user profile (basic)
      const { data: profileData, error: profileError } = await supabase
        .from('profiles')
        .select('*')
        .eq('id', session.user.id)
        .single();
      if (profileError) {
        // If profile doesn't exist, insert a basic profile
        const { error: insertError } = await supabase.from('profiles').insert([{
          id: session.user.id,
          email: session.user.email,
          full_name: session.user.user_metadata.full_name || ''
        }]);
        if (insertError) throw insertError;
        // Fetch the newly inserted profile
        const { data: newProfile, error: newProfileError } = await supabase
          .from('profiles')
          .select('*')
          .eq('id', session.user.id)
          .single();
        if (newProfileError) throw newProfileError;
        profileData = newProfile;
      }

      // Fetch detailed profile
      const { data: detailedProfile, error: detailedProfileError } = await supabase
        .from('detailed_profiles')
        .select('*')
        .eq('user_id', session.user.id)
        .maybeSingle();
      if (detailedProfileError) throw detailedProfileError;

      // If detailed profile does not exist, redirect to create-detailed-profile
      if (!detailedProfile) {
        navigate('/create-detailed-profile');
        return;
      }

      // Merge both profiles
      setProfile({ ...profileData, ...detailedProfile });

      axios.get('http://localhost:5001/api/majors')
        .then(response => {
          setMajors(response.data);
        })
        .catch(err => {
          setError('Failed to load majors. Please try again later.');
          console.error('Error fetching majors:', err);
        });
    } catch (error) {
      setError(error.message);
    } finally {
      setLoading(false);
    }
  };

  const toggleFormStyle = () => {
    setUseModernForm(prev => !prev);
  };

  const handleEditChange = (e) => {
    setEditProfile({ ...editProfile, [e.target.name]: e.target.value });
  };

  const handleSaveProfile = async () => {
    setSaveLoading(true);
    setSaveError(null);
    setSaveSuccess(false);
    try {
      const { error } = await supabase
        .from('detailed_profiles')
        .update({
          major: editProfile.major,
          college_interests: editProfile.college_interests,
          post_grad_goal: editProfile.post_grad_goal,
          long_term_goal: editProfile.long_term_goal,
        })
        .eq('user_id', user.id);
      if (error) {
        setSaveError(error.message);
        console.error('Profile update error:', error);
        return;
      }
      setProfile({ ...profile, ...editProfile });
      setIsEditing(false);
      setSaveSuccess(true);
    } catch (err) {
      setSaveError(err.message);
      console.error('Profile update exception:', err);
    } finally {
      setSaveLoading(false);
      setTimeout(() => setSaveSuccess(false), 2000);
    }
  };

  const handleBuildDreamPath = async () => {
    setBuildLoading(true);
    try {
      const payload = {
        user_id: user.id,
        profile_id: profile.id,
        iteration_name: 'DreamPath',
        major: editProfile?.major || '',
        collegeInterests: editProfile?.college_interests || '',
        postGradGoal: editProfile?.post_grad_goal || '',
        longTermGoal: editProfile?.long_term_goal || '',
      };
      const response = await fetch('/api/recommendations', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const data = await response.json();
      setRecommendations(data);
      console.log('Recommendations response:', data);
    } catch (error) {
      console.error('Error fetching recommendations:', error);
    } finally {
      setBuildLoading(false);
    }
  };

  if (loading) {
    return (
      <div style={{ minHeight: '100vh', background: '#f8f6fc' }}>
        <DashboardNavbar />
        <Container className="py-5 d-flex justify-content-center align-items-center" style={{ minHeight: '80vh' }}>
          <Spinner animation="border" variant="secondary" />
        </Container>
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ minHeight: '100vh', background: '#f8f6fc' }}>
        <DashboardNavbar />
        <Container className="py-5">
          <div className="alert alert-danger">{error}</div>
        </Container>
      </div>
    );
  }

  return (
    <div style={{ minHeight: '100vh', background: '#f8f6fc' }}>
      <DashboardNavbar />
      <Container className="py-4">
        <Row className="mb-4">
          <Col>
            <div className="d-flex justify-content-between align-items-center">
              <h1 className="h2 mb-0" style={{ fontFamily: 'Lora, serif', fontWeight: 300 }}>Welcome, {firstName}</h1>
            </div>
          </Col>
        </Row>
        <Row>
          <Col md={4} className="h-100">
            <Card className="mb-4 h-100" style={{ background: '#faf9fb', border: 'none', minHeight: 420 }}>
              <Card.Body style={{ height: '100%', display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
                <div className="d-flex justify-content-between align-items-center mb-3">
                  <h3 className="h5 mb-0">Your Profile</h3>
                  {!isEditing && (
                    <Button variant="outline-primary" size="sm" onClick={() => setIsEditing(true)}>
                      Edit
                    </Button>
                  )}
                </div>
                <Form>
                  <Form.Group className="mb-3">
                    <Form.Label>Major</Form.Label>
                    {isEditing ? (
                      <Form.Select
                        name="major"
                        value={editProfile?.major || ''}
                        onChange={handleEditChange}
                        style={{ background: '#f7f5fc', border: '0.5px solid #d6cdea', boxShadow: 'none', borderRadius: 8, padding: '8px 12px' }}
                      >
                        <option value="">Select a major</option>
                        {majors.map((m) => (
                          <option key={m} value={m}>{m}</option>
                        ))}
                      </Form.Select>
                    ) : (
                      <Form.Control
                        plaintext
                        readOnly
                        value={editProfile?.major || ''}
                        style={{ background: '#f3f0fa', border: 'none', color: '#222', borderRadius: 8, padding: '8px 12px' }}
                      />
                    )}
                  </Form.Group>
                  <Form.Group className="mb-3">
                    <Form.Label>College Interests</Form.Label>
                    {isEditing ? (
                      <Form.Control
                        as="textarea"
                        rows={3}
                        style={{ resize: 'none', overflowY: 'auto', minHeight: 80, maxHeight: 80, background: '#f7f5fc', border: '0.5px solid #d6cdea', boxShadow: 'none', borderRadius: 8, padding: '8px 12px' }}
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
                        style={{ background: '#f3f0fa', border: 'none', color: '#222', resize: 'none', minHeight: 80, maxHeight: 80, borderRadius: 8, padding: '8px 12px' }}
                      />
                    )}
                  </Form.Group>
                  <Form.Group className="mb-3">
                    <Form.Label>Post-Graduation Goal</Form.Label>
                    {isEditing ? (
                      <Form.Control
                        as="textarea"
                        rows={3}
                        style={{ resize: 'none', overflowY: 'auto', minHeight: 80, maxHeight: 80, background: '#f7f5fc', border: '0.5px solid #d6cdea', boxShadow: 'none', borderRadius: 8, padding: '8px 12px' }}
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
                        style={{ background: '#f3f0fa', border: 'none', color: '#222', resize: 'none', minHeight: 80, maxHeight: 80, borderRadius: 8, padding: '8px 12px' }}
                      />
                    )}
                  </Form.Group>
                  <Form.Group className="mb-3">
                    <Form.Label>Long-Term Goal</Form.Label>
                    {isEditing ? (
                      <Form.Control
                        as="textarea"
                        rows={3}
                        style={{ resize: 'none', overflowY: 'auto', minHeight: 80, maxHeight: 80, background: '#f7f5fc', border: '0.5px solid #d6cdea', boxShadow: 'none', borderRadius: 8, padding: '8px 12px' }}
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
                        style={{ background: '#f3f0fa', border: 'none', color: '#222', resize: 'none', minHeight: 80, maxHeight: 80, borderRadius: 8, padding: '8px 12px' }}
                      />
                    )}
                  </Form.Group>
                  {isEditing && (
                    <div className="d-flex justify-content-end gap-2">
                      <Button
                        variant="secondary"
                        onClick={() => { setEditProfile(profile); setIsEditing(false); }}
                        disabled={saveLoading}
                        style={{ minWidth: 100 }}
                      >
                        Cancel
                      </Button>
                      <Button
                        variant="primary"
                        onClick={handleSaveProfile}
                        disabled={saveLoading}
                        style={{ minWidth: 100 }}
                      >
                        {saveLoading ? 'Saving...' : 'Save'}
                      </Button>
                    </div>
                  )}
                  {saveError && <div className="text-danger mt-2">{saveError}</div>}
                  {saveSuccess && <div className="text-success mt-2">Profile updated!</div>}
                </Form>
              </Card.Body>
            </Card>
          </Col>
          <Col md={8} className="h-100 position-relative">
            <div style={{ position: 'relative', height: '100%' }}>
              {/* Overlay to disable right column when loading */}
              {buildLoading && (
                <div style={{
                  position: 'absolute',
                  top: 0,
                  left: 0,
                  width: '100%',
                  height: '100%',
                  background: 'rgba(128,128,128,0.10)',
                  zIndex: 10,
                  pointerEvents: 'all',
                  borderRadius: 16,
                  opacity: 1,
                  transition: 'opacity 0.3s',
                  animation: 'fadeInOverlay 0.3s',
                }} />
              )}
              <Card className="mb-4 h-100" style={{ background: '#faf9fb', border: 'none', minHeight: 420, display: 'flex', flexDirection: 'column', justifyContent: 'center', borderRadius: 16 }}>
                <Card.Body className="d-flex flex-column justify-content-center align-items-center h-100" style={{ width: '100%' }}>
                  {/* Placeholder if no recommendations */}
                  {(!recommendations || !recommendations.majorRecommendations) && (
                    <div className="text-center mb-4">
                      <h4 className="mb-3">Your DreamPath</h4>
                      <p style={{ color: '#888', fontSize: 18 }}>
                        Build your DreamPath to identify highly-personalized courses, clubs, and alumni connections along with actionable next steps to maximize your potential.
                      </p>
                    </div>
                  )}
                  {/* Recommendations Preview */}
                  {recommendations && recommendations.coursePath && (
                    <div className="dreampath-visualization-container w-100">
                      <div className="d-flex justify-content-between mb-4">
                        {/* Top Course Recommendations (simplified) */}
                        <div className="dreampath-top-courses mb-4" style={{ width: '100%' }}>
                          <TopRecommendations
                            majorCourse={(recommendations.majorRecommendations || [])[0]}
                            complementaryCourse={(recommendations.complementaryRecommendations || [])[0]}
                            clubRecommendation={
                              Object.values(recommendations.clubRecommendations || {})
                                .sort((a, b) => (b.score || 0) - (a.score || 0))[0]
                            }
                            onViewAll={() => { /* TODO: navigate to courses tab */ }}
                            onViewAllClubs={() => { /* TODO: navigate to clubs tab */ }}
                          />
                        </div>
                      </div>
                      <CourseTimeline coursePath={recommendations.coursePath} />
                    </div>
                  )}
                </Card.Body>
              </Card>
            </div>
            {/* Loader below the right column's Card (not inside the Card) */}
            {buildLoading && (
              <div className="d-flex flex-column justify-content-center align-items-center w-100" style={{ marginTop: 16 }}>
                <Spinner animation="border" variant="secondary" size="sm" style={{ marginBottom: 6, width: 18, height: 18 }} />
                <span
                  className={`loader-fade ${fadeState}`}
                  style={{
                    color: '#888',
                    fontStyle: 'italic',
                    minWidth: 500,
                    maxWidth: 500,
                    textAlign: 'center',
                    display: 'inline-block',
                    position: 'relative',
                    transition: 'opacity 600ms',
                  }}
                >
                  {loaderMessages[loaderMsgIdx]}
                  <span className="loading-ellipsis">{ellipsis}</span>
                </span>
              </div>
            )}
            {/* Fixed Build DreamPath button at bottom right */}
            <div style={{ position: 'fixed', right: 40, bottom: 40, zIndex: 1000, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 12 }}>
              <Button
                size="sm"
                className="d-flex align-items-center"
                style={{
                  fontWeight: 500,
                  background: 'linear-gradient(135deg, var(--dream-purple) 0%, var(--dream-blue) 100%)',
                  border: 'none',
                  color: 'white',
                  boxShadow: '0 2px 8px 0 rgba(140, 110, 180, 0.07)',
                }}
                onClick={handleBuildDreamPath}
                disabled={buildLoading}
              >
                <Hammer className="me-2" />Build DreamPath
              </Button>
            </div>
          </Col>
        </Row>
      </Container>
      <style>{`
        .loading-ellipsis {
          display: inline-block;
          width: 1.2em;
          text-align: left;
          vertical-align: bottom;
          direction: ltr;
        }
        .loader-fade.fade-in {
          opacity: 1;
          transition: opacity 600ms;
        }
        .loader-fade.fade-out {
          opacity: 0;
          transition: opacity 600ms;
        }
        @keyframes fadeInOverlay {
          from { opacity: 0; }
          to { opacity: 1; }
        }
        .dashboard-container[aria-disabled='true'] {
          filter: grayscale(0.2) brightness(0.95);
        }
      `}</style>
    </div>
  );
}

export default Dashboard;
