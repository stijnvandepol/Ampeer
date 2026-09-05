import { describe, expect, it } from "vitest";
import { ApiError } from "@/lib/api";
import { describeAuthError } from "@/app/_account/messages";

describe("what a visitor reads when the account API said no", () => {
  it("shows a 400's field messages, which are Dutch and come from the API", () => {
    const error = new ApiError(
      400,
      { email: ["er bestaat al een account met dit e-mailadres"] },
      "",
    );
    expect(describeAuthError(error)).toBe(
      "er bestaat al een account met dit e-mailadres",
    );
  });

  it("joins two field messages rather than showing one of them", () => {
    const error = new ApiError(400, { password: ["te kort", "te simpel"] }, "");
    expect(describeAuthError(error)).toBe("te kort te simpel");
  });

  it("shows a 401 as the API wrote it, which is one answer for two causes", () => {
    // A wrong password and an unknown address answer identically on purpose.
    const error = new ApiError(401, {}, "e-mailadres of wachtwoord klopt niet");
    expect(describeAuthError(error)).toBe(
      "e-mailadres of wachtwoord klopt niet",
    );
  });

  it("shows a 403 as the API wrote it, which is the sentence saying to reload", () => {
    const error = new ApiError(
      403,
      {},
      "deze pagina stond te lang open, herlaad hem en probeer het opnieuw",
    );
    expect(describeAuthError(error)).toBe(
      "deze pagina stond te lang open, herlaad hem en probeer het opnieuw",
    );
  });

  it("shows a 429 as the API wrote it, because the API knows how long", () => {
    const error = new ApiError(429, {}, "Probeer het over een uur opnieuw.");
    expect(describeAuthError(error)).toBe("Probeer het over een uur opnieuw.");
  });

  it("writes its own sentence for a fault with no body", () => {
    expect(describeAuthError(new ApiError(500, {}, ""))).toBe(
      "De server had een storing. Probeer het straks opnieuw.",
    );
  });

  it("writes its own sentence for a success this frontend could not read", () => {
    expect(describeAuthError(new ApiError(200, {}, ""))).toBe(
      "De server gaf een antwoord dat wij niet konden lezen.",
    );
  });

  it("writes its own sentence when nothing came back at all", () => {
    expect(describeAuthError(new TypeError("Failed to fetch"))).toBe(
      "Wij konden de server niet bereiken. Controleer uw verbinding en probeer het opnieuw.",
    );
  });

  it("never prints ApiError's own English default, even sent by hand", () => {
    // Not `new ApiError(401)`: that exercises the constructor's own default
    // parameters and not this file's code. Constructed the way
    // `accounts.ts`'s `call()` does, three arguments given by hand, with a
    // detail that happens to equal that default word for word: the one input
    // the guard in `describeAuthError` exists for.
    const error = new ApiError(401, {}, "advice API returned 401");
    expect(describeAuthError(error)).not.toContain("advice API returned");
  });
});
