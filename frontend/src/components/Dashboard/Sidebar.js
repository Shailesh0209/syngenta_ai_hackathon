import React, { useState } from 'react';
import { FaChevronLeft, FaChevronRight } from 'react-icons/fa';
import '../../styles/Dashboard.css';

const Sidebar = ({ queryHistory, sampleQuestions, permissions, onQuestionClick }) => {
  const [expanded, setExpanded] = useState(true);

  return (
    <div className={`sidebar ${expanded ? 'expanded' : 'collapsed'}`}>
      <button 
        className="toggle-sidebar" 
        onClick={() => setExpanded(!expanded)}
        aria-label={expanded ? 'Collapse sidebar' : 'Expand sidebar'}
      >
        {expanded ? <FaChevronLeft /> : <FaChevronRight />}
      </button>
      
      {expanded && (
        <>
          <div className="sidebar-section">
            <h3>Query History</h3>
            <ul>
              {queryHistory.map((query, index) => (
                <li key={index} onClick={() => onQuestionClick(query)}>
                  {query.length > 30 ? `${query.substring(0, 30)}...` : query}
                </li>
              ))}
            </ul>
          </div>
          
          <div className="sidebar-section">
            <h3>Sample Questions</h3>
            <ul>
              {sampleQuestions.map((question, index) => (
                <li key={index} onClick={() => onQuestionClick(question)}>
                  {question.length > 30 ? `${question.substring(0, 30)}...` : question}
                </li>
              ))}
            </ul>
          </div>
          
          <div className="sidebar-section">
            <h3>Permissions</h3>
            <p>Access: {permissions}</p>
          </div>
        </>
      )}
    </div>
  );
};

export default Sidebar;
