import React from 'react';
import { Navbar, Nav } from 'react-bootstrap';
import { Link } from 'react-router-dom';
import { BoxArrowRight, InfoCircle } from 'react-bootstrap-icons';

const DREAMPATH_PURPLE = '#8A6BC1';
const NAV_TEXT = '#222';

/**
 * DashboardNavbar - Top navigation bar with logo and controls
 * Navigation links are in LeftSidebar component
 *
 * Props:
 *   onSignOut: Optional callback for sign out action
 */
const DashboardNavbar = ({ onSignOut }) => {

  return (
    <Navbar
      bg="white"
      expand="lg"
      className="w-100"
      style={{
        height: 'var(--navbar-height, 68px)',
        minHeight: 'var(--navbar-height, 68px)',
        boxShadow: '0 1px 4px 0 rgba(0,0,0,0.10)',
        borderBottom: 'none',
        margin: 0,
        paddingLeft: 0,
        paddingRight: 0,
        width: '100vw',
        left: 0,
        right: 0,
        position: 'sticky',
        top: 0,
        zIndex: 1001,
        backgroundColor: '#ffffff',
      }}
    >
      {/* Left: Brand */}
      <Navbar.Brand
        className="fw-bold ms-3 d-flex flex-column align-items-start"
        style={{ fontFamily: 'Lora, serif', color: DREAMPATH_PURPLE, fontSize: 24, letterSpacing: 0.2 }}
      >
        <Link to="/" style={{ textDecoration: 'none' }}>
          <span style={{ fontFamily: 'Lora, serif', color: DREAMPATH_PURPLE, fontSize: 24, letterSpacing: 0.2 }}>
            DreamPath
          </span>
        </Link>
        <img src="/Dartmouth_College_logo.svg" alt="Dartmouth Logo" style={{ height: 12, marginTop: 2, marginLeft: 2, pointerEvents: 'none', paddingBottom: 2 }} />
      </Navbar.Brand>

      {/* Right: Info and Logout icons */}
      <Nav className="ms-auto align-items-center gap-2" style={{ fontSize: 16 }}>
        <Nav.Link className="d-flex align-items-center px-2" style={{ color: NAV_TEXT }}>
          <InfoCircle className="me-1" />
        </Nav.Link>
        {onSignOut && (
          <Nav.Link
            onClick={onSignOut}
            className="d-flex align-items-center px-2 logout-icon-link"
            style={{ color: NAV_TEXT, cursor: 'pointer' }}
          >
            <BoxArrowRight size={20} />
          </Nav.Link>
        )}
      </Nav>
      <style>{`
        .logout-icon-link:hover {
          color: #d32f2f !important;
        }
      `}</style>
    </Navbar>
  );
};

export default DashboardNavbar;
