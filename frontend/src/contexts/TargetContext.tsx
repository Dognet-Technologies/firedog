/**
 * Target Selection Context
 * Gestione globale del target selezionato per le pagine Rules, Whitelist, BlockedIPs, etc.
 */
import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import apiService from '../services/api';
import type { Target } from '../types';

interface TargetContextType {
  selectedTarget: Target | null;
  targets: Target[];
  loading: boolean;
  error: string | null;
  setSelectedTarget: (target: Target | null) => void;
  refreshTargets: () => Promise<void>;
}

const TargetContext = createContext<TargetContextType | undefined>(undefined);

export const TargetProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [selectedTarget, setSelectedTarget] = useState<Target | null>(null);
  const [targets, setTargets] = useState<Target[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Carica targets all'avvio
  useEffect(() => {
    loadTargets();
  }, []);

  // Salva selectedTarget in localStorage
  useEffect(() => {
    if (selectedTarget) {
      localStorage.setItem('selectedTargetId', selectedTarget.id.toString());
    }
  }, [selectedTarget]);

  const loadTargets = async () => {
    try {
      setLoading(true);
      setError(null);
      
      const response = await apiService.getTargets();
      const onlineTargets = response.results.filter(t => t.status === 'online');
      
      setTargets(onlineTargets);

      // Auto-seleziona primo target online o ultimo selezionato
      if (onlineTargets.length > 0) {
        const savedTargetId = localStorage.getItem('selectedTargetId');
        
        if (savedTargetId) {
          const savedTarget = onlineTargets.find(t => t.id === parseInt(savedTargetId));
          setSelectedTarget(savedTarget || onlineTargets[0]);
        } else {
          setSelectedTarget(onlineTargets[0]);
        }
      } else {
        setSelectedTarget(null);
      }
    } catch (err: any) {
      console.error('Error loading targets:', err);
      setError('Impossibile caricare i target');
    } finally {
      setLoading(false);
    }
  };

  const refreshTargets = async () => {
    await loadTargets();
  };

  return (
    <TargetContext.Provider
      value={{
        selectedTarget,
        targets,
        loading,
        error,
        setSelectedTarget,
        refreshTargets,
      }}
    >
      {children}
    </TargetContext.Provider>
  );
};

// Hook per usare il context
export const useTarget = (): TargetContextType => {
  const context = useContext(TargetContext);
  if (!context) {
    throw new Error('useTarget must be used within a TargetProvider');
  }
  return context;
};
