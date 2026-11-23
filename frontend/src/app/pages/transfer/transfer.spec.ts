import { provideHttpClient } from '@angular/common/http';
import {
  HttpTestingController,
  TestRequest,
  provideHttpClientTesting,
} from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';

import { Account, Beneficiary, Transfer as TransferResult } from '../../core/models';
import { IDEMPOTENCY_KEY, Transfer } from './transfer';

const account = (overrides: Partial<Account>): Account => ({
  id: 1,
  iban: 'AE769991043321819600133',
  iban_display: 'AE76 9991 0433 2181 9600 133',
  type: 'CURRENT',
  type_label: 'Everyday Current Account',
  nickname: 'Everyday',
  currency: 'AED',
  balance: '1000.00',
  status: 'ACTIVE',
  opened_at: '2026-08-24T08:00:00+04:00',
  ...overrides,
});

const ACCOUNTS = [
  account({}),
  account({ id: 2, nickname: 'Rainy day', type: 'SAVINGS', balance: '500.00' }),
  account({ id: 3, nickname: 'Old account', status: 'FROZEN', balance: '9999.00' }),
];

const beneficiary = (overrides: Partial<Beneficiary>): Beneficiary => ({
  id: 10,
  name: 'Omar Ali',
  iban: 'AE070331234567890123456',
  iban_display: 'AE07 0331 2345 6789 0123 456',
  nickname: '',
  status: 'ACTIVE',
  created_at: '2026-11-20T08:00:00+04:00',
  activated_at: '2026-11-20T08:05:00+04:00',
  ...overrides,
});

const BENEFICIARIES = [
  beneficiary({}),
  beneficiary({ id: 11, name: 'Pending Person', status: 'PENDING' }),
];

const result = (overrides: Partial<TransferResult> = {}): TransferResult => ({
  id: 99,
  reference: 'TRF261123AB12CD34',
  uetr: '5b8a6e1c-0000-4000-8000-000000000000',
  kind: 'OWN',
  status: 'COMPLETED',
  from_account: 1,
  to_account: 2,
  beneficiary: null,
  creditor_name: 'Sara Khan',
  creditor_iban: 'AE769991043321819600134',
  amount: '250.00',
  currency: 'AED',
  remarks: '',
  created_at: '2026-11-23T09:00:00+04:00',
  ...overrides,
});

