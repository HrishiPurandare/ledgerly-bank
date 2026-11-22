import { MoneyPipe } from './money.pipe';

describe('MoneyPipe', () => {
  const pipe = new MoneyPipe();

  it.each([
    ['32079.82', 'AED 32,079.82'],
    ['0.5', 'AED 0.50'],
    ['1000000', 'AED 1,000,000.00'],
    ['-45.5', '-AED 45.50'],
    ['0.10', 'AED 0.10'],
  ])('formats %s as %s', (amount, expected) => {
    expect(pipe.transform(amount)).toBe(expected);
  });

  it('keeps cents a float would lose', () => {
    // As a JavaScript number, 0.1 + 0.2 is 0.30000000000000004. The pipe never converts to a number.
    expect(pipe.transform('9007199254740993.01')).toBe('AED 9,007,199,254,740,993.01');
  });

  it.each([null, undefined, '', 'abc', '12,50'])('shows nothing for %s', (bad) => {
    expect(pipe.transform(bad as string)).toBe('');
  });

  it('uses the given currency', () => {
    expect(pipe.transform('10', 'USD')).toBe('USD 10.00');
  });
});
