import React, { useState, useEffect, useRef } from 'react';
import { flushSync } from 'react-dom';
import { Card, Form, Button, Spinner, Dropdown } from 'react-bootstrap';
import { Send, X, ChatDots, Plus, List } from 'react-bootstrap-icons';
import { useQueryClient } from '@tanstack/react-query';
import { apiClient } from '../lib/api';
import CoursePathOperations from './CoursePathOperations';
import ClubPathOperations from './ClubPathOperations';
import ProfileUpdate from './ProfileUpdate';
import '../styles/ChatWindow.css';

/**
 * ChatWindow (Compass) - A collapsible chat interface for interacting with the Compass agent
 *
 * Features:
 * - Streaming responses
 * - Interrupt handling
 * - Persistent conversation (via threadId)
 * - Thread management (create, list, switch)
 * - Slides in from the right
 */
const getCompassIcon = (nodeStatus) => {
  if (!nodeStatus) return '/compass_baseline.png';
  if (nodeStatus.status === 'thinking') return '/compass_baseline.png';

  const node = nodeStatus.next_node;
  if (node === 'course_search' || node === 'career_search' || node === 'activity_search') return '/compass_search.png';
  if (node === 'course_path' || node === 'club_path' || node === 'modify_profile' || node === 'curate' || node === 'build_dreampath') return '/compass_edit.png';
  if (node === 'finalize') return '/compass_finalize.png';
  return '/compass_baseline.png';
};

