import React from 'react';
import '../styles/InitLoadingOverlay.css';

const PHASE_LABELS = {
  plan_build: 'Plan',
  update_profile: 'Profile',
  course_search: 'Courses',
  activity_search: 'Activities',
  curate: 'Curate',
  build_dreampath: 'Build',
  reflect: 'Reflect',
  refine: 'Refine',
  finish: 'Finish',
};

const routeMessages = {
  'course_search': 'Searching Courses',
  'activity_search': 'Searching Activities',
  'career_search': 'Exploring Career Paths',
  'plan_builder': 'Planning CoursePath Modifications',
  'course_path': 'Executing CoursePath Operations',
  'club_path': 'Executing ClubPath Operations',
  'modify_profile': 'Updating Profile',
  'rebuild_course_path': 'Building CoursePath',
  'curate': 'Curating Recommendations',
  'build_dreampath': 'Building DreamPath',
  'plan_build': 'Creating Build Plan',
  'finalize': 'Finalizing',
};

// Meta-nodes that shouldn't show as status updates
const HIDDEN_NODES = new Set(['change_mode', 'complete_phase']);

function InitLoadingOverlay({ isOpen, nodeStatus, buildPhases }) {
  if (!isOpen) return null;

  // Find the active phase index for the progress line
  const activeIndex = buildPhases
    ? buildPhases.findIndex(p => p.status === 'active')
    : -1;
  // Progress line fills up to the last completed phase
  const lastCompleteIndex = buildPhases
    ? buildPhases.reduce((acc, p, i) => p.status === 'complete' ? i : acc, -1)
    : -1;
  const progressFraction = buildPhases
    ? (lastCompleteIndex + 1 + (activeIndex > lastCompleteIndex ? 0.5 : 0)) / buildPhases.length
    : 0;

  const activePhase = buildPhases && activeIndex >= 0 ? buildPhases[activeIndex] : null;

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

        {/* Phase stepper timeline */}
        {buildPhases && (
          <div className="phase-stepper">
            {/* Background track */}
            <div className="phase-stepper-track" />
            {/* Progress fill */}
            <div
              className="phase-stepper-fill"
              style={{ width: `${progressFraction * 100}%` }}
            />
            {/* Phase nodes */}
            {buildPhases.map((phase, i) => {
              const left = buildPhases.length > 1
                ? (i / (buildPhases.length - 1)) * 100
                : 50;
              return (
                <div
                  key={phase.name}
                  className="phase-node-container"
                  style={{ left: `${left}%` }}
                >
                  <div className={`phase-node phase-${phase.status}`}>
                    {phase.status === 'complete' && (
                      <svg width="8" height="8" viewBox="0 0 10 10">
                        <path d="M2 5 L4.5 7.5 L8 3" stroke="white" strokeWidth="1.8" fill="none" strokeLinecap="round" strokeLinejoin="round" />
                      </svg>
                    )}
                  </div>
                  <span className={`phase-label ${phase.status === 'active' ? 'phase-label-active' : ''}`}>
                    {PHASE_LABELS[phase.name] || phase.name}
                  </span>
                </div>
              );
            })}
          </div>
        )}

        <img
          src="/compass.svg"
          alt="Compass"
          className="compass-swivel-small"
        />

        {/* Status area — show active phase context or node status */}
        <div className="init-status">
          {activePhase && (
            <div className="phase-active-label">
              {PHASE_LABELS[activePhase.name] || activePhase.name}
            </div>
          )}

          {nodeStatus && nodeStatus.status === 'thinking' && (
            <span className="init-thinking-text">
              Analyzing
            </span>
          )}

          {nodeStatus && nodeStatus.status === 'node_info' && !HIDDEN_NODES.has(nodeStatus.next_node) && (
            <>
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
            </>
          )}

          {!nodeStatus && !activePhase && (
            <span className="init-thinking-text">
              Preparing
            </span>
          )}
        </div>
      </div>
    </div>
  );
}

export default InitLoadingOverlay;
