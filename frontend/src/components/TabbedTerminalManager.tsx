/**
 * Tabbed Terminal Manager Component
 * Gestisce max 5 terminali SSH in parallelo con sistema di tab
 */
import React, { useState, useEffect, useRef } from 'react';
import SSHTerminal from './SSHTerminal';
import type { Target } from '../types';
import './TabbedTerminalManager.css';

export interface TerminalOperation {
  id: string;
  target: Target;
  type: 'install' | 'reinstall' | 'test';
  status: 'running' | 'waiting_input' | 'completed' | 'error';
  requiresFocus: boolean;
  sshPassword?: string; // Password SSH per prima installazione
}

interface TabbedTerminalManagerProps {
  operations: TerminalOperation[];
  onOperationComplete: (operationId: string) => void;
  onOperationError: (operationId: string) => void;
  onCloseOperation: (operationId: string) => void;
  onUpdateOperation: (operationId: string, updates: Partial<TerminalOperation>) => void;
}

const TabbedTerminalManager: React.FC<TabbedTerminalManagerProps> = ({
  operations,
  onOperationComplete,
  onOperationError,
  onCloseOperation,
  onUpdateOperation
}) => {
  const [activeTabId, setActiveTabId] = useState<string | null>(null);
  const tabsContainerRef = useRef<HTMLDivElement>(null);

  // Imposta il primo tab come attivo quando operations cambia
  useEffect(() => {
    if (operations.length > 0 && !activeTabId) {
      setActiveTabId(operations[0].id);
    } else if (operations.length === 0) {
      setActiveTabId(null);
    } else if (activeTabId && !operations.find(op => op.id === activeTabId)) {
      // Il tab attivo è stato rimosso, passa al primo disponibile
      setActiveTabId(operations[0]?.id || null);
    }
  }, [operations, activeTabId]);

  // Focus management: switch automatico a tab che richiede input
  useEffect(() => {
    const needsFocus = operations.find(op => op.requiresFocus && op.status === 'waiting_input');

    if (needsFocus && activeTabId !== needsFocus.id) {
      setActiveTabId(needsFocus.id);

      // Scroll alla tab
      const tabButton = document.querySelector(`[data-tab-id="${needsFocus.id}"]`);
      if (tabButton) {
        tabButton.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'center' });
      }
    }
  }, [operations, activeTabId]);

  const getStatusBadge = (status: TerminalOperation['status']) => {
    switch (status) {
      case 'running':
        return <span className="status-badge running">🔄</span>;
      case 'waiting_input':
        return <span className="status-badge waiting pulse">⚠️</span>;
      case 'completed':
        return <span className="status-badge completed">✅</span>;
      case 'error':
        return <span className="status-badge error">❌</span>;
    }
  };

  const getTabLabel = (operation: TerminalOperation) => {
    return operation.target.hostname || operation.target.ip_address;
  };

  if (operations.length === 0) {
    return (
      <div className="no-operations">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
          <rect x="3" y="3" width="18" height="18" rx="2" />
          <path d="M7 7l5 5-5 5M13 17h5" />
        </svg>
        <p>No active operations</p>
      </div>
    );
  }

  return (
    <div className="tabbed-terminal-manager">
      {/* Tabs Header */}
      <div className="tabs-header">
        <div className="tabs-container" ref={tabsContainerRef}>
          {operations.map((operation) => (
            <button
              key={operation.id}
              data-tab-id={operation.id}
              className={`tab-button ${activeTabId === operation.id ? 'active' : ''} status-${operation.status}`}
              onClick={() => setActiveTabId(operation.id)}
            >
              <span className="tab-label">{getTabLabel(operation)}</span>
              {getStatusBadge(operation.status)}
              <button
                className="tab-close"
                onClick={(e) => {
                  e.stopPropagation();
                  onCloseOperation(operation.id);
                }}
                title="Close terminal"
              >
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
                  <path d="M18 6L6 18M6 6l12 12" />
                </svg>
              </button>
            </button>
          ))}
        </div>

        {operations.length >= 5 && (
          <div className="max-tabs-warning">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
              <circle cx="12" cy="12" r="10" />
              <line x1="12" y1="8" x2="12" y2="12" />
              <line x1="12" y1="16" x2="12.01" y2="16" />
            </svg>
            <span>Max 5 parallel operations</span>
          </div>
        )}
      </div>

      {/* Terminal Content */}
      <div className="terminals-content">
        {operations.map((operation) => (
          <div
            key={operation.id}
            className={`terminal-tab-content ${activeTabId === operation.id ? 'active' : 'hidden'}`}
          >
            <SSHTerminal
              targetId={operation.target.id}
              sshPassword={operation.sshPassword}
              onClose={() => onCloseOperation(operation.id)}
              onInstallComplete={() => {
                onUpdateOperation(operation.id, { status: 'completed' });
                onOperationComplete(operation.id);
              }}
            />
          </div>
        ))}
      </div>
    </div>
  );
};

export default TabbedTerminalManager;
