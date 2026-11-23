import { NgTemplateOutlet } from '@angular/common';
import { HttpClient, HttpResponse } from '@angular/common/http';
import { Component, InjectionToken, OnInit, computed, inject, input, signal } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { forkJoin } from 'rxjs';

import { ApiProblem, toProblem } from '../../core/api-error';
import { Account, Beneficiary, Page, Transfer as TransferResult } from '../../core/models';
import { toCents } from '../../shared/money';
import { MoneyPipe } from '../../shared/money.pipe';

/** Makes the Idempotency-Key. A token, so tests can supply predictable keys. */
export const IDEMPOTENCY_KEY = new InjectionToken<() => string>('IDEMPOTENCY_KEY', {
  providedIn: 'root',
  factory: () => () => crypto.randomUUID(),
});

/** Up to 12 digits and at most 2 decimals, matching the API's DecimalField(max_digits=14, 2). */
export const AMOUNT = /^\d{1,12}(\.\d{1,2})?$/;

type Step = 'loading' | 'load-error' | 'form' | 'review' | 'sending' | 'uncertain' | 'done';

@Component({
  selector: 'lb-transfer',
  imports: [MoneyPipe, NgTemplateOutlet, ReactiveFormsModule, RouterLink],
  templateUrl: './transfer.html',
})
export class Transfer implements OnInit {
  private readonly http = inject(HttpClient);
  private readonly newKey = inject(IDEMPOTENCY_KEY);

  /** ?beneficiary=12 from the "Send money" link on the beneficiaries page. */
  readonly beneficiary = input<string>();

  readonly step = signal<Step>('loading');
  readonly accounts = signal<Account[]>([]);
  readonly beneficiaries = signal<Beneficiary[]>([]);
  readonly problem = signal<ApiProblem | null>(null);
  readonly result = signal<TransferResult | null>(null);
  readonly replayed = signal(false);
  /** Set by Review: from then on an empty amount is an error, not just an untouched field. */
  readonly submitted = signal(false);

  /**
   * One rule: every Review starts a new transfer with a new key (set only in review()), and every
   * retry of that reviewed transfer reuses it. Edit, a refusal or "Send another" all go through Review again.
   */
  private idempotencyKey: string | null = null;

  readonly form = inject(FormBuilder).nonNullable.group({
    from_account: [0, [Validators.min(1)]],
    destination: ['own' as 'own' | 'beneficiary'],
    to_account: [0],
    beneficiary: [0],
    amount: ['', [Validators.required, Validators.pattern(AMOUNT)]],
    remarks: ['', [Validators.maxLength(140)]],
  });

  private readonly value = toSignal(this.form.valueChanges, {
    initialValue: this.form.getRawValue(),
  });

  readonly activeAccounts = computed(() => this.accounts().filter((a) => a.status === 'ACTIVE'));
  readonly activeBeneficiaries = computed(() =>
    this.beneficiaries().filter((b) => b.status === 'ACTIVE'),
  );
  readonly fromAccount = computed(
    () => this.accounts().find((a) => a.id === Number(this.value().from_account)) ?? null,
  );
  readonly toChoices = computed(() =>
    this.activeAccounts().filter((a) => a.id !== this.fromAccount()?.id),
  );
  readonly payee = computed(() => {
    const v = this.value();
    if (v.destination === 'own') {
      const account = this.accounts().find((a) => a.id === Number(v.to_account));
      return account
        ? { name: account.nickname || account.type_label, iban: account.iban_display }
        : null;
    }
    const b = this.beneficiaries().find((x) => x.id === Number(v.beneficiary));
    return b ? { name: b.name, iban: b.iban_display } : null;
  });

