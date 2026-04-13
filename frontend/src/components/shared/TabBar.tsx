import React from 'react';
import './TabBar.css';

interface TabItem {
  id: string;
  label: string;
}

interface TabBarProps {
  tabs: TabItem[];
  activeTab: string;
  onChange: (id: string) => void;
}

const TabBar: React.FC<TabBarProps> = ({ tabs, activeTab, onChange }) => {
  return (
    <div className="tab-bar" role="tablist">
      {tabs.map((tab) => (
        <button
          key={tab.id}
          role="tab"
          aria-selected={activeTab === tab.id}
          className={`tab-bar-item${activeTab === tab.id ? ' active' : ''}`}
          onClick={() => onChange(tab.id)}
        >
          {tab.label}
        </button>
      ))}
    </div>
  );
};

export default TabBar;
