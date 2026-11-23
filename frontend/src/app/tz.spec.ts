/**
 * Dates on screen must be Dubai time whatever the computer's time zone, so the tests run in UTC
 * (`TZ=UTC` in package.json). On a Mac set to Dubai, a page that forgot the time zone would still look
 * right and pass; this guard makes sure the tests can't silently run in Dubai's zone.
 */
describe('test environment', () => {
  it('runs in UTC, not in the time zone the app displays', () => {
    expect(new Date('2026-11-20T23:30:00Z').getTimezoneOffset()).toBe(0);
  });
});
