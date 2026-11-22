import { HttpClient } from '@angular/common/http';
import { Component, OnInit, inject, signal } from '@angular/core';

import { Account, Page } from '../../core/models';
import { MoneyPipe } from '../../shared/money.pipe';

type State = 'loading' | 'ready' | 'error';

@Component({
  selector: 'lb-accounts',
  imports: [MoneyPipe],
  templateUrl: './accounts.html',
})
export class Accounts implements OnInit {
  private readonly http = inject(HttpClient);
  readonly state = signal<State>('loading');
  readonly accounts = signal<Account[]>([]);

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
