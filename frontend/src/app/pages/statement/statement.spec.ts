import { provideHttpClient } from '@angular/common/http';
import {
  HttpTestingController,
  TestRequest,
  provideHttpClientTesting,
} from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { Router, provideRouter, withComponentInputBinding } from '@angular/router';
import { RouterTestingHarness } from '@angular/router/testing';

import { Account, Page, Transaction } from '../../core/models';
import { Statement, parseQuery, toParams } from './statement';

const ACCOUNT: Account = {
  id: 1,
  iban: 'AE769991043321819600133',
  iban_display: 'AE76 9991 0433 2181 9600 133',
  type: 'CURRENT',
  type_label: 'Everyday Current Account',
  nickname: 'Everyday',
  currency: 'AED',
  balance: '18240.15',
  status: 'ACTIVE',
  opened_at: '2026-08-24T08:00:00+04:00',
};

const tx = (overrides: Partial<Transaction>): Transaction => ({
  id: 1,
  reference: 'LDG261120000001',
  direction: 'DEBIT',
  category: 'CARD',
  amount: '45.50',
  balance_after: '18240.15',
  description: 'Card purchase Marina Coffee House',
  counterparty: 'Marina Coffee House',
  created_at: '2026-11-20T23:30:00Z', // 03:30 on 21 Nov in Dubai
  ...overrides,
});

const page = (results: Transaction[], extra: Partial<Page<Transaction>> = {}) => ({
  count: results.length,
  next: null,
  previous: null,
  results,
  ...extra,
});

describe('parseQuery (the URL is user input)', () => {
  it('keeps valid filters', () => {
    expect(
      parseQuery({
        page: '3',
        direction: 'DEBIT',
        category: 'CARD',
        date_from: '2026-11-01',
        date_to: '2026-11-30',
        search: '  coffee ',
      }),
    ).toEqual({
      page: 3,
      direction: 'DEBIT',
      category: 'CARD',
      date_from: '2026-11-01',
      date_to: '2026-11-30',
      search: 'coffee',
    });
  });

  it.each([
    ['page', '0'],
    ['page', '-2'],
    ['page', '1.5'],
    ['page', 'abc'],
    ['direction', 'SIDEWAYS'],
    ['category', 'toString'], // inherited by every object: a plain `in` check let this through
    ['category', 'LOTTERY'],
    ['date_from', '20/11/2026'],
    ['date_to', '2026-11-30T00:00'],
  ])('drops %s=%s', (key, value) => {
    expect(parseQuery({ [key]: value })).toEqual(parseQuery({}));
  });

  it('caps the search length', () => {
    expect(parseQuery({ search: 'x'.repeat(500) }).search).toHaveLength(100);
  });
});

describe('toParams', () => {
  it('only sends what is set, and leaves page 1 implicit', () => {
    expect(toParams(parseQuery({ direction: 'CREDIT', page: '1' }))).toEqual({
      direction: 'CREDIT',
    });
    expect(toParams(parseQuery({ page: '2' }))).toEqual({ page: '2' });
  });
});

