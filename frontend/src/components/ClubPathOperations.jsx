import React, { useState, useEffect } from 'react';
import { Card } from 'react-bootstrap';

const pulseAnimation = `
  @keyframes clubPulse {
    0%, 100% {
      box-shadow: 0 0 10px rgba(121, 197, 94, 0.2), 0 0 20px rgba(133, 194, 90, 0.1);
    }
    50% {
      box-shadow: 0 0 22px rgba(144, 197, 103, 0.4), 0 0 45px rgba(134, 206, 101, 0.2);
    }
  }
`;

const CLUB_GREEN = '#5a9e5e';
const CLUB_GREEN_BORDER = 'rgba(90, 158, 94, 0.22)';
const CLUB_GREEN_HOVER = 'rgba(17, 65, 20, 0.15)';
const CONFIRMED_BG = 'rgba(90, 158, 94, 0.10)';

const OP_STYLES = {
  add: { bg: 'rgba(76, 175, 80, 0.15)', border: '#4CAF50', color: '#2e7d32', prefix: '+', label: 'Add' },
  remove: { bg: 'rgba(244, 67, 54, 0.15)', border: '#f44336', color: '#c62828', prefix: '-', label: 'Remove' },
  reorder: { bg: 'rgba(33, 150, 243, 0.15)', border: '#2196F3', color: '#1565c0', prefix: '↕', label: 'Reorder' },
  edit: { bg: 'rgba(138, 107, 193, 0.15)', border: '#8A6BC1', color: '#6A4C93', prefix: '✎', label: 'Edit' },
};

