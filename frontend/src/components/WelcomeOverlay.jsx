import React from 'react';
import '../styles/WelcomeOverlay.css';

/**
 * WelcomeOverlay - Centered modal-style welcome message
 *
 * Displays after user completes onboarding with DreamPath theme styling
 */
function WelcomeOverlay({ show, onClose }) {
  if (!show) return null;

  return (
    <div className="welcome-overlay-backdrop" onClick={onClose}>
      <div className="welcome-overlay-card" onClick={(e) => e.stopPropagation()}>
        {/* Close button */}
        <button className="welcome-close-btn" onClick={onClose} aria-label="Close">
          <svg width="20" height="20" viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path
              d="M15 5L5 15M5 5L15 15"
              stroke="#666"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </button>

        {/* DreamPath logo */}
        <div className="welcome-icon">
          <img
            src="/logo.png"
            alt="DreamPath Logo"
            className="welcome-logo"
          />
        </div>

        <h2 className="welcome-title">Welcome to DreamPath!</h2>

        <p className="welcome-message">
          Your personalized course path has been built.
        </p>

        <p className="welcome-submessage">
          Explore your courses and chat with <span className="compass-highlight">Compass</span> to make changes anytime.
        </p>

        <button className="welcome-cta-btn" onClick={onClose}>
          Get Started
        </button>
      </div>
    </div>
  );
}

export default WelcomeOverlay;
