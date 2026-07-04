import React from 'react';
import './SeverityBadge.css';

interface SeverityBadgeProps {
  severity: 'critical' | 'high' | 'medium' | 'low';
}

const SeverityBadge: React.FC<SeverityBadgeProps> = ({ severity }) => {
  return (
    <span className={`severity-badge severity-badge-${severity}`}>
      {severity.charAt(0).toUpperCase() + severity.slice(1)}
    </span>
  );
};

export default SeverityBadge;
