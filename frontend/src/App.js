import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import AppNavbar from './components/AppNavbar';
import HomePage from './pages/HomePage';
import ItemsPage from './pages/ItemsPage';

function App() {
  return (
    <Router>
      <AppNavbar />
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/items" element={<ItemsPage />} />
      </Routes>
    </Router>
  );
}

export default App;
