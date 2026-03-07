import { render, screen } from '@testing-library/react';
import App from './App';

test('renders YoloHome brand in navbar', () => {
  render(<App />);
  const brand = screen.getAllByText(/YoloHome/i);
  expect(brand.length).toBeGreaterThan(0);
});

test('renders home page welcome heading', () => {
  render(<App />);
  expect(screen.getByText(/Welcome to YoloHome/i)).toBeInTheDocument();
});
