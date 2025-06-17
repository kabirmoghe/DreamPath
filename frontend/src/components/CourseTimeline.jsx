import React from 'react';

// Props: coursePath (array of arrays of course objects)
// Each course object: { courseCode, isMajor, isComplementary, ... }
const labelColors = {
  major: '#b4a7d6',
  complementary: '#9fc5e8',
  default: '#bbb',
};
const dotColors = {
  major: '#d9d2e9',
  complementary: '#cfe2f3',
  default: '#eee',
};

// For 4 nodes: above, below, above, above
const labelAbove = [true, false, true, true];

const NODE_HEIGHT = 180;
const DOT_SIZE = 24;
const DASHED_HEIGHT = 30;
const LABEL_GAP = 16;
const LABEL_SHIFT = 24;
const LINE_SHIFT = 10;

const yearLabels = ['Y1', 'Y2', 'Y3', 'Y4'];

const CourseTimeline = ({ coursePath }) => {
  return (
    <div className="dreampath-timeline mb-4" style={{ width: '100%', overflowX: 'auto', padding: '48px 0 24px 0', position: 'relative', minHeight: NODE_HEIGHT }}>
      {/* Horizontal line */}
      <div style={{ position: 'absolute', top: '50%', left: 0, right: 0, height: 4, background: '#e0e0e0', zIndex: 0, transform: 'translateY(-50%)' }} />
      <div className="d-flex align-items-center justify-content-between" style={{ position: 'relative', zIndex: 1, width: '100%' }}>
        {Array.from({ length: 4 }).map((_, groupIdx) => {
          // Get all courses for this group of 3 terms
          const groupCourses = [];
          for (let i = 0; i < 3; i++) {
            const termCourses = coursePath[groupIdx * 3 + i] || [];
            groupCourses.push(...termCourses);
          }
          // Only use major courses
          const majorCourses = groupCourses.filter(c => c.isMajor);
          const topCourse = majorCourses
            .sort((a, b) => ((b.majorTotalScore || 0) - (a.majorTotalScore || 0))
              || (a.courseCode || '').localeCompare(b.courseCode || ''))[0];
          // Color logic
          let labelColor = labelColors.default, dotColor = dotColors.default;
          if (topCourse) { labelColor = labelColors.major; dotColor = dotColors.major; }
          const isAbove = labelAbove[groupIdx];
          return (
            <div key={groupIdx} style={{ flex: 1, minWidth: 120, height: NODE_HEIGHT, position: 'relative', display: 'flex', justifyContent: 'center' }}>
              {/* Year label (opposite side of course label) */}
              {isAbove ? (
                <div style={{
                  position: 'absolute',
                  left: '50%',
                  top: `calc(50% + ${DOT_SIZE / 2}px - 10px)`,
                  transform: 'translateX(-50%)',
                  color: '#888',
                  fontStyle: 'italic',
                  fontSize: 15,
                  zIndex: 2,
                }}>{yearLabels[groupIdx]}</div>
              ) : (
                <div style={{
                  position: 'absolute',
                  left: '50%',
                  top: `calc(50% - ${DOT_SIZE / 2}px - 38px)`,
                  transform: 'translateX(-50%)',
                  color: '#888',
                  fontStyle: 'italic',
                  fontSize: 15,
                  zIndex: 2,
                }}>{yearLabels[groupIdx]}</div>
              )}
              {/* Dot always centered on timeline */}
              <div style={{
                position: 'absolute',
                left: '50%',
                top: `calc(50% - ${DOT_SIZE / 2}px)`,
                transform: 'translate(-50%, -50%)',
                width: DOT_SIZE, height: DOT_SIZE,
                borderRadius: DOT_SIZE / 2,
                background: dotColor,
                border: '4px solid #fff',
                boxShadow: '0 1px 4px rgba(0,0,0,0.06)',
                zIndex: 2,
              }} />
              {/* Dashed line and label (above) */}
              {isAbove && topCourse && (
                <>
                  {/* Dashed line from dot up to label, shorter and shifted upward */}
                  <div style={{
                    position: 'absolute',
                    left: '50%',
                    top: `calc(50% - ${DOT_SIZE / 2}px - ${LINE_SHIFT}px)`,
                    width: 2,
                    height: DASHED_HEIGHT,
                    transform: 'translateX(-50%) translateY(-100%)',
                    borderLeft: '2px dashed #bbb',
                    zIndex: 1,
                  }} />
                  {/* Label above, at end of dashed line, shifted upward */}
                  <div style={{
                    position: 'absolute',
                    left: '50%',
                    top: `calc(50% - ${DOT_SIZE / 2}px - ${DASHED_HEIGHT}px - ${LABEL_GAP}px - ${LABEL_SHIFT}px)`,
                    transform: 'translateX(-50%)',
                    background: labelColor,
                    color: '#222',
                    fontWeight: 700,
                    fontSize: 14,
                    borderRadius: 8,
                    padding: '2px 8px',
                    boxShadow: '0 2px 8px rgba(0,0,0,0.08)',
                    letterSpacing: 0.5,
                    border: 'none',
                    zIndex: 3,
                  }}>{topCourse.courseCode}</div>
                </>
              )}
              {/* Dashed line and label (below) */}
              {!isAbove && topCourse && (
                <>
                  {/* Dashed line from dot down to label, shorter and shifted upward */}
                  <div style={{
                    position: 'absolute',
                    left: '50%',
                    top: `calc(50% + ${DOT_SIZE / 2}px - ${LINE_SHIFT}px)`,
                    width: 2,
                    height: DASHED_HEIGHT,
                    transform: 'translateX(-50%)',
                    borderLeft: '2px dashed #bbb',
                    zIndex: 1,
                  }} />
                  {/* Label below, at end of dashed line, shifted upward */}
                  <div style={{
                    position: 'absolute',
                    left: '50%',
                    top: `calc(50% + ${DOT_SIZE / 2}px + ${DASHED_HEIGHT}px + ${LABEL_GAP}px - ${LABEL_SHIFT}px)`,
                    transform: 'translateX(-50%)',
                    background: labelColor,
                    color: '#222',
                    fontWeight: 700,
                    fontSize: 14,
                    borderRadius: 8,
                    padding: '2px 8px',
                    boxShadow: '0 2px 8px rgba(0,0,0,0.08)',
                    letterSpacing: 0.5,
                    border: 'none',
                    zIndex: 3,
                  }}>{topCourse.courseCode}</div>
                </>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default CourseTimeline; 