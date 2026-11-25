import { HttpErrorResponse, provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { Router, provideRouter } from '@angular/router';

import { Login, messageFor, safeReturnUrl } from './login';

const SARA = {
  id: 1,
  email: 'sara@example.com',
  full_name: 'Sara Khan',
  date_joined: '2026-11-01T00:00:00Z',
};

describe('Login page', () => {
  let fixture: ComponentFixture<Login>;
  let http: HttpTestingController;
  let navigate: ReturnType<typeof vi.spyOn>;

  const el = (testId: string) =>
    fixture.nativeElement.querySelector(`[data-testid="${testId}"]`) as HTMLElement | null;

  function type(testId: string, value: string) {
    const input = el(testId) as HTMLInputElement;
    input.value = value;
    input.dispatchEvent(new Event('input'));
  }

  async function submit() {
    el('login-submit')!.click();
    await fixture.whenStable();
  }

  beforeEach(async () => {
    localStorage.clear();
    TestBed.configureTestingModule({
      imports: [Login],
      providers: [provideRouter([]), provideHttpClient(), provideHttpClientTesting()],
    });
    http = TestBed.inject(HttpTestingController);
    navigate = vi.spyOn(TestBed.inject(Router), 'navigateByUrl').mockResolvedValue(true);
    fixture = TestBed.createComponent(Login);
    await fixture.whenStable();
  });

  afterEach(() => http.verify());

  it('shows field errors and sends nothing when the form is empty', async () => {
    await submit();
    expect(el('login-email-error')?.textContent).toContain('Enter your email.');
    expect(el('login-password-error')?.textContent).toContain('Enter your password.');
    http.expectNone('/api/auth/login/');
  });

  it('rejects a malformed email before calling the API', async () => {
    type('login-email', 'sara-at-example');
    type('login-password', 'whatever');
    await submit();
    expect(el('login-email-error')?.textContent).toContain('valid email');
    http.expectNone('/api/auth/login/');
  });

  it('logs in and goes to the page the user came from', async () => {
    fixture.componentRef.setInput('returnUrl', '/accounts?tab=savings');
    type('login-email', '  sara@example.com ');
    type('login-password', 'NovaBank-Demo-2026');
    await submit();
    const call = http.expectOne('/api/auth/login/');
    expect(call.request.body.email).toBe('sara@example.com'); // trimmed
    call.flush({ access: 'A', refresh: 'R' });
    http.expectOne('/api/auth/me/').flush(SARA);
    expect(navigate).toHaveBeenCalledWith('/accounts?tab=savings');
  });

  it('disables the button while logging in, so a double click sends one request', async () => {
    type('login-email', 'sara@example.com');
    type('login-password', 'x');
    await submit();
    expect((el('login-submit') as HTMLButtonElement).disabled).toBe(true);
    expect(el('login-submit')?.textContent).toContain('Logging in');
    await submit();
    http
      .expectOne('/api/auth/login/')
      .flush({ detail: 'nope' }, { status: 401, statusText: 'Unauthorized' });
  });

  it('shows the API error and lets the user try again', async () => {
    type('login-email', 'sara@example.com');
    type('login-password', 'wrong');
    await submit();
    http
      .expectOne('/api/auth/login/')
      .flush({ detail: 'nope' }, { status: 401, statusText: 'Unauthorized' });
    await fixture.whenStable();
    expect(el('login-error')?.textContent).toContain('Email or password is incorrect.');
    expect((el('login-submit') as HTMLButtonElement).disabled).toBe(false);
  });

  it('explains an expired session', async () => {
    fixture.componentRef.setInput('expired', '1');
    await fixture.whenStable();
    expect(el('session-expired')).not.toBeNull();
  });
});

describe('login helpers', () => {
  it.each([
    [401, 'Email or password is incorrect.'],
    [429, 'Too many attempts. Please wait a minute and try again.'],
    [0, "Can't reach NovaBank. Check your connection and try again."],
    [500, 'Something went wrong. Please try again.'],
  ])('message for HTTP %i', (status, message) => {
    expect(messageFor(new HttpErrorResponse({ status }))).toBe(message);
  });

  it.each([
    ['/accounts', '/accounts'],
    ['https://evil.example/phish', '/accounts'],
    ['//evil.example', '/accounts'],
    ['javascript:alert(1)', '/accounts'],
    [undefined, '/accounts'],
  ])('returnUrl %s goes to %s (no open redirect)', (url, expected) => {
    expect(safeReturnUrl(url)).toBe(expected);
  });
});
