import { provideHttpClient } from '@angular/common/http';
import { TestBed } from '@angular/core/testing';
import {
  ActivatedRouteSnapshot,
  Router,
  RouterStateSnapshot,
  UrlTree,
  provideRouter,
} from '@angular/router';

import { authGuard, guestGuard } from './auth.guard';
import { STORAGE_KEY } from './auth.service';

function run(guard: typeof authGuard, url = '/accounts') {
  TestBed.configureTestingModule({ providers: [provideRouter([]), provideHttpClient()] });
  return TestBed.runInInjectionContext(() =>
    guard({} as ActivatedRouteSnapshot, { url } as RouterStateSnapshot),
  ) as boolean | UrlTree;
}

describe('route guards', () => {
  beforeEach(() => localStorage.clear());

  it('lets a logged-in customer into private pages', () => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ access: 'A', refresh: 'R' }));
    expect(run(authGuard)).toBe(true);
  });

  it('sends a logged-out visitor to login and remembers where they were going', () => {
    const result = run(authGuard, '/accounts?tab=savings') as UrlTree;
    expect(TestBed.inject(Router).serializeUrl(result)).toBe(
      '/login?returnUrl=%2Faccounts%3Ftab%3Dsavings',
    );
  });

  it('sends a logged-in customer away from the login page', () => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ access: 'A', refresh: 'R' }));
    const result = run(guestGuard) as UrlTree; // configure first, then inject
    expect(TestBed.inject(Router).serializeUrl(result)).toBe('/accounts');
  });

  it('shows the login page to a logged-out visitor', () => {
    expect(run(guestGuard)).toBe(true);
  });
});
