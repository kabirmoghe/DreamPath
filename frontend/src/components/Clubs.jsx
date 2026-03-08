import React, { useState, useEffect, useRef } from 'react';
import { Card, Container, Spinner, Button, CloseButton } from 'react-bootstrap';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { useAuth } from '../contexts/AuthContext';
import { apiClient } from '../lib/api';
import DashboardNavbar from './DashboardNavbar';
import LeftSidebar from './LeftSidebar';
import ChatWindow from './ChatWindow';

const CLUB_GREEN = '#5a9e5e';
const CLUB_GREEN_SUBTLE = 'rgba(90, 158, 94, 0.07)';
const CLUB_GREEN_BORDER = 'rgba(90, 158, 94, 0.18)';

const FILTER_OPTIONS = {
  sort: [
    { value: 'rank', label: 'Rank' },
    { value: 'name', label: 'Name' },
    { value: 'confidence', label: 'Confidence' },
  ],
  membership: [
    { value: 'all', label: 'All' },
    { value: 'not_yet_joined', label: 'Not Joined' },
    { value: 'joining', label: 'Joining' },
    { value: 'active_member', label: 'Active' },
    { value: 'inactive_member', label: 'Inactive' },
    { value: 'left', label: 'Left' },
  ],
  confidence: [
    { value: 'all', label: 'All' },
    { value: 'high', label: 'High' },
    { value: 'medium', label: 'Medium' },
    { value: 'low', label: 'Low' },
  ],
};

