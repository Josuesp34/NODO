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

export function dayInZone(value: string | Date, timezone: string) {
  const parts = new Intl.DateTimeFormat("en-CA", { timeZone: timezone, year: "numeric", month: "2-digit", day: "2-digit" }).formatToParts(new Date(value));
  const part = (name: string) => parts.find((item) => item.type === name)?.value;
  return `${part("year")}-${part("month")}-${part("day")}`;
}

export function dateAtZone(day: string, timezone: string, hour = 7) {
  const desired = Date.parse(`${day}T${String(hour).padStart(2, "0")}:00:00Z`);
  let instant = desired;
  for (let pass = 0; pass < 3; pass++) {
    const parts = new Intl.DateTimeFormat("en-CA", { timeZone: timezone, year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", second: "2-digit", hourCycle: "h23" }).formatToParts(new Date(instant));
    const part = (name: string) => parts.find((item) => item.type === name)?.value;
    const shown = Date.parse(`${part("year")}-${part("month")}-${part("day")}T${part("hour")}:${part("minute")}:${part("second")}Z`);
    instant += desired - shown;
  }
  return new Date(instant).toISOString();
}
