import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { Input } from './Input';

describe('Input', () => {
  it('renders the label associated with the input via htmlFor/id', () => {
    render(<Input label="Username" value="" onChange={() => {}} />);
    const label = screen.getByText('Username');
    const input = screen.getByRole('textbox');
    expect(label.getAttribute('for')).toBe(input.id);
  });

  it('calls onChange with the raw new string when typed', () => {
    const onChange = vi.fn();
    render(<Input label="Name" value="" onChange={onChange} />);
    const input = screen.getByRole('textbox');
    fireEvent.change(input, { target: { value: 'hello' } });
    expect(onChange).toHaveBeenCalledWith('hello');
  });

  it('renders error text when error is set', () => {
    render(<Input label="Email" value="" onChange={() => {}} error="Required field" />);
    expect(screen.getByText('Required field')).not.toBeNull();
  });

  it('does not render error text when error is null', () => {
    render(<Input label="Email" value="" onChange={() => {}} error={null} />);
    expect(screen.queryByRole('alert')).toBeNull();
  });

  it('does not render error text when error is undefined', () => {
    render(<Input label="Email" value="" onChange={() => {}} />);
    expect(screen.queryByRole('alert')).toBeNull();
  });

  it('applies mono class when mono prop is true', () => {
    render(<Input label="Token" value="abc" onChange={() => {}} mono />);
    const input = screen.getByRole('textbox');
    expect(input.className).toMatch(/mono/);
  });

  it('does not apply mono class when mono prop is false', () => {
    render(<Input label="Name" value="" onChange={() => {}} />);
    const input = screen.getByRole('textbox');
    // The mono class should not be present (just the base .input class)
    expect(input.className).not.toMatch(/\bmono\b/);
  });

  it('disabled prevents typing (input is disabled)', () => {
    render(<Input label="Name" value="" onChange={() => {}} disabled />);
    const input = screen.getByRole('textbox');
    expect(input).toBeDisabled();
  });

  it('type="password" produces a password-type input', () => {
    const { container } = render(
      <Input label="Password" value="secret" onChange={() => {}} type="password" />
    );
    const input = container.querySelector('input[type="password"]');
    expect(input).not.toBeNull();
  });

  it('auto-generated id is stable and label htmlFor matches input id', () => {
    render(<Input label="Username" value="" onChange={() => {}} />);
    const label = screen.getByText('Username') as HTMLLabelElement;
    const input = screen.getByRole('textbox') as HTMLInputElement;
    expect(label.htmlFor).toBe(input.id);
    expect(input.id.length).toBeGreaterThan(0);
  });

  it('explicit id prop overrides auto-generated id', () => {
    render(<Input label="Username" value="" onChange={() => {}} id="my-input" />);
    const input = screen.getByRole('textbox');
    expect(input.id).toBe('my-input');
    const label = screen.getByText('Username') as HTMLLabelElement;
    expect(label.htmlFor).toBe('my-input');
  });

  it('autoComplete passes through to the native input', () => {
    render(
      <Input label="Username" value="" onChange={() => {}} autoComplete="username" />
    );
    const input = screen.getByRole('textbox');
    expect(input.getAttribute('autocomplete')).toBe('username');
  });

  it('placeholder passes through to the native input', () => {
    render(
      <Input label="Email" value="" onChange={() => {}} placeholder="user@example.com" />
    );
    const input = screen.getByRole('textbox');
    expect(input.getAttribute('placeholder')).toBe('user@example.com');
  });

  it('applies hasError class to input when error is set', () => {
    render(<Input label="Email" value="" onChange={() => {}} error="Invalid" />);
    const input = screen.getByRole('textbox');
    expect(input.className).toMatch(/hasError/);
  });

  it('does not apply hasError class when no error', () => {
    render(<Input label="Email" value="" onChange={() => {}} />);
    const input = screen.getByRole('textbox');
    expect(input.className).not.toMatch(/hasError/);
  });
});
