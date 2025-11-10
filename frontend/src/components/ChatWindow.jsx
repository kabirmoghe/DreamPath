import React, { useState, useEffect, useRef } from 'react';
import { flushSync } from 'react-dom';
import { Card, Form, Button, Spinner, Dropdown } from 'react-bootstrap';
import { Send, X, ChatDots, Plus, List } from 'react-bootstrap-icons';
import { useQueryClient } from '@tanstack/react-query';
import { apiClient } from '../lib/api';
import CoursePathOperations from './CoursePathOperations';
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

  // Mapping of route names to user-friendly messages
  const routeMessages = {
    'course_search': 'Searching Courses',
    'plan_builder': 'Planning CoursePath Modifications',
    'course_path': 'Executing CoursePath Operations',
    'modify_profile': 'Updating Profile',
    'rebuild_course_path': 'Rebuilding CoursePath',
    'finalize': 'Finalizing',
  };

  // Initialize thread on mount
  useEffect(() => {
    if (!userId) return;

    // Load threads from localStorage
    const userThreads = apiClient.getUserThreads(userId);
    setThreads(userThreads);

    // Get or create current thread
    let currentThreadId = apiClient.getCurrentThreadId(userId);
    if (!currentThreadId || userThreads.length === 0) {
      // Create first thread
      const newThread = apiClient.createThread(userId);
      currentThreadId = newThread.id;
      setThreads([newThread]);
    }

    setThreadId(currentThreadId);

    // Load history for this thread
    loadThreadHistory(currentThreadId);
  }, [userId]);

  // Load history for a thread
  const loadThreadHistory = async (tid) => {
    setLoadingHistory(true);
    try {
      const history = await apiClient.getHistory(tid);
      if (history && history.messages) {
        // Limit to last 50 messages for performance
        const recentMessages = history.messages.slice(-50);
        setMessages(recentMessages);
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
  const handleCreateNewThread = () => {
    const newThread = apiClient.createThread(userId);
    setThreadId(newThread.id);
    setThreads([newThread, ...threads]);
    setMessages([]);
    setError(null);
    setNodeStatus(null);
  };

  // Switch to a different thread
  const handleSwitchThread = async (tid) => {
    if (tid === threadId) return; // Already on this thread

    apiClient.switchThread(userId, tid);
    setThreadId(tid);
    setError(null);
    setNodeStatus(null);

    // Load history for the new thread
    await loadThreadHistory(tid);
  };

  const handleSend = async () => {
    if (!input.trim() || isLoading || !threadId) return;

    const userMessage = input.trim();
    setInput('');
    setError(null);
    setNodeStatus(null); // Clear any previous node status

    // Reset textarea height
    if (inputRef.current) {
      inputRef.current.style.height = 'auto';
    }

    // Add user message to chat
    setMessages(prev => [...prev, { type: 'human', content: userMessage }]);
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
      queryClient.invalidateQueries(['profile', userId]);

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
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

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

      // Check if line is a heading (###, ##, #)
      const headingMatch = line.match(/^(#{1,3})\s+(.+)$/);
      if (headingMatch) {
        elements.push(
          <div key={`line-${lineIdx}`} style={{ fontWeight: 'bold', marginTop: lineIdx > 0 ? '8px' : 0 }}>
            {headingMatch[2]}
          </div>
        );
        return;
      }

      // Process inline markdown: links, bold, italic, code
      const patterns = [
        { regex: /\[([^\]]+)\]\(([^)]+)\)/g, type: 'link' },      // [text](url)
        { regex: /\*\*([^*]+)\*\*/g, type: 'bold' },              // **bold**
        { regex: /\*([^*]+)\*/g, type: 'italic' },                // *italic*
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

      elements.push(<div key={`line-${lineIdx}`}>{parts}</div>);
    });

    return elements;
  };

  const renderMessage = (msg, idx) => {
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
                />
              )}
              {msg.custom_data.event_type === 'profile_update' && (
                <ProfileUpdate changes={msg.custom_data.changes} isPending={isPending} />
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

        <Card.Body className="chat-messages">

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
                      <span className="thinking-text">{nodeStatus.message || 'Thinking'}</span>
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
          <Form.Group className="mb-0">
            <div className="input-group">
              <Form.Control
                ref={inputRef}
                as="textarea"
                placeholder="Ask me anything..."
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyPress={handleKeyPress}
                disabled={isLoading}
                className="chat-input"
                style={{ minHeight: '40px', fontSize: '14px' }}
              />
              <Button
                variant="primary"
                onClick={handleSend}
                disabled={isLoading || !input.trim()}
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
