import { Routes } from '@angular/router';

import { authGuard, guestGuard } from './core/auth.guard';

export const routes: Routes = [
  { path: '', pathMatch: 'full', redirectTo: 'accounts' },
  {
    path: 'login',
    canActivate: [guestGuard],
    title: 'Log in · Ledgerly Bank',
    loadComponent: () => import('./pages/login/login').then((m) => m.Login),
  },
  {
    path: 'accounts',
    canActivate: [authGuard],
    title: 'Accounts · Ledgerly Bank',
    loadComponent: () => import('./pages/accounts/accounts').then((m) => m.Accounts),
  },
  {
    path: 'accounts/:id',
    canActivate: [authGuard],
    title: 'Statement · Ledgerly Bank',
    loadComponent: () => import('./pages/statement/statement').then((m) => m.Statement),
  },
  { path: '**', redirectTo: 'accounts' },
];
