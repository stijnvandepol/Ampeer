/**
 * An amount, written the way a Dutch reader writes one.
 *
 * Two rules meet here and they look like they conflict. `CLAUDE.md` says the
 * application is Dutch, and "1684.85" is not Dutch: a reader here writes
 * "1.684,85", with the point and the comma the other way round. `CLAUDE.md`
 * also says amounts are Decimal on the way in and strings on the wire, because
 * JSON has floats and no decimals, so an amount that passes through a number
 * is rounded by whichever parser touched it last.
 *
 * Both hold at once because this is a transformation of the characters and
 * never of a value. Nothing below parses, rounds, or asks the runtime what the
 * number is; the digits that come in are the digits that go out, in the same
 * order, with two separators moved. `Intl.NumberFormat` and `toLocaleString`
 * are the obvious tools and both take a number, which is precisely the step
 * that may not happen. A test feeds it more digits than a double can hold, so
 * a future rewrite that reaches for one of them fails rather than rounds.
 *
 * Anything that is not a plain decimal is handed back untouched. The API sends
 * amounts in one shape today; guessing at a second one would put a number on
 * the screen that nobody computed.
 */

/** A sign, digits, and at most one fractional part. Nothing else is recognised. */
const PLAIN_DECIMAL = /^([+-]?)(\d+)(?:\.(\d+))?$/;

/** Digits into groups of three from the right: 1234567 becomes 1.234.567. */
function groupThousands(digits: string): string {
  const groups: string[] = [];
  for (let end = digits.length; end > 0; end -= 3) {
    groups.unshift(digits.slice(Math.max(0, end - 3), end));
  }
  return groups.join(".");
}

/**
 * "1684.85" becomes "1.684,85". A string this does not recognise comes back as
 * it arrived.
 */
export function dutchAmount(amount: string): string {
  const parts = PLAIN_DECIMAL.exec(amount);
  if (parts === null) return amount;
  const [, sign = "", whole = "", fraction] = parts;
  const grouped = `${sign}${groupThousands(whole)}`;
  return fraction === undefined ? grouped : `${grouped},${fraction}`;
}
