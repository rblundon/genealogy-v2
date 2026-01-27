import { NavLink } from 'react-router-dom';
import { useState, useEffect } from 'react';
import { getPeopleReadyForSync } from '../../api/client';

export function Navigation() {
  const [readyCount, setReadyCount] = useState(0);

  useEffect(() => {
    loadReadyCount();
  }, []);

  const loadReadyCount = async () => {
    try {
      const data = await getPeopleReadyForSync(0.80, 2);
      setReadyCount(data.count || 0);
    } catch (err) {
      console.error('Failed to load ready count:', err);
    }
  };

  const navLinkClass = ({ isActive }) => `
    px-3 py-2 text-sm font-medium transition-colors
    ${isActive
      ? 'text-blue-600 border-b-2 border-blue-600'
      : 'text-gray-600 hover:text-blue-600 border-b-2 border-transparent'
    }
  `;

  return (
    <nav className="flex space-x-6">
      <NavLink to="/" className={navLinkClass}>
        Process
      </NavLink>
      <NavLink to="/obituaries" className={navLinkClass}>
        Obituaries
      </NavLink>
      <NavLink to="/people" className={navLinkClass}>
        <span className="flex items-center gap-2">
          People
          {readyCount > 0 && (
            <span className="inline-flex items-center justify-center px-2 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
              {readyCount}
            </span>
          )}
        </span>
      </NavLink>
    </nav>
  );
}