  /** Client-side checks are for quick feedback only; the API re-checks everything. */
  readonly amountError = computed(() => {
    const amount = (this.value().amount ?? '').trim();
    // `submitted` is a signal; `control.touched` is not, so a computed() would never re-run on it.
    if (!this.submitted() && amount === '') return null;
    if (amount === '') return 'Enter an amount.';
    if (!AMOUNT.test(amount)) return 'Enter an amount like 250 or 250.50.';
    if (toCents(amount) === 0n) return 'The amount must be more than zero.';
    const from = this.fromAccount();
    if (from && toCents(amount) > toCents(from.balance)) {
      return 'That is more than the available balance.';
    }
    return null;
  });

  ngOnInit(): void {
    this.load();
  }

  load(): void {
    this.step.set('loading');
    forkJoin({
      accounts: this.http.get<Page<Account>>('/api/accounts/'),
      beneficiaries: this.http.get<Page<Beneficiary>>('/api/beneficiaries/'),
    }).subscribe({
      next: ({ accounts, beneficiaries }) => {
        this.accounts.set(accounts.results);
        this.beneficiaries.set(beneficiaries.results);
        this.prefill();
        this.step.set('form');
      },
      error: () => this.step.set('load-error'),
    });
  }

  review(): void {
    this.form.markAllAsTouched();
    this.submitted.set(true);
    this.problem.set(null);
    if (this.form.invalid || this.amountError() || !this.fromAccount() || !this.payee()) {
      return;
    }
    this.idempotencyKey = this.newKey(); // a new transfer: a new key
    this.step.set('review');
  }

  edit(): void {
    this.step.set('form');
  }

  send(): void {
    if (this.step() === 'sending' || !this.idempotencyKey) {
      return; // a double click must not send twice (and the key would protect us anyway)
    }
    this.step.set('sending');
    this.problem.set(null);
    const v = this.form.getRawValue();
    const body: Record<string, unknown> = {
      from_account: Number(v.from_account),
      amount: v.amount.trim(),
      remarks: v.remarks.trim(),
    };
    if (v.destination === 'own') {
      body['to_account'] = Number(v.to_account);
    } else {
      body['beneficiary'] = Number(v.beneficiary);
    }
    this.http
      .post<TransferResult>('/api/transfers/', body, {
        headers: { 'Idempotency-Key': this.idempotencyKey },
        observe: 'response',
      })
      .subscribe({
        next: (response: HttpResponse<TransferResult>) => {
          this.result.set(response.body);
          this.replayed.set(response.headers.get('Idempotent-Replayed') === 'true');
          this.step.set('done');
          this.refreshBalances();
        },
        error: (err: unknown) => {
          const problem = toProblem(err);
          this.problem.set(problem);
          if (problem.uncertain) {
            // No answer, or the server failed mid-way: the money may have moved. Keep the key, so
            // "Try again" either completes the transfer or replays the one that already happened.
            this.step.set('uncertain');
            return;
          }
          // A clear "no": nothing happened. Back to the form; the next Review makes a new key.
          this.step.set('form');
        },
      });
  }

  startAgain(): void {
    this.result.set(null);
    this.replayed.set(false);
    this.problem.set(null);
    this.form.patchValue({ amount: '', remarks: '' });
    this.submitted.set(false);
    this.step.set('form');
  }

  private prefill(): void {
    const first = this.activeAccounts()[0];
    const wanted = Number(this.beneficiary());
    const preselected = this.activeBeneficiaries().find((b) => b.id === wanted);
    this.form.patchValue({
      from_account: first?.id ?? 0,
      destination: preselected ? 'beneficiary' : 'own',
      beneficiary: preselected?.id ?? this.activeBeneficiaries()[0]?.id ?? 0,
      to_account: this.activeAccounts().find((a) => a.id !== first?.id)?.id ?? 0,
    });
  }

  private refreshBalances(): void {
    this.http.get<Page<Account>>('/api/accounts/').subscribe({
      next: (page) => this.accounts.set(page.results),
      error: () => undefined, // the transfer itself succeeded; stale balances are not an error
    });
  }
}
