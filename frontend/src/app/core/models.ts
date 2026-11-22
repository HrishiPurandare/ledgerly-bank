/** Shapes returned by the Ledgerly API (see backend/openapi.yaml). Money is always a string, never a number. */

export interface Tokens {
  access: string;
  refresh: string;
}

export interface User {
  id: number;
  email: string;
  full_name: string;
  date_joined: string;
}

export interface Account {
  id: number;
  iban: string;
  iban_display: string;
  type: 'CURRENT' | 'SAVINGS' | 'PREMIER';
  type_label: string;
  nickname: string;
  currency: string;
  balance: string;
  status: 'ACTIVE' | 'FROZEN';
  opened_at: string;
}

export interface Page<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}
