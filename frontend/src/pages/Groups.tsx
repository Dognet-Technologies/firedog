/**
 * Groups Page — grid of target group cards
 */
import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import apiService from '../services/api';
import PageHeader from '../components/shared/PageHeader';
import StatusDot from '../components/shared/StatusDot';
import './Groups.css';

interface TargetGroup {
  id: number;
  name: string;
  description: string;
  color: string;
  icon: string;
  target_count: number;
  online_count: number;
  threat_count?: number;
  rule_count?: number;
  created_at: string;
  updated_at: string;
}

const Groups: React.FC = () => {
  const navigate = useNavigate();
  const [groups, setGroups] = useState<TargetGroup[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchGroups = async () => {
      try {
        setLoading(true);
        const data = await apiService.getGroups();
        // API may return paginated or plain array
        const results = data.results ?? data;
        setGroups(Array.isArray(results) ? results : []);
      } catch (err) {
        setError('Failed to load groups');
        console.error('Groups fetchGroups error:', err);
      } finally {
        setLoading(false);
      }
    };
    fetchGroups();
  }, []);

  const getWorstStatus = (onlineCount: number, totalCount: number): 'online' | 'offline' | 'warning' => {
    if (totalCount === 0) return 'offline';
    if (onlineCount === totalCount) return 'online';
    if (onlineCount > 0) return 'warning';
    return 'offline';
  };

  if (loading) {
    return (
      <div className="loading-state">
        <div className="spinner" />
        <p>Loading groups...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="empty-state">
        <h3>Error</h3>
        <p>{error}</p>
      </div>
    );
  }

  return (
    <div className="groups-page">
      <PageHeader
        title="Groups"
        subtitle={`${groups.length} group${groups.length !== 1 ? 's' : ''}`}
        icon={
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <polygon points="12 2 2 7 12 12 22 7 12 2" />
            <polyline points="2 17 12 22 22 17" />
            <polyline points="2 12 12 17 22 12" />
          </svg>
        }
      />

      {groups.length === 0 ? (
        <div className="empty-state">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
            <polygon points="12 2 2 7 12 12 22 7 12 2" />
            <polyline points="2 17 12 22 22 17" />
          </svg>
          <h3>No groups</h3>
          <p>Create groups in the Discovery section to organize your targets.</p>
        </div>
      ) : (
        <div className="groups-grid">
          {groups.map((group) => {
            const worstStatus = getWorstStatus(group.online_count, group.target_count);
            const offlineCount = group.target_count - group.online_count;
            return (
              <div
                key={group.id}
                className="group-card"
                onClick={() => navigate(`/groups/${group.id}`)}
                role="button"
                tabIndex={0}
                onKeyDown={(e) => { if (e.key === 'Enter') navigate(`/groups/${group.id}`); }}
              >
                <div className="group-card-header">
                  <div
                    className="group-card-icon"
                    style={{ borderColor: group.color || 'var(--accent-primary)' }}
                  >
                    <svg viewBox="0 0 24 24" fill="none" stroke={group.color || 'var(--accent-primary)'} strokeWidth="2">
                      <polygon points="12 2 2 7 12 12 22 7 12 2" />
                      <polyline points="2 17 12 22 22 17" />
                      <polyline points="2 12 12 17 22 12" />
                    </svg>
                  </div>
                  <div className="group-card-status">
                    <StatusDot
                      status={worstStatus === 'warning' ? 'warning' : worstStatus === 'online' ? 'online' : 'offline'}
                    />
                  </div>
                </div>

                <div className="group-card-body">
                  <h3 className="group-card-name">{group.name}</h3>
                  {group.description && (
                    <p className="group-card-desc">{group.description}</p>
                  )}
                </div>

                <div className="group-card-stats">
                  <div className="group-stat">
                    <span className="group-stat-value">{group.target_count}</span>
                    <span className="group-stat-label">Targets</span>
                  </div>
                  <div className="group-stat group-stat-online">
                    <span className="group-stat-value">{group.online_count}</span>
                    <span className="group-stat-label">Online</span>
                  </div>
                  {offlineCount > 0 && (
                    <div className="group-stat group-stat-offline">
                      <span className="group-stat-value">{offlineCount}</span>
                      <span className="group-stat-label">Offline</span>
                    </div>
                  )}
                </div>

                <div className="group-card-footer">
                  <span className="group-card-link">View details →</span>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};

export default Groups;