describe('Transfer page', () => {
  let fixture: ComponentFixture<Transfer>;
  let http: HttpTestingController;
  let keys: number;

  const el = <T extends HTMLElement = HTMLElement>(testId: string) =>
    fixture.nativeElement.querySelector(`[data-testid="${testId}"]`) as T | null;
  const text = (testId: string) => el(testId)?.textContent?.trim().replace(/\s+/g, ' ');

  async function stable() {
    await fixture.whenStable();
  }

  async function type(testId: string, value: string) {
    const input = el<HTMLInputElement>(testId)!;
    input.value = value;
    input.dispatchEvent(new Event('input'));
    input.dispatchEvent(new Event('blur'));
    await stable();
  }

  async function choose(testId: string, index: number) {
    const select = el<HTMLSelectElement>(testId)!;
    select.selectedIndex = index;
    select.dispatchEvent(new Event('change'));
    await stable();
  }

  async function click(testId: string) {
    el(testId)!.click();
    await stable();
  }

  async function open(beneficiaryParam?: string) {
    fixture = TestBed.createComponent(Transfer);
    if (beneficiaryParam) fixture.componentRef.setInput('beneficiary', beneficiaryParam);
    await stable();
    http
      .expectOne('/api/accounts/')
      .flush({ count: 3, next: null, previous: null, results: ACCOUNTS });
    http
      .expectOne('/api/beneficiaries/')
      .flush({ count: 2, next: null, previous: null, results: BENEFICIARIES });
    await stable();
  }

  function transferRequest(): TestRequest {
    return http.expectOne((req) => req.method === 'POST' && req.url === '/api/transfers/');
  }

  /** After a successful transfer the page reloads balances. */
  function answerBalances() {
    http
      .expectOne('/api/accounts/')
      .flush({ count: 3, next: null, previous: null, results: ACCOUNTS });
  }

  beforeEach(() => {
    keys = 0;
    TestBed.configureTestingModule({
      imports: [Transfer],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        provideRouter([]),
        { provide: IDEMPOTENCY_KEY, useValue: () => `key-${++keys}` },
      ],
    });
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('offers only active accounts and confirmed beneficiaries', async () => {
    await open();
    const from = [...el<HTMLSelectElement>('transfer-from')!.options].map((o) => o.text.trim());
    expect(from).toEqual(['Everyday · AED 1,000.00', 'Rainy day · AED 500.00']); // not the frozen one
    // "To" never offers the account money is coming from.
    expect(
      [...el<HTMLSelectElement>('transfer-to-account')!.options].map((o) => o.text.trim()),
    ).toEqual(['Rainy day']);
    await click('dest-beneficiary');
    const payees = [...el<HTMLSelectElement>('transfer-beneficiary')!.options].map((o) => o.text);
    expect(payees).toHaveLength(1);
    expect(payees[0]).toContain('Omar Ali'); // not the one still waiting for its code
  });

  it('preselects the beneficiary from the "Send money" link', async () => {
    await open('10');
    expect(el<HTMLInputElement>('dest-beneficiary')!.checked).toBe(true);
  });

  it('shows "enter an amount" when Review is clicked with no amount', async () => {
    await open();
    await click('transfer-review');
    expect(text('transfer-amount-error')).toBe('Enter an amount.');
    expect(el('transfer-summary')).toBeNull();
  });

  it.each([
    ['abc', 'Enter an amount like 250 or 250.50.'],
    ['10.555', 'Enter an amount like 250 or 250.50.'],
    ['-5', 'Enter an amount like 250 or 250.50.'],
    ['0.00', 'The amount must be more than zero.'],
    ['1000.01', 'That is more than the available balance.'],
  ])('refuses %s before calling the API', async (amount, message) => {
    await open();
    await type('transfer-amount', amount);
    await click('transfer-review');
    expect(text('transfer-amount-error')).toBe(message);
    expect(el('transfer-summary')).toBeNull();
  });

  it('accepts exactly the whole balance', async () => {
    await open();
    await type('transfer-amount', '1000');
    await click('transfer-review');
    expect(text('summary-amount')).toBe('AED 1,000.00');
  });

  it('reviews, then sends once with an Idempotency-Key, and shows the reference', async () => {
    await open();
    await type('transfer-amount', '250');
    await type('transfer-remarks', 'Rent share');
    await click('transfer-review');
    expect(text('summary-to')).toContain('Rainy day');
    expect(text('summary-remarks')).toBe('Rent share');

    await click('transfer-confirm');
    await click('transfer-confirm'); // a double click: the button is already "Sending…" and disabled
    const req = transferRequest(); // expectOne: exactly one request
    expect(req.request.headers.get('Idempotency-Key')).toBe('key-1');
    expect(req.request.body).toEqual({
      from_account: 1,
      to_account: 2,
      amount: '250',
      remarks: 'Rent share',
    });
    req.flush(result());
    answerBalances();
    await stable();
    expect(text('transfer-success')).toContain('Money sent');
    expect(text('transfer-reference')).toBe('TRF261123AB12CD34');
    expect(el('transfer-replayed')).toBeNull();
  });

  it('sends to a beneficiary with the beneficiary id, not an account', async () => {
    await open('10');
    await type('transfer-amount', '75.5');
    await click('transfer-review');
    await click('transfer-confirm');
    const req = transferRequest();
    expect(req.request.body).toEqual({
      from_account: 1,
      beneficiary: 10,
      amount: '75.5',
      remarks: '',
    });
    req.flush(result({ kind: 'LOCAL', status: 'PENDING', beneficiary: 10, to_account: null }));
    answerBalances();
    await stable();
    expect(text('transfer-success')).toContain('Payment sent to the other bank');
    expect(el('transfer-pending-note')).not.toBeNull();
  });

  it('after a network failure, "Try again" reuses the SAME key, so it can never pay twice', async () => {
    await open();
    await type('transfer-amount', '250');
    await click('transfer-review');
    await click('transfer-confirm');
    transferRequest().error(new ProgressEvent('error')); // no response at all
    await stable();
    expect(text('transfer-uncertain')).toContain(
      "We can't tell whether this transfer went through",
    );

    await click('transfer-retry');
    const retry = transferRequest();
    expect(retry.request.headers.get('Idempotency-Key')).toBe('key-1');
    // The first attempt had in fact gone through: the server replays it instead of paying again.
    retry.flush(result(), { headers: { 'Idempotent-Replayed': 'true' } });
    answerBalances();
    await stable();
    expect(text('transfer-replayed')).toContain('You were not charged twice');
  });

  it('a 500 is uncertain too: keep the key', async () => {
    await open();
    await type('transfer-amount', '250');
    await click('transfer-review');
    await click('transfer-confirm');
    transferRequest().flush(null, { status: 502, statusText: 'Bad Gateway' });
    await stable();
    expect(el('transfer-uncertain')).not.toBeNull();
    await click('transfer-retry');
    expect(transferRequest().request.headers.get('Idempotency-Key')).toBe('key-1');
  });

  it('a business-rule "no" goes back to the form with the message; the next try gets a new key', async () => {
    await open();
    await type('transfer-amount', '250');
    await click('transfer-review');
    await click('transfer-confirm');
    transferRequest().flush(
      {
        code: 'daily_limit_exceeded',
        detail: 'This would exceed your daily limit. You can send AED 100.00 more today.',
      },
      { status: 400, statusText: 'Bad Request' },
    );
    await stable();
    expect(el('transfer-error')!.getAttribute('data-error-code')).toBe('daily_limit_exceeded');
    expect(text('transfer-error')).toContain('AED 100.00 more today');
    expect(el<HTMLInputElement>('transfer-amount')!.value).toBe('250'); // their input is kept

    await type('transfer-amount', '100');
    await click('transfer-review');
    await click('transfer-confirm');
    // A different transfer: a different key (reusing key-1 for different details would be a 409).
    expect(transferRequest().request.headers.get('Idempotency-Key')).toBe('key-2');
  });

  it('editing after review makes the next send a new transfer with a new key', async () => {
    await open();
    await type('transfer-amount', '250');
    await click('transfer-review');
    await click('transfer-edit');
    await type('transfer-amount', '300');
    await click('transfer-review');
    await click('transfer-confirm');
    const req = transferRequest();
    expect(req.request.headers.get('Idempotency-Key')).toBe('key-2');
    expect(req.request.body.amount).toBe('300');
  });

  it('"Send another" starts a fresh transfer', async () => {
    await open();
    await type('transfer-amount', '250');
    await click('transfer-review');
    await click('transfer-confirm');
    transferRequest().flush(result());
    answerBalances();
    await stable();
    await click('transfer-another');
    expect(el<HTMLInputElement>('transfer-amount')!.value).toBe('');
    await type('transfer-amount', '250'); // the same amount again is a NEW transfer
    await click('transfer-review');
    await click('transfer-confirm');
    expect(transferRequest().request.headers.get('Idempotency-Key')).toBe('key-2');
  });

  it('shows a load error with a retry', async () => {
    fixture = TestBed.createComponent(Transfer);
    await stable();
    http.expectOne('/api/accounts/').flush(null, { status: 500, statusText: 'x' });
    http.expectOne('/api/beneficiaries/'); // cancelled by forkJoin when the other fails
    await stable();
    expect(el('transfer-load-error')).not.toBeNull();
    await click('transfer-load-retry');
    http
      .expectOne('/api/accounts/')
      .flush({ count: 3, next: null, previous: null, results: ACCOUNTS });
    http
      .expectOne('/api/beneficiaries/')
      .flush({ count: 0, next: null, previous: null, results: [] });
    await stable();
    await click('dest-beneficiary');
    expect(text('no-beneficiaries')).toContain('No confirmed beneficiaries yet');
  });
});