describe('Statement page', () => {
  let harness: RouterTestingHarness;
  let http: HttpTestingController;
  let router: Router;

  const el = (testId: string): HTMLElement | null =>
    harness.routeNativeElement!.querySelector(`[data-testid="${testId}"]`);
  const text = (testId: string) => el(testId)?.textContent?.trim();
  const rows = () =>
    harness.routeNativeElement!.querySelectorAll<HTMLElement>('[data-test-role="transaction"]');
  const txRequest = (): TestRequest =>
    http.expectOne((req) => req.url === '/api/accounts/1/transactions/');

  async function open(url: string) {
    await harness.navigateByUrl(url);
    await harness.fixture.whenStable();
  }

  async function flush(req: TestRequest, body: object) {
    req.flush(body);
    await harness.fixture.whenStable();
  }

  async function fail(req: TestRequest, status: number, body: object | null = null) {
    req.flush(body, { status, statusText: 'x' });
    await harness.fixture.whenStable();
  }

  /** Opens the page and answers both requests. */
  async function openWith(url: string, results: Page<Transaction>) {
    await open(url);
    await flush(http.expectOne('/api/accounts/1/'), ACCOUNT);
    await flush(txRequest(), results);
  }

  beforeEach(async () => {
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        provideRouter(
          [{ path: 'accounts/:id', component: Statement }],
          withComponentInputBinding(),
        ),
      ],
    });
    http = TestBed.inject(HttpTestingController);
    router = TestBed.inject(Router);
    harness = await RouterTestingHarness.create();
  });

  afterEach(() => http.verify());

  it('shows the account header and the transactions, in Dubai time', async () => {
    await openWith(
      '/accounts/1',
      page([
        tx({}),
        tx({
          id: 2,
          reference: 'LDG261125000002',
          direction: 'CREDIT',
          category: 'SALARY',
          amount: '18000',
          description: 'Monthly salary',
        }),
      ]),
    );
    expect(text('statement-account-name')).toBe('Everyday');
    expect(text('statement-balance')).toBe('AED 18,240.15');
    expect(rows()).toHaveLength(2);
    const [debit, credit] = rows();
    // The bank's day is Dubai's day, whatever time zone the browser (or CI machine) is in.
    expect(debit.querySelector('[data-testid="tx-date"]')!.textContent!.trim()).toBe(
      '21 Nov 2026, 03:30',
    );
    expect(debit.querySelector('[data-testid="tx-amount"]')!.textContent!.trim()).toBe(
      '-AED 45.50',
    );
    expect(debit.querySelector('[data-testid="tx-category"]')!.textContent!.trim()).toBe(
      'Card purchase',
    );
    expect(credit.querySelector('[data-testid="tx-amount"]')!.textContent!.trim()).toBe(
      'AED 18,000.00',
    );
    expect(credit.classList).toContain('credit');
  });

  it('sends the filters from the URL to the API and shows them in the form', async () => {
    await open('/accounts/1?direction=DEBIT&category=CARD&search=coffee&date_from=2026-11-01');
    http.expectOne('/api/accounts/1/').flush(ACCOUNT);
    const req = txRequest();
    expect(req.request.params.toString()).toBe(
      'direction=DEBIT&category=CARD&date_from=2026-11-01&search=coffee',
    );
    await flush(req, page([tx({})]));
    expect((el('filter-direction') as HTMLSelectElement).value).toBe('DEBIT');
    expect((el('filter-search') as HTMLInputElement).value).toBe('coffee');
    expect(el('filter-clear')).not.toBeNull();
  });

  it('never sends junk from the URL to the API', async () => {
    await open('/accounts/1?direction=SIDEWAYS&page=-1&date_to=yesterday');
    http.expectOne('/api/accounts/1/').flush(ACCOUNT);
    const req = txRequest();
    expect(req.request.params.keys()).toEqual([]);
    await flush(req, page([]));
  });

  it('applying filters updates the URL, starts at page 1, and refetches only the transactions', async () => {
    await openWith('/accounts/1?page=3', page([tx({})], { count: 45, previous: 'p2' }));
    (el('filter-direction') as HTMLSelectElement).value = 'CREDIT';
    el('filter-direction')!.dispatchEvent(new Event('change'));
    el('filter-apply')!.click();
    await harness.fixture.whenStable();
    expect(router.url).toBe('/accounts/1?direction=CREDIT');
    const req = txRequest(); // and no second request for the account: expectNone below
    http.expectNone('/api/accounts/1/');
    expect(req.request.params.toString()).toBe('direction=CREDIT');
    await flush(req, page([]));
    expect(text('statement-empty')).toBe('No transactions match these filters.');
  });

  it('refuses a "from" date after the "to" date without calling the API', async () => {
    await openWith('/accounts/1', page([tx({})]));
    const from = el('filter-from') as HTMLInputElement;
    const to = el('filter-to') as HTMLInputElement;
    from.value = '2026-11-20';
    from.dispatchEvent(new Event('input'));
    to.value = '2026-11-01';
    to.dispatchEvent(new Event('input'));
    el('filter-apply')!.click();
    await harness.fixture.whenStable();
    expect(text('filter-error')).toContain('"From" must be on or before "To"');
    expect(router.url).toBe('/accounts/1');
    http.expectNone((req) => req.url.includes('/transactions/'));
  });

  it('clear removes every filter', async () => {
    await openWith('/accounts/1?category=ATM', page([]));
    el('filter-clear')!.click();
    await harness.fixture.whenStable();
    expect(router.url).toBe('/accounts/1');
    await flush(txRequest(), page([]));
    expect(text('statement-empty')).toBe('No transactions yet.');
    expect(el('filter-clear')).toBeNull();
  });

  it('a slow, older response can never overwrite a newer one', async () => {
    await open('/accounts/1?category=CARD');
    http.expectOne('/api/accounts/1/').flush(ACCOUNT);
    const slow = txRequest();
    await router.navigateByUrl('/accounts/1?category=SALARY'); // the user changes their mind
    await harness.fixture.whenStable();
    expect(slow.cancelled).toBe(true); // switchMap unsubscribed from the old request
    await flush(txRequest(), page([tx({ category: 'SALARY', description: 'Monthly salary' })]));
    expect(text('tx-description')).toBe('Monthly salary');
  });

  it('pages through the statement keeping the filters', async () => {
    await openWith('/accounts/1?direction=DEBIT', page([tx({})], { count: 45, next: 'p2' }));
    expect(text('page-info')).toBe('Page 1 of 3');
    expect((el('page-prev') as HTMLButtonElement).disabled).toBe(true);
    el('page-next')!.click();
    await harness.fixture.whenStable();
    expect(router.url).toBe('/accounts/1?direction=DEBIT&page=2');
    const req = txRequest();
    expect(req.request.params.toString()).toBe('direction=DEBIT&page=2');
    await flush(req, page([tx({})], { count: 45, next: 'p3', previous: 'p1' }));
    expect(text('page-info')).toBe('Page 2 of 3');
    expect((el('page-prev') as HTMLButtonElement).disabled).toBe(false);
  });

  it("someone else's account (404) says not found, without hinting that it exists", async () => {
    await open('/accounts/1');
    await fail(http.expectOne('/api/accounts/1/'), 404);
    expect(text('statement-not-found')).toContain("doesn't exist or isn't yours");
    expect(el('filters')).toBeNull();
    txRequest().flush(null, { status: 404, statusText: 'Not Found' }); // the parallel request is ignored
  });

  it('a page past the end offers the first page instead of "not found"', async () => {
    await open('/accounts/1?page=99');
    await flush(http.expectOne('/api/accounts/1/'), ACCOUNT);
    await fail(txRequest(), 404, { detail: 'Invalid page.' });
    expect(text('statement-no-such-page')).toContain("That page doesn't exist");
    el('first-page')!.click();
    await harness.fixture.whenStable();
    expect(router.url).toBe('/accounts/1');
    await flush(txRequest(), page([tx({})]));
    expect(rows()).toHaveLength(1);
  });

  it("shows the API's message when it rejects a filter", async () => {
    await open('/accounts/1?date_from=2026-02-30'); // looks like a date, isn't one
    await flush(http.expectOne('/api/accounts/1/'), ACCOUNT);
    await fail(txRequest(), 400, { date_from: ['Enter a valid date.'] });
    expect(text('statement-bad-filter')).toBe('date_from: Enter a valid date.');
  });

  it('recovers from a server error with "Try again"', async () => {
    await open('/accounts/1');
    await flush(http.expectOne('/api/accounts/1/'), ACCOUNT);
    await fail(txRequest(), 500);
    expect(text('statement-error')).toContain("couldn't load the transactions");
    el('statement-retry')!.click();
    await harness.fixture.whenStable();
    await flush(txRequest(), page([tx({})]));
    expect(rows()).toHaveLength(1);
  });
});

describe('Statement filters are labelled for people and for tests', () => {
  it('names each control by its label alone', async () => {
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        provideRouter(
          [{ path: 'accounts/:id', component: Statement }],
          withComponentInputBinding(),
        ),
      ],
    });
    const harness = await RouterTestingHarness.create('/accounts/1');
    const root = harness.routeNativeElement!;
    for (const [label, testId] of [
      ['Type', 'filter-direction'],
      ['Category', 'filter-category'],
      ['From', 'filter-from'],
      ['To', 'filter-to'],
      ['Search', 'filter-search'],
    ]) {
      const control = root.querySelector(`[data-testid="${testId}"]`) as HTMLInputElement;
      // Exactly the label text: what a screen reader announces and what getByLabel('Type') matches.
      expect([...control.labels!].map((l) => l.textContent!.trim())).toEqual([label]);
    }
    TestBed.inject(HttpTestingController).match(() => true); // requests aren't the point here
  });
});
