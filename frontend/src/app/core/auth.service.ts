import { HttpClient } from '@angular/common/http';
import { Injectable, computed, inject, signal } from '@angular/core';
import { Observable, finalize, map, shareReplay, switchMap, tap } from 'rxjs';

import { Tokens, User } from './models';

export const STORAGE_KEY = 'ledgerly.auth';

/**
 * Login state as signals. Tokens live in localStorage so a page reload keeps you logged in and
 * Playwright can reuse a saved login (storage state). Trade-off: any script injected into the page
 * could read them. A production bank would use httpOnly, Secure, SameSite cookies set by the server.
 */
@Injectable({ providedIn: 'root' })
export class AuthService {
  private readonly http = inject(HttpClient);
  private readonly tokens = signal<Tokens | null>(readStoredTokens());
  private refreshInFlight: Observable<string> | null = null;

  readonly user = signal<User | null>(null);
  readonly isLoggedIn = computed(() => this.tokens() !== null);

  get accessToken(): string | null {
    return this.tokens()?.access ?? null;
  }

  login(email: string, password: string): Observable<User> {
    return this.http.post<Tokens>('/api/auth/login/', { email, password }).pipe(
      tap((tokens) => this.store(tokens)),
      switchMap(() => this.loadUser()),
    );
  }

  loadUser(): Observable<User> {
    return this.http.get<User>('/api/auth/me/').pipe(tap((user) => this.user.set(user)));
  }

  /** One refresh at a time: five requests failing together share a single refresh call. */
  refresh(): Observable<string> {
    const refreshToken = this.tokens()?.refresh;
    if (!refreshToken) {
      throw new Error('Not logged in');
    }
    this.refreshInFlight ??= this.http
      .post<Tokens>('/api/auth/refresh/', { refresh: refreshToken })
      .pipe(
        tap((tokens) => this.store(tokens)), // the refresh token rotates: always keep the new one
        map((tokens) => tokens.access),
        finalize(() => (this.refreshInFlight = null)),
        shareReplay(1),
      );
    return this.refreshInFlight;
  }

  logout(): void {
    this.tokens.set(null);
    this.user.set(null);
    safeStorage()?.removeItem(STORAGE_KEY);
  }

  private store(tokens: Tokens): void {
    this.tokens.set(tokens);
    safeStorage()?.setItem(STORAGE_KEY, JSON.stringify(tokens));
  }
}

function safeStorage(): Storage | null {
  try {
    return globalThis.localStorage ?? null;
  } catch {
    return null; // private mode or blocked storage: stay logged in for this page only
  }
}

function readStoredTokens(): Tokens | null {
  try {
    const parsed = JSON.parse(safeStorage()?.getItem(STORAGE_KEY) ?? 'null');
    return parsed?.access && parsed?.refresh ? parsed : null;
  } catch {
    return null; // corrupted value: treat as logged out
  }
}
