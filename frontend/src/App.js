import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import AppNavbar from './components/AppNavbar';
import HomePage from './pages/HomePage';
import ItemsPage from './pages/ItemsPage';
import TimerPage from './pages/TimerPage';
import AlertPage from './pages/AlertPage';

function App() {
  return (
    <Router>
      <AppNavbar />
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/items" element={<ItemsPage />} />
        <Route path="/timers" element={<TimerPage />} />
        <Route path="/alerts" element={<AlertPage />} />  
      </Routes>
    </Router>
  );
}

export default App;