function formatSlugAsName(slug) {
  return slug.replace(/-/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

function formatMembership(status) {
  if (!status) return null;
  return status.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

/** Build the nicely formatted header summary from operations */
function buildHeaderSummary(operations) {
  return operations.map(op => {
    const style = OP_STYLES[op.type] || {};
    const name = op.display_name || formatSlugAsName(op.activity_slug || '');
    const label = style.label || op.type;
    if (op.type === 'reorder' && op.rank) return `${label} ${name} to Rank ${op.rank}`;
    if (op.type === 'edit') return `${label} ${name}`;
    return `${label} ${name}`;
  }).join(', ');
}

/**
 * ClubPathOperations - Renders ClubPath operations in a card style
 *
 * Header: nicely formatted summary (always visible, even when collapsed)
 * Body: exact operation details with color-coded prefixes (collapsible)
 */
function ClubPathOperations({ operations, opString, isPending = false, confirmationStatus = "pending" }) {
  const [isCollapsed, setIsCollapsed] = useState(false);

  useEffect(() => {
    if (confirmationStatus === 'confirmed' || confirmationStatus === 'rejected' || confirmationStatus === 'skipped') {
      setIsCollapsed(true);
    }
  }, [confirmationStatus]);

  if (!operations || operations.length === 0) {
    return null;
  }

  const headerSummary = buildHeaderSummary(operations);

  return (
    <>
      {isPending && <style>{pulseAnimation}</style>}

      <Card
        style={{
          background: `linear-gradient(135deg, rgba(90, 158, 94, 0.04) 0%, rgba(90, 158, 94, 0.02) 100%)`,
          border: `1px solid ${CLUB_GREEN_BORDER}`,
          borderRadius: '8px',
          padding: '0',
          marginTop: '8px',
          fontSize: '13px',
          width: '100%',
          boxSizing: 'border-box',
          ...(isPending && { animation: 'clubPulse 3s ease-in-out infinite' }),
        }}
      >
        {/* Header — always visible */}
        <div
          style={{
            padding: '10px 12px',
            borderBottom: `1px solid ${CLUB_GREEN_BORDER}`,
            position: 'relative',
          }}
        >
          <div style={{ fontWeight: 600, color: CLUB_GREEN, fontSize: '12px', marginBottom: '3px', fontFamily: 'Lora, serif' }}>
            ClubPath Modification
          </div>
          <div style={{ color: '#555', fontSize: '13px', fontFamily: 'Lora, serif', paddingRight: '20px' }}>
            {headerSummary}
          </div>
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
            onMouseEnter={(e) => { e.currentTarget.style.background = CLUB_GREEN_HOVER; }}
            onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent'; }}
          >
            <svg
              width="12" height="12" viewBox="0 0 12 12" fill="none" xmlns="http://www.w3.org/2000/svg"
              style={{ transform: isCollapsed ? 'rotate(0deg)' : 'rotate(180deg)', transition: 'transform 0.2s ease' }}
            >
              <path d="M2 4L6 8L10 4" stroke={CLUB_GREEN} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </button>
        </div>

        {/* Operations detail — collapsible */}
        <div
          style={{
            padding: isCollapsed ? '0 12px' : '10px 12px',
            maxHeight: isCollapsed ? '0' : '1000px',
            overflow: 'hidden',
            transition: isCollapsed
              ? 'max-height 0.05s ease, padding 0.05s ease'
              : 'max-height 0.1s ease, padding 0.1s ease',
          }}
        >
          {operations.map((op, idx) => {
            const style = OP_STYLES[op.type] || OP_STYLES.add;
            const slug = op.activity_slug || '';

            // Build detail lines for edit operations
            const editDetails = [];
            if (op.type === 'edit') {
              if (op.membership_status) editDetails.push({ label: 'Status', value: formatMembership(op.membership_status) });
              if (op.current_role != null) editDetails.push({ label: 'Role', value: op.current_role === '' ? 'Clear' : op.current_role });
              if (op.rank) editDetails.push({ label: 'Rank', value: `→ ${op.rank}` });
            }

            return (
              <div
                key={idx}
                style={{
                  backgroundColor: style.bg,
                  borderLeft: `3px solid ${style.border}`,
                  color: style.color,
                  padding: '8px 12px',
                  marginBottom: idx < operations.length - 1 ? '6px' : '0',
                  borderRadius: '4px',
                  transition: 'all 0.2s',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                  <span style={{ fontWeight: 'bold', fontSize: '15px', minWidth: '16px', textAlign: 'center' }}>
                    {style.prefix}
                  </span>
                  <span style={{ fontFamily: 'monospace', fontSize: '13px' }}>
                    {op.type === 'reorder' && op.rank ? `${slug} → Rank ${op.rank}` : slug}
                  </span>
                </div>
                {editDetails.length > 0 && (
                  <div style={{ marginLeft: '26px', marginTop: '4px', display: 'flex', flexDirection: 'column', gap: '2px' }}>
                    {editDetails.map(d => (
                      <div key={d.label} style={{ fontSize: '12px', display: 'flex', gap: '6px' }}>
                        <span style={{ opacity: 0.6, fontWeight: 500 }}>{d.label}:</span>
                        <span style={{ fontWeight: 600 }}>{d.value}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </div>

        {/* Footer */}
        <div
          style={{
            padding: '8px 12px',
            borderTop: (!isCollapsed && confirmationStatus === 'pending') ? `1px solid ${CLUB_GREEN_BORDER}` : 'none',
            fontSize: confirmationStatus === 'pending' ? '12px' : '11px',
            color: confirmationStatus === 'confirmed' ? '#3d7a42' : (confirmationStatus === 'skipped' || confirmationStatus === 'rejected') ? '#5a5a5a' : '#888',
            fontFamily: 'Lora, serif',
            textAlign: 'center',
            fontWeight: confirmationStatus !== 'pending' ? 700 : 400,
            backgroundColor: confirmationStatus === 'confirmed' ? CONFIRMED_BG : (confirmationStatus === 'skipped' || confirmationStatus === 'rejected') ? '#f0f0f0' : 'transparent',
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
                <path d="M2 7L5.5 10.5L12 3.5" stroke="#3d7a42" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
              <span>CONFIRMED</span>
            </>
          )}
          {confirmationStatus === 'rejected' && (
            <>
              <svg width="12" height="12" viewBox="0 0 12 12" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M2 2L10 10M10 2L2 10" stroke="#5a5a5a" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
              <span>REJECTED</span>
            </>
          )}
          {confirmationStatus === 'skipped' && (
            <>
              <svg width="12" height="12" viewBox="0 0 12 12" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M2 2L10 10M10 2L2 10" stroke="#5a5a5a" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
              <span>SKIPPED</span>
            </>
          )}
        </div>
      </Card>
    </>
  );
}

export default ClubPathOperations;
