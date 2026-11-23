import { HttpClient } from '@angular/common/http';
import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { RouterLink } from '@angular/router';

import { ApiProblem, toProblem } from '../../core/api-error';
import { Beneficiary, Page } from '../../core/models';

/** "ae07 0331 2345 6789 0123 456" -> "AE070331234567890123456". */
export function normaliseIban(value: string): string {
  return value.replace(/\s+/g, '').toUpperCase();
}

/** Format only. The server also checks the mod-97 check digits; the browser check is for quick feedback. */
export const UAE_IBAN = /^AE\d{21}$/;

type ListState = 'loading' | 'ready' | 'error';

@Component({
  selector: 'lb-beneficiaries',
  imports: [ReactiveFormsModule, RouterLink],
  templateUrl: './beneficiaries.html',
})
export class Beneficiaries implements OnInit {
  private readonly http = inject(HttpClient);
  private readonly fb = inject(FormBuilder).nonNullable;

  readonly state = signal<ListState>('loading');
  readonly beneficiaries = signal<Beneficiary[]>([]);

  readonly adding = signal(false);
  readonly addError = signal<ApiProblem | null>(null);
  readonly addForm = this.fb.group({
    name: ['', [Validators.required, Validators.maxLength(140)]],
    iban: ['', [Validators.required]],
    nickname: ['', [Validators.maxLength(40)]],
  });

  /** The beneficiary whose code is being entered, if any. */
  readonly confirmingId = signal<number | null>(null);
  readonly confirming = computed(
    () => this.beneficiaries().find((b) => b.id === this.confirmingId()) ?? null,
  );
  readonly otpBusy = signal(false);
  readonly otpError = signal<string | null>(null);
  // A form group, not a lone control: (ngSubmit) only exists on a <form> with a form directive.
  // Without it the button did a native submit (a page reload) and confirm() never ran.
  readonly otpForm = this.fb.group({
    otp: ['', [Validators.required, Validators.pattern(/^\d{6}$/)]],
  });
  readonly otp = this.otpForm.controls.otp;
  readonly notice = signal<string | null>(null);

  readonly deletingId = signal<number | null>(null);

  ngOnInit(): void {
    this.load();
  }

  load(): void {
    this.state.set('loading');
    this.http.get<Page<Beneficiary>>('/api/beneficiaries/').subscribe({
      next: (page) => {
        this.beneficiaries.set(page.results);
        this.state.set('ready');
      },
      error: () => this.state.set('error'),
    });
  }

  get ibanInvalid(): boolean {
    const control = this.addForm.controls.iban;
    return control.touched && control.value !== '' && !UAE_IBAN.test(normaliseIban(control.value));
  }

  add(): void {
    this.addForm.markAllAsTouched();
    const value = this.addForm.getRawValue();
    const iban = normaliseIban(value.iban);
    if (this.addForm.invalid || !UAE_IBAN.test(iban) || this.adding()) {
      return;
    }
    this.adding.set(true);
    this.addError.set(null);
    this.notice.set(null);
    const body = { name: value.name.trim(), iban, nickname: value.nickname.trim() };
    this.http.post<Beneficiary>('/api/beneficiaries/', body).subscribe({
      next: (created) => {
        this.beneficiaries.update((list) => [...list, created]);
        this.addForm.reset();
        this.adding.set(false);
        this.startConfirm(created.id);
        this.notice.set(`We emailed you a 6-digit code to confirm ${created.name}.`);
      },
      error: (err: unknown) => {
        this.addError.set(toProblem(err));
        this.adding.set(false);
      },
    });
  }

  startConfirm(id: number): void {
    this.confirmingId.set(id);
    this.otp.reset();
    this.otpError.set(null);
  }

  cancelConfirm(): void {
    this.confirmingId.set(null);
  }

  confirm(): void {
    this.otp.markAsTouched();
    const id = this.confirmingId();
    if (id === null || this.otp.invalid || this.otpBusy()) {
      return;
    }
    this.otpBusy.set(true);
    this.otpError.set(null);
    this.http
      .post<Beneficiary>(`/api/beneficiaries/${id}/confirm/`, { otp: this.otp.value })
      .subscribe({
        next: (updated) => {
          this.replace(updated);
          this.otpBusy.set(false);
          this.confirmingId.set(null);
          this.notice.set(`${updated.name} is confirmed. You can now send money to them.`);
        },
        error: (err: unknown) => {
          const problem = toProblem(err);
          this.otpBusy.set(false);
          this.otp.reset();
          if (problem.code === 'otp_locked' || problem.code === 'otp_expired') {
            // Nothing more can be done with this code: show why on the row, and close the form.
            if (problem.code === 'otp_locked') {
              this.patchStatus(id, 'LOCKED');
            }
            this.confirmingId.set(null);
            this.notice.set(problem.message);
            return;
          }
          this.otpError.set(problem.message);
        },
      });
  }

  askDelete(id: number): void {
    this.deletingId.set(id);
  }

  delete(beneficiary: Beneficiary): void {
    this.http.delete(`/api/beneficiaries/${beneficiary.id}/`).subscribe({
      next: () => {
        this.beneficiaries.update((list) => list.filter((b) => b.id !== beneficiary.id));
        this.deletingId.set(null);
        if (this.confirmingId() === beneficiary.id) {
          this.confirmingId.set(null);
        }
        this.notice.set(`${beneficiary.name} was removed.`);
      },
      error: (err: unknown) => {
        this.deletingId.set(null);
        this.notice.set(toProblem(err).message);
      },
    });
  }

  private replace(updated: Beneficiary): void {
    this.beneficiaries.update((list) => list.map((b) => (b.id === updated.id ? updated : b)));
  }

  private patchStatus(id: number, status: Beneficiary['status']): void {
    this.beneficiaries.update((list) => list.map((b) => (b.id === id ? { ...b, status } : b)));
  }
}
