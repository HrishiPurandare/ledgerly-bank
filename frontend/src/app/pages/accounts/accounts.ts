import { HttpClient } from '@angular/common/http';
import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';

import { Account, Page } from '../../core/models';
import { sumMoney } from '../../shared/money';
import { MoneyPipe } from '../../shared/money.pipe';

type State = 'loading' | 'ready' | 'error';

export interface Total {
  currency: string;
  amount: string;
  accounts: number;
}

/** One total per currency: adding AED to USD would be a meaningless number. */
export function totalsByCurrency(accounts: readonly Account[]): Total[] {
  const groups = new Map<string, string[]>();
  for (const account of accounts) {
    groups.set(account.currency, [...(groups.get(account.currency) ?? []), account.balance]);
  }
  return [...groups].map(([currency, balances]) => ({
    currency,
    amount: sumMoney(balances),
    accounts: balances.length,
  }));
}

/** The dashboard: every account, its balance, and the total. */
@Component({
  selector: 'lb-accounts',
  imports: [MoneyPipe, RouterLink],
  templateUrl: './accounts.html',
})
export class Accounts implements OnInit {
  private readonly http = inject(HttpClient);
  readonly state = signal<State>('loading');
  readonly accounts = signal<Account[]>([]);
  readonly totals = computed(() => totalsByCurrency(this.accounts()));

  ngOnInit(): void {
    this.load();
  }

  load(): void {
    this.state.set('loading');
    this.http.get<Page<Account>>('/api/accounts/').subscribe({
      next: (page) => {
        this.accounts.set(page.results);
        this.state.set('ready');
      },
      error: () => this.state.set('error'),
    });
  }
}
