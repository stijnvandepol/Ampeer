import { expect, test, type Page } from "@playwright/test";
import fixture from "../tests/fixtures/advice-response.json";

/**
 * From the landing page to an advice, and back into it from the link alone.
 *
 * The API is stubbed. What is being tested is the seam this repository owns on
 * this side of the wire: that the four questions produce exactly the body
 * `EstimateInputSerializer` accepts, that the answer is reached over the path
 * the shareable link uses, and that opening that path in a browser which has
 * never seen this visitor produces the same page. The other side of the seam
 * has its own test in `tests/test_frontend_contract.py`.
 */

const TOKEN = fixture.token;

/** What the browser sends. Recorded so the assertion is about a body, not a promise. */
interface Recorded {
  url: string;
  body: unknown;
}

async function stubApi(page: Page, recorded: Recorded[]): Promise<void> {
  await page.route("**/api/advice/**", async (route) => {
    const request = route.request();
    if (request.method() === "OPTIONS") {
      // A POST with content-type: application/json is not a simple request, so
      // the browser asks first. The real API answers this from django-cors-
      // headers; here it has to be answered too or the POST never happens.
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
      recorded.push({
        url: request.url(),
        body: request.postDataJSON() as unknown,
      });
    }
    await route.fulfill({
      status: request.method() === "POST" ? 201 : 200,
      contentType: "application/json",
      headers: { "access-control-allow-origin": "*" },
      body: JSON.stringify(fixture),
    });
  });
}

test("a visitor answers four questions and lands on an advice", async ({
  page,
}) => {
  const recorded: Recorded[] = [];
  await stubApi(page, recorded);

  await page.goto("/");
  // `.first()`, because the landing page offers the way in twice: once closing
  // the first screen and once closing the page. Two is the ceiling and a test
  // in tests/app/pages.test.tsx holds it there; this walk takes the one a
  // visitor meets first.
  await page
    .getByRole("link", { name: "Bereken wat er bij u verandert" })
    .first()
    .click();
  await expect(page).toHaveURL(/\/berekenen\/$/);

  // Question one, and the refusal to skip it. The button is not disabled, so
  // there is something to read rather than something that does nothing.
  await expect(page.getByText("Vraag 1 van 4")).toBeVisible();
  await page.getByRole("button", { name: "Volgende" }).click();
  // Scoped to main: Next appends its own route announcer with role="alert" to
  // the body, and an unscoped query matches two things.
  await expect(page.locator("main").getByRole("alert")).toHaveText(
    "Beantwoord deze vraag om verder te gaan.",
  );

  await page
    .getByRole("textbox", {
      name: "Wat zijn de eerste vier cijfers van uw postcode?",
    })
    .fill("5401");
  await page.getByRole("button", { name: "Volgende" }).click();

  await expect(page.getByText("Vraag 2 van 4")).toBeVisible();
  await page
    .getByRole("textbox", {
      name: "Hoeveel wattpiek aan zonnepanelen ligt er op uw dak?",
    })
    .fill("4200");
  await page.getByRole("button", { name: "Volgende" }).click();

  await expect(page.getByText("Vraag 3 van 4")).toBeVisible();
  // The roof is one question about one roof, which is why four questions
  // collect five values. Chosen with the keyboard, because that is the path
  // that has to work and the one a mouse test would never exercise.
  await page.getByLabel("Zuidwest").check();
  await page.getByRole("button", { name: "Volgende" }).click();

  await expect(page.getByText("Vraag 4 van 4")).toBeVisible();
  await page
    .getByRole("textbox", {
      name: "Hoeveel stroom verbruikt u per jaar, zonder auto en warmtepomp?",
    })
    .fill("3400");
  await page.getByRole("button", { name: "Bereken" }).click();

  await expect(page).toHaveURL(new RegExp(`/advies/${TOKEN}/$`));
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(
    "Wat het einde van de saldering u per jaar kost",
  );
  await expect(
    page.getByText(fixture.confidence_label, { exact: true }).first(),
  ).toBeVisible();

  const posted = recorded.filter((entry) => entry.url.includes("/estimate/"));
  expect(posted).toHaveLength(1);
  expect(posted[0]?.body).toEqual({
    // A string, because the API's field is a RegexField over four digits.
    postcode4: "5401",
    peak_power_wp: 4200,
    // Southwest, on the convention where zero is south and west is positive.
    azimuth_deg: 45,
    tilt_deg: 35,
    annual_consumption_kwh: 3400,
  });
});

test("the shareable link opens the advice in a browser that has never been here", async ({
  browser,
}) => {
  const context = await browser.newContext();
  const page = await context.newPage();
  await stubApi(page, []);
  await page.goto(`/advies/${TOKEN}/`);

  await expect(
    page.getByText(fixture.confidence_label, { exact: true }).first(),
  ).toBeVisible();
  await expect(page.locator('[data-band-kind="percentile"]')).toBeVisible();
  // Every fired rule from the fixture reached the page, keyed by its own id,
  // so the advice stays traceable back to the rule that produced it.
  // Counted rather than flattened: flatMap widens the per-route element type
  // to a union and the loop below stops type checking. A fixture with no rule
  // in it would make that loop assert nothing while still reading as a check
  // that every fired rule reached the page.
  const fired = fixture.routes.reduce(
    (total, route) => total + route.rules.length,
    0,
  );
  expect(
    fired,
    "the fixture fires no rule, so the loop below would check nothing",
  ).toBeGreaterThan(0);
  for (const route of fixture.routes) {
    for (const rule of route.rules) {
      await expect(
        page.locator(`[data-rule-id="${rule.rule_id}"]`),
      ).toBeVisible();
    }
  }
  await context.close();
});

test("a token the API never issued is refused without a request", async ({
  page,
}) => {
  const seen: string[] = [];
  await page.route("**/api/advice/**", async (route) => {
    seen.push(route.request().url());
    await route.fulfill({
      status: 404,
      contentType: "application/json",
      body: "{}",
    });
  });

  await page.goto("/advies/nietEenToken/");
  await expect(page.locator("main").getByRole("alert")).toContainText(
    "Deze link hoort niet bij een berekening",
  );
  // No round trip was spent telling the visitor what the shape of the token
  // already said.
  expect(seen).toEqual([]);
});

test("the methodology page is the file from the repository, rendered", async ({
  page,
}) => {
  await page.goto("/methodologie/");
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(
    "Hoe Ampeer rekent",
  );
  // A table from the document, as a table rather than as pipes.
  await expect(page.getByRole("table").first()).toBeVisible();
  // Nothing was injected as markup: the source is Markdown and the renderer
  // builds elements, so a literal asterisk pair would mean the parser fell
  // through and a tag would mean something worse.
  const body = await page.locator("main").innerText();
  expect(body).not.toContain("**");
  expect(body).not.toContain("<strong>");
});