function formatTag(text) {
  if (!text) return null;
  return text.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

const formatMembership = formatTag;

function Clubs() {
  const { user, signOut } = useAuth();
  const navigate = useNavigate();

  const {
    data: clubPathData,
    isLoading: loading,
    error: queryError,
  } = useQuery({
    queryKey: ['clubPath', user?.id ? String(user.id) : null],
    queryFn: async () => {
      if (!user?.id) return null;
      return await apiClient.getClubPath(String(user.id));
    },
    enabled: !!user?.id,
    staleTime: 1000 * 30,
  });

  const error = queryError?.message || null;

  const [expandedActivity, setExpandedActivity] = useState(null);
  const [detailsVisible, setDetailsVisible] = useState(false);
  const [isChatOpen, setIsChatOpen] = useState(false);
  const [typedText, setTypedText] = useState('');
  const [showCursor, setShowCursor] = useState(true);
  const [sortBy, setSortBy] = useState('rank');
  const [membershipFilter, setMembershipFilter] = useState('all');
  const [confidenceFilter, setConfidenceFilter] = useState('all');
  const detailsPanelRef = useRef(null);

  useEffect(() => {
    if (!user) { navigate('/login'); }
  }, [user, navigate]);

  // Typing animation
  useEffect(() => {
    const fullText = 'Clubs';
    let currentIndex = 0;
    setTypedText('');
    setShowCursor(true);
    const cursorInterval = setInterval(() => setShowCursor(prev => !prev), 500);
    const typingInterval = setInterval(() => {
      if (currentIndex <= fullText.length) {
        setTypedText(fullText.slice(0, currentIndex));
        currentIndex++;
      } else {
        clearInterval(typingInterval);
        setTimeout(() => { clearInterval(cursorInterval); setShowCursor(false); }, 1500);
      }
    }, 50);
    return () => { clearInterval(typingInterval); clearInterval(cursorInterval); };
  }, []);

  // Prevent body scroll when modal is open
  useEffect(() => {
    document.body.style.overflow = detailsVisible ? 'hidden' : '';
    return () => { document.body.style.overflow = ''; };
  }, [detailsVisible]);

  const handleSignOut = async () => { await signOut(); navigate('/login'); };

  const handleOpenDetails = (activity) => {
    setExpandedActivity(activity);
    setTimeout(() => setDetailsVisible(true), 10);
  };

  const handleCloseDetails = () => {
    setDetailsVisible(false);
    setTimeout(() => setExpandedActivity(null), 300);
  };

  // Filter and sort activities
  const getFilteredActivities = () => {
    if (!clubPathData?.activities) return [];
    let activities = clubPathData.activities.map((a, idx) => ({ ...a, originalRank: idx + 1 }));

    if (membershipFilter !== 'all') {
      activities = activities.filter(a => (a.membership_status || 'not_yet_joined') === membershipFilter);
    }
    if (confidenceFilter !== 'all') {
      activities = activities.filter(a => (a.data_confidence || '').toLowerCase() === confidenceFilter);
    }

    if (sortBy === 'name') {
      activities.sort((a, b) => (a.display_name || '').localeCompare(b.display_name || ''));
    } else if (sortBy === 'confidence') {
      const order = { high: 0, medium: 1, low: 2, '': 3 };
      activities.sort((a, b) => (order[(a.data_confidence || '').toLowerCase()] ?? 3) - (order[(b.data_confidence || '').toLowerCase()] ?? 3));
    }
    // 'rank' keeps original order

    return activities;
  };

  const activities = getFilteredActivities();
  const hasActiveFilters = membershipFilter !== 'all' || confidenceFilter !== 'all';

  const renderFilterBar = () => (
    <div style={{
      display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '20px',
      flexWrap: 'wrap', fontFamily: 'Lora, serif',
    }}>
      {/* Sort */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
        <span style={{ fontSize: '12px', color: '#888', fontWeight: 500 }}>Sort:</span>
        {FILTER_OPTIONS.sort.map(opt => (
          <button
            key={opt.value}
            onClick={() => setSortBy(opt.value)}
            style={{
              fontSize: '12px', padding: '3px 10px', borderRadius: '12px', border: 'none',
              cursor: 'pointer', transition: 'all 0.15s ease', fontFamily: 'Lora, serif',
              background: sortBy === opt.value ? CLUB_GREEN : '#f0f0f0',
              color: sortBy === opt.value ? 'white' : '#666',
              fontWeight: sortBy === opt.value ? 600 : 400,
            }}
          >{opt.label}</button>
        ))}
      </div>

      {/* Membership */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
        <span style={{ fontSize: '12px', color: '#888', fontWeight: 500 }}>Status:</span>
        <select
          value={membershipFilter}
          onChange={e => setMembershipFilter(e.target.value)}
          style={{
            fontSize: '12px', padding: '3px 8px', borderRadius: '8px',
            border: `1px solid ${membershipFilter !== 'all' ? CLUB_GREEN : '#ddd'}`,
            background: membershipFilter !== 'all' ? CLUB_GREEN_SUBTLE : 'white',
            color: membershipFilter !== 'all' ? CLUB_GREEN : '#666',
            fontFamily: 'Lora, serif', cursor: 'pointer', outline: 'none',
          }}
        >
          {FILTER_OPTIONS.membership.map(opt => (
            <option key={opt.value} value={opt.value}>{opt.label}</option>
          ))}
        </select>
      </div>

      {/* Confidence */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
        <span style={{ fontSize: '12px', color: '#888', fontWeight: 500 }}>Confidence:</span>
        <select
          value={confidenceFilter}
          onChange={e => setConfidenceFilter(e.target.value)}
          style={{
            fontSize: '12px', padding: '3px 8px', borderRadius: '8px',
            border: `1px solid ${confidenceFilter !== 'all' ? CLUB_GREEN : '#ddd'}`,
            background: confidenceFilter !== 'all' ? CLUB_GREEN_SUBTLE : 'white',
            color: confidenceFilter !== 'all' ? CLUB_GREEN : '#666',
            fontFamily: 'Lora, serif', cursor: 'pointer', outline: 'none',
          }}
        >
          {FILTER_OPTIONS.confidence.map(opt => (
            <option key={opt.value} value={opt.value}>{opt.label}</option>
          ))}
        </select>
      </div>

      {hasActiveFilters && (
        <button
          onClick={() => { setMembershipFilter('all'); setConfidenceFilter('all'); }}
          style={{
            fontSize: '11px', padding: '2px 8px', borderRadius: '10px',
            border: '1px solid #ddd', background: '#f8f8f8', color: '#888',
            cursor: 'pointer', fontFamily: 'Lora, serif',
          }}
        >Clear filters</button>
      )}
    </div>
  );

  const renderActivityCard = (activity) => (
    <div
      key={activity.activity_slug}
      onClick={() => handleOpenDetails(activity)}
      style={{
        background: 'white',
        borderRadius: '12px',
        padding: '16px',
        border: `1px solid ${CLUB_GREEN_BORDER}`,
        cursor: 'pointer',
        transition: 'all 0.2s ease',
        boxShadow: '0 2px 6px rgba(0,0,0,0.04)',
        display: 'flex',
        flexDirection: 'column',
        gap: '8px',
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.boxShadow = '0 4px 14px rgba(90, 158, 94, 0.12)';
        e.currentTarget.style.transform = 'translateY(-2px)';
        e.currentTarget.style.borderColor = 'rgba(90, 158, 94, 0.35)';
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.boxShadow = '0 2px 6px rgba(0,0,0,0.04)';
        e.currentTarget.style.transform = 'translateY(0)';
        e.currentTarget.style.borderColor = CLUB_GREEN_BORDER;
      }}
    >
      {/* Rank badge */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: '15px', fontWeight: 600, color: '#333', fontFamily: 'Lora, serif', marginBottom: '2px' }}>
            {activity.display_name}
          </div>
          <div style={{ fontSize: '11px', color: '#999', fontFamily: 'monospace' }}>
            {activity.activity_slug}
          </div>
        </div>
        <span style={{
          fontSize: '11px', fontWeight: 600, color: CLUB_GREEN,
          background: CLUB_GREEN_SUBTLE, padding: '2px 8px', borderRadius: '10px',
          flexShrink: 0, marginLeft: '8px',
        }}>#{activity.originalRank}</span>
      </div>

      {/* Tags */}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '5px' }}>
        {activity.activity_type && (
          <span style={{
            fontSize: '10px', color: '#5a9e5e', background: 'rgba(90, 158, 94, 0.08)',
            padding: '2px 8px', borderRadius: '10px', fontWeight: 500,
          }}>{formatTag(activity.activity_type)}</span>
        )}
        {activity.domain && (
          <span style={{
            fontSize: '10px', color: '#5a8a6e', background: 'rgba(90, 158, 94, 0.06)',
            padding: '2px 8px', borderRadius: '10px', fontWeight: 500,
          }}>{formatTag(activity.domain)}</span>
        )}
      </div>

      {/* Mission preview */}
      {activity.mission_synth && (
        <div style={{
          fontSize: '12px', color: '#777', lineHeight: '1.4',
          fontFamily: 'Lora, serif',
          display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical',
          overflow: 'hidden',
        }}>
          {activity.mission_synth}
        </div>
      )}

      {/* Bottom row: aligned params left, status right */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', marginTop: 'auto' }}>
        {activity.aligned_parameters && activity.aligned_parameters.length > 0 ? (
          <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap' }}>
            {activity.aligned_parameters.map(param => (
              <span key={param} style={{
                fontSize: '9px', color: '#8A6BC1', background: 'rgba(138, 107, 193, 0.08)',
                padding: '1px 7px', borderRadius: '8px', fontWeight: 500, textTransform: 'capitalize',
              }}>{param.replace(/_/g, ' ')}</span>
            ))}
          </div>
        ) : <div />}
        <div style={{ display: 'flex', alignItems: 'center', gap: '5px', flexShrink: 0 }}>
          <span className={`clubs-status-dot clubs-status-dot--${activity.membership_status || 'not_yet_joined'}`} />
          <span style={{ fontSize: '10px', color: '#888', fontWeight: 500 }}>
            {formatMembership(activity.membership_status || 'not_yet_joined')}
          </span>
        </div>
      </div>
    </div>
  );

  const ALIGNMENT_ICONS = {
    interests: { icon: '/interests_icon.svg', label: 'Interests' },
    post_grad: { icon: '/post_grad_goal_icon.svg', label: 'Post-Grad' },
    career: { icon: '/career_goal_icon.svg', label: 'Career' },
  };

  const renderDetailsModal = () => {
    if (!expandedActivity) return null;
    const a = expandedActivity;

    return (
      <>
        <div
          className={`clubs-modal-overlay ${detailsVisible ? 'visible' : ''}`}
          onClick={handleCloseDetails}
        />
        <div className={`clubs-details-modal ${detailsVisible ? 'visible' : ''}`} ref={detailsPanelRef}>
          {/* Header */}
          <div className="clubs-modal-header">
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px', flexWrap: 'wrap' }}>
                <h5 style={{ margin: 0, fontSize: '18px', fontWeight: 600, color: '#333' }}>{a.display_name}</h5>
                <span style={{
                  fontSize: '11px', fontWeight: 600, color: CLUB_GREEN,
                  background: CLUB_GREEN_SUBTLE, padding: '2px 8px', borderRadius: '10px',
                }}>#{a.originalRank}</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                <span style={{ fontSize: '12px', color: '#999', fontFamily: 'monospace' }}>{a.activity_slug}</span>
                {a.activity_type && (
                  <span style={{ fontSize: '11px', color: '#888', background: '#f5f5f5', padding: '1px 8px', borderRadius: '8px' }}>{formatTag(a.activity_type)}</span>
                )}
                {a.domain && (
                  <span style={{ fontSize: '11px', color: '#888', background: '#f5f5f5', padding: '1px 8px', borderRadius: '8px' }}>{formatTag(a.domain)}</span>
                )}
              </div>
            </div>
            <CloseButton onClick={handleCloseDetails} />
          </div>

          {/* Content */}
          <div className="clubs-modal-content">
            {/* Alignment section */}
            {a.aligned_parameters && a.aligned_parameters.length > 0 && (
              <div className="clubs-alignment-section">
                <h6 className="clubs-section-title" style={{ color: '#7b6fa0', marginBottom: '8px' }}>Alignment</h6>
                <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                  {a.aligned_parameters.map(param => {
                    const info = ALIGNMENT_ICONS[param] || { label: param };
                    return (
                      <span key={param} className="clubs-alignment-badge">
                        {info.icon && <img src={info.icon} alt="" style={{ width: 22, height: 22 }} />}
                        <span style={{ fontStyle: 'italic' }}>{info.label}</span>
                      </span>
                    );
                  })}
                </div>
              </div>
            )}

            {/* Mission */}
            {a.mission_synth && (
              <div className="clubs-modal-section">
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <h6 className="clubs-section-title" style={{ marginBottom: 0 }}>Mission</h6>
                  {a.source_of_truth_url && (
                    <a
                      href={a.source_of_truth_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      style={{ display: 'flex', alignItems: 'center', color: '#999', transition: 'color 0.15s' }}
                      onMouseEnter={e => e.currentTarget.style.color = '#666'}
                      onMouseLeave={e => e.currentTarget.style.color = '#999'}
                    >
                      <svg width="12" height="12" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
                        <path d="M6 3H3.5A1.5 1.5 0 002 4.5v8A1.5 1.5 0 003.5 14h8a1.5 1.5 0 001.5-1.5V10m-4-7h4m0 0v4m0-4L7 9" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                      </svg>
                    </a>
                  )}
                </div>
                <p style={{ fontSize: '13.5px', color: '#555', lineHeight: '1.55', margin: '6px 0 0' }}>
                  {a.mission_synth}
                </p>
              </div>
            )}
            {/* Status + quick facts row */}
            <div style={{
              display: 'flex',
              alignItems: 'flex-start',
              justifyContent: 'space-between',
              marginBottom: '25px',
              flexWrap: 'wrap',
              gap: '10px',
              padding: '12px 0px'
            }}>
              {/* Left: membership status in green box */}
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '7px' }}>
                  <span className={`clubs-status-dot clubs-status-dot--${a.membership_status || 'not_yet_joined'}`} />
                  <span style={{ fontSize: '13px', color: '#444', fontWeight: 500 }}>
                    {formatMembership(a.membership_status || 'not_yet_joined')}
                  </span>
                </div>
                <div style={{ fontSize: '12px', color: '#888', marginTop: '3px', marginLeft: '15px' }}>
                  Role: {a.current_role || 'None'}
                </div>
              </div>
              {/* Right: quick facts */}
              {(a.owner_type || a.selectivity_est || a.time_commitment_est) && (
                <div style={{ display: 'flex', gap: '16px', flexWrap: 'wrap' }}>
                  {a.owner_type && (
                    <div className="clubs-glance-item">
                      <span className="clubs-glance-label">Structure</span>
                      <span className="clubs-glance-value">{formatTag(a.owner_type)}</span>
                    </div>
                  )}
                  {a.selectivity_est && (
                    <div className="clubs-glance-item">
                      <span className="clubs-glance-label">Selectivity</span>
                      <span className="clubs-glance-value">{formatTag(a.selectivity_est)}</span>
                    </div>
                  )}
                  {a.time_commitment_est && (
                    <div className="clubs-glance-item">
                      <span className="clubs-glance-label">Commitment</span>
                      <span className="clubs-glance-value">{formatTag(a.time_commitment_est)}</span>
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* Detail sections */}
            {a.what_you_do_synth && (
              <div className="clubs-modal-section">
                <h6 className="clubs-section-title">What You Do</h6>
                <p className="clubs-section-text">{a.what_you_do_synth}</p>
                <div style={{ display: 'flex', gap: '5px', flexWrap: 'wrap', marginTop: '10px' }}>
                  {a.skills_exposed.map(skill => (
                    <span key={skill} className="clubs-detail-pill">{formatTag(skill)}</span>
                  ))}
                </div>
              </div>
            )}
            {a.who_its_for_synth && (
              <div className="clubs-modal-section">
                <h6 className="clubs-section-title">Who It's For</h6>
                <p className="clubs-section-text">{a.who_its_for_synth}</p>
                {a.career_alignment && a.career_alignment.length > 0 && (
                  <div style={{ display: 'flex', gap: '5px', flexWrap: 'wrap', marginTop: '10px' }}>
                    {a.career_alignment.map(career => (
                      <span key={career} className="clubs-detail-pill">{formatTag(career)}</span>
                    ))}
                  </div>
                )}
              </div>
            )}
            {a.how_to_join_synth && (
              <div className="clubs-modal-section">
                <h6 className="clubs-section-title">How to Join</h6>
                <p className="clubs-section-text">{a.how_to_join_synth}</p>
              </div>
            )}

            {/* Available Roles */}
            {a.roles_exposed && a.roles_exposed.length > 0 && (
              <div className="clubs-modal-section">
                <h6 className="clubs-section-title">Available Roles</h6>
                <div style={{ display: 'flex', gap: '5px', flexWrap: 'wrap' }}>
                  {a.roles_exposed.map(role => (
                    <span key={role} className="clubs-role-pill">{formatTag(role)}</span>
                  ))}
                </div>
              </div>
            )}

            {/* Subtags */}
            {a.subtags && a.subtags.length > 0 && (
              <div className="clubs-modal-section">
                <h6 className="clubs-section-title">Other Tags</h6>
                <div style={{ display: 'flex', gap: '5px', flexWrap: 'wrap' }}>
                  {a.subtags.map(tag => (
                    <span key={tag} className="clubs-detail-pill">{formatTag(tag)}</span>
                  ))}
                </div>
              </div>
            )}

            {/* Data confidence — bottom */}
            {a.data_confidence && (
              <div style={{ fontSize: '11px', color: '#bbb', textAlign: 'right', marginTop: '20px' }}>
                Data confidence: {a.data_confidence}
              </div>
            )}
          </div>
        </div>
      </>
    );
  };

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
            <Card.Body style={{ padding: '1.25rem' }}>
              {loading ? (
                <div className="d-flex flex-column align-items-center justify-content-center" style={{ minHeight: 200 }}>
                  <Spinner animation="border" variant="secondary" />
                  <span className="mt-3 text-muted">Loading your club path...</span>
                </div>
              ) : error ? (
                <div className="alert alert-danger">{error}</div>
              ) : !clubPathData?.activities?.length ? (
                <div className="text-center text-muted" style={{ padding: '40px 0' }}>
                  <p style={{ fontSize: '15px', marginBottom: '8px' }}>No clubs in your ClubPath yet.</p>
                  <p className="small" style={{ marginBottom: '16px' }}>Build and tweak your ClubPath using Compass.</p>
                  <Button
                    onClick={() => navigate('/dashboard')}
                    style={{
                      background: CLUB_GREEN, border: 'none', borderRadius: 8,
                      fontFamily: 'Lora, serif', padding: '8px 20px',
                    }}
                  >Go to Dashboard</Button>
                </div>
              ) : (
                <>
                  {renderFilterBar()}
                  <p style={{ color: '#888', fontStyle: 'italic', textAlign: 'center', marginBottom: '1.5rem', fontFamily: 'Lora, serif', fontSize: '16px' }}>Your personalized set of extracurricular activities.</p>

                  {activities.length === 0 && hasActiveFilters ? (
                    <div className="text-center text-muted" style={{ padding: '30px 0' }}>
                      <p style={{ fontSize: '14px' }}>No clubs match your filters.</p>
                    </div>
                  ) : (
                    <div style={{
                      display: 'grid',
                      gridTemplateColumns: 'repeat(2, 1fr)',
                      gap: '14px',
                    }}>
                      {activities.map(renderActivityCard)}
                    </div>
                  )}
                </>
              )}
            </Card.Body>
          </Card>
          {renderDetailsModal()}
        </Container>
      </div>

      {/* Styles */}
      <style>{`
        .clubs-modal-overlay {
          position: fixed;
          top: 0; left: 0;
          width: 100vw; height: 100vh;
          background: rgba(0, 0, 0, 0.6);
          z-index: 2000;
          opacity: 0;
          visibility: hidden;
          transition: opacity 0.25s ease-out;
        }
        .clubs-modal-overlay.visible {
          opacity: 1;
          visibility: visible;
        }

        .clubs-details-modal {
          font-family: 'Lora', serif;
          position: fixed;
          top: 50%; left: 50%;
          transform: translate(-50%, -50%) scale(0.95);
          width: 560px;
          max-width: 90vw;
          max-height: 85vh;
          background: white;
          border-radius: 12px;
          box-shadow: 0 20px 60px rgba(0, 0, 0, 0.25);
          z-index: 2001;
          opacity: 0;
          visibility: hidden;
          transition: all 0.3s ease-out;
          display: flex;
          flex-direction: column;
          overflow: hidden;
        }
        .clubs-details-modal.visible {
          opacity: 1;
          visibility: visible;
          transform: translate(-50%, -50%) scale(1);
        }

        .clubs-modal-header {
          display: flex;
          justify-content: space-between;
          align-items: flex-start;
          padding: 22px 24px 16px;
          border-bottom: 1px solid #f0f0f0;
          flex-shrink: 0;
          gap: 16px;
        }

        .clubs-modal-content {
          flex: 1;
          overflow-y: auto;
          padding: 16px 24px 24px;
          scrollbar-width: none;
        }
        .clubs-modal-content::-webkit-scrollbar {
          display: none;
        }

        .clubs-modal-section {
          margin-top: 8px;
          margin-bottom: 25px;
        }

        .clubs-section-title {
          font-size: 0.7rem;
          font-weight: 600;
          color: #999;
          margin-bottom: 6px;
          text-transform: uppercase;
          letter-spacing: 0.5px;
        }

        .clubs-section-text {
          font-size: 13px;
          color: #555;
          line-height: 1.5;
          margin: 0;
        }

        .clubs-detail-pill {
          font-size: 11px;
          color: #666;
          background: #f5f5f5;
          padding: 3px 10px;
          border-radius: 10px;
          font-weight: 500;
          white-space: nowrap;
        }

        .clubs-alignment-section {
          background: linear-gradient(135deg, rgb(239 232 249), rgba(107, 143, 199, 0.06));
          border-radius: 10px;
          padding: 12px 14px;
          margin-bottom: 16px;
        }

        .clubs-alignment-badge {
          display: inline-flex;
          align-items: center;
          gap: 6px;
          background: white;
          padding: 4px 12px;
          border-radius: 10px;
          font-size: 12px;
          color: #7b6fa0;
          font-weight: 500;
          box-shadow: 0 1px 4px rgba(0,0,0,0.06);
        }

        .clubs-status-dot {
          width: 8px;
          height: 8px;
          border-radius: 50%;
          flex-shrink: 0;
        }
        .clubs-status-dot--not_yet_joined { background: #ccc; }
        .clubs-status-dot--joining { background: #e8a735; }
        .clubs-status-dot--active_member { background: #5a9e5e; }
        .clubs-status-dot--inactive_member { background: #b0b0b0; }
        .clubs-status-dot--left { background: #c85046; }

        .clubs-role-pill {
          font-size: 11px;
          color: #7b6fa0;
          background: rgba(138, 107, 193, 0.10);
          padding: 3px 10px;
          border-radius: 10px;
          font-weight: 500;
          white-space: nowrap;
        }

        .clubs-glance-grid {
          display: grid;
          grid-template-columns: repeat(2, 1fr);
          gap: 10px 20px;
        }

        .clubs-glance-item {
          display: flex;
          flex-direction: column;
          gap: 1px;
        }

        .clubs-glance-label {
          font-size: 10px;
          font-weight: 600;
          color: #999;
          text-transform: uppercase;
          letter-spacing: 0.4px;
        }

        .clubs-glance-value {
          font-size: 13px;
          color: #444;
          font-weight: 500;
        }

        .clubs-mini-tiles {
          display: flex;                                                                                                                                           
          flex-direction: column; 
          gap: 10px;
          margin-bottom: 16px;
        }

        .clubs-mini-tile {
          background: #fafbfd;
          border: 1px solid #f0f0f0;
          border-radius: 8px;
          padding: 12px;
        }

        .clubs-mini-tile-label {
          font-size: 10px;
          font-weight: 600;
          color: #999;
          text-transform: uppercase;
          letter-spacing: 0.5px;
          margin-bottom: 4px;
        }

        .clubs-mini-tile-text {
          font-size: 12px;
          color: #555;
          line-height: 1.45;
          display: -webkit-box;
          -webkit-line-clamp: 5;
          -webkit-box-orient: vertical;
          overflow: hidden;
        }
      `}</style>

      <ChatWindow
        userId={user?.id ? String(user.id) : null}
        isOpen={isChatOpen}
        onToggle={() => setIsChatOpen(!isChatOpen)}
      />
    </div>
  );
}

export default Clubs;
