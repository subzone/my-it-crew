import React from 'react';
import { render, fireEvent, waitFor } from '@testing-library/react';
import AgentArchitecture from './AgentArchitecture';

const mockPerception = jest.fn();
const mockReasoning = jest.fn();
const mockAction = jest.fn();
const mockLearning = jest.fn();

jest.mock('../Perception', () => ({ perception: mockPerception }));
jest.mock('../Reasoning', () => ({ reasoning: mockReasoning }));
jest.mock('../Action', () => ({ action: mockAction }));
jest.mock('../Learning', () => ({ learning: mockLearning }));

describe('AgentArchitecture', () => {
  it('should render correctly', () => {
    const { getByText } = render(<AgentArchitecture />);
    expect(getByText('Agent Architecture')).toBeInTheDocument();
  });
});