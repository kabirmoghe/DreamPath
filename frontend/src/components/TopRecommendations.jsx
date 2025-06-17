import React from 'react';
import { ArrowRightShort, BookmarkStar, Star, People } from 'react-bootstrap-icons';

// Props: majorCourse, complementaryCourse, clubRecommendation, onViewAll, onViewAllClubs
const TILE_MAX_WIDTH = 370;
const TopRecommendations = ({ majorCourse, complementaryCourse, clubRecommendation, onViewAll, onViewAllClubs }) => {
  return (
    <div className="top-course-recommendations d-flex w-100" style={{ gap: 16, justifyContent: 'space-between' }}>
      {/* Left: Courses */}
      <div style={{ flex: 1, minWidth: 0 }}>
        {/* Major course card */}
        {majorCourse && (
          <div className="d-flex align-items-center bg-light rounded shadow-sm p-2 mb-2" style={{ minHeight: 48, maxWidth: TILE_MAX_WIDTH, wordBreak: 'break-word' }}>
            <div className="d-flex align-items-center justify-content-center rounded-circle me-2" style={{ width: 32, height: 32, background: '#f3e8ff' }}>
              <BookmarkStar style={{ color: '#8A6BC1', fontSize: 18 }} />
            </div>
            <div>
              <div style={{ fontWeight: 700, fontSize: 15, lineHeight: 1.1 }}>{majorCourse.courseCode}{majorCourse.courseTitle ? `: ${majorCourse.courseTitle}` : ''}</div>
              <div style={{ color: '#6c757d', fontSize: 13 }}>Major Course</div>
            </div>
          </div>
        )}
        {/* Complementary course card */}
        {complementaryCourse && (
          <div className="d-flex align-items-center bg-light rounded shadow-sm p-2" style={{ minHeight: 48, maxWidth: TILE_MAX_WIDTH, wordBreak: 'break-word' }}>
            <div className="d-flex align-items-center justify-content-center rounded-circle me-2" style={{ width: 32, height: 32, background: '#e7f2fb' }}>
              <Star style={{ color: '#4A90E2', fontSize: 18 }} />
            </div>
            <div>
              <div style={{ fontWeight: 700, fontSize: 15, lineHeight: 1.1 }}>{complementaryCourse.courseCode}{complementaryCourse.courseTitle ? `: ${complementaryCourse.courseTitle}` : ''}</div>
              <div style={{ color: '#6c757d', fontSize: 13 }}>Complementary Course</div>
            </div>
          </div>
        )}
        {/* View all courses button */}
        <button
          className="btn btn-link p-0 mb-2"
          style={{ color: '#8A6BC1', fontWeight: 500, background: 'none', border: 'none', display: 'flex', alignItems: 'center', gap: 4, fontSize: 15, textDecoration: 'none', fontStyle: 'normal', marginTop: 10 }}
          onClick={onViewAll}
        >
          View complete course recommendations
          <ArrowRightShort style={{ fontSize: 20, marginLeft: 2, marginBottom: -2 }} />
        </button>
      </div>
      {/* Right: Club Recommendation */}
      <div style={{ flex: 'none', minWidth: 260, display: 'flex', flexDirection: 'column', alignItems: 'flex-end', marginRight: 0, paddingRight: 0 }}>
        {clubRecommendation && (
          <div className="d-flex align-items-center bg-light rounded shadow-sm p-2 mb-2" style={{ minHeight: 48, maxWidth: TILE_MAX_WIDTH, wordBreak: 'break-word' }}>
            <div className="d-flex align-items-center justify-content-center rounded-circle me-2" style={{ width: 32, height: 32, background: '#e6f9f0' }}>
              <People style={{ color: '#228B5A', fontSize: 18 }} />
            </div>
            <div>
              <div style={{ fontWeight: 700, fontSize: 15, lineHeight: 1.1 }}>{clubRecommendation.clubName}</div>
              <div style={{ color: '#6c757d', fontSize: 13 }}>Club Recommendation</div>
            </div>
          </div>
        )}
        {/* View all clubs button */}
        <button
          className="btn btn-link p-0 mb-2"
          style={{ color: '#228B5A', fontWeight: 500, background: 'none', border: 'none', display: 'flex', alignItems: 'center', gap: 4, fontSize: 15, textDecoration: 'none', fontStyle: 'normal', marginTop: 10 }}
          onClick={onViewAllClubs}
        >
          View complete club recommendations
          <ArrowRightShort style={{ fontSize: 20, marginLeft: 2, marginBottom: -2 }} />
        </button>
      </div>
    </div>
  );
};

export default TopRecommendations; 