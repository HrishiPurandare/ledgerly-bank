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
  {
    path: 'beneficiaries',
    canActivate: [authGuard],
    title: 'Beneficiaries · Ledgerly Bank',
    loadComponent: () => import('./pages/beneficiaries/beneficiaries').then((m) => m.Beneficiaries),
  },
  {
    path: 'transfer',
    canActivate: [authGuard],
    title: 'Send money · Ledgerly Bank',
    loadComponent: () => import('./pages/transfer/transfer').then((m) => m.Transfer),
  },
  { path: '**', redirectTo: 'accounts' },
];
