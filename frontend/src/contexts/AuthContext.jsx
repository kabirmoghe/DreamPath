import React, { createContext, useContext, useState, useEffect } from 'react';

/**
 * AuthContext - Simple authentication context for DreamPath
 *
 * For now, this uses localStorage for user session management.
 * In production, you'd want to implement proper JWT-based authentication
 * with your FastAPI backend.
 */

const AuthContext = createContext(null);

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Check for stored user on mount
    const storedUser = localStorage.getItem('dreampath_user');
    if (storedUser) {
      try {
        setUser(JSON.parse(storedUser));
      } catch (e) {
        console.error('Failed to parse stored user:', e);
        localStorage.removeItem('dreampath_user');
      }
    }
    setLoading(false);
  }, []);

  const signIn = async (email, password) => {
    // TODO: Implement real authentication with your backend
    // For now, this is a mock implementation
    // In production, you would:
    // 1. POST to your backend's /auth/login endpoint
    // 2. Receive a JWT token
    // 3. Store the token and user info

    // Mock user for development
    const mockUser = {
      id: 1, // This should come from your database
      email: email,
      name: email.split('@')[0],
    };

    setUser(mockUser);
    localStorage.setItem('dreampath_user', JSON.stringify(mockUser));

    return { user: mockUser, error: null };
  };

  const signUp = async (email, password, fullName) => {
    // TODO: Implement real registration with your backend
    // For now, this is a mock implementation

    const mockUser = {
      id: 1, // This should come from your database
      email: email,
      name: fullName || email.split('@')[0],
    };

    setUser(mockUser);
    localStorage.setItem('dreampath_user', JSON.stringify(mockUser));

    return { user: mockUser, error: null };
  };

  const signOut = async () => {
    setUser(null);
    localStorage.removeItem('dreampath_user');
  };

  const value = {
    user,
    loading,
    signIn,
    signUp,
    signOut,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};
