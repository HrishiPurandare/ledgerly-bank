import { HttpErrorResponse } from '@angular/common/http';

import { toProblem } from './api-error';

const http = (status: number, error: unknown) => new HttpErrorResponse({ status, error });

describe('toProblem', () => {
  it('keeps the stable code of a business rule', () => {
    const p = toProblem(
      http(400, { code: 'daily_limit_exceeded', detail: 'You can send AED 100.00 more today.' }),
    );
    expect(p).toEqual({
      code: 'daily_limit_exceeded',
      message: 'You can send AED 100.00 more today.',
      fields: {},
      uncertain: false,
    });
  });

  it('maps field errors and the general one', () => {
    const p = toProblem(
      http(400, {
        amount: ['Ensure this value is greater than or equal to 0.01.'],
        non_field_errors: ['Send to exactly one of: to_account, beneficiary.'],
      }),
    );
    expect(p.code).toBe('validation');
    expect(p.fields['amount']).toContain('0.01');
    expect(p.message).toBe('Send to exactly one of: to_account, beneficiary.');
  });

  it('keeps a 409 business code (idempotency key reused)', () => {
    expect(toProblem(http(409, { code: 'idempotency_key_reused', detail: 'x' })).code).toBe(
      'idempotency_key_reused',
    );
  });

  it.each([
    [0, 'network'],
    [500, 'server'],
    [503, 'server'],
  ])('a %s is uncertain: the money may or may not have moved', (status, code) => {
    const p = toProblem(http(status, null));
    expect(p.code).toBe(code);
    expect(p.uncertain).toBe(true);
  });

  it('a 400 or 404 is certain: the server answered and did nothing', () => {
    expect(toProblem(http(404, { detail: 'Not found.' })).uncertain).toBe(false);
    expect(toProblem(http(400, { code: 'x', detail: 'y' })).uncertain).toBe(false);
  });

  it('survives bodies it does not expect', () => {
    expect(toProblem(http(400, 'plain text')).code).toBe('unknown');
    expect(toProblem(new Error('boom')).code).toBe('unknown');
  });

  it('a 5xx with a business code is a deliberate, certain answer', () => {
    const p = toProblem(
      http(503, { code: 'otp_not_sent', detail: "We couldn't send your confirmation code." }),
    );
    expect(p.code).toBe('otp_not_sent');
    expect(p.uncertain).toBe(false);
  });

  it('a 502 from the proxy, with an HTML body, stays uncertain', () => {
    expect(toProblem(http(502, '<html>Bad Gateway</html>')).uncertain).toBe(true);
  });
});
