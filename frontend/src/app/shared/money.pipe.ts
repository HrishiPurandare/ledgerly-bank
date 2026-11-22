import { Pipe, PipeTransform } from '@angular/core';

/**
 * "32079.82" + "AED" -> "AED 32,079.82". Works on the string the API sends, never through a float,
 * so the cents shown are exactly the cents stored.
 */
@Pipe({ name: 'money' })
export class MoneyPipe implements PipeTransform {
  transform(amount: string | null | undefined, currency = 'AED'): string {
    if (amount == null || !/^-?\d+(\.\d+)?$/.test(amount)) {
      return '';
    }
    const negative = amount.startsWith('-');
    const [whole, fraction = ''] = amount.replace('-', '').split('.');
    const grouped = whole.replace(/\B(?=(\d{3})+(?!\d))/g, ',');
    return `${negative ? '-' : ''}${currency} ${grouped}.${(fraction + '00').slice(0, 2)}`;
  }
}
