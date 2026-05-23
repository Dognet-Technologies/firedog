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

  // Carica targets all'avvio + polling ogni 30s. Senza polling, se i target
  // erano offline al mount (es. agent ancora in handshake) il context resta
  // vuoto per sempre fino a refresh manuale della pagina.
  useEffect(() => {
    loadTargets();
    const id = setInterval(() => loadTargets({ silent: true }), 30_000);
    return () => clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Salva selectedTarget in localStorage
  useEffect(() => {
    if (selectedTarget) {
      localStorage.setItem('selectedTargetId', selectedTarget.id.toString());
    }
  }, [selectedTarget]);

  const loadTargets = async (opts: { silent?: boolean } = {}) => {
    try {
      if (!opts.silent) setLoading(true);
      setError(null);

      const response = await apiService.getTargets();
      // Mostra TUTTI i target, non solo gli online. Rules, BlockedIPs e
      // Whitelist sono stato persistente e devono restare gestibili anche con
      // target temporaneamente offline. Lo stato live è già visibile via
      // StatusDot nel selettore.
      const allTargets = response.results;

      setTargets(allTargets);

      // Auto-seleziona se non c'è già una selezione valida
      const savedTargetId = localStorage.getItem('selectedTargetId');
      const stillValid = selectedTarget && allTargets.some(t => t.id === selectedTarget.id);

      if (!stillValid) {
        if (allTargets.length > 0) {
          if (savedTargetId) {
            const savedTarget = allTargets.find(t => t.id === parseInt(savedTargetId));
            setSelectedTarget(savedTarget || allTargets[0]);
          } else {
            setSelectedTarget(allTargets[0]);
          }
        } else {
          setSelectedTarget(null);
        }
      }
    } catch (err: any) {
      console.error('Error loading targets:', err);
      if (!opts.silent) setError('Impossibile caricare i target');
    } finally {
      if (!opts.silent) setLoading(false);
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
