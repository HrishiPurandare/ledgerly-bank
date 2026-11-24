import { HttpErrorResponse } from '@angular/common/http';

/**
 * What went wrong, in a shape the pages can show. The API sends two kinds of 400:
 * - business rules: {"code": "daily_limit_exceeded", "detail": "..."}: match on `code`, never on wording;
 * - field validation: {"amount": ["..."], "non_field_errors": ["..."]}.
 */
export interface ApiProblem {
  /** Stable code from a business rule, or 'validation' / 'network' / 'server' / 'not_found' / 'unknown'. */
  code: string;
  message: string;
  fields: Record<string, string>;
  /** True when we can't know whether the server acted (no response, or a 5xx). */
  uncertain: boolean;
}

export function toProblem(err: unknown): ApiProblem {
  const problem = (code: string, message: string, uncertain = false): ApiProblem => ({
    code,
    message,
    fields: {},
    uncertain,
  });
  if (!(err instanceof HttpErrorResponse)) {
    return problem('unknown', 'Something went wrong. Please try again.');
  }
  if (err.status === 0) {
    return problem('network', "We couldn't reach Ledgerly Bank.", true);
  }
  // A business code is a deliberate answer, so it's certain even on a 5xx: e.g. 503 otp_not_sent means
  // "nothing was saved". A 5xx WITHOUT one (a crash, a proxy's 502) stays uncertain.
  const body: unknown = err.error;
  if (isRecord(body) && typeof body['code'] === 'string' && typeof body['detail'] === 'string') {
    return problem(body['code'], body['detail']);
  }
  if (err.status >= 500) {
    return problem('server', 'Ledgerly Bank had a problem answering.', true);
  }
  if (err.status === 404) {
    return problem('not_found', "That doesn't exist any more. Refresh and try again.");
  }
  if (err.status === 400 && isRecord(body)) {
    const fields: Record<string, string> = {};
    for (const [field, messages] of Object.entries(body)) {
      fields[field] = Array.isArray(messages) ? messages.join(' ') : String(messages);
    }
    const general = fields['non_field_errors'] ?? fields['detail'];
    return {
      code: 'validation',
      message: general ?? 'Please check the highlighted fields.',
      fields,
      uncertain: false,
    };
  }
  return problem('unknown', 'Something went wrong. Please try again.');
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}
