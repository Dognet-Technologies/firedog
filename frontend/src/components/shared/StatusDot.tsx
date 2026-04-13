import React from 'react';
import './StatusDot.css';

type StatusType = 'online' | 'offline' | 'unknown' | 'warning' | 'error' | 'installing' | 'pending';

interface StatusDotProps {
  status: StatusType;
  pulse?: boolean;
}

const StatusDot: React.FC<StatusDotProps> = ({ status, pulse }) => {
  const shouldPulse = pulse !== undefined ? pulse : status === 'online' || status === 'installing';

  return (
    <span
      className={`status-dot-shared status-dot-${status}${shouldPulse ? ' status-dot-pulse' : ''}`}
      title={status.charAt(0).toUpperCase() + status.slice(1)}
    />
  );
};

export default StatusDot;
