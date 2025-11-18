import React from 'react';
import { Nav } from 'react-bootstrap';
import { Link, useLocation } from 'react-router-dom';
import { HouseIcon, BookIcon, PeopleIcon, NetworkIcon } from './icons/DreamPathIcons';
import '../styles/LeftSidebar.css';

const DREAMPATH_PURPLE = '#8A6BC1';
const NAV_TEXT = '#222';
const NAV_TEXT_ACTIVE = '#111';

/**
 * LeftSidebar - Vertical navigation sidebar for DreamPath
 *
 * Features:
 * - Fixed left position
 * - Vertical navigation links with icons
 * - Active state highlighting
 * - Responsive (collapsible on mobile)
 */
const LeftSidebar = () => {
  const location = useLocation();

  const isActive = (path) => location.pathname === path;

  const navItems = [
    { path: '/dashboard', icon: HouseIcon, label: 'Home', disabled: false },
    { path: '/courses', icon: BookIcon, label: 'Courses', disabled: false },
    { path: '/clubs', icon: PeopleIcon, label: 'Clubs', disabled: true },
    { path: '/alumni', icon: NetworkIcon, label: 'Alumni', disabled: true },
  ];

  return (
    <div className="left-sidebar">
      <Nav className="flex-column">
        {navItems.map(({ path, icon: Icon, label, disabled }) => (
          disabled ? (
            <Nav.Link
              key={path}
              className="sidebar-nav-link disabled"
              onClick={(e) => e.preventDefault()}
              style={{ cursor: 'not-allowed' }}
            >
              <Icon size={20} className="sidebar-icon" />
              <span className="sidebar-label">{label}</span>
            </Nav.Link>
          ) : (
            <Nav.Link
              key={path}
              as={Link}
              to={path}
              className={`sidebar-nav-link ${isActive(path) ? 'active' : ''}`}
            >
              <Icon size={20} className="sidebar-icon" />
              <span className="sidebar-label">{label}</span>
            </Nav.Link>
          )
        ))}
      </Nav>
    </div>
  );
};

export default LeftSidebar;
