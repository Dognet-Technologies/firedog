/**
 * Collapsible Terminal Panel Component
 * Panel collassabile che contiene il gestore di tab terminali
 */
import React, { useState, useEffect, useRef } from 'react';
import './CollapsibleTerminalPanel.css';

interface CollapsibleTerminalPanelProps {
  isOpen: boolean;
  onClose: () => void;
  children: React.ReactNode;
  title?: string;
}

const CollapsibleTerminalPanel: React.FC<CollapsibleTerminalPanelProps> = ({
  isOpen,
  onClose,
  children,
  title = 'Installation Progress'
}) => {
  const [isExpanded, setIsExpanded] = useState(true);
  const panelRef = useRef<HTMLDivElement>(null);

  // Quando il panel si apre, assicurati che sia espanso
  useEffect(() => {
    if (isOpen) {
      setIsExpanded(true);
    }
  }, [isOpen]);

  // Scroll automatico quando il panel si apre
  useEffect(() => {
    if (isOpen && panelRef.current) {
      setTimeout(() => {
        panelRef.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      }, 100);
    }
  }, [isOpen]);

  if (!isOpen) return null;

  return (
    <div className={`collapsible-terminal-panel ${isExpanded ? 'expanded' : 'collapsed'}`} ref={panelRef}>
      <div className="panel-header">
        <div className="panel-title">
          <button
            className="expand-toggle"
            onClick={() => setIsExpanded(!isExpanded)}
            title={isExpanded ? 'Collapse panel' : 'Expand panel'}
          >
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              className={`expand-icon ${isExpanded ? 'expanded' : ''}`}
            >
              <polyline points="6 9 12 15 18 9" />
            </svg>
          </button>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" className="terminal-icon">
            <rect x="3" y="3" width="18" height="18" rx="2" />
            <path d="M7 7l5 5-5 5M13 17h5" />
          </svg>
          <h3>{title}</h3>
        </div>
        <button
          className="panel-close"
          onClick={onClose}
          title="Close panel"
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
            <path d="M18 6L6 18M6 6l12 12" />
          </svg>
        </button>
      </div>

      <div className={`panel-content ${isExpanded ? 'visible' : 'hidden'}`}>
        {children}
      </div>
    </div>
  );
};

export default CollapsibleTerminalPanel;
