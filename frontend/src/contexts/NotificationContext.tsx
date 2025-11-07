// frontend/src/contexts/NotificationContext.tsx

import React, { createContext, useContext, useState, useCallback } from 'react';

// Types
interface Toast {
  id: string;
  type: 'info' | 'success' | 'warning' | 'error';
  title: string;
  message: string;
  duration?: number;
}

interface ConfirmOptions {
  title: string;
  message: string;
  confirmText?: string;
  cancelText?: string;
  type?: 'info' | 'warning' | 'danger';
  onConfirm: () => void | Promise<void>;
  onCancel?: () => void;
}

interface NotificationContextType {
  // Toast notifications
  showToast: (toast: Omit<Toast, 'id'>) => void;
  // Confirm dialog
  showConfirm: (options: ConfirmOptions) => void;
  // Info modal
  showInfo: (title: string, message: string) => void;
}

const NotificationContext = createContext<NotificationContextType | undefined>(undefined);

export const useNotifications = () => {
  const context = useContext(NotificationContext);
  if (!context) {
    throw new Error('useNotifications must be used within NotificationProvider');
  }
  return context;
};

export const NotificationProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const [confirmDialog, setConfirmDialog] = useState<ConfirmOptions | null>(null);
  const [infoModal, setInfoModal] = useState<{ title: string; message: string } | null>(null);

  // Toast functions
  const showToast = useCallback((toast: Omit<Toast, 'id'>) => {
    const id = Date.now().toString();
    const newToast = { ...toast, id, duration: toast.duration || 5000 };
    
    setToasts(prev => [...prev, newToast]);
    
    setTimeout(() => {
      setToasts(prev => prev.filter(t => t.id !== id));
    }, newToast.duration);
  }, []);

  const removeToast = useCallback((id: string) => {
    setToasts(prev => prev.filter(t => t.id !== id));
  }, []);

  // Confirm dialog
  const showConfirm = useCallback((options: ConfirmOptions) => {
    setConfirmDialog(options);
  }, []);

  const handleConfirm = async () => {
    if (confirmDialog?.onConfirm) {
      await confirmDialog.onConfirm();
    }
    setConfirmDialog(null);
  };

  const handleCancel = () => {
    if (confirmDialog?.onCancel) {
      confirmDialog.onCancel();
    }
    setConfirmDialog(null);
  };

  // Info modal
  const showInfo = useCallback((title: string, message: string) => {
    setInfoModal({ title, message });
  }, []);

  return (
    <NotificationContext.Provider value={{ showToast, showConfirm, showInfo }}>
      {children}

      {/* Toast Container */}
      <div className="toast-container">
        {toasts.map(toast => (
          <div key={toast.id} className={`toast toast-${toast.type}`}>
            <div className="toast-icon">
              {toast.type === 'success' && '✓'}
              {toast.type === 'error' && '✗'}
              {toast.type === 'warning' && '⚠'}
              {toast.type === 'info' && 'ℹ'}
            </div>
            <div className="toast-content">
              <div className="toast-title">{toast.title}</div>
              <div className="toast-message">{toast.message}</div>
            </div>
            <button className="toast-close" onClick={() => removeToast(toast.id)}>×</button>
          </div>
        ))}
      </div>

      {/* Confirm Dialog */}
      {confirmDialog && (
        <div className="modal-overlay">
          <div className="modal-content confirm-dialog">
            <div className="modal-header">
              <h3>{confirmDialog.title}</h3>
            </div>
            <div className="modal-body">
              <p>{confirmDialog.message}</p>
            </div>
            <div className="modal-footer">
              <button className="btn-secondary" onClick={handleCancel}>
                {confirmDialog.cancelText || 'Annulla'}
              </button>
              <button 
                className={`btn-${confirmDialog.type === 'danger' ? 'danger' : 'primary'}`}
                onClick={handleConfirm}
              >
                {confirmDialog.confirmText || 'Conferma'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Info Modal */}
      {infoModal && (
        <div className="modal-overlay" onClick={() => setInfoModal(null)}>
          <div className="modal-content" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h3>{infoModal.title}</h3>
              <button className="modal-close" onClick={() => setInfoModal(null)}>×</button>
            </div>
            <div className="modal-body">
              <p>{infoModal.message}</p>
            </div>
            <div className="modal-footer">
              <button className="btn-primary" onClick={() => setInfoModal(null)}>
                OK
              </button>
            </div>
          </div>
        </div>
      )}
    </NotificationContext.Provider>
  );
};