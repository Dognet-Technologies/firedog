import React from 'react';
import './ScoreBar.css';

interface ScoreBarProps {
  score: number; // 0-100
}

const getScoreColor = (score: number): string => {
  if (score < 40) return 'var(--status-success)';
  if (score < 70) return 'var(--status-warning)';
  if (score < 85) return '#ff8c00';
  return 'var(--status-danger)';
};

const ScoreBar: React.FC<ScoreBarProps> = ({ score }) => {
  const clampedScore = Math.max(0, Math.min(100, score));
  const color = getScoreColor(clampedScore);

  return (
    <div className="score-bar">
      <div
        className="score-bar-fill"
        style={{ width: `${clampedScore}%`, background: color }}
      />
      <span className="score-bar-label">{clampedScore}</span>
    </div>
  );
};

export default ScoreBar;
