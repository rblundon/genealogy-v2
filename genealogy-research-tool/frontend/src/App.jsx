import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { Layout } from './components/layout/Layout';
import { ProcessPage } from './pages/ProcessPage';
import { ObituaryListPage } from './pages/ObituaryListPage';
import { ObituaryDetailPage } from './pages/ObituaryDetailPage';

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<ProcessPage />} />
          <Route path="obituaries" element={<ObituaryListPage />} />
          <Route path="obituaries/:id" element={<ObituaryDetailPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default App;
