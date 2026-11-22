import { HttpErrorResponse } from '@angular/common/http';
import { Component, inject, input, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router } from '@angular/router';

import { AuthService } from '../../core/auth.service';

@Component({
  selector: 'lb-login',
  imports: [ReactiveFormsModule],
  templateUrl: './login.html',
})
export class Login {
  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);

  /** From the URL (?returnUrl=/accounts&expired=1), bound by the router. */
  readonly returnUrl = input<string>('/accounts');
  readonly expired = input<string>();

  readonly submitting = signal(false);
  readonly error = signal<string | null>(null);

  readonly form = inject(FormBuilder).nonNullable.group({
    email: ['', [Validators.required, Validators.email]],
    password: ['', [Validators.required]],
  });

  submit(): void {
    this.form.markAllAsTouched();
    if (this.form.invalid || this.submitting()) {
      return; // also blocks a double submit while the first request is in flight
    }
    this.submitting.set(true);
    this.error.set(null);
    const { email, password } = this.form.getRawValue();
    this.auth.login(email.trim(), password).subscribe({
      next: () => void this.router.navigateByUrl(safeReturnUrl(this.returnUrl())),
      error: (err: unknown) => {
        this.error.set(messageFor(err));
        this.submitting.set(false);
      },
    });
  }
}

/** Only same-site paths: ?returnUrl=https://evil.example must not turn the login page into a redirector. */
export function safeReturnUrl(url: string | undefined): string {
  return url && url.startsWith('/') && !url.startsWith('//') ? url : '/accounts';
}

export function messageFor(err: unknown): string {
  if (err instanceof HttpErrorResponse) {
    if (err.status === 401) return 'Email or password is incorrect.';
    if (err.status === 429) return 'Too many attempts. Please wait a minute and try again.';
    if (err.status === 0) return "Can't reach Ledgerly Bank. Check your connection and try again.";
  }
  return 'Something went wrong. Please try again.';
}
