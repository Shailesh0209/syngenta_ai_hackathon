import React, { useState, useEffect, useRef } from 'react';
import api from '../../services/api';
import '../../styles/Dashboard.css';

const ChatInterface = ({ addToQueryHistory, prefill, onClearPrefill }) => {
  const [query, setQuery] = useState('');
  const [messages, setMessages] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef(null);

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // when parent sends a prefill, update input and then clear it
  useEffect(() => {
    if (prefill) {
      setQuery(prefill);
      onClearPrefill();
    }
  }, [prefill, onClearPrefill]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  // helper to toggle text-to-speech: start if idle, stop if speaking
  const speakText = (text) => {
    if (!window.speechSynthesis) {
      console.warn('TTS not supported');
      return;
    }
    if (window.speechSynthesis.speaking) {
      // stop ongoing speech
      window.speechSynthesis.cancel();
    } else {
      const utterance = new SpeechSynthesisUtterance(text);
      window.speechSynthesis.speak(utterance);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!query.trim()) return;

    const userQuery = query.trim();
    setMessages(prev => [...prev, { role: 'user', content: userQuery }]);
    setQuery('');
    setIsLoading(true);

    try {
      const response = await api.post('/api/query', { query: userQuery });
      const { 
        answer, 
        accessDenied, 
        documentUrl, 
        charts, 
        predictionResults, // This is already destructured
        proactiveSuggestions,
        leaderboardPosition,
        complianceScore,
        accessAttemptLogged
      } = response.data;
      
      if (accessDenied) {
        setMessages(prev => [...prev, { 
          role: 'system', 
          content: answer, 
          isError: true 
        }]);
      } else {
        const formattedContent = formatResponse(
          answer, 
          predictionResults, 
          proactiveSuggestions, 
          leaderboardPosition, 
          complianceScore,
          accessAttemptLogged
        );
        
        setMessages(prev => [...prev, { 
          role: 'assistant', 
          content: formattedContent,
          documentUrl,
          charts,
          predictionResults // Add predictionResults to the message object
        }]);
      }
      
      // Add to query history
      addToQueryHistory(userQuery);
    } catch (error) {
      setMessages(prev => [...prev, { 
        role: 'system', 
        content: 'Sorry, an error occurred while processing your request.', 
        isError: true 
      }]);
    } finally {
      setIsLoading(false);
    }
  };

  // Helper function to format the response with predictions
  const formatResponse = (answer, predictionResults, suggestions, position, score, accessLog) => {
    // Don't modify the original answer, as it may contain formatted tables already
    return answer;
  };

  // Clear chat function
  const clearChat = () => {
    setMessages([]);
  };

  // Create a component to render a formatted message with styled sections
  const FormattedMessage = ({ message }) => {
    const { content, charts, documentUrl, predictionResults } = message; // Destructure predictionResults
    
    // Function to handle suggestion clicks
    const handleSuggestionClick = (suggestion) => {
      setQuery(suggestion);
      handleSubmit({ preventDefault: () => {} });
    };
    
    // Check if the content contains a table (ASCII table with + and | chars)
    const hasTable = content.includes('+---') || content.includes('|');
    
    // Split content into sections
    const sections = content.split('\n\n');
    
    return (
      <div className="formatted-message">
        {sections.map((section, idx) => {
          // Check what type of section this is
          if (section.startsWith('Database results:') || section.includes('customer ID') || hasTable) {
            return (
              <div key={idx} className="result-table-section">
                <pre>{section}</pre>
              </div>
            );
          } else if (section.startsWith('Explanation and insights:')) {
            return (
              <div key={idx} className="explanation-section">
                <h4>Explanation and Insights</h4>
                <p>{section.replace('Explanation and insights:', '')}</p>
              </div>
            );
          } else if (section.startsWith('SQL query used:')) {
            return (
              <div key={idx} className="sql-query-section">
                <details>
                  <summary>SQL Query Used</summary>
                  <pre>{section.replace('SQL query used:', '')}</pre>
                </details>
              </div>
            );
          } else if (section.startsWith('Access attempt logged:')) {
            return (
              <div key={idx} className="access-log-section">
                <p><i>{section}</i></p>
              </div>
            );
          } else if (section.startsWith('Proactive Suggestions:')) {
            // Extract suggestions as clickable buttons
            const suggestionsText = section.replace('Proactive Suggestions:', '').trim();
            const suggestionsList = suggestionsText.split('?,').map(s => 
              s.endsWith('?') ? s : s + '?'
            );
            
            return (
              <div key={idx} className="suggestions-section">
                <h4>Proactive Suggestions</h4>
                <div className="suggestion-buttons">
                  {suggestionsList.map((suggestion, i) => (
                    <button 
                      key={i} 
                      className="suggestion-button"
                      onClick={() => handleSuggestionClick(suggestion)}
                    >
                      {suggestion}
                    </button>
                  ))}
                </div>
              </div>
            );
          } else if (section.includes('Leaderboard Position:') || section.includes('Compliance Score:')) {
            return (
              <div key={idx} className="metadata-section">
                <p>{section}</p>
              </div>
            );
          } else if (section.toLowerCase().startsWith('prediction results:')) { 
            // If prediction results are part of the main content string, render them here.
            return (
              <div key={idx} className="prediction-results-section">
                <h4>Prediction Results</h4>
                <p>{section.substring(section.toLowerCase().indexOf(':') + 1).trim()}</p>
              </div>
            );
          }
           else {
            return <p key={idx}>{section}</p>;
          }
        })}
        
        {/* Display top-level predictionResults if it's not empty and not already handled in sections */}
        {predictionResults && typeof predictionResults === 'string' && !content.toLowerCase().includes('prediction results:') && (
          <div className="prediction-results-section">
            <h4>Prediction Results</h4>
            <p>{predictionResults}</p>
          </div>
        )}
        
        {documentUrl && (
          <div className="document-link">
            <a href={documentUrl} target="_blank" rel="noopener noreferrer">
              View Document
            </a>
          </div>
        )}
      </div>
    );
  };

  // Enhanced chart renderer
  const renderChart = (chart) => {
    if (!chart) return null;
    
    const dataset = chart.data.datasets[0];
    const maxValue = Math.max(...dataset.data);
    // console.log("Chart rendering. MaxValue:", maxValue, "Data:", dataset.data); // For debugging

    return (
      <div className="chart-container">
        <h4>{chart.options?.plugins?.title?.text || 'Chart'}</h4>
        <div className="chart-visualization">
          <div className="chart-placeholder">
            {/* In a real app, you would use Chart.js or another library here */}
            <div className="chart-type-bar">
              {chart.data.labels.map((label, idx) => {
                const value = dataset.data[idx];
                const percentage = maxValue === 0 ? 0 : (value / maxValue) * 100;
                const backgroundColor = dataset.backgroundColor[idx % dataset.backgroundColor.length];
                
                // console.log(`Bar: ${label}, Value: ${value}, Percentage: ${percentage}%`); // For debugging
                
                return (
                  <div key={idx} className="chart-bar-container">
                    <div 
                      className="chart-bar" 
                      style={{ 
                        height: `${percentage}%`,
                        backgroundColor
                      }}
                      title={`${label}: $${value.toFixed(2)}`}
                    ></div>
                    <div className="chart-label">{label.replace('Customer ', '')}</div>
                  </div>
                );
              })}
            </div>
            <div className="chart-y-axis">
              <div>Total Order Value ($)</div>
            </div>
          </div>
        </div>
      </div>
    );
  };

  return (
    <div className="chat-interface">
      <div className="chat-messages">
        {messages.map((message, index) => (
          <div 
            key={index} 
            className={`message ${message.role === 'user' ? 'user-message' : ''} ${message.isError ? 'error-message' : ''}`}
          >
            <div className="message-content">
              {message.role === 'user' ? (
                <p>{message.content}</p>
              ) : (
                <FormattedMessage message={message} />
              )}
              {/* speaker button toggles start/stop */}
              {message.role === 'assistant' && (
                <button
                  type="button"
                  className="speaker-button"
                  onClick={() => speakText(message.content)}
                >
                  🔊
                </button>
              )}
              {message.charts && message.charts.length > 0 && (
                <div className="charts-section">
                  {message.charts.map((chart, chartIndex) => (
                    <div key={chartIndex}>
                      {renderChart(chart)}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        ))}
        {isLoading && (
          <div className="message">
            <div className="loading-indicator">
              <div className="loading-dot"></div>
              <div className="loading-dot"></div>
              <div className="loading-dot"></div>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      <div className="chat-input-container">
        <form onSubmit={handleSubmit} className="chat-form">
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Ask about inventory, policies, etc."
            className="chat-input"
          />
          <button type="submit" className="send-button">Send</button>
          <button type="button" className="clear-button" onClick={clearChat}>Clear Chat</button>
        </form>
      </div>
    </div>
  );
};

export default ChatInterface;
