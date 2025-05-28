import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import ChatInterface from './ChatInterface';
import Sidebar from './Sidebar';
import UserInfo from './UserInfo';
import api from '../../services/api';
import '../../styles/Dashboard.css';

const Dashboard = () => {
  const [user, setUser] = useState(null);
  const [queryHistory, setQueryHistory] = useState([]);
  const [sampleQuestions, setSampleQuestions] = useState([
    'Who are our top 10 customers by total order value?',
    'Based on our Product Quality Assurance standards, which products had the highest number of quality-related returns in the past year?',
    'What criteria do we use to qualify new suppliers based on our Supplier Selection policy?',
    'What are the required steps for handling obsolete inventory write-offs?',
    'What cyber security measures must be implemented to protect supply chain data according to our Data Security policy?',
  ]);
  const [prefill, setPrefill] = useState('');
  const navigate = useNavigate();

  useEffect(() => {
    const storedUser = localStorage.getItem('user');
    if (!storedUser) {
      navigate('/login');
      return;
    }

    setUser(JSON.parse(storedUser));
    loadQueryHistory();
  }, [navigate]);

  const loadQueryHistory = async () => {
    try {
      const response = await api.get('/api/history');
      setQueryHistory(response.data.history);
    } catch (error) {
      console.error('Error fetching query history:', error);
    }
  };

  const addToQueryHistory = (query) => {
    setQueryHistory(prev => {
      // Add to beginning and limit to 10 items
      const newHistory = [query, ...prev].slice(0, 10);
      return newHistory;
    });
  };

  const handleQuestionClick = (question) => {
    setPrefill(question);
  };

  const handleLogout = () => {
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    navigate('/login');
  };

  if (!user) {
    return <div>Loading...</div>;
  }

  const permissions = `${user.role}, ${user.region}`;

  return (
    <div className="dashboard">
      <div className="dashboard-header">
        <h1>Syngenta AI Supply Chain Assistant</h1>
        <UserInfo user={user} onLogout={handleLogout} />
      </div>
      
      <div className="dashboard-content">
        <Sidebar 
          queryHistory={queryHistory} 
          sampleQuestions={sampleQuestions}
          permissions={permissions}
          onQuestionClick={handleQuestionClick}
        />
        
        <div className="main-content">
          <ChatInterface 
            addToQueryHistory={addToQueryHistory} 
            prefill={prefill} 
            onClearPrefill={() => setPrefill('')}
          />
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
