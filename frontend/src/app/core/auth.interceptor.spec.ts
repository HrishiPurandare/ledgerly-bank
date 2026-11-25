import { Location } from '@angular/common';
import { HttpClient, provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { Router, provideRouter } from '@angular/router';

import { authInterceptor } from './auth.interceptor';
import { AuthService, STORAGE_KEY } from './auth.service';

describe('authInterceptor', () => {
  let http: HttpTestingController;
  let client: HttpClient;
  let router: Router;

  beforeEach(() => {
    localStorage.clear();
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ access: 'A1', refresh: 'R1' }));
    TestBed.configureTestingModule({
      providers: [
        provideRouter([]),
        provideHttpClient(withInterceptors([authInterceptor])),
        provideHttpClientTesting(),
      ],
    });
    http = TestBed.inject(HttpTestingController);
    client = TestBed.inject(HttpClient);
    router = TestBed.inject(Router);
  });

  afterEach(() => http.verify());

  it('adds the access token to API calls', () => {
    client.get('/api/accounts/').subscribe();
    expect(http.expectOne('/api/accounts/').request.headers.get('Authorization')).toBe('Bearer A1');
  });

  it.each(['/api/auth/login/', '/api/auth/refresh/', '/api/health/'])(
    'never sends a token to %s',
    (url) => {
      client.post(url, {}).subscribe();
      expect(http.expectOne(url).request.headers.has('Authorization')).toBe(false);
    },
  );

  it('never sends the token to another site', () => {
    client.get('https://example.com/api/accounts/').subscribe();
    expect(
      http.expectOne('https://example.com/api/accounts/').request.headers.has('Authorization'),
    ).toBe(false);
  });

  it('on a 401, refreshes once and retries with the new token', () => {
    let body: unknown;
    client.get('/api/accounts/').subscribe((b) => (body = b));
    http.expectOne('/api/accounts/').flush(null, { status: 401, statusText: 'Unauthorized' });
    http.expectOne('/api/auth/refresh/').flush({ access: 'A2', refresh: 'R2' });
    const retry = http.expectOne('/api/accounts/');
    expect(retry.request.headers.get('Authorization')).toBe('Bearer A2');
    retry.flush({ results: [] });
    expect(body).toEqual({ results: [] });
  });

  it('when the refresh fails too, logs out and sends the user to login', () => {
    const navigate = vi.spyOn(router, 'navigate').mockResolvedValue(true);
    let failed = false;
    client.get('/api/accounts/').subscribe({ error: () => (failed = true) });
    http.expectOne('/api/accounts/').flush(null, { status: 401, statusText: 'Unauthorized' });
    http.expectOne('/api/auth/refresh/').flush(null, { status: 401, statusText: 'Unauthorized' });
    expect(failed).toBe(true);
    expect(TestBed.inject(AuthService).isLoggedIn()).toBe(false);
    expect(navigate).toHaveBeenCalledWith(
      ['/login'],
      expect.objectContaining({ queryParams: expect.objectContaining({ expired: 1 }) }),
    );
  });

  describe('remembers the right page when the session expires', () => {
    function expireAndCapture(): unknown {
      const navigate = vi.spyOn(router, 'navigate').mockResolvedValue(true);
      client.get('/api/auth/me/').subscribe({ error: () => undefined });
      http.expectOne('/api/auth/me/').flush(null, { status: 401, statusText: 'Unauthorized' });
      http.expectOne('/api/auth/refresh/').flush(null, { status: 401, statusText: 'Unauthorized' });
      return navigate.mock.calls[0][1]?.queryParams?.['returnUrl'];
    }

    it('before the first navigation has finished, uses the address the user opened', () => {
      // The bug: router.url is still "/" here, so the customer used to land on Accounts after logging in.
      vi.spyOn(TestBed.inject(Location), 'path').mockReturnValue('/beneficiaries?tab=new');
      expect(router.navigated).toBe(false);
      expect(expireAndCapture()).toBe('/beneficiaries?tab=new');
    });

    it('during a navigation, uses where the user is going', () => {
      vi.spyOn(router, 'currentNavigation').mockReturnValue({
        extractedUrl: router.parseUrl('/transfer?beneficiary=7'),
      } as ReturnType<Router['currentNavigation']>);
      expect(expireAndCapture()).toBe('/transfer?beneficiary=7');
    });

    it('after navigating, uses the current page', async () => {
      router.resetConfig([{ path: 'accounts/:id', children: [] }]);
      await router.navigateByUrl('/accounts/3?direction=DEBIT');
      expect(expireAndCapture()).toBe('/accounts/3?direction=DEBIT');
    });
  });

  it('passes other errors straight through (no refresh on 403, 404 or 500)', () => {
    let status = 0;
    client.get('/api/accounts/9/').subscribe({ error: (e) => (status = e.status) });
    http.expectOne('/api/accounts/9/').flush(null, { status: 404, statusText: 'Not Found' });
    http.expectNone('/api/auth/refresh/');
    expect(status).toBe(404);
  });
});
