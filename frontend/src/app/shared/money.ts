/**
 * Exact money arithmetic on the API's strings. Adding "0.10" and "0.20" as JavaScript numbers gives
 * 0.30000000000000004; here each amount becomes a whole number of cents (BigInt) first, so totals are exact.
 */

const MONEY = /^-?\d+(\.\d{1,2})?$/;

export function toCents(amount: string): bigint {
  if (!MONEY.test(amount)) {
    throw new Error(`Not a money amount: "${amount}"`);
  }
  const negative = amount.startsWith('-');
  const [whole, fraction = ''] = amount.replace('-', '').split('.');
  const cents = BigInt(whole) * 100n + BigInt((fraction + '00').slice(0, 2));
  return negative ? -cents : cents;
}

export function fromCents(cents: bigint): string {
  const negative = cents < 0n;
  const abs = negative ? -cents : cents;
  const fraction = (abs % 100n).toString().padStart(2, '0');
  return `${negative ? '-' : ''}${abs / 100n}.${fraction}`;
}

export function sumMoney(amounts: readonly string[]): string {
  return fromCents(amounts.reduce((total, amount) => total + toCents(amount), 0n));
}
