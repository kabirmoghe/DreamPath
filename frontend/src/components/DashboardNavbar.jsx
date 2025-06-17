import React from 'react';
import { Navbar, Nav } from 'react-bootstrap';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { supabase } from '../lib/supabase';
import { House, Calendar, People, Diagram3, Person, BoxArrowRight } from 'react-bootstrap-icons';

const DREAMPATH_PURPLE = '#8A6BC1';
const NAV_TEXT = '#222';
const NAV_TEXT_ACTIVE = '#111';

const DashboardNavbar = () => {
  const navigate = useNavigate();
  const location = useLocation();

  const handleLogout = async () => {
    await supabase.auth.signOut();
    navigate('/login');
  };

  const isActive = (path) => location.pathname === path;

  return (
    <Navbar
      bg="white"
      expand="lg"
      className="w-100"
      style={{
        minHeight: 56,
        boxShadow: '0 1px 4px 0 rgba(0,0,0,0.10)',
        borderBottom: 'none',
        margin: 0,
        paddingLeft: 0,
        paddingRight: 0,
        width: '100vw',
        left: 0,
        right: 0,
        position: 'relative',
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

      {/* Center: Nav Links - absolutely centered */}
      <Nav
        className="gap-3 align-items-center"
        style={{
          fontSize: 16,
          position: 'absolute',
          left: '50%',
          top: 0,
          bottom: 0,
          transform: 'translateX(-50%)',
          height: '100%',
          display: 'flex',
          alignItems: 'center',
        }}
      >
        <Nav.Link
          as={Link}
          to="/dashboard"
          className="d-flex align-items-center px-2"
          style={{
            color: isActive('/dashboard') ? NAV_TEXT_ACTIVE : NAV_TEXT,
            fontWeight: isActive('/dashboard') ? 600 : 400,
            background: 'none',
            border: 'none',
          }}
        >
          <House className="me-1" /> Home
        </Nav.Link>
        <Nav.Link
          as={Link}
          to="/courses"
          className="d-flex align-items-center px-2"
          style={{
            color: isActive('/courses') ? NAV_TEXT_ACTIVE : NAV_TEXT,
            fontWeight: isActive('/courses') ? 600 : 400,
            background: 'none',
            border: 'none',
          }}
        >
          <Calendar className="me-1" /> Courses
        </Nav.Link>
        <Nav.Link
          as={Link}
          to="/clubs"
          className="d-flex align-items-center px-2"
          style={{
            color: isActive('/clubs') ? NAV_TEXT_ACTIVE : NAV_TEXT,
            fontWeight: isActive('/clubs') ? 600 : 400,
            background: 'none',
            border: 'none',
          }}
        >
          <People className="me-1" /> Clubs
        </Nav.Link>
        <Nav.Link
          as={Link}
          to="/alumni"
          className="d-flex align-items-center px-2"
          style={{
            color: isActive('/alumni') ? NAV_TEXT_ACTIVE : NAV_TEXT,
            fontWeight: isActive('/alumni') ? 600 : 400,
            background: 'none',
            border: 'none',
          }}
        >
          <Diagram3 className="me-1" /> Alumni
        </Nav.Link>
      </Nav>

      {/* Right: Profile and Logout (icon only, with red hover) */}
      <Nav className="ms-auto align-items-center gap-2" style={{ fontSize: 16 }}>
        <Nav.Link as={Link} to="/profile" className="d-flex align-items-center px-2" style={{ color: NAV_TEXT }}>
          <Person className="me-1" /> Profile
        </Nav.Link>
        <Nav.Link
          onClick={handleLogout}
          className="d-flex align-items-center px-2 logout-icon-link"
          style={{ color: NAV_TEXT, cursor: 'pointer' }}
        >
          <BoxArrowRight size={20} />
        </Nav.Link>
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