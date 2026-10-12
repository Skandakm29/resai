/**
 * Money arrives from the API as decimal strings ("210.00"). Client-side
 * arithmetic is done in integer paise to avoid floating-point drift. These
 * totals are for display only: the backend re-validates every price.
 */
export function toPaise(amount: string | number): number {
  const s = typeof amount === "number" ? amount.toFixed(2) : amount.trim();
  const match = /^(-)?(\d+)(?:\.(\d{1,2}))?$/.exec(s);
  if (!match) throw new Error(`Invalid amount: ${amount}`);
  const [, sign, rupees, paise = "0"] = match;
  const value = Number(rupees) * 100 + Number(paise.padEnd(2, "0"));
  return sign ? -value : value;
}

export function fromPaise(paise: number): string {
  const sign = paise < 0 ? "-" : "";
  const abs = Math.abs(paise);
  return `${sign}${Math.floor(abs / 100)}.${String(abs % 100).padStart(2, "0")}`;
}

const inr = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 2, minimumFractionDigits: 0 });

/** ₹250 or ₹249.50 */
export function formatINR(amount: string | number): string {
  const paise = toPaise(amount);
  const rupees = paise / 100;
  return `₹${paise % 100 === 0 ? inr.format(Math.round(rupees)) : rupees.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}
