import React from 'react';
import { render, fireEvent, waitFor } from '@testing-library/react';
import AgentArchitecture from './AgentArchitecture';

const mockProps = {
  // mock props
};

describe('AgentArchitecture', () => {
  it('renders correctly', () => {
    const { getByText } = render(<AgentArchitecture {...mockProps} />);
    expect(getByText('Agent Architecture')).toBeInTheDocument();
  });
});