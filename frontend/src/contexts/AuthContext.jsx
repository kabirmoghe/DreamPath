import React, { createContext, useContext, useState, useEffect } from 'react';
import { createClient } from '@supabase/supabase-js';

/**
 * AuthContext - Supabase authentication context for DreamPath
 *
 * Uses Supabase Auth for JWT-based authentication with PostgreSQL backend.
 * User IDs are UUIDs from Supabase.
 */

// Initialize Supabase client
const supabase = createClient(
  import.meta.env.VITE_SUPABASE_URL,
  import.meta.env.VITE_SUPABASE_ANON_KEY
);

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
    // Get initial session
    supabase.auth.getSession().then(({ data: { session } }) => {
      setUser(session?.user ?? null);
      setLoading(false);
    });

    // Listen for auth changes
    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, session) => {
      setUser(session?.user ?? null);
    });

    return () => subscription.unsubscribe();
  }, []);

  const signIn = async (email, password) => {
    const { data, error } = await supabase.auth.signInWithPassword({
      email,
      password,
    });

    if (error) return { user: null, error: error.message };
    return { user: data.user, error: null };
  };

  const signUp = async (email, password, fullName) => {
    const { data, error } = await supabase.auth.signUp({
      email,
      password,
      options: {
        data: {
          full_name: fullName,
        },
        // Redirect to onboarding after email confirmation
        emailRedirectTo: `${window.location.origin}/onboarding`,
      },
    });

    if (error) return { user: null, error: error.message };

    // Note: Supabase user object structure:
    // - id: UUID string (e.g., "a1b2c3d4-e5f6-7890-abcd-ef1234567890")
    // - email: string
    // - user_metadata.full_name: string
    // - session: null until email is confirmed (when confirmation is enabled)

    // Check if email confirmation is required
    // If there's no session, it means email needs to be confirmed
    const needsEmailConfirmation = data.user && !data.session;

    return {
      user: data.user,
      error: null,
      needsEmailConfirmation
    };
  };

  const signOut = async () => {
    await supabase.auth.signOut();
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
