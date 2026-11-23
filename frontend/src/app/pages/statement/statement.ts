import { DatePipe } from '@angular/common';
import { HttpClient, HttpErrorResponse, HttpParams } from '@angular/common/http';
import { Component, computed, effect, inject, input, signal } from '@angular/core';
import { takeUntilDestroyed, toObservable } from '@angular/core/rxjs-interop';
import { FormBuilder, ReactiveFormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { catchError, map, of, switchMap } from 'rxjs';

import { Account, CATEGORIES, Category, Direction, Page, Transaction } from '../../core/models';
import { MoneyPipe } from '../../shared/money.pipe';

/** Must match REST_FRAMEWORK["PAGE_SIZE"] in backend/config/settings.py. */
export const PAGE_SIZE = 20;

export interface StatementQuery {
  page: number;
  direction: Direction | '';
  category: Category | '';
  date_from: string;
  date_to: string;
  search: string;
}

const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/;

/**
 * The URL is the source of truth for the filters (so a statement can be bookmarked, shared and reloaded),
 * but the URL is also user input: anything unexpected is dropped here instead of being sent to the API.
 */
export function parseQuery(
  raw: Partial<Record<keyof StatementQuery, string | undefined>>,
): StatementQuery {
  const page = Number(raw.page);
  return {
    page: Number.isInteger(page) && page > 0 ? page : 1,
    direction: raw.direction === 'CREDIT' || raw.direction === 'DEBIT' ? raw.direction : '',
    // Object.hasOwn, not `in`: `'toString' in CATEGORIES` is true (it's inherited from Object.prototype).
    category:
      raw.category && Object.hasOwn(CATEGORIES, raw.category) ? (raw.category as Category) : '',
    date_from: raw.date_from && ISO_DATE.test(raw.date_from) ? raw.date_from : '',
    date_to: raw.date_to && ISO_DATE.test(raw.date_to) ? raw.date_to : '',
    search: (raw.search ?? '').trim().slice(0, 100),
  };
}

/** Only the filters that are set, so the URL and the API call stay short and readable. */
export function toParams(query: StatementQuery): Record<string, string> {
  const params: Record<string, string> = {};
  for (const key of ['direction', 'category', 'date_from', 'date_to', 'search'] as const) {
    if (query[key] !== '') {
      params[key] = query[key];
    }
  }
  if (query.page > 1) {
    params['page'] = String(query.page); // last, so URLs read "filters, then where you are"
  }
  return params;
}

type AccountState =
  | { kind: 'loading' }
  | { kind: 'ready'; account: Account }
  | { kind: 'not-found' }
  | { kind: 'error' };

type PageState =
  | { kind: 'loading' }
  | { kind: 'ready'; page: Page<Transaction> }
  | { kind: 'no-such-page' }
  | { kind: 'not-found' }
  | { kind: 'bad-filter'; message: string }
  | { kind: 'error' };

@Component({
  selector: 'lb-statement',
  imports: [DatePipe, MoneyPipe, ReactiveFormsModule, RouterLink],
  templateUrl: './statement.html',
})
export class Statement {
  private readonly http = inject(HttpClient);
  private readonly router = inject(Router);

  /** Path and query parameters, bound by the router (withComponentInputBinding). */
  readonly id = input.required<string>();
  readonly page = input<string>();
  readonly direction = input<string>();
  readonly category = input<string>();
  readonly date_from = input<string>();
  readonly date_to = input<string>();
  readonly search = input<string>();

  readonly categories = Object.entries(CATEGORIES) as [Category, string][];
  readonly categoryLabel = CATEGORIES;

  readonly query = computed(() =>
    parseQuery({
      page: this.page(),
      direction: this.direction(),
      category: this.category(),
      date_from: this.date_from(),
      date_to: this.date_to(),
      search: this.search(),
    }),
  );
  readonly filtered = computed(
    () => Object.keys(toParams({ ...this.query(), page: 1 })).length > 0,
  );

  private readonly attempt = signal(0); // bumped by "Try again" to refetch the same page

  readonly accountState = signal<AccountState>({ kind: 'loading' });
  readonly pageState = signal<PageState>({ kind: 'loading' });
  readonly filterError = signal<string | null>(null);

  // Narrowed views of the two states, so the template doesn't have to re-check the kind.
  readonly account = computed(() => {
    const state = this.accountState();
    return state.kind === 'ready' ? state.account : null;
  });
  readonly results = computed(() => {
    const state = this.pageState();
    return state.kind === 'ready' ? state.page : null;
  });
  readonly badFilter = computed(() => {
    const state = this.pageState();
    return state.kind === 'bad-filter' ? state.message : null;
  });
  readonly totalPages = computed(() =>
    Math.max(1, Math.ceil((this.results()?.count ?? 0) / PAGE_SIZE)),
  );

  readonly form = inject(FormBuilder).nonNullable.group({
    direction: '',
    category: '',
    date_from: '',
    date_to: '',
    search: '',
  });

  constructor() {
    // The header only depends on the account id, so changing a filter doesn't refetch it.
    toObservable(this.id)
      .pipe(
        switchMap((id) =>
          this.http.get<Account>(`/api/accounts/${encodeURIComponent(id)}/`).pipe(
            map((account): AccountState => ({ kind: 'ready', account })),
            catchError((err: unknown) =>
              of<AccountState>({ kind: isStatus(err, 404) ? 'not-found' : 'error' }),
            ),
          ),
        ),
        takeUntilDestroyed(),
      )
      .subscribe((state) => this.accountState.set(state));

    // switchMap cancels the previous request: if filters change faster than the API answers, a slow old
    // response can never overwrite the newer one (a classic "results don't match the filters" bug).
    const request = computed(() => ({
      id: this.id(),
      query: this.query(),
      attempt: this.attempt(),
    }));
    toObservable(request)
      .pipe(
        switchMap(({ id, query }) => {
          this.pageState.set({ kind: 'loading' });
          return this.http
            .get<Page<Transaction>>(`/api/accounts/${encodeURIComponent(id)}/transactions/`, {
              params: new HttpParams({ fromObject: toParams(query) }),
            })
            .pipe(
              map((page): PageState => ({ kind: 'ready', page })),
              catchError((err: unknown) => of(pageError(err, query))),
            );
        }),
        takeUntilDestroyed(),
      )
      .subscribe((state) => this.pageState.set(state));

    // Keep the form showing what the URL says (after back/forward, a shared link, or "Clear").
    effect(() => {
      const { direction, category, date_from, date_to, search } = this.query();
      this.form.setValue({ direction, category, date_from, date_to, search });
    });
  }

  applyFilters(): void {
    const value = this.form.getRawValue();
    if (value.date_from && value.date_to && value.date_from > value.date_to) {
      this.filterError.set('"From" must be on or before "To".');
      return; // no request: the API would only say the same thing slower
    }
    this.filterError.set(null);
    // A new filter starts again at page 1; ISO dates compare correctly as strings.
    void this.router.navigate([], { queryParams: toParams(parseQuery(value)) });
  }

  clearFilters(): void {
    this.filterError.set(null);
    void this.router.navigate([], { queryParams: {} });
  }

  goToPage(page: number): void {
    void this.router.navigate([], { queryParams: toParams({ ...this.query(), page }) });
  }

  retry(): void {
    this.attempt.update((n) => n + 1);
  }
}

function isStatus(err: unknown, status: number): boolean {
  return err instanceof HttpErrorResponse && err.status === status;
}

function pageError(err: unknown, query: StatementQuery): PageState {
  if (isStatus(err, 404)) {
    // DRF answers 404 both for someone else's account and for a page past the end ("Invalid page.").
    return query.page > 1 ? { kind: 'no-such-page' } : { kind: 'not-found' };
  }
  if (isStatus(err, 400)) {
    const body = (err as HttpErrorResponse).error as Record<string, string[]> | null;
    const first = body && Object.entries(body)[0];
    return {
      kind: 'bad-filter',
      message: first ? `${first[0]}: ${first[1]}` : 'Check the filters.',
    };
  }
  return { kind: 'error' };
}
