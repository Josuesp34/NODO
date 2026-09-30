export function isoDay(value = new Date()) {
  const local = new Date(value.getTime() - value.getTimezoneOffset() * 60_000);
  return local.toISOString().slice(0, 10);
}

export function addDays(day: string, amount: number) {
  const value = new Date(`${day}T12:00:00`);
  value.setDate(value.getDate() + amount);
  return isoDay(value);
}

export function weekRange(day = isoDay()) {
  const value = new Date(`${day}T12:00:00`);
  const mondayOffset = (value.getDay() + 6) % 7;
  return { start: addDays(day, -mondayOffset), end: addDays(day, 6 - mondayOffset) };
}

export function monthRange(day = isoDay()) {
  const value = new Date(`${day}T12:00:00`);
  const start = new Date(value.getFullYear(), value.getMonth(), 1);
  const end = new Date(value.getFullYear(), value.getMonth() + 1, 0);
  return { start: isoDay(start), end: isoDay(end) };
}

export function formatDay(day: string, options: Intl.DateTimeFormatOptions = {}) {
  return new Intl.DateTimeFormat("es-MX", options).format(new Date(`${day.slice(0, 10)}T12:00:00`));
}
