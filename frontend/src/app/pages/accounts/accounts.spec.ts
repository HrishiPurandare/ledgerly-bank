import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';

import { Account } from '../../core/models';
import { Accounts, totalsByCurrency } from './accounts';

const account = (overrides: Partial<Account>): Account => ({
  id: 1,
  iban: 'AE769991043321819600133',
  iban_display: 'AE76 9991 0433 2181 9600 133',
  type: 'CURRENT',
  type_label: 'Everyday Current Account',
  nickname: 'Everyday',
  currency: 'AED',
  balance: '32079.82',
  status: 'ACTIVE',
  opened_at: '2026-08-24T08:00:00+04:00',
  ...overrides,
});

describe('Accounts page', () => {
  let fixture: ComponentFixture<Accounts>;
  let http: HttpTestingController;
  const text = (testId: string) =>
    fixture.nativeElement.querySelector(`[data-testid="${testId}"]`)?.textContent?.trim();

  beforeEach(async () => {
    TestBed.configureTestingModule({
      imports: [Accounts],
      providers: [provideHttpClient(), provideHttpClientTesting(), provideRouter([])],
    });
    http = TestBed.inject(HttpTestingController);
    fixture = TestBed.createComponent(Accounts);
    await fixture.whenStable();
  });

  afterEach(() => http.verify());

  async function respond(results: Account[]) {
    http
      .expectOne('/api/accounts/')
      .flush({ count: results.length, next: null, previous: null, results });
    await fixture.whenStable();
  }

  it('shows a loading state first', () => {
    expect(text('accounts-loading')).toContain('Loading');
    http.expectOne('/api/accounts/');
  });

  it('lists each account with its balance formatted exactly', async () => {
    await respond([
      account({}),
      account({
        id: 2,
        type: 'SAVINGS',
        type_label: 'Smart Savings Account',
        nickname: '',
        balance: '5643.8',
      }),
    ]);
    const rows = fixture.nativeElement.querySelectorAll('[data-test-role="account"]');
    expect(rows.length).toBe(2);
    expect(rows[0].querySelector('[data-testid="account-balance"]').textContent.trim()).toBe(
      'AED 32,079.82',
    );
    expect(rows[1].querySelector('[data-testid="account-name"]').textContent.trim()).toBe(
      'Smart Savings Account',
    );
    expect(rows[1].querySelector('[data-testid="account-balance"]').textContent.trim()).toBe(
      'AED 5,643.80',
    );
  });

  it('marks a frozen account', async () => {
    await respond([account({ status: 'FROZEN' })]);
    expect(text('account-frozen')).toBe('Frozen');
  });

  it('has an empty state', async () => {
    await respond([]);
    expect(text('accounts-empty')).toContain("don't have any accounts");
  });

  it('shows an error with a retry that works', async () => {
    http.expectOne('/api/accounts/').flush(null, { status: 500, statusText: 'Server Error' });
    await fixture.whenStable();
    expect(text('accounts-error')).toContain("couldn't load");
    fixture.nativeElement.querySelector('[data-testid="accounts-retry"]').click();
    await respond([account({})]);
    expect(text('account-balance')).toBe('AED 32,079.82');
  });

  it('shows the exact total and links each account to its statement', async () => {
    await respond([
      account({ balance: '0.10' }),
      account({ id: 2, balance: '0.20' }), // as floats: 0.30000000000000004
      account({ id: 3, balance: '18240.15', status: 'FROZEN' }), // frozen money is still yours
    ]);
    expect(text('total-amount')).toBe('AED 18,240.45');
    expect(text('total-AED')).toContain('3 accounts');
    const link = fixture.nativeElement.querySelector(
      '[data-testid="account-2"] [data-testid="account-name"]',
    );
    expect(link.getAttribute('href')).toBe('/accounts/2');
  });
});

describe('totalsByCurrency', () => {
  it('never adds different currencies together', () => {
    const aed = account({ balance: '100.00' });
    const usd = account({ id: 2, currency: 'USD', balance: '50.00' });
    expect(totalsByCurrency([aed, usd, aed])).toEqual([
      { currency: 'AED', amount: '200.00', accounts: 2 },
      { currency: 'USD', amount: '50.00', accounts: 1 },
    ]);
    expect(totalsByCurrency([])).toEqual([]);
  });
});
