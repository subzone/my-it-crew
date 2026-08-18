import React from 'react';
import { render, fireEvent, waitFor } from '@testing-library/react';
import TicketTriageDashboard from '../TicketTriageDashboard';

const mockData = [
  { id: 1, title: 'Ticket 1', description: 'Description 1' },
  { id: 2, title: 'Ticket 2', description: 'Description 2' },
];

it('renders ticket triage dashboard', () => {
  const { getByText } = render(<TicketTriageDashboard tickets={mockData} />);
  expect(getByText('Ticket 1')).toBeInTheDocument();
  expect(getByText('Ticket 2')).toBeInTheDocument();
});