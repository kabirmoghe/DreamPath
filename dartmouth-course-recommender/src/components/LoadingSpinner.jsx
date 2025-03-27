import React, { useState, useEffect } from 'react';
import { Spinner } from 'react-bootstrap';

function LoadingSpinner({ message }) {
  const [subtitleIndex, setSubtitleIndex] = useState(0);
  const [ellipsisCount, setEllipsisCount] = useState(0);
  const [fadeState, setFadeState] = useState('visible');
  
  const subtitleBases = [
    "Finding courses that match your interests",
    "Discovering classes aligned with your post-grad goals",
    "Selecting courses for your career aspirations",
    "Building your DreamPath"
  ];

  // Dynamic ellipsis effect
  useEffect(() => {
    const ellipsisInterval = setInterval(() => {
      setEllipsisCount(prev => prev < 3 ? prev + 1 : 0);
    }, 250); // Change ellipsis every 500ms
    
    return () => clearInterval(ellipsisInterval);
  }, []);

  // Message transition effect
  useEffect(() => {
    const messageInterval = setInterval(() => {
      // Start fade out
      setFadeState('fadeOut');
      
      // After fade out completes, change message and fade in
      setTimeout(() => {
        setSubtitleIndex(prevIndex => (prevIndex + 1) % subtitleBases.length);
        setFadeState('fadeIn');
      }, 500); // Match this with CSS transition time
      
      // Reset to visible after fade in completes
      setTimeout(() => {
        setFadeState('visible');
      }, 500); // Match this with CSS transition time + delay
      
    }, 3500); // Change message every 3.5 seconds
    
    return () => clearInterval(messageInterval);
  }, []);

  return (
    <div className="loading-container">
      <div className="spinner-container">
        <Spinner animation="border" role="status" variant="primary" className="dream-spinner" />
      </div>
      <h4 className="mt-4 loading-title">Building your <span className="dream-text">DreamPath</span></h4>
      <div className="subtitle-container">
        <p className={`loading-subtitle ${fadeState}`}>
          {subtitleBases[subtitleIndex]}
          <span className="loading-ellipsis" aria-hidden="true">
            {'.'.repeat(ellipsisCount)}
          </span>
        </p>
      </div>
    </div>
  );
}

export default LoadingSpinner; 