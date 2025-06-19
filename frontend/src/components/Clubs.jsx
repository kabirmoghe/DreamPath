import React, { useState, useEffect, useRef } from 'react';
import { Card, Badge, Row, Col, Button, Container, CloseButton, Nav } from 'react-bootstrap';
import DashboardNavbar from './DashboardNavbar';
import { supabase } from '../lib/supabase';
import styles from './Clubs.module.css';

function Clubs() {
  const [user, setUser] = useState(null);
  const [clubs, setClubs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [activeCategory, setActiveCategory] = useState('All');
  const [expandedClub, setExpandedClub] = useState(null);
  const [detailsPanelVisible, setDetailsPanelVisible] = useState(false);
  const detailsPanelRef = useRef(null);

  // Dynamically compute unique categories from clubs data
  const clubCategories = React.useMemo(() => {
    const cats = Array.from(new Set(clubs.map(club => club.clubCategory).filter(Boolean)));
    return ['All', ...cats];
  }, [clubs]);

  // Sort clubs by score descending before filtering
  const sortedClubs = React.useMemo(() => {
    return [...clubs].sort((a, b) => (b.score || 0) - (a.score || 0));
  }, [clubs]);

  // Filter clubs by category
  const filteredClubs = activeCategory === 'All'
    ? sortedClubs
    : sortedClubs.filter(club => (club.clubCategory || '').toLowerCase() === activeCategory.toLowerCase());

  useEffect(() => {
    const fetchUserAndClubs = async () => {
      setLoading(true);
      try {
        const { data: { user } } = await supabase.auth.getUser();
        setUser(user);
        if (!user) throw new Error('Not logged in');
        // Fetch most recent dreampath_iteration for user
        const { data: iterations, error: iterError } = await supabase
          .from('dreampath_iterations')
          .select('*')
          .eq('user_id', user.id)
          .order('created_at', { ascending: false });
        if (iterError) throw iterError;
        if (!iterations || iterations.length === 0) {
          setClubs([]);
          setLoading(false);
          return;
        }
        const iterationId = iterations[0].id;
        // Fetch recommendations for this iteration
        const recsResp = await fetch(`/api/recommendations/${iterationId}`);
        if (!recsResp.ok) throw new Error('Failed to fetch recommendations');
        const recsData = await recsResp.json();
        let clubRecs = recsData.clubRecommendations || [];
        if (!Array.isArray(clubRecs)) clubRecs = Object.values(clubRecs);
        setClubs(clubRecs);
      } catch (err) {
        setError('Failed to load clubs.');
      } finally {
        setLoading(false);
      }
    };
    fetchUserAndClubs();
  }, []);

  // Open details slider
  const handleLearnMore = (club) => {
    setExpandedClub(club);
    setDetailsPanelVisible(true);
  };

  // Close details slider
  const handleClosePanel = () => {
    setDetailsPanelVisible(false);
    setTimeout(() => setExpandedClub(null), 300); // Wait for animation
  };

  // Details slider
  const renderDetailsPanel = () => (
    <>
      <div className={`panel-overlay ${detailsPanelVisible ? 'visible' : ''}`} onClick={handleClosePanel}></div>
      <div className={`course-details-panel ${detailsPanelVisible ? 'visible' : ''}`} ref={detailsPanelRef}>
        <div className="details-header d-flex justify-content-between align-items-center mb-3">
          <h4 className="mb-0">Club Details</h4>
          <CloseButton onClick={handleClosePanel} />
        </div>
        <div className="details-content">
          {expandedClub && (
            <>
              <h5>{expandedClub.clubName}</h5>
              <h6 className="mb-3 text-muted">{expandedClub.clubCategory}</h6>
              <div className="mb-3">
                <h6 className="fw-bold">Description</h6>
                <p className="small">{expandedClub.clubBlurb || expandedClub.description || 'No description available.'}</p>
              </div>
              {expandedClub.tags && expandedClub.tags.length > 0 && (
                <div className="mb-3">
                  <h6 className="fw-bold">Tags</h6>
                  <div className="d-flex flex-wrap gap-1">
                    {expandedClub.tags.map((tag, idx) => (
                      <Badge key={idx} bg="light" text="dark" className="tag-badge">{tag}</Badge>
                    ))}
                  </div>
                </div>
              )}
              <div className="mb-3">
                <h6 className="fw-bold">Score</h6>
                <Badge bg="success" pill>{expandedClub.score !== undefined ? expandedClub.score.toFixed(2) : '--'}</Badge>
              </div>
              {expandedClub.urls && expandedClub.urls.length > 0 && (
                <div className="mb-3">
                  <h6 className="fw-bold">Links</h6>
                  <div className="d-flex flex-column gap-1">
                    {expandedClub.urls.map((url, idx) => (
                      <a key={idx} href={url} target="_blank" rel="noopener noreferrer" className="small text-decoration-none">🔗 {url}</a>
                    ))}
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </>
  );

  return (
    <div style={{ minHeight: '100vh', background: '#f8f6fc' }}>
      <DashboardNavbar />
      <Container className="py-4" style={{ height: 'calc(100vh - 80px)', display: 'flex', flexDirection: 'column' }}>
        {/* Sticky header section */}
        <div style={{
          position: 'sticky',
          top: 0,
          zIndex: 10,
          background: '#f8f6fc',
          borderBottom: '1px solid #e0e0e0'
        }}>
          <h2 className="mb-2" style={{ fontFamily: 'Lora, serif', fontWeight: 400, fontSize: 32, letterSpacing: 0.5 }}>Student Clubs & Organizations</h2>
          <div className="mb-4" style={{ color: '#666', fontSize: 18, fontFamily: 'Lora, serif', fontWeight: 400 }}>
            Discover clubs that match your interests and enhance your college experience.
          </div>
          <div className="mb-4 d-flex flex-wrap gap-2">
            {clubCategories.map(category => (
              <Button
                key={category}
                variant={activeCategory === category ? 'success' : 'outline-secondary'}
                size="sm"
                style={{ borderRadius: 20, fontWeight: 500, minWidth: 90 }}
                onClick={() => setActiveCategory(category)}
              >
                {category}
              </Button>
            ))}
          </div>
        </div>
        {/* Scrollable card grid */}
        <div className={styles.clubsScrollArea} style={{ flex: 1, minHeight: 0, paddingTop: 24 }}>
          {loading ? (
            <div className="d-flex flex-column align-items-center justify-content-center" style={{ minHeight: 200 }}>
              <span className="spinner-border text-success" role="status"></span>
              <span className="mt-3 text-muted">Loading clubs...</span>
            </div>
          ) : error ? (
            <div className="alert alert-danger">{error}</div>
          ) : filteredClubs.length === 0 ? (
            <div className="text-center text-muted">No clubs found for this category.</div>
          ) : (
            <Row xs={1} md={2} className="g-4">
              {filteredClubs.map((club, idx) => (
                <Col key={club.clubName}>
                  <Card className="h-100 shadow-sm border-0" style={{ background: '#fff', borderRadius: 14 }}>
                    <Card.Body className="d-flex flex-column justify-content-between h-100">
                      <div>
                        <div className="d-flex justify-content-between align-items-start mb-2">
                          <div>
                            <div className="fw-bold" style={{ fontSize: 20 }}>{club.clubName}</div>
                            <div className="text-muted mb-2" style={{ fontSize: 15 }}>{club.clubCategory}</div>
                            {/* Tags beneath clubCategory */}
                            <div className="mb-2 d-flex flex-wrap gap-1">
                              {club.tags && club.tags.slice(0, 4).map((tag, tagIdx) => (
                                <Badge key={tagIdx} bg="light" text="dark" className="tag-badge">{tag}</Badge>
                              ))}
                            </div>
                          </div>
                          <Badge bg="success" pill style={{ fontSize: 15, fontWeight: 500, padding: '6px 14px' }}>
                            {club.score !== undefined ? club.score.toFixed(2) : '--'}
                          </Badge>
                        </div>
                        <div className="mb-2" style={{ color: '#555', fontSize: 15, minHeight: 40 }}>
                          {(() => {
                            const desc = club.clubBlurb || club.description || 'No description available.';
                            if (desc.length > 160) {
                              return desc.substring(0, 160) + '...';
                            }
                            return desc;
                          })()}
                        </div>
                      </div>
                      {/* Centered Learn More button at the bottom */}
                      <div className="d-flex justify-content-center mt-auto pt-2">
                        <Button variant="outline-primary" size="sm" onClick={() => handleLearnMore(club)} style={{ minWidth: 110, fontWeight: 500 }}>
                          Learn More
                        </Button>
                      </div>
                    </Card.Body>
                  </Card>
                </Col>
              ))}
            </Row>
          )}
          {renderDetailsPanel()}
        </div>
      </Container>
    </div>
  );
}

export default Clubs; 