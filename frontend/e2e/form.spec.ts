import { expect, test, type Page, type Route } from "@playwright/test";
import fixture from "../tests/fixtures/advice-response.json";

/**
 * The four questions, measured against the site that ships.
 *
 * Every check here is about something a unit test in jsdom cannot settle on
 * its own: whether a radio arrives checked in a real browser, whether a real
 * click on a real disabled button reaches a handler, and whether a body that
 * is not an advice leaves the page with something to read rather than an empty
 * main element. The API is stubbed, because what is being tested is this side
 * of the wire; the other side has `tests/test_frontend_contract.py`.
 */

interface Options {
  /** What a POST to the compute endpoint answers with. */
  readonly body?: unknown;
  readonly status?: number;
  /** Milliseconds a POST spends in flight, so the busy window can be stood in. */
  readonly delayMs?: number;
}

/** Every POST the browser made, in order. One entry is one full simulation. */
async function stubApi(
  page: Page,
  posted: unknown[],
  options: Options = {},
): Promise<void> {
  const { body = fixture, status = 201, delayMs = 0 } = options;
  await page.route("**/api/advice/**", async (route: Route) => {
    const request = route.request();
    if (request.method() === "OPTIONS") {
      // A POST carrying application/json is not a simple request, so the
      // browser asks first. django-cors-headers answers this in production.
      await route.fulfill({
        status: 204,
        headers: {
          "access-control-allow-origin": "*",
          "access-control-allow-methods": "GET,POST,OPTIONS",
          "access-control-allow-headers": "content-type",
        },
      });
      return;
    }
    if (request.method() === "POST") {
      posted.push(request.postDataJSON() as unknown);
      if (delayMs > 0)
        await new Promise((resolve) => setTimeout(resolve, delayMs));
      await route.fulfill({
        status,
        contentType: "application/json",
        headers: { "access-control-allow-origin": "*" },
        body: JSON.stringify(body),
      });
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      headers: { "access-control-allow-origin": "*" },
      body: JSON.stringify(fixture),
    });
  });
}

/** The two questions before the roof, answered. */
async function reachTheRoof(page: Page): Promise<void> {
  await page.goto("/berekenen/");
  await page.getByLabel("Postcode, alleen de vier cijfers").fill("5401");
  await page.getByRole("button", { name: "Volgende" }).click();
  await page.getByLabel("Vermogen van de installatie").fill("4200");
  await page.getByRole("button", { name: "Volgende" }).click();
  await expect(page.getByText("Vraag 3 van 4")).toBeVisible();
}

test("the roof question arrives with no direction chosen for the visitor", async ({
  page,
}) => {
  await stubApi(page, []);
  await reachTheRoof(page);
  // South is the most common roof in the Netherlands and it used to arrive
  // checked. A checked radio is announced as "Zuid, aangevinkt" before
  // anybody has answered, and it is then the one direction that cannot be
  // given as an answer: a click on an already checked radio fires no change
  // event, so the only way forward was to pick a wrong roof and come back.
  const radios = await page.getByRole("radio").all();
  // Without this the loop below is a test that passes on a page with no radio
  // on it: "none of them is checked" is trivially true of none of them. The
  // compass has eight points, and any number above zero means the picker
  // rendered and the claim is about something.
  expect(
    radios.length,
    "the roof picker rendered no radio, so the check below reads nothing",
  ).toBeGreaterThan(0);
  for (const radio of radios) {
    await expect(radio).not.toBeChecked();
  }
});

test("south can be chosen, and it is the answer that gets sent", async ({
  page,
}) => {
  const posted: unknown[] = [];
  await stubApi(page, posted);
  await reachTheRoof(page);
  await page.getByLabel("Zuid", { exact: true }).check();
  await page.getByRole("button", { name: "Volgende" }).click();
  await expect(page.getByText("Vraag 4 van 4")).toBeVisible();
  await page.getByLabel("Verbruik per jaar").fill("3400");
  await page.getByRole("button", { name: "Bereken" }).click();
  await expect(page).toHaveURL(new RegExp(`/advies/${fixture.token}/$`));
  expect(posted).toHaveLength(1);
  expect(posted[0]).toMatchObject({ azimuth_deg: 0, tilt_deg: 35 });
});

