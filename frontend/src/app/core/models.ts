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

export type Direction = 'CREDIT' | 'DEBIT';

export const CATEGORIES = {
  SALARY: 'Salary',
  TRANSFER_IN: 'Transfer in',
  TRANSFER_OUT: 'Transfer out',
  CARD: 'Card purchase',
  BILL: 'Bill payment',
  ATM: 'ATM withdrawal',
  FEE: 'Fee',
  INTEREST: 'Interest',
} as const;

export type Category = keyof typeof CATEGORIES;

export interface Transaction {
  id: number;
  reference: string;
  direction: Direction;
  category: Category;
  amount: string;
  balance_after: string;
  description: string;
  counterparty: string;
  created_at: string;
}

export interface Beneficiary {
  id: number;
  name: string;
  iban: string;
  iban_display: string;
  nickname: string;
  status: 'PENDING' | 'ACTIVE' | 'LOCKED';
  created_at: string;
  activated_at: string | null;
}

export interface Transfer {
  id: number;
  reference: string;
  uetr: string;
  kind: 'OWN' | 'INTERNAL' | 'LOCAL';
  status: 'COMPLETED' | 'PENDING';
  from_account: number;
  to_account: number | null;
  beneficiary: number | null;
  creditor_name: string;
  creditor_iban: string;
  amount: string;
  currency: string;
  remarks: string;
  created_at: string;
}
