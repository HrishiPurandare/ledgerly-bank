import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';

import { AuthService, STORAGE_KEY } from './auth.service';

const SARA = {
  id: 1,
  email: 'sara@example.com',
  full_name: 'Sara Khan',
  date_joined: '2026-11-01T00:00:00Z',
};

describe('AuthService', () => {
  let http: HttpTestingController;

  function setup(): AuthService {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    http = TestBed.inject(HttpTestingController);
    return TestBed.inject(AuthService);
  }

  beforeEach(() => localStorage.clear());
  afterEach(() => http.verify()); // no unexpected or unanswered requests

  it('logs in, stores both tokens and loads the profile', () => {
    const auth = setup();
    let loaded: unknown;
    auth.login('sara@example.com', 'secret').subscribe((user) => (loaded = user));

    const login = http.expectOne('/api/auth/login/');
    expect(login.request.method).toBe('POST');
    expect(login.request.body).toEqual({ email: 'sara@example.com', password: 'secret' });
    login.flush({ access: 'A1', refresh: 'R1' });
    http.expectOne('/api/auth/me/').flush(SARA);

    expect(loaded).toEqual(SARA);
    expect(auth.isLoggedIn()).toBe(true);
    expect(auth.user()?.full_name).toBe('Sara Khan');
    expect(JSON.parse(localStorage.getItem(STORAGE_KEY)!)).toEqual({ access: 'A1', refresh: 'R1' });
  });

  it('stays logged out when the password is wrong', () => {
    const auth = setup();
    let status = 0;
    auth.login('sara@example.com', 'wrong').subscribe({ error: (e) => (status = e.status) });
    http
      .expectOne('/api/auth/login/')
      .flush({ detail: 'No active account' }, { status: 401, statusText: 'Unauthorized' });
    expect(status).toBe(401);
    expect(auth.isLoggedIn()).toBe(false);
    expect(localStorage.getItem(STORAGE_KEY)).toBeNull();
  });

  it('survives a page reload (tokens read back from storage)', () => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ access: 'A1', refresh: 'R1' }));
    const auth = setup();
    expect(auth.isLoggedIn()).toBe(true);
    expect(auth.accessToken).toBe('A1');
  });

  it.each(['not json', '{"access":"only-one"}', 'null'])(
    'treats a corrupted stored value as logged out: %s',
    (bad) => {
      localStorage.setItem(STORAGE_KEY, bad);
      expect(setup().isLoggedIn()).toBe(false);
    },
  );

  it('keeps the rotated refresh token after a refresh', () => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ access: 'A1', refresh: 'R1' }));
    const auth = setup();
    auth.refresh().subscribe();
    const call = http.expectOne('/api/auth/refresh/');
    expect(call.request.body).toEqual({ refresh: 'R1' });
    call.flush({ access: 'A2', refresh: 'R2' });
    expect(auth.accessToken).toBe('A2');
    expect(JSON.parse(localStorage.getItem(STORAGE_KEY)!).refresh).toBe('R2'); // R1 is now blacklisted
  });

  it('shares one refresh call between requests that fail together', () => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ access: 'A1', refresh: 'R1' }));
    const auth = setup();
    const tokens: string[] = [];
    auth.refresh().subscribe((t) => tokens.push(t));
    auth.refresh().subscribe((t) => tokens.push(t));
    http.expectOne('/api/auth/refresh/').flush({ access: 'A2', refresh: 'R2' }); // exactly one request
    expect(tokens).toEqual(['A2', 'A2']);
  });

  it('logout forgets everything', () => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ access: 'A1', refresh: 'R1' }));
    const auth = setup();
    auth.logout();
    expect(auth.isLoggedIn()).toBe(false);
    expect(auth.user()).toBeNull();
    expect(localStorage.getItem(STORAGE_KEY)).toBeNull();
  });
});
