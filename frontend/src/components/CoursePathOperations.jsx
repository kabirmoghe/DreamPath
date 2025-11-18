import React, { useState } from 'react';
import { Card } from 'react-bootstrap';

// Add keyframe animation for pulsating glow
const pulseAnimation = `
  @keyframes orangePulse {
    0%, 100% {
      box-shadow: 0 0 10px rgba(255, 152, 0, 0.25), 0 0 20px rgba(255, 152, 0, 0.12);
    }
    50% {
      box-shadow: 0 0 22px rgba(255, 152, 0, 0.45), 0 0 45px rgba(255, 152, 0, 0.25);
    }
  }
`;

/**
 * CoursePathOperations - Renders CoursePath operations in a git-diff style
 *
 * Displays operations with color-coded prefixes:
 * - Green "+" for additions
 * - Red "-" for removals
 * - Blue "↔" for moves
 *
 * @param {string} confirmationStatus - "pending", "confirmed", or "skipped"
 */
function CoursePathOperations({ operations, opString, isPending = false, confirmationStatus = "pending" }) {
  const [isCollapsed, setIsCollapsed] = useState(false);

  if (!operations || operations.length === 0) {
    return null;
  }

  const getOperationStyle = (type) => {
    switch (type) {
      case 'add':
        return {
          backgroundColor: 'rgba(76, 175, 80, 0.15)',
          borderLeft: '3px solid #4CAF50',
          color: '#2e7d32',
        };
      case 'remove':
        return {
          backgroundColor: 'rgba(244, 67, 54, 0.15)',
          borderLeft: '3px solid #f44336',
          color: '#c62828',
        };
      case 'move':
        return {
          backgroundColor: 'rgba(33, 150, 243, 0.15)',
          borderLeft: '3px solid #2196F3',
          color: '#1565c0',
        };
      default:
        return {
          backgroundColor: 'rgba(158, 158, 158, 0.15)',
          borderLeft: '3px solid #9e9e9e',
          color: '#424242',
        };
    }
  };

  const getOperationPrefix = (type) => {
    switch (type) {
      case 'add':
        return '+';
      case 'remove':
        return '-';
      case 'move':
        return '↔';
      default:
        return '•';
    }
  };

  const formatOperation = (op) => {
    switch (op.type) {
      case 'add':
        return `${op.course_code} → Term ${op.term}`;
      case 'remove':
        return `${op.course_code} (Term ${op.term})`;
      case 'move':
        return `${op.course_code}: Term ${op.from_term} → Term ${op.to_term}`;
      default:
        return JSON.stringify(op);
    }
  };

  return (
    <>
      {/* Inject animation styles only if pending */}
      {isPending && <style>{pulseAnimation}</style>}

      <Card
        style={{
          background: 'linear-gradient(135deg, rgb(250 238 219) 0%, rgb(255 249 232) 100%)',
          border: '1px solid rgba(255, 152, 0, 0.3)',
          borderRadius: '8px',
          padding: '0',
          marginTop: '8px',
          fontFamily: 'monospace',
          fontSize: '13px',
          width: '100%',
          boxSizing: 'border-box',
          ...(isPending && { animation: 'orangePulse 3s ease-in-out infinite' }),
        }}
      >
      {/* Header with "Pending Modification" */}
      <div
        style={{
          padding: '12px',
          borderBottom: '1px solid rgba(255, 152, 0, 0.2)',
          position: 'relative',
        }}
      >
        <div style={{ fontWeight: 'bold', color: '#f57c00', fontSize: '12px', marginBottom: '4px', fontFamily: 'Lora, serif' }}>
          Pending Modification
        </div>
        {opString && (
          <div style={{ color: '#666', fontSize: '13px', fontFamily: 'monospace' }}>
            {opString}
          </div>
        )}
        {/* Collapse/Expand button */}
        <button
          onClick={() => setIsCollapsed(!isCollapsed)}
          style={{
            position: 'absolute',
            top: '2px',
            right: '2px',
            background: 'transparent',
            border: 'none',
            borderRadius: '4px',
            width: '18px',
            height: '18px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            cursor: 'pointer',
            transition: 'all 0.2s ease',
            padding: '0',
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.background = 'rgba(255, 152, 0, 0.2)';
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = 'transparent';
          }}
        >
          <svg
            width="12"
            height="12"
            viewBox="0 0 12 12"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
            style={{
              transform: isCollapsed ? 'rotate(0deg)' : 'rotate(180deg)',
              transition: 'transform 0.2s ease',
            }}
          >
            <path
              d="M2 4L6 8L10 4"
              stroke="#f57c00"
              strokeWidth="1.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </button>
      </div>

      {/* Operation details - collapsible */}
      <div
        style={{
          padding: isCollapsed ? '0 12px' : '12px',
          maxHeight: isCollapsed ? '0' : '1000px',
          overflow: 'hidden',
          transition: isCollapsed
            ? 'max-height 0.05s ease, padding 0.05s ease'
            : 'max-height 0.1s ease, padding 0.1s ease',
        }}
      >
        {operations.map((op, idx) => (
          <div
            key={idx}
            style={{
              ...getOperationStyle(op.type),
              padding: '8px 12px',
              marginBottom: '6px',
              borderRadius: '4px',
              display: 'flex',
              alignItems: 'center',
              transition: 'all 0.2s',
            }}
          >
            <span
              style={{
                fontWeight: 'bold',
                marginRight: '12px',
                fontSize: '16px',
                minWidth: '20px',
              }}
            >
              {getOperationPrefix(op.type)}
            </span>
            <span>{formatOperation(op)}</span>
          </div>
        ))}
      </div>

      {/* Footer with status */}
      <div
        style={{
          padding: '10px 12px',
          borderTop: (!isCollapsed && confirmationStatus === 'pending') ? '1px solid rgba(255, 152, 0, 0.2)' : 'none',
          fontSize: confirmationStatus === 'pending' ? '12px' : '11px',
          color: confirmationStatus === 'confirmed' ? '#2e7d32' : confirmationStatus === 'skipped' ? '#5a5a5a' : '#666',
          fontFamily: 'Lora, serif',
          textAlign: 'center',
          fontWeight: confirmationStatus !== 'pending' ? 700 : 400,
          backgroundColor: confirmationStatus === 'confirmed' ? '#e5f1d3' : confirmationStatus === 'skipped' ? '#e8e8e8' : 'transparent',
          borderBottomLeftRadius: '8px',
          borderBottomRightRadius: '8px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          gap: '6px',
        }}
      >
        {confirmationStatus === 'pending' && 'Awaiting Confirmation'}
        {confirmationStatus === 'confirmed' && (
          <>
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path
                d="M2 7L5.5 10.5L12 3.5"
                stroke="#2e7d32"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
            <span>CONFIRMED</span>
          </>
        )}
        {confirmationStatus === 'skipped' && (
          <>
            <svg width="12" height="12" viewBox="0 0 12 12" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path
                d="M2 2L10 10M10 2L2 10"
                stroke="#5a5a5a"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
            <span>SKIPPED</span>
          </>
        )}
      </div>
    </Card>
    </>
  );
}

export default CoursePathOperations;
