import { BrowserRouter, Routes, Route, Link, useLocation } from 'react-router-dom';
import { Review } from './pages/Review';

function NavLink({ to, children }: { to: string; children: React.ReactNode }) {
  const location = useLocation();
  const isActive = location.pathname === to;

  return (
    <Link
      to={to}
      style={{
        padding: '8px 16px',
        textDecoration: 'none',
        color: isActive ? '#2563eb' : '#374151',
        fontWeight: isActive ? 600 : 400,
        borderBottom: isActive ? '2px solid #2563eb' : '2px solid transparent',
      }}
    >
      {children}
    </Link>
  );
}

function Layout({ children }: { children: React.ReactNode }) {
  return (
    <div style={{ minHeight: '100vh', backgroundColor: '#f3f4f6' }}>
      {/* Header */}
      <header
        style={{
          backgroundColor: '#ffffff',
          borderBottom: '1px solid #e5e7eb',
          padding: '0 24px',
        }}
      >
        <div
          style={{
            maxWidth: '1200px',
            margin: '0 auto',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            height: '64px',
          }}
        >
          <Link
            to="/"
            style={{
              fontSize: '18px',
              fontWeight: 700,
              color: '#111827',
              textDecoration: 'none',
            }}
          >
            Genealogy Tool
          </Link>
          <nav style={{ display: 'flex', gap: '8px' }}>
            <NavLink to="/">Home</NavLink>
            <NavLink to="/review">Review Facts</NavLink>
          </nav>
        </div>
      </header>

      {/* Main content */}
      <main>{children}</main>
    </div>
  );
}

function Home() {
  return (
    <div style={{ maxWidth: '800px', margin: '0 auto', padding: '48px 24px' }}>
      <h1 style={{ fontSize: '32px', fontWeight: 700, marginBottom: '16px', color: '#111827' }}>
        Genealogy Research Tool
      </h1>
      <p style={{ fontSize: '18px', color: '#6b7280', marginBottom: '32px' }}>
        Extract and organize family relationship data from obituaries using AI.
      </p>

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))',
          gap: '16px',
        }}
      >
        <Link
          to="/review"
          style={{
            padding: '24px',
            backgroundColor: '#ffffff',
            borderRadius: '8px',
            border: '1px solid #e5e7eb',
            textDecoration: 'none',
            color: 'inherit',
          }}
        >
          <h2 style={{ fontSize: '18px', fontWeight: 600, marginBottom: '8px', color: '#111827' }}>
            Review Facts
          </h2>
          <p style={{ fontSize: '14px', color: '#6b7280' }}>
            View extracted facts from obituaries, approve or reject them, and sync to Gramps.
          </p>
        </Link>
      </div>
    </div>
  );
}

function App() {
  return (
    <BrowserRouter>
      <Layout>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/review" element={<Review />} />
        </Routes>
      </Layout>
    </BrowserRouter>
  );
}

export default App;