test("the tilt slider on its own is not an answer about the direction", async ({
  page,
}) => {
  await stubApi(page, []);
  await reachTheRoof(page);
  // Moved with the keyboard, which is the path a mouse test never exercises
  // and the one somebody who cannot use a mouse is left with.
  await page.getByRole("slider").focus();
  await page.keyboard.press("ArrowRight");
  await expect(page.getByRole("slider")).toHaveValue("36");
  await page.getByRole("button", { name: "Volgende" }).click();
  await expect(page.locator("main").getByRole("alert")).toHaveText(
    "Beantwoord deze vraag om verder te gaan.",
  );
  await expect(page.getByText("Vraag 3 van 4")).toBeVisible();
});

test("an impatient visitor gets one computation, not four", async ({
  page,
}) => {
  // Four clicks were four POSTs and four full server-side simulations, a
  // fifth of this household's twenty an hour, and nothing in this codebase
  // retries so nothing undoes them.
  const posted: unknown[] = [];
  await stubApi(page, posted, { delayMs: 1500 });
  await reachTheRoof(page);
  await page.getByLabel("Zuidwest").check();
  await page.getByRole("button", { name: "Volgende" }).click();
  await page.getByLabel("Verbruik per jaar").fill("3400");

  const compute = page.getByRole("button", { name: "Bereken" });
  await compute.click();
  await expect(compute).toBeDisabled();
  await expect(compute).toHaveAttribute("aria-busy", "true");
  await expect(page.getByRole("button", { name: "Terug" })).toBeDisabled();
  await expect(page.locator("main").getByRole("status")).toContainText(
    "doorgerekend",
  );
  // Real clicks on a disabled button, forced past the actionability wait that
  // would otherwise time out. A disabled button that still submits is exactly
  // what this test exists to catch.
  await compute.click({ force: true });
  await compute.click({ force: true });
  await compute.click({ force: true });

  await expect(page).toHaveURL(new RegExp(`/advies/${fixture.token}/$`));
  expect(posted).toHaveLength(1);
});

test("a 200 that is not an advice says so instead of blanking the page", async ({
  page,
}) => {
  // The one failure on this site that used to produce no message at all: the
  // body parsed, the cast believed it, a renderer reached for a field that was
  // not there and React unmounted the tree. Header and footer stayed, main
  // held nothing, and nothing said why.
  const posted: unknown[] = [];
  await stubApi(page, posted, { status: 200, body: { error: "upstream" } });
  await reachTheRoof(page);
  await page.getByLabel("Zuidwest").check();
  await page.getByRole("button", { name: "Volgende" }).click();
  await page.getByLabel("Verbruik per jaar").fill("3400");
  await page.getByRole("button", { name: "Bereken" }).click();

  await expect(page.locator("main").getByRole("alert")).toContainText(
    "De rekenserver gaf een antwoord dat wij niet konden lezen.",
  );
  // Still on the question, with the answers intact, rather than on an advice
  // page that has nothing to show.
  await expect(page).toHaveURL(/\/berekenen\/$/);
  await expect(page.getByLabel("Verbruik per jaar")).toHaveValue("3400");
});

test("a refused number is told once, and told truthfully", async ({ page }) => {
  await stubApi(page, []);
  await page.goto("/berekenen/");
  await page.getByLabel("Postcode, alleen de vier cijfers").fill("99999999");
  await page.getByRole("button", { name: "Volgende" }).click();
  // One message, and it is the one that names the bound. "Beantwoord deze
  // vraag om verder te gaan" underneath it says the question was not
  // answered, which is false: it was answered with something unusable.
  const alerts = page.locator("main").getByRole("alert");
  await expect(alerts).toHaveCount(1);
  await expect(alerts).toContainText("Vul hoogstens 9999");
  await expect(
    page.getByText("Beantwoord deze vraag om verder te gaan."),
  ).toHaveCount(0);
});
