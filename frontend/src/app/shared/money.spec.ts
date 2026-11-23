import { fromCents, sumMoney, toCents } from './money';

describe('money arithmetic', () => {
  it('adds exactly where floats would not', () => {
    expect(0.1 + 0.2).not.toBe(0.3); // the reason this file exists
    expect(sumMoney(['0.10', '0.20'])).toBe('0.30');
  });

  it.each([
    [[], '0.00'],
    [['18240.15', '5643.8'], '23883.95'],
    [['100', '-0.01'], '99.99'],
    [['-5', '2.5'], '-2.50'],
    [['9007199254740993.01', '0.99'], '9007199254740994.00'], // past Number.MAX_SAFE_INTEGER
    [['9007199254740993.01'], '9007199254740993.01'], // a float would say ...992.00
  ])('sums %j to %s', (amounts, expected) => {
    expect(sumMoney(amounts)).toBe(expected);
  });

  it('converts both ways', () => {
    expect(toCents('12.3')).toBe(1230n);
    expect(toCents('-0.05')).toBe(-5n);
    expect(fromCents(-5n)).toBe('-0.05');
    expect(fromCents(0n)).toBe('0.00');
  });

  it.each(['', 'abc', '1.234', '1,000.00', '1e3'])('refuses %j instead of guessing', (bad) => {
    expect(() => toCents(bad)).toThrow('Not a money amount');
  });
});
