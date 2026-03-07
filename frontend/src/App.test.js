import { render, screen } from '@testing-library/react';
import App from './App';

test('renders YoloHome navbar brand', () => {
  render(<App />);
  const brandElements = screen.getAllByText(/YoloHome/i);
  expect(brandElements.length).toBeGreaterThan(0);
});
