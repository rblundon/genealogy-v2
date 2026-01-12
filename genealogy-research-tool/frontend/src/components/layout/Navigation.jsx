import { NavLink } from 'react-router-dom';

export function Navigation() {
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
    </nav>
  );
}
