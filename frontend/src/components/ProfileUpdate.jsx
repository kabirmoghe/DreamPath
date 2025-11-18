import React from 'react';
import { Card } from 'react-bootstrap';

// Add keyframe animation for pulsating glow
const pulseAnimation = `
  @keyframes purplePulse {
    0%, 100% {
      box-shadow: 0 0 10px rgba(138, 107, 193, 0.2), 0 0 20px rgba(138, 107, 193, 0.1);
    }
    50% {
      box-shadow: 0 0 22px rgba(138, 107, 193, 0.3), 0 0 45px rgba(138, 107, 193, 0.15);
    }
  }
`;

/**
 * ProfileUpdate - Renders profile changes in a mini card format
 *
 * Shows before/after values for changed fields with highlighted styling
 */
function ProfileUpdate({ changes, isPending = false }) {
  if (!changes || Object.keys(changes).length === 0) {
    return null;
  }

  const fieldLabels = {
    major: 'Major',
    college_interests: 'College Interests',
    post_grad_goals: 'Post-Graduation Goals',
    career_goals: 'Career Goals',
  };

  return (
    <>
      {/* Inject animation styles only if pending */}
      {isPending && <style>{pulseAnimation}</style>}

      <Card
        style={{
          background: 'linear-gradient(135deg, rgba(138, 107, 193, 0.05) 0%, rgba(107, 143, 199, 0.05) 100%)',
          border: '1px solid rgba(138, 107, 193, 0.3)',
          borderRadius: '8px',
          padding: '0',
          marginTop: '8px',
          ...(isPending && { animation: 'purplePulse 3s ease-in-out infinite' }),
        }}
      >
        {/* Header */}
        <div
          style={{
            padding: '12px',
            borderBottom: '1px solid rgba(138, 107, 193, 0.2)',
          }}
        >
          <div style={{ fontWeight: 'bold', color: '#8A6BC1', fontFamily: 'Lora, serif' }}>
            Pending Profile Updates:
          </div>
        </div>

        {/* Body - Profile changes */}
        <div style={{ padding: '12px' }}>
          {Object.entries(changes).map(([field, change]) => (
            <div
              key={field}
              style={{
                marginBottom: '12px',
                padding: '10px',
                background: 'white',
                borderRadius: '6px',
                border: '1px solid rgba(138, 107, 193, 0.2)',
              }}
            >
              <div style={{ fontWeight: 600, color: '#666', fontSize: '12px', marginBottom: '6px' }}>
                {fieldLabels[field] || field}
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', fontSize: '13px' }}>
                {change.old && (
                  <div
                    style={{
                      padding: '6px 8px',
                      background: 'rgba(244, 67, 54, 0.08)',
                      borderLeft: '2px solid #f44336',
                      borderRadius: '3px',
                      color: '#666',
                      fontStyle: 'italic',
                    }}
                  >
                    <span style={{ color: '#c62828', marginRight: '6px' }}>-</span>
                    {change.old}
                  </div>
                )}
                <div
                  style={{
                    padding: '6px 8px',
                    background: 'rgba(76, 175, 80, 0.08)',
                    borderLeft: '2px solid #4CAF50',
                    borderRadius: '3px',
                    color: '#333',
                  }}
                >
                  <span style={{ color: '#2e7d32', marginRight: '6px' }}>+</span>
                  {change.new}
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* Footer with confirmation message */}
        <div
          style={{
            padding: '10px 12px',
            borderTop: '1px solid rgba(138, 107, 193, 0.2)',
            fontSize: '12px',
            color: '#666',
            fontFamily: 'Lora, serif',
            textAlign: 'center',
          }}
        >
          How do you feel about these updates?
        </div>
      </Card>
    </>
  );
}

export default ProfileUpdate;
