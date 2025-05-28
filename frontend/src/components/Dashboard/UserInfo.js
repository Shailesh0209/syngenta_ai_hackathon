import React from 'react';

const UserInfo = ({ user, onLogout }) => {
  if (!user) return null;

  return (
    <div className="user-info">
      <p>
        {user.name} | {user.role} | {user.region}
      </p>
      <button className="logout-button" onClick={onLogout}>
        Logout
      </button>
    </div>
  );
};

export default UserInfo;
