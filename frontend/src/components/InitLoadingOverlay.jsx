import React from 'react';
import '../styles/InitLoadingOverlay.css';

/**
 * InitLoadingOverlay - Full-page loading screen for initialization
 *
 * Displays during course path initialization with streaming status updates
 * Shows glowing compass animation and current processing step
 */
function InitLoadingOverlay({ isOpen, nodeStatus }) {
  const routeMessages = {
    'rebuild_course_path': 'Building CoursePath',
    'finalize': 'Finalizing',
  };

  if (!isOpen) return null;

  return (
    <div className="init-overlay">
      <div className="init-overlay-backdrop" />
      <div className="init-card">
        <img
          src="/logo.png"
          alt="DreamPath Logo"
          className="init-logo"
        />
        <h2 className="init-title">
          Building your DreamPath
          <span className="ellipses-container">
            <span className="dot">.</span>
            <span className="dot">.</span>
            <span className="dot">.</span>
          </span>
        </h2>
        <img
          src="/compass.svg"
          alt="Compass"
          className="compass-swivel-small"
        />

        {nodeStatus && nodeStatus.status === 'thinking' && (
          <div className="init-status">
            <span className="thinking-text">
              {nodeStatus.message || 'Analyzing'}
            </span>
          </div>
        )}

        {nodeStatus && nodeStatus.status === 'node_info' && (
          <div className="init-status">
            <div className="status-step">
              {routeMessages[nodeStatus.next_node] || nodeStatus.next_node}
            </div>
            {nodeStatus.reason && (
              <div className="status-reason">
                {nodeStatus.next_node === 'finalize'
                  ? 'Putting the finishing touches on your DreamPath'
                  : nodeStatus.reason}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export default InitLoadingOverlay;
