import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { Container } from 'react-bootstrap';
import LandingPage from './components/LandingPage';
import Login from './components/Auth/Login';
import SignUp from './components/Auth/SignUp';
import Dashboard from './components/Dashboard';
import CreateDetailedProfile from './components/CreateDetailedProfile';
import ProtectedRoute from './components/ProtectedRoute';
import Courses from './components/Courses';
import Clubs from './components/Clubs';

function App() {
  return (
    <Router>
      <div className="app">
        <Routes>
          <Route path="/" element={<LandingPage />} />
          <Route path="/login" element={<Login />} />
          <Route path="/signup" element={<SignUp />} />
          <Route 
            path="/dashboard" 
            element={
              <ProtectedRoute>
                <Dashboard />
              </ProtectedRoute>
            } 
          />
          <Route 
            path="/create-detailed-profile" 
            element={
              <ProtectedRoute>
                <CreateDetailedProfile />
              </ProtectedRoute>
            } 
          />
          <Route path="/courses" element={<Courses />} />
          <Route path="/clubs" element={<Clubs />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </div>
    </Router>
  );
}

export default App; 