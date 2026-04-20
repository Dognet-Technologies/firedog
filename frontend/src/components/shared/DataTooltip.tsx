import React, { useRef, useState, useCallback } from 'react';
import './DataTooltip.css';

export type DttType = 'avg' | 'count' | 'sum' | 'rate' | 'last' | 'delta';

interface DataTooltipProps {
  children: React.ReactNode;
  title: string;
  description: string;
  type?: DttType;
  source?: string;
  inline?: boolean;
}

const TYPE_LABELS: Record<DttType, string> = {
  avg: 'Media',
  count: 'Conteggio',
  sum: 'Somma',
  rate: 'Tasso',
  last: 'Ultimo valore',
  delta: 'Variazione',
};

const DataTooltip: React.FC<DataTooltipProps> = ({ children, title, description, type, source, inline }) => {
  const [visible, setVisible] = useState(false);
  const [pos, setPos] = useState({ x: 0, y: 0 });
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const handleMouseEnter = useCallback((e: React.MouseEvent) => {
    setPos({ x: e.clientX, y: e.clientY });
    timerRef.current = setTimeout(() => setVisible(true), 2000);
  }, []);

  const handleMouseMove = useCallback((e: React.MouseEvent) => {
    if (!visible) setPos({ x: e.clientX, y: e.clientY });
  }, [visible]);

  const handleMouseLeave = useCallback(() => {
    if (timerRef.current) clearTimeout(timerRef.current);
    setVisible(false);
  }, []);

  const tooltipStyle: React.CSSProperties = (() => {
    const W = 272;
    const H = 130;
    const OFFSET = 14;
    let left = pos.x + OFFSET;
    let top = pos.y + OFFSET;
    if (left + W > window.innerWidth - 8) left = pos.x - W - OFFSET;
    if (top + H > window.innerHeight - 8) top = pos.y - H - OFFSET;
    return { left, top };
  })();

  return (
    <div
      className={inline ? 'dtt-wrapper dtt-wrapper--inline' : 'dtt-wrapper'}
      onMouseEnter={handleMouseEnter}
      onMouseMove={handleMouseMove}
      onMouseLeave={handleMouseLeave}
    >
      {children}
      {visible && (
        <div className="dtt-card" style={tooltipStyle}>
          <div className="dtt-header">
            <span className="dtt-title">{title}</span>
            {type && <span className={`dtt-badge dtt-badge-${type}`}>{TYPE_LABELS[type]}</span>}
          </div>
          <p className="dtt-desc">{description}</p>
          {source && <div className="dtt-source">{source}</div>}
        </div>
      )}
    </div>
  );
};

export default DataTooltip;
