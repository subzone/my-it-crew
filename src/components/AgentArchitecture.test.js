import React from 'react';
import { render, fireEvent, waitFor } from '@testing-library/react';
import AgentArchitecture from './AgentArchitecture';

describe('AgentArchitecture', () => {
  it('renders correctly', () => {
    const { getByText } = render(<AgentArchitecture />);
    expect(getByText('Agent Architecture')).toBeInTheDocument();
  });
});