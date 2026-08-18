import React from 'react';
import { render, fireEvent, waitFor } from '@testing-library/react';
import ConfigMap from './ConfigMap';

const mockConfig = {
  foo: 'bar'
};

describe('ConfigMap', () => {
  it('renders correctly', () => {
    const { getByText } = render(<ConfigMap config={mockConfig} />);
    expect(getByText('ConfigMap')).toBeInTheDocument();
  });
});