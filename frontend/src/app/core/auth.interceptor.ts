import { HttpErrorResponse, HttpInterceptorFn, HttpRequest } from '@angular/common/http';
import { inject } from '@angular/core';
import { Router } from '@angular/router';
import { catchError, switchMap, throwError } from 'rxjs';

import { AuthService } from './auth.service';

/** Endpoints that must never carry a token or trigger a refresh. */
const PUBLIC = ['/api/auth/login/', '/api/auth/refresh/', '/api/auth/register/', '/api/health/'];

const withToken = (req: HttpRequest<unknown>, token: string) =>
  req.clone({ setHeaders: { Authorization: `Bearer ${token}` } });

/**
 * Adds the access token to API calls. On a 401 it refreshes once and retries; if the refresh fails too,
 * the session is over: log out and go to the login page, remembering where the user was.
 */
export const authInterceptor: HttpInterceptorFn = (req, next) => {
  const auth = inject(AuthService);
  const router = inject(Router);
  const isApi = req.url.startsWith('/api/');
  const isPublic = PUBLIC.some((path) => req.url.startsWith(path));
  const token = auth.accessToken;

  if (!isApi || isPublic || !token) {
    return next(req);
  }

  return next(withToken(req, token)).pipe(
    catchError((error: unknown) => {
      if (!(error instanceof HttpErrorResponse) || error.status !== 401) {
        return throwError(() => error);
      }
      return auth.refresh().pipe(
        switchMap((fresh) => next(withToken(req, fresh))),
        catchError((refreshError: unknown) => {
          auth.logout();
          void router.navigate(['/login'], { queryParams: { returnUrl: router.url, expired: 1 } });
          return throwError(() => refreshError);
        }),
      );
    }),
  );
};
