import { provideHttpClient } from '@angular/common/http';
import {
  HttpTestingController,
  TestRequest,
  provideHttpClientTesting,
} from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';

import { Beneficiary } from '../../core/models';
import { Beneficiaries, UAE_IBAN, normaliseIban } from './beneficiaries';

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

describe('normaliseIban', () => {
  it('removes spaces and upper-cases, so pasted IBANs work', () => {
    expect(normaliseIban(' ae07 0331 2345 6789 0123 456 ')).toBe('AE070331234567890123456');
    expect(UAE_IBAN.test(normaliseIban('ae07 0331 2345 6789 0123 456'))).toBe(true);
  });

  it.each(['GB07033123456789012345', 'AE0703312345678901234', 'AE07033123456789012345X'])(
    'rejects %s',
    (iban) => expect(UAE_IBAN.test(iban)).toBe(false),
  );
});

describe('Beneficiaries page', () => {
  let fixture: ComponentFixture<Beneficiaries>;
  let http: HttpTestingController;

  const root = () => fixture.nativeElement as HTMLElement;
  const el = <T extends HTMLElement = HTMLElement>(testId: string, within: ParentNode = root()) =>
    within.querySelector(`[data-testid="${testId}"]`) as T | null;
  const text = (testId: string, within?: ParentNode) =>
    el(testId, within)?.textContent?.trim().replace(/\s+/g, ' ');
  const row = (id: number) => el(`beneficiary-${id}`)!;

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
  async function click(testId: string, within?: ParentNode) {
    el(testId, within)!.click();
    await stable();
  }
  async function flush(req: TestRequest, body: object | null, status = 200) {
    req.flush(body, { status, statusText: 'x' });
    await stable();
  }

  async function open(list: Beneficiary[]) {
    fixture = TestBed.createComponent(Beneficiaries);
    await stable();
    await flush(http.expectOne('/api/beneficiaries/'), {
      count: list.length,
      next: null,
      previous: null,
      results: list,
    });
  }

  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [Beneficiaries],
      providers: [provideHttpClient(), provideHttpClientTesting(), provideRouter([])],
    });
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('lists beneficiaries with a plain-language status and the right action', async () => {
    await open([
      beneficiary({}),
      beneficiary({ id: 11, name: 'Pending Person', status: 'PENDING' }),
      beneficiary({ id: 12, name: 'Locked Person', status: 'LOCKED' }),
    ]);
    expect(text('beneficiary-status', row(10))).toBe('Confirmed');
    expect(el('beneficiary-send', row(10))!.getAttribute('href')).toBe('/transfer?beneficiary=10');
    expect(text('beneficiary-status', row(11))).toBe('Waiting for code');
    expect(el('beneficiary-enter-code', row(11))).not.toBeNull();
    expect(el('beneficiary-send', row(11))).toBeNull(); // can't pay someone unconfirmed
    expect(text('beneficiary-status', row(12))).toBe('Locked');
    expect(el('beneficiary-enter-code', row(12))).toBeNull();
  });

  it('has an empty state', async () => {
    await open([]);
    expect(text('beneficiaries-empty')).toContain('No beneficiaries yet');
  });

  it('checks the IBAN format before calling the API', async () => {
    await open([]);
    await type('add-name', 'Lina Haddad');
    await type('add-iban', 'GB29 NWBK 6016 1331 9268 19');
    await click('add-submit');
    expect(text('add-iban-error')).toBe('A UAE IBAN is AE followed by 21 digits.');
    http.expectNone('/api/beneficiaries/');
  });

  it('adds a beneficiary (IBAN sent without spaces) and asks for the emailed code', async () => {
    await open([]);
    await type('add-name', '  Lina Haddad ');
    await type('add-iban', 'ae07 0331 2345 6789 0123 456');
    await click('add-submit');
    const req = http.expectOne((r) => r.method === 'POST' && r.url === '/api/beneficiaries/');
    expect(req.request.body).toEqual({
      name: 'Lina Haddad',
      iban: 'AE070331234567890123456',
      nickname: '',
    });
    await flush(req, beneficiary({ id: 20, name: 'Lina Haddad', status: 'PENDING' }), 201);
    expect(text('beneficiary-notice')).toBe(
      'We emailed you a 6-digit code to confirm Lina Haddad.',
    );
    expect(el('otp-panel')).not.toBeNull();
    expect(el<HTMLInputElement>('add-name')!.value).toBe(''); // form cleared for the next one
  });

  it("shows the API's reason when adding fails", async () => {
    await open([]);
    await type('add-name', 'Lina Haddad');
    await type('add-iban', 'AE070331234567890123456');
    await click('add-submit');
    await flush(
      http.expectOne((r) => r.method === 'POST'),
      { code: 'duplicate_beneficiary', detail: 'You already have a beneficiary with this IBAN.' },
      400,
    );
    expect(text('add-error')).toBe('You already have a beneficiary with this IBAN.');
  });

  it('confirms with the code and the row becomes Confirmed', async () => {
    await open([beneficiary({ id: 11, name: 'Pending Person', status: 'PENDING' })]);
    await click('beneficiary-enter-code', row(11));
    await type('otp-input', '12345'); // 5 digits
    await click('otp-submit');
    expect(text('otp-format-error')).toBe('The code is 6 digits.');
    http.expectNone('/api/beneficiaries/11/confirm/');

    await type('otp-input', '123456');
    await click('otp-submit');
    const req = http.expectOne('/api/beneficiaries/11/confirm/');
    expect(req.request.body).toEqual({ otp: '123456' });
    await flush(req, beneficiary({ id: 11, name: 'Pending Person', status: 'ACTIVE' }));
    expect(text('beneficiary-status', row(11))).toBe('Confirmed');
    expect(el('otp-panel')).toBeNull();
    expect(text('beneficiary-notice')).toContain('Pending Person is confirmed');
  });

  it('a wrong code says how many attempts are left and clears the box', async () => {
    await open([beneficiary({ id: 11, status: 'PENDING' })]);
    await click('beneficiary-enter-code', row(11));
    await type('otp-input', '000000');
    await click('otp-submit');
    await flush(
      http.expectOne('/api/beneficiaries/11/confirm/'),
      { code: 'otp_invalid', detail: 'That code is wrong. 2 attempt(s) left.' },
      400,
    );
    expect(text('otp-error')).toBe('That code is wrong. 2 attempt(s) left.');
    expect(el<HTMLInputElement>('otp-input')!.value).toBe('');
  });

  it('the third wrong code locks it: the row says Locked and the code box closes', async () => {
    await open([beneficiary({ id: 11, status: 'PENDING' })]);
    await click('beneficiary-enter-code', row(11));
    await type('otp-input', '000000');
    await click('otp-submit');
    await flush(
      http.expectOne('/api/beneficiaries/11/confirm/'),
      {
        code: 'otp_locked',
        detail: 'Too many wrong codes. Delete this beneficiary and add it again.',
      },
      400,
    );
    expect(text('beneficiary-status', row(11))).toBe('Locked');
    expect(el('otp-panel')).toBeNull();
    expect(text('beneficiary-notice')).toContain('Too many wrong codes');
  });

  it('removing asks first, then deletes', async () => {
    await open([beneficiary({})]);
    await click('beneficiary-delete', row(10));
    http.expectNone((r) => r.method === 'DELETE');
    await click('beneficiary-delete-no', row(10));
    expect(el('beneficiary-delete', row(10))).not.toBeNull();

    await click('beneficiary-delete', row(10));
    await click('beneficiary-delete-yes', row(10));
    await flush(
      http.expectOne((r) => r.method === 'DELETE' && r.url === '/api/beneficiaries/10/'),
      null,
      204,
    );
    expect(el('beneficiary-10')).toBeNull();
    expect(text('beneficiary-notice')).toBe('Omar Ali was removed.');
  });
});