function ChatWindow({ userId, isOpen = true, onToggle }) {
  const queryClient = useQueryClient();
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [threadId, setThreadId] = useState(null);
  const [threads, setThreads] = useState([]);
  const [error, setError] = useState(null);
  const [nodeStatus, setNodeStatus] = useState(null); // Track current node status
  const [loadingHistory, setLoadingHistory] = useState(false);
  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);
  const chatBodyRef = useRef(null);
  const [isScrolledUp, setIsScrolledUp] = useState(false);
  const [confirmNote, setConfirmNote] = useState('');
  const [showConfirmNote, setShowConfirmNote] = useState(false);
  const [agentMode, setAgentMode] = useState('advise'); // 'advise' or 'build'
  const [buildPhases, setBuildPhases] = useState(null); // array of {name, status} during build

  // Track scroll position — tuck mascot when user scrolls up
  useEffect(() => {
    const el = chatBodyRef.current;
    if (!el) return;

    const handleScroll = () => {
      const threshold = 80;
      const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < threshold;
      setIsScrolledUp(!atBottom);
    };

    el.addEventListener('scroll', handleScroll, { passive: true });
    return () => el.removeEventListener('scroll', handleScroll);
  }, [isOpen]);

  // Mapping of route names to user-friendly messages
  const routeMessages = {
    'course_search': 'Searching Courses',
    'activity_search': 'Searching Activities',
    'career_search': 'Understanding Careers',
    'course_path': 'Executing CoursePath Operations',
    'club_path': 'Updating ClubPath',
    'modify_profile': 'Updating Profile',
    'change_mode': 'Switching Mode',
    'plan_build': 'Planning Build',
    'complete_phase': 'Advancing Phase',
    'curate': 'Curating Recommendations',
    'build_dreampath': 'Building DreamPath',
    'finalize': 'Finalizing',
  };

  // Initialize thread on mount
  useEffect(() => {
    const initializeThreads = async () => {
      if (!userId) return;

      try {
        // Load threads from database
        const userThreads = await apiClient.getUserThreads(userId);
        setThreads(userThreads);

        // Get or create current thread
        let currentThreadId = apiClient.getCurrentThreadId(userId);

        if (userThreads.length === 0) {
          // No threads exist - create first thread
          const newThread = await apiClient.createThread(userId);
          currentThreadId = newThread.id;
          setThreads([newThread]);
        } else if (!currentThreadId) {
          // Threads exist but no current selection (e.g., incognito) - use most recent
          currentThreadId = userThreads[0].id;
        } else {
          // Have a stored thread ID - verify it still exists
          const threadExists = userThreads.some(t => t.id === currentThreadId);
          if (!threadExists) {
            // Stored thread doesn't exist anymore - use most recent
            currentThreadId = userThreads[0].id;
          }
        }

        setThreadId(currentThreadId);

        // Set mode from thread data
        const currentThread = userThreads.find(t => t.id === currentThreadId);
        if (currentThread?.mode) {
          setAgentMode(currentThread.mode);
          setBuildPhases(currentThread.mode === 'build' ? null : null);
        }

        // Load history for this thread
        await loadThreadHistory(currentThreadId);
      } catch (error) {
        console.error('Failed to initialize threads:', error);
        setError('Failed to load conversation threads');
      }
    };

    initializeThreads();
  }, [userId]);

  // Load history for a thread
  const loadThreadHistory = async (tid) => {
    setLoadingHistory(true);
    try {
      const history = await apiClient.getHistory(tid);
      if (history && history.messages) {
        // Limit to last 50 messages for performance
        const recentMessages = history.messages.slice(-50);

        // Process messages to mark confirmation responses as hidden in UI
        const processedMessages = recentMessages.map((msg, idx) => {
          if (msg.type === 'human' && (
            msg.content?.startsWith('confirm') || msg.content?.startsWith('reject') ||
            msg.content?.startsWith('accept') || msg.content?.startsWith('cancel')
          )) {
            const prevMsg = recentMessages[idx - 1];
            if (prevMsg?.type === 'ai' && (
              prevMsg.custom_data?.event_type === 'coursepath_operations' ||
              prevMsg.custom_data?.event_type === 'clubpath_operations' ||
              prevMsg.custom_data?.event_type === 'profile_update'
            )) {
              return { ...msg, hideInUI: true };
            }
          }
          return msg;
        });

        setMessages(processedMessages);
      } else {
        setMessages([]);
      }
    } catch (err) {
      console.error('Failed to load thread history:', err);
      // If history fails, just start with empty messages
      // This is expected for new threads that haven't been used yet
      setMessages([]);
    } finally {
      setLoadingHistory(false);
    }
  };


  // Auto-scroll to bottom when new messages arrive or node status updates
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, nodeStatus]);

  // Scroll to bottom when history finishes loading
  useEffect(() => {
    if (!loadingHistory && messages.length > 0) {
      // Use setTimeout to ensure DOM has updated
      setTimeout(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'instant' });
      }, 50);
    }
  }, [loadingHistory]);

  // Scroll to bottom when chat window opens
  useEffect(() => {
    if (isOpen && messages.length > 0) {
      // Use setTimeout to ensure animation/rendering completes
      setTimeout(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'instant' });
      }, 350); // Slightly longer than the slideIn animation (300ms)
    }
  }, [isOpen]);

  // Focus input when chat opens
  useEffect(() => {
    if (isOpen && inputRef.current) {
      inputRef.current.focus();
    }
  }, [isOpen]);

  // Auto-resize textarea based on content
  useEffect(() => {
    if (inputRef.current) {
      inputRef.current.style.height = 'auto';
      inputRef.current.style.height = `${inputRef.current.scrollHeight}px`;
    }
  }, [input]);

  // Create new thread
  const handleCreateNewThread = async () => {
    try {
      const newThread = await apiClient.createThread(userId);
      setThreadId(newThread.id);
      setThreads([newThread, ...threads]);
      setMessages([]);
      setError(null);
      setNodeStatus(null);
      setAgentMode('advise');
      setBuildPhases(null);
    } catch (error) {
      console.error('Failed to create thread:', error);
      setError('Failed to create new conversation');
    }
  };

  // Switch to a different thread
  const handleSwitchThread = async (tid) => {
    if (tid === threadId) return; // Already on this thread

    apiClient.switchThread(userId, tid);
    setThreadId(tid);
    setError(null);
    setNodeStatus(null);

    // Set mode from thread data
    const thread = threads.find(t => t.id === tid);
    setAgentMode(thread?.mode || 'advise');
    setBuildPhases(null);

    // Load history for the new thread
    await loadThreadHistory(tid);
  };

  const handleSend = async (messageOverride = null) => {
    const userMessage = messageOverride || input.trim();
    if (!userMessage || isLoading || !threadId) return;

    setInput('');
    setConfirmNote('');
    setShowConfirmNote(false);
    setError(null);
    setNodeStatus(null); // Clear any previous node status

    // Reset textarea height
    if (inputRef.current) {
      inputRef.current.style.height = 'auto';
    }

    // Add user message to chat
    // Mark confirmation responses as hidden (don't render in UI, but send to backend)
    const isConfirmationResponse =
      userMessage.startsWith('confirm') || userMessage.startsWith('reject') ||
      userMessage.startsWith('accept') || userMessage.startsWith('cancel');
    setMessages(prev => [...prev, {
      type: 'human',
      content: userMessage,
      ...(isConfirmationResponse && { hideInUI: true })
    }]);
    setIsLoading(true);

    try {
      // Stream the response
      let assistantMessage = '';
      let isFirstChunk = true;
      let receivedTokens = false; // Track if we're receiving token stream
      let streamStartTime = null;
      let tokenCount = 0;

      for await (const chunk of apiClient.stream({
        message: userMessage,
        userId: String(userId),
        threadId: threadId,
        streamTokens: true,
      })) {

        if (typeof chunk === 'string') {
          // Token streaming
          tokenCount++;
          assistantMessage += chunk;
          receivedTokens = true;

          if (!streamStartTime) {
            streamStartTime = Date.now();
            console.log('🔵 FRONTEND: Token streaming started');
          }

          // ALWAYS clear node status when receiving tokens
          flushSync(() => {
            setNodeStatus(null);
          });

          // Use flushSync to prevent React from batching updates
          // This ensures tokens appear immediately as they stream in
          flushSync(() => {
            if (isFirstChunk) {
              setMessages(prev => [...prev, { type: 'ai', content: chunk }]);
              isFirstChunk = false;
            } else {
              setMessages(prev => {
                const newMessages = [...prev];
                newMessages[newMessages.length - 1] = {
                  type: 'ai',
                  content: assistantMessage,
                };
                return newMessages;
              });
            }
          });
        } else if (typeof chunk === 'object') {
          // Check if this is a node status event
          if (chunk.custom_data && chunk.custom_data.event_type === 'node_status') {
            // Don't show node status if we're already receiving token stream
            if (!receivedTokens) {
              flushSync(() => {
                setNodeStatus(chunk.custom_data);
              });
            }
          } else if (chunk.custom_data && chunk.custom_data.event_type === 'mode_change') {
            // Mode change — update pill immediately
            flushSync(() => {
              setAgentMode(chunk.custom_data.mode);
              if (chunk.custom_data.mode === 'advise') {
                setBuildPhases(null);
              }
            });
          } else if (chunk.custom_data && chunk.custom_data.event_type === 'phase_update') {
            // Build mode phase progress — update stepper
            flushSync(() => {
              setBuildPhases(chunk.custom_data.phases || null);
            });
          } else if (chunk.type === 'ai') {
            // Only process AI messages that have meaningful content or structured data
            const hasContent = chunk.content && chunk.content.trim().length > 0;
            const hasStructuredData = chunk.custom_data && chunk.custom_data.event_type;

            if (hasContent || hasStructuredData) {
              // Skip complete message if we already received tokens
              // (the complete message would overwrite the accumulated tokens)
              if (receivedTokens && hasContent && !hasStructuredData) {
                console.log('🔵 FRONTEND: Skipping complete message (tokens already streamed)');
                continue;
              }

              // Clear node status when actual content arrives
              flushSync(() => {
                setNodeStatus(null);
              });

              // Complete message object
              flushSync(() => {
                if (isFirstChunk) {
                  setMessages(prev => [...prev, chunk]);
                  isFirstChunk = false;
                } else {
                  setMessages(prev => {
                    const newMessages = [...prev];
                    newMessages[newMessages.length - 1] = chunk;
                    return newMessages;
                  });
                }
              });
            }
          }
        }
      }

      if (streamStartTime) {
        const elapsed = Date.now() - streamStartTime;
        console.log(`🔵 FRONTEND: Token streaming ended (${tokenCount} tokens in ${elapsed}ms)`);
      }

      // Stream completed successfully - invalidate queries to refetch
      // This ensures the app updates with any changes made by Compass
      queryClient.invalidateQueries(['coursePath', userId]);
      queryClient.invalidateQueries(['clubPath', userId]);
      queryClient.invalidateQueries(['profile', userId]);

      // Refetch thread to pick up mode changes
      try {
        const updatedThread = await apiClient.getThread(threadId);
        if (updatedThread?.mode) {
          setAgentMode(updatedThread.mode);
          if (updatedThread.mode === 'advise') {
            setBuildPhases(null);
          }
        }
      } catch (e) {
        console.error('Failed to refetch thread mode:', e);
      }

      // Update thread timestamp
      apiClient.updateThreadTimestamp(userId, threadId);

    } catch (err) {
      console.error('Chat error:', err);
      setError(err.message || 'Failed to send message');
      setMessages(prev => [
        ...prev,
        {
          type: 'ai',
          content: `❌ Error: ${err.message || 'Failed to send message'}`,
        },
      ]);
    } finally {
      setIsLoading(false);
      setNodeStatus(null); // Clear node status when done

      // Update thread's last_message_at timestamp in database
      if (threadId) {
        try {
          await apiClient.updateThreadTimestamp(userId, threadId);
        } catch (err) {
          console.error('Failed to update thread timestamp:', err);
          // Non-critical error, don't show to user
        }
      }
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  // Return the event_type of the pending confirmation, or null if none
  const getPendingConfirmationType = () => {
    if (messages.length === 0 || isLoading) return null;

    // Find last visible message (skip hidden confirm/reject responses)
    let lastVisibleMsg = null;
    for (let i = messages.length - 1; i >= 0; i--) {
      const msg = messages[i];
      if (msg.hideInUI) continue;
      lastVisibleMsg = msg;
      break;
    }

    if (!lastVisibleMsg) return null;

    const eventType = lastVisibleMsg.custom_data?.event_type;
    if (lastVisibleMsg.type === 'ai' &&
        (eventType === 'coursepath_operations' || eventType === 'clubpath_operations' || eventType === 'profile_update')) {
      return eventType;
    }

    return null;
  };

  const pendingConfirmationType = getPendingConfirmationType();
  const showConfirmButtons = pendingConfirmationType !== null;

  // Build the action message, appending the optional note if provided
  const buildActionMessage = (action) =>
    confirmNote.trim() ? `${action}: ${confirmNote.trim()}` : action;

  // Custom lightweight markdown renderer
  const renderMarkdown = (text) => {
    if (!text) return null;

    // Split by lines to handle headings
    const lines = text.split('\n');
    const elements = [];

    lines.forEach((line, lineIdx) => {
      let processedLine = line;
      const parts = [];
      let lastIndex = 0;
      let key = 0;

      // Check if line is a heading
      const headingMatch = line.match(/^(#{1,4})\s+(.+)$/);
      if (headingMatch) {
        const level = headingMatch[1].length;
        if (level <= 3) {
          // h1-h3: pill style
          const fontSize = level === 1 ? '16px' : level === 2 ? '15px' : '14px';
          elements.push(
            <div
              key={`line-${lineIdx}`}
              className="chat-heading-pill"
              style={{
                fontSize,
                marginTop: lineIdx > 0 ? '10px' : 0,
              }}
            >
              {headingMatch[2].replace(/\*\*/g, '')}
            </div>
          );
        } else {
          // h4: simple bold
          elements.push(
            <div key={`line-${lineIdx}`} style={{ fontWeight: 'bold', marginTop: lineIdx > 0 ? '8px' : 0 }}>
              {headingMatch[2].replace(/\*\*/g, '')}
            </div>
          );
        }
        return;
      }

      // Process inline markdown: links, bold, italic, code
      const patterns = [
        { regex: /\[([^\]]+)\]\(([^)]+)\)/g, type: 'link' },      // [text](url)
        { regex: /\*\*([^*]+)\*\*/g, type: 'bold' },              // **bold**
        { regex: /(?<!\*)\*(?!\*)([^*]+)\*(?!\*)/g, type: 'italic' },  // *italic* (not **)

        { regex: /`([^`]+)`/g, type: 'code' },                    // `code`
      ];

      // Find all matches with their positions
      const matches = [];
      patterns.forEach(({ regex, type }) => {
        const matches_for_pattern = [...processedLine.matchAll(regex)];
        matches_for_pattern.forEach(match => {
          matches.push({
            type,
            start: match.index,
            end: match.index + match[0].length,
            match: match,
            fullText: match[0],
          });
        });
      });

      // Sort by position, then by length (longer matches first to handle ** before *)
      matches.sort((a, b) => {
        if (a.start !== b.start) return a.start - b.start;
        return b.end - a.end; // Longer match first
      });

      // Remove overlapping matches (keep first/longest at each position)
      const filteredMatches = [];
      let lastEnd = 0;
      matches.forEach(match => {
        if (match.start >= lastEnd) {
          filteredMatches.push(match);
          lastEnd = match.end;
        }
      });

      // Build the line with mixed text and formatted parts
      filteredMatches.forEach(({ type, start, end, match }) => {
        // Add text before this match
        if (start > lastIndex) {
          parts.push(processedLine.substring(lastIndex, start));
        }

        // Add the formatted element
        if (type === 'link') {
          parts.push(
            <a
              key={`${lineIdx}-${key++}`}
              href={match[2]}
              target="_blank"
              rel="noopener noreferrer"
              style={{ color: '#6B8FC7', textDecoration: 'underline' }}
            >
              {match[1]}
            </a>
          );
        } else if (type === 'bold') {
          parts.push(<strong key={`${lineIdx}-${key++}`}>{match[1]}</strong>);
        } else if (type === 'italic') {
          parts.push(<em key={`${lineIdx}-${key++}`}>{match[1]}</em>);
        } else if (type === 'code') {
          parts.push(
            <code
              key={`${lineIdx}-${key++}`}
              style={{
                background: '#f5f5f5',
                padding: '2px 6px',
                borderRadius: 3,
                fontFamily: 'monospace',
                fontSize: '0.9em',
              }}
            >
              {match[1]}
            </code>
          );
        }

        lastIndex = end;
      });

      // Add remaining text
      if (lastIndex < processedLine.length) {
        parts.push(processedLine.substring(lastIndex));
      }

      // If no matches, just add the plain line
      if (parts.length === 0) {
        parts.push(processedLine);
      }

      // Empty lines become visible paragraph breaks
      if (processedLine.trim() === '') {
        elements.push(<div key={`line-${lineIdx}`} style={{ height: '0.5em' }} />);
      } else {
        elements.push(<div key={`line-${lineIdx}`}>{parts}</div>);
      }
    });

    return elements;
  };

  const renderMessage = (msg, idx) => {
    // Skip hidden messages (e.g., confirm/cancel responses)
    if (msg.hideInUI) {
      return null;
    }

    const isUser = msg.type === 'human';

    // Check for structured message types
    const hasStructuredData = msg.custom_data && msg.custom_data.event_type;
    const hasTextContent = msg.content && msg.content.trim().length > 0;

    // Determine if this message is "pending" (awaiting user action)
    // A message is pending if it's the last message, or if it's second-to-last and last is user message
    const isLastMessage = idx === messages.length - 1;
    const isSecondToLast = idx === messages.length - 2;
    const lastMessageIsUser = messages.length > 0 && messages[messages.length - 1].type === 'human';
    const isPending = isLastMessage || (isSecondToLast && lastMessageIsUser);

    // Determine confirmation status for structured cards
    let confirmationStatus = 'pending';
    const nextMsg = messages[idx + 1];
    if (nextMsg && nextMsg.type === 'human') {
      if (msg.custom_data?.event_type === 'coursepath_operations' || msg.custom_data?.event_type === 'clubpath_operations') {
        if (nextMsg.content?.startsWith('confirm')) {
          confirmationStatus = 'confirmed';
        } else if (nextMsg.content?.startsWith('reject') || nextMsg.content?.startsWith('cancel')) {
          confirmationStatus = 'rejected';
        }
      } else if (msg.custom_data?.event_type === 'profile_update') {
        if (nextMsg.content?.startsWith('accept')) {
          confirmationStatus = 'accepted';
        } else if (nextMsg.content?.startsWith('reject')) {
          confirmationStatus = 'rejected';
        }
      }
    }

    return (
      <div
        key={idx}
        className={`message ${isUser ? 'message-user' : 'message-assistant'}`}
      >
        <div
          className="message-content"
          style={
            !isUser && hasStructuredData && !hasTextContent
              ? {
                  background: 'transparent',
                  padding: 0,
                  border: 'none',
                  maxWidth: '90%',
                }
              : {}
          }
        >
          {/* Only render text if there's actual content */}
          {hasTextContent && (
            <div className="message-text" style={{ fontFamily: 'Lora, serif' }}>
              {isUser ? msg.content : renderMarkdown(msg.content)}
            </div>
          )}

          {/* Render structured components for assistant messages */}
          {!isUser && hasStructuredData && (
            <div style={{ marginTop: hasTextContent ? '8px' : '0' }}>
              {msg.custom_data.event_type === 'coursepath_operations' && (
                <CoursePathOperations
                  operations={msg.custom_data.operations}
                  opString={msg.custom_data.op_string}
                  isPending={isPending}
                  confirmationStatus={confirmationStatus}
                />
              )}
              {msg.custom_data.event_type === 'clubpath_operations' && (
                <ClubPathOperations
                  operations={msg.custom_data.operations}
                  opString={msg.custom_data.op_string}
                  isPending={isPending}
                  confirmationStatus={confirmationStatus}
                />
              )}
              {msg.custom_data.event_type === 'profile_update' && (
                <ProfileUpdate changes={msg.custom_data.changes} isPending={isPending} confirmationStatus={confirmationStatus} />
              )}
            </div>
          )}
        </div>
      </div>
    );
  };

  if (!isOpen) {
    return (
      <div className="compass-toggle-button" onClick={onToggle}>
        <div className="compass-toggle-content">
          <img src="/compass.svg" alt="Compass" style={{ width: '20px', height: '20px' }} />
          <span className="compass-label">Chat</span>
        </div>
      </div>
    );
  }

  return (
    <div className="compass-window">
      <Card className="h-100">
        <Card.Header className="d-flex justify-content-between align-items-center compass-header">
          <h6 className="mb-0" style={{ fontFamily: 'Lora, serif', fontWeight: 500, color: '#cdcdec', letterSpacing: 0 }}>Compass</h6>

          <div className="d-flex align-items-center gap-2">
            {/* Thread History Dropdown */}
            <Dropdown>
              <Dropdown.Toggle
                as="button"
                className="thread-control-btn"
                style={{
                  background: 'rgba(255, 255, 255, 0.15)',
                  border: '1px solid rgba(255, 255, 255, 0.2)',
                  borderRadius: '6px',
                  padding: '4px 8px',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '4px',
                  cursor: 'pointer',
                  transition: 'all 0.2s',
                  fontSize: '12px',
                  fontWeight: 500,
                  color: '#cdcdec',
                }}
                title="View all chats"
              >
                <List size={14} />
              </Dropdown.Toggle>
              <Dropdown.Menu
                align="end"
                style={{
                  maxHeight: '300px',
                  overflowY: 'auto',
                  borderRadius: '8px',
                  border: '1px solid #e0e0e0',
                  boxShadow: '0 4px 12px rgba(0,0,0,0.1)',
                  minWidth: '200px',
                }}
              >
                {threads.length > 0 ? (
                  threads.map((thread) => (
                    <Dropdown.Item
                      key={thread.id}
                      active={thread.id === threadId}
                      onClick={() => handleSwitchThread(thread.id)}
                      style={{
                        padding: '8px 16px',
                        fontSize: '13px',
                        fontWeight: thread.id === threadId ? 600 : 400,
                        backgroundColor: thread.id === threadId ? '#f3f0fa' : 'transparent',
                        color: thread.id === threadId ? '#8A6BC1' : '#333',
                      }}
                    >
                      {thread.label}
                    </Dropdown.Item>
                  ))
                ) : (
                  <Dropdown.Item disabled style={{ fontSize: '13px', color: '#999' }}>
                    No threads yet
                  </Dropdown.Item>
                )}
              </Dropdown.Menu>
            </Dropdown>

            {/* New Thread Button */}
            <button
              onClick={handleCreateNewThread}
              className="new-thread-btn"
              style={{
                background: 'rgba(255, 255, 255, 0.2)',
                border: '1px solid rgba(255, 255, 255, 0.3)',
                borderRadius: '6px',
                width: '24px',
                height: '24px',
                padding: '0',
                display: 'flex',
                justifyContent: 'center',
                alignItems: 'center',
                cursor: 'pointer',
                transition: 'all 0.2s',
                color: '#cdcdec',
              }}
              title="Start new conversation"
            >
              <Plus size={16} strokeWidth={2.5} />
            </button>

            {/* Close Button */}
            <Button
              variant="link"
              size="sm"
              onClick={onToggle}
              style={{ color: '#cdcdec', padding: 0 }}
              title="Close"
            >
              <X size={20} />
            </Button>
          </div>
        </Card.Header>

        <Card.Body ref={chatBodyRef} className="chat-messages">

          {loadingHistory ? (
            <div className="d-flex justify-content-center align-items-center" style={{ height: '200px' }}>
              <div className="text-center">
                <Spinner animation="border" variant="secondary" size="sm" />
                <p className="text-muted small mt-2">Loading conversation...</p>
              </div>
            </div>
          ) : (
            <>
              {messages.length === 0 && (
                <div className="chat-welcome">
                  <p className="text-muted" style={{ fontSize: '15px' }}>
                    <strong>Hi! I'm <span style={{ fontStyle: 'italic', color: '#9b86d4' }}>Compass</span>, your DreamPath Advisor.</strong>
                  </p>
                  <p className="text-muted small">Ask me about:</p>
                  <ul className="text-muted small">
                    <li>Personalized course recommendations</li>
                    <li>Brainstorming & refining career options</li>
                    <li>Making modifications to your CoursePath</li>
                    <li>Updating your Student Profile</li>
                    <li><strong>How to plan for your future...</strong></li>
                  </ul>
                </div>
              )}

              {messages.map((msg, idx) => renderMessage(msg, idx))}

          {/* Node Status Indicator */}
          {nodeStatus && (
            nodeStatus.status === 'thinking' ? (
              // Thinking status - with bubble
              <div className="message message-status">
                <div className="message-content">
                  <div className="message-text" style={{ fontFamily: 'Lora, serif', color: '#666' }}>
                    <div style={{ opacity: 0.8 }}>
                      <span className="chat-thinking-text">{nodeStatus.message || 'Thinking'}</span>
                    </div>
                  </div>
                </div>
              </div>
            ) : (
              // Node info status - keep bubble
              <div className="message message-status">
                <div className="message-content">
                  <div className="message-text" style={{ fontFamily: 'Lora, serif', color: '#666' }}>
                    {nodeStatus.status === 'node_info' && nodeStatus.next_node && (
                      <div style={{ fontSize: '14px', opacity: 0.8 }}>
                        <div className="status-with-ellipses" style={{ fontWeight: 'bold' }}>
                          {routeMessages[nodeStatus.next_node] || nodeStatus.next_node}
                          <span className="ellipses-animation"></span>
                        </div>
                        {nodeStatus.reason && (
                          <div style={{ fontSize: '12px', marginTop: '4px', fontStyle: 'italic' }}>
                            {nodeStatus.reason}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            )
          )}

              {error && (
                <div className="alert alert-danger alert-sm mt-2">{error}</div>
              )}

              <div ref={messagesEndRef} />
            </>
          )}
        </Card.Body>

        <Card.Footer className="chat-input-container">
          {/* Compass mascot - peeks up when agent is working */}
          {(() => {
            const icon = getCompassIcon(nodeStatus);
            const isWide = icon === '/compass_plan_modify.png';
            return (
              <img
                src={icon}
                alt="Compass"
                className={`compass-mascot ${isLoading ? 'compass-mascot-active' : ''} ${isScrolledUp ? 'compass-mascot-scrolled' : ''} ${isWide ? 'compass-mascot-wide' : ''}`}
              />
            );
          })()}

          {/* Confirm/Accept + Reject buttons positioned above textarea */}
          {showConfirmButtons && (
            <div className="confirm-buttons-container">
              {/* Note textarea — appears above the button row when expanded */}
              {showConfirmNote && (
                <textarea
                  value={confirmNote}
                  onChange={(e) => setConfirmNote(e.target.value)}
                  placeholder="Wanted a different term, prefer a different course..."
                  rows={2}
                  style={{
                    width: '100%',
                    border: '1px dashed rgb(227 222 237)',
                    borderRadius: '6px',
                    padding: '6px 8px',
                    fontSize: '12px',
                    fontFamily: 'Lora, serif',
                    color: 'rgb(85, 85, 85)',
                    resize: 'none',
                    outline: 'none',
                    background: 'rgb(248 239 255 / 95%)',
                    marginBottom: '6px',
                    display: 'block',
                  }}
                />
              )}
              {/* Action buttons + pencil note toggle — all inline */}
              <div className="confirm-buttons">
                <button
                  onClick={() => handleSend(buildActionMessage(pendingConfirmationType === 'profile_update' ? 'accept' : 'confirm'))}
                  disabled={isLoading}
                  className="confirm-btn"
                >
                  {pendingConfirmationType === 'profile_update' ? 'Accept' : 'Confirm'}
                </button>
                <button
                  onClick={() => handleSend(buildActionMessage('reject'))}
                  disabled={isLoading}
                  className="skip-btn"
                >
                  Reject
                </button>
                {/* Pencil icon toggles note textarea */}
                <button
                  onClick={() => setShowConfirmNote(!showConfirmNote)}
                  title="Add a note"
                  style={{
                    background: showConfirmNote ? 'rgba(138, 107, 193, 0.12)' : 'transparent',
                    border: 'none',
                    borderRadius: '6px',
                    padding: '4px 6px',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    color: showConfirmNote ? '#8A6BC1' : '#aaa',
                    transition: 'all 0.15s',
                  }}
                >
                  <svg width="13" height="13" viewBox="0 0 13 13" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <path
                      d="M9.5 1.5L11.5 3.5L4.5 10.5H2.5V8.5L9.5 1.5Z"
                      stroke="currentColor"
                      strokeWidth="1.4"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    />
                  </svg>
                </button>
              </div>
            </div>
          )}

          {/* Text input - always visible, disabled when buttons showing */}
          <Form.Group className="mb-0">
            <div className="input-group" style={{ position: 'relative' }}>
              <Form.Control
                ref={inputRef}
                as="textarea"
                placeholder="Ask me anything..."
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyPress={handleKeyPress}
                disabled={isLoading || showConfirmButtons}
                className="chat-input"
                style={{ minHeight: '40px', fontSize: '14px', paddingBottom: '24px' }}
              />
              {/* Mode pill inside textarea */}
              <div style={{
                position: 'absolute',
                bottom: '5px',
                left: '8px',
                display: 'inline-flex',
                alignItems: 'center',
                gap: '4px',
                background: agentMode === 'build' ? 'rgba(255, 152, 0, 0.06)' : 'rgba(138, 107, 193, 0.06)',
                border: 'none',
                padding: '1px 8px',
                borderRadius: '3px',
                fontFamily: "'Lora'",
                pointerEvents: 'none',
                transition: 'all 0.3s ease',
              }}>
                <div style={{
                  width: '5px',
                  height: '5px',
                  borderRadius: '50%',
                  background: agentMode === 'build' ? '#FF9800' : '#8A6BC1',
                }} />
                <span style={{
                  fontSize: '9px',
                  fontWeight: 600,
                  color: agentMode === 'build' ? '#e65100' : '#8A6BC1',
                  letterSpacing: '0.3px',
                }}>
                  {agentMode === 'build' ? 'Build' : 'Advise'}
                </span>
                {agentMode === 'build' && buildPhases && (
                  <>
                    <div style={{ width: '1px', height: '8px', background: 'rgba(0,0,0,0.1)', margin: '0 1px' }} />
                    {buildPhases.map((phase, i) => (
                      <div
                        key={i}
                        title={phase.name}
                        style={{
                          width: '5px',
                          height: '5px',
                          borderRadius: '50%',
                          background: phase.status === 'complete' ? '#4CAF50'
                            : phase.status === 'active' ? '#FF9800'
                            : 'rgba(0,0,0,0.1)',
                          transition: 'all 0.3s ease',
                        }}
                      />
                    ))}
                  </>
                )}
              </div>
              <Button
                variant="primary"
                onClick={() => handleSend()}
                disabled={isLoading || !input.trim() || showConfirmButtons}
                className="send-button"
              >
                {isLoading ? (
                  <img
                    src="/compass.svg"
                    alt="Sending"
                    className="compass-swivel"
                    style={{ width: '18px', height: '18px' }}
                  />
                ) : (
                  <img
                    src="/compass.svg"
                    alt="Send"
                    style={{ width: '18px', height: '18px' }}
                  />
                )}
              </Button>
            </div>
          </Form.Group>
        </Card.Footer>
      </Card>

      {/* Styles for thread controls */}
      <style>{`
        .thread-control-btn:hover {
          background: rgba(255, 255, 255, 0.25) !important;
          border-color: rgba(255, 255, 255, 0.4) !important;
        }

        .new-thread-btn:hover {
          background: rgba(255, 255, 255, 0.3) !important;
          border-color: rgba(255, 255, 255, 0.5) !important;
        }

        .new-thread-btn:active {
          background: rgba(255, 255, 255, 0.15) !important;
        }

        .dropdown-item:hover {
          background-color: #f8f8f8 !important;
        }

        .dropdown-item.active:hover {
          background-color: #ebe4f5 !important;
        }
      `}</style>
    </div>
  );
}

export default ChatWindow;
