import { HttpErrorResponse, HttpInterceptorFn, HttpRequest } from '@angular/common/http';
import { Location } from '@angular/common';
import { inject } from '@angular/core';
import { Router } from '@angular/router';
import { catchError, switchMap, throwError } from 'rxjs';

import { AuthService } from './auth.service';

/** Endpoints that must never carry a token or trigger a refresh. */
const PUBLIC = ['/api/auth/login/', '/api/auth/refresh/', '/api/auth/register/', '/api/health/'];

/**
 * Where the user is, or is about to be. `router.url` alone is wrong during the first navigation: the
 * app's first API call (who am I?) can fail before the router has finished navigating, when
 * `router.url` is still "/", and the user would lose the page they opened.
 */
export function currentPlace(router: Router, location: Location): string {
  const navigation = router.currentNavigation();
  if (navigation) {
    return router.serializeUrl(navigation.finalUrl ?? navigation.extractedUrl);
  }
  return router.navigated ? router.url : location.path() || '/';
}

const withToken = (req: HttpRequest<unknown>, token: string) =>
  req.clone({ setHeaders: { Authorization: `Bearer ${token}` } });

/**
 * Adds the access token to API calls. On a 401 it refreshes once and retries; if the refresh fails too,
 * the session is over: log out and go to the login page, remembering where the user was.
 */
export const authInterceptor: HttpInterceptorFn = (req, next) => {
  const auth = inject(AuthService);
  const router = inject(Router);
  const location = inject(Location);
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
          void router.navigate(['/login'], {
            queryParams: { returnUrl: currentPlace(router, location), expired: 1 },
          });
          return throwError(() => refreshError);
        }),
      );
    }),
  );
};
