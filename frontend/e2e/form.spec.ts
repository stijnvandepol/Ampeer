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

/**
 * The questions of round one, in the words the page uses.
 *
 * These are the `<h2>` on each screen and, since 2026-09-02, also the
 * accessible name of the field underneath it: the controls are named by the
 * heading through `aria-labelledby` instead of carrying a second label in
 * different words. Before that, question two was headed "Hoeveel wattpiek aan
 * zonnepanelen ligt er?" over a field labelled "Vermogen van de installatie",
 * and a screen reader read both.
 *
 * `getByRole("textbox", { name })` and not `getByLabel`, because the heading
 * names two things: the field and the `<section>` around the question. A label
 * query matches both and trips Playwright's strict mode; the role says which
 * one is meant.
 */
const POSTCODE_QUESTION = "Wat zijn de eerste vier cijfers van uw postcode?";
const PEAK_POWER_QUESTION =
  "Hoeveel wattpiek aan zonnepanelen ligt er op uw dak?";
const ROOF_QUESTION = "Hoe ligt het dak?";
const CONSUMPTION_QUESTION =
  "Hoeveel stroom verbruikt u per jaar, zonder auto en warmtepomp?";

/**
 * Every computation the browser asked for, in order. One entry is one full
 * simulation.
 *
 * The counters are deliberately not in here. The page also posts to
 * `/api/advice/count/`, which is a date, a name and an integer and carries
 * nothing about the household, so counting those alongside the computations
 * made `toHaveLength(1)` fail with six on a page doing exactly the right
 * thing. The route is still stubbed, so the requests are answered rather than
 * left to fail against a server that is not there; they are just not the
 * subject of these tests.
 */
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
      if (!request.url().includes("/api/advice/count/")) {
        posted.push(request.postDataJSON() as unknown);
      }
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
  await page.getByRole("textbox", { name: POSTCODE_QUESTION }).fill("5401");
  await page.getByRole("button", { name: "Volgende" }).click();
  await page.getByRole("textbox", { name: PEAK_POWER_QUESTION }).fill("4200");
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
  await page.getByRole("textbox", { name: CONSUMPTION_QUESTION }).fill("3400");
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
  await page.getByRole("textbox", { name: CONSUMPTION_QUESTION }).fill("3400");

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
  await page.getByRole("textbox", { name: CONSUMPTION_QUESTION }).fill("3400");
  await page.getByRole("button", { name: "Bereken" }).click();

  await expect(page.locator("main").getByRole("alert")).toContainText(
    "De rekenserver gaf een antwoord dat wij niet konden lezen.",
  );
  // Still on the question, with the answers intact, rather than on an advice
  // page that has nothing to show.
  await expect(page).toHaveURL(/\/berekenen\/$/);
  await expect(
    page.getByRole("textbox", { name: CONSUMPTION_QUESTION }),
  ).toHaveValue("3400");
});

test("a refused number is told once, and told truthfully", async ({ page }) => {
  await stubApi(page, []);
  await page.goto("/berekenen/");
  await page.getByRole("textbox", { name: POSTCODE_QUESTION }).fill("99999999");
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

/**
 * What the built page says before, and without, any JavaScript.
 *
 * `javaScriptEnabled: false` and not a string search over `out/index.html`,
 * for two reasons. The browser is reading exactly the file that ships, parsed
 * and laid out, so `innerText` counts words a person would see rather than
 * words that happen to be in the file; and a `<noscript>` block, a
 * `display: none` shell or a hidden template would all pass a grep over the
 * source and fail here, which is the difference between having the content and
 * having it findable. The static export is what the webServer in
 * playwright.config.ts serves, so there is no dev server in the way.
 *
 * Measured on 2026-09-02, before the fix: `out/berekenen/index.html` carried
 * ZERO `<h1>` and 32 words of body text, all of them the header, the footer and
 * "De vragen worden klaargezet." The route sits in the sitemap at priority 0.8.
 * Googlebot has to render to see anything, and the retrieval crawlers that
 * decide what an AI answer cites (OAI-SearchBot, PerplexityBot,
 * Claude-SearchBot) largely do not run JavaScript at retrieval time, so to them
 * the one page in this product that a summary cannot answer away was blank.
 */
test.describe("the calculator page with no JavaScript", () => {
  test.use({ javaScriptEnabled: false });

  test("/berekenen/ ships one h1 and a page worth reading", async ({
    page,
  }) => {
    await page.goto("/berekenen/");

    const headings = await page.locator("h1").allTextContents();
    expect(headings, "the built page has no first-level heading").toEqual([
      "Uw situatie doorrekenen",
    ]);

    const text = await page.locator("body").innerText();
    const words = text.split(/\s+/).filter((word) => word.length > 0);
    // 180 and not a rounder number: the shipping page measures 407 words and
    // the defect measured 32, so this floor is unreachable by the header and
    // the footer alone and is not tight enough to fail on an edit to one
    // paragraph. It may rise. It may not fall to meet a page that shrank.
    expect(
      words.length,
      `only ${words.length} words render without JavaScript: ${text.slice(0, 300)}`,
    ).toBeGreaterThan(180);

    // Not a word count alone. A page can reach 180 words of navigation and
    // legal boilerplate, so these are the four things this route has to say
    // for the count to mean anything: what it computes, what it asks, that it
    // costs nothing to answer, and what nobody is being sold.
    for (const phrase of [
      "De salderingsregeling stopt op 1 januari 2027",
      "De vier vragen",
      "wattpiek aan zonnepanelen",
      "geen e-mailadres",
      "Ampeer verkoopt geen zonnepanelen",
    ]) {
      expect(text, `the built page never says "${phrase}"`).toContain(phrase);
    }
  });

  test("the h1 and the title are one name for one page", async ({ page }) => {
    // They disagreed until 2026-09-02: the tab said "Uw situatie doorrekenen"
    // and the first heading said "Uw gegevens", so somebody arriving with a
    // screen reader heard two different names for where they were.
    await page.goto("/berekenen/");
    const title = await page.title();
    const heading = (await page.locator("h1").innerText()).trim();
    // The root layout's template is "%s | Ampeer", so the page's own name is
    // what stands before the separator.
    expect(title.split(" | ")[0]).toBe(heading);
  });
});

test("nothing in the first question outgrows the column at 320 pixels", async ({
  page,
}) => {
  // 320 CSS pixels is what 1280 becomes at the 400% zoom SC 1.4.10 asks about,
  // and the width the success criterion names outright. Measured on 2026-09-02
  // before the fix, at 320 wide: the row holding the postcode field is 272
  // pixels of column and 286 pixels of content, because a text input will not
  // shrink below its own `size` and the hint beside it had nowhere to go.
  //
  // THE ASSERTION IS PER ELEMENT AND NOT ONLY ON THE DOCUMENT, and that is the
  // whole reason this test catches what `e2e/rules.spec.ts` does not. The sweep
  // there compares document.scrollWidth with clientWidth at 320, and passes:
  // the page has 24 pixels of padding on the right, the row overruns by 14, and
  // the padding swallows it. It is a real failure all the same. In a browser
  // whose scrollbar takes 15 pixels of the viewport the same page reports
  // scrollWidth 314 against clientWidth 305, which is where the audit found it,
  // and at 280 pixels this build reported 310 against 280. A check that only
  // ever looks at the document is a check whose result depends on how much
  // padding happens to be left over.
  await stubApi(page, []);
  await page.setViewportSize({ width: 320, height: 640 });
  await page.goto("/berekenen/");
  await expect(
    page.getByRole("textbox", { name: POSTCODE_QUESTION }),
  ).toBeVisible();

  const overflow = await page.evaluate(() => {
    const root = document.documentElement;
    const wider: string[] = [];
    for (const element of document.querySelectorAll("main *")) {
      // Anything that scrolls or clips on purpose is allowed to hold more than
      // it shows. That is what the overflow property is for.
      if (getComputedStyle(element).overflowX !== "visible") continue;
      if (element.scrollWidth > element.clientWidth + 1) {
        wider.push(
          `${element.tagName}.${String(element.className).slice(0, 40)} ` +
            `holds ${element.scrollWidth} in ${element.clientWidth}`,
        );
      }
    }
    return {
      scrollWidth: root.scrollWidth,
      clientWidth: root.clientWidth,
      wider,
    };
  });
  expect(
    overflow.wider,
    `at 320 pixels these hold more than they show: ${overflow.wider.join("; ")}`,
  ).toEqual([]);
  expect(
    overflow.scrollWidth,
    `the page itself scrolls sideways: ${overflow.scrollWidth} against ${overflow.clientWidth}`,
  ).toBeLessThanOrEqual(overflow.clientWidth);
});

test("every question is asked once, in one wording", async ({ page }) => {
  // Until 2026-09-02 each screen asked its question twice and in two different
  // sentences: the heading said "Is er overdag meestal iemand thuis?" and the
  // legend under it said "Is er op een doordeweekse dag meestal iemand thuis?",
  // and the qualifier that decides the answer was only in the second. A screen
  // reader read both. So: the question appears once in what a visitor sees,
  // and the control on the screen answers to that same sentence.
  await stubApi(page, []);
  await page.goto("/berekenen/");

  const questions = [
    POSTCODE_QUESTION,
    PEAK_POWER_QUESTION,
    ROOF_QUESTION,
    CONSUMPTION_QUESTION,
  ] as const;

  for (const [index, question] of questions.entries()) {
    await expect(page.getByRole("heading", { name: question })).toBeVisible();

    const text = await page.locator("body").innerText();
    const occurrences = text.split(question).length - 1;
    expect(
      occurrences,
      `"${question}" appears ${occurrences} times on the screen`,
    ).toBe(1);

    if (question === ROOF_QUESTION) {
      // The roof is one question about two things, a direction and a slope, so
      // it is the one screen whose controls are named more narrowly than the
      // heading rather than by it. Those two names are not the heading in
      // other words; they are the two halves of it.
      await page.getByLabel("Zuidwest").check();
    } else {
      await expect(
        page.getByRole("textbox", { name: question }),
        `the field on screen ${index + 1} does not answer to its own question`,
      ).toBeVisible();
      await page
        .getByRole("textbox", { name: question })
        .fill(["5401", "4200", "", "3400"][index] ?? "");
    }
    if (index < questions.length - 1) {
      await page.getByRole("button", { name: "Volgende" }).click();
    }
  }
});

test("round one counts exactly its four questions, in order, and nothing else", async ({
  page,
}) => {
  // The regression this guards: `funnel_question_${index + 1}` was cast to
  // `CountName` with `as`, which compiles for any string. A fifth round-one
  // question would have produced `funnel_question_5`, which `tsc` cannot
  // object to, which the backend 400s because it is not in
  // `DailyCounter.CLIENT_NAMES`, which `count.ts`'s own `.catch` swallows.
  // The funnel would stop recording the last question of the round with the
  // build, the type checker and the rest of this suite all green. This test
  // is the one place that would actually notice: it runs the real flow and
  // counts what the page really sent, rather than reading the source for what
  // it says it sends.
  const counted: string[] = [];
  await stubApi(page, []);
  // Playwright matches the most recently registered route first, so this has
  // to come after `stubApi`, whose `**/api/advice/**` would otherwise win
  // and answer with a 201/estimate body instead of the 204 a real count
  // response is.
  await page.route("**/api/advice/count/**", async (route: Route) => {
    const request = route.request();
    if (request.method() === "POST") {
      const body = request.postDataJSON() as { name?: unknown };
      if (typeof body.name === "string") counted.push(body.name);
    }
    await route.fulfill({
      status: 204,
      headers: { "access-control-allow-origin": "*" },
    });
  });

  await page.goto("/berekenen/");
  await page.getByRole("textbox", { name: POSTCODE_QUESTION }).fill("5401");
  await page.getByRole("button", { name: "Volgende" }).click();
  await page.getByRole("textbox", { name: PEAK_POWER_QUESTION }).fill("4200");
  await page.getByRole("button", { name: "Volgende" }).click();
  await page.getByLabel("Zuidwest").check();
  await page.getByRole("button", { name: "Volgende" }).click();
  await page.getByRole("textbox", { name: CONSUMPTION_QUESTION }).fill("3400");
  await page.getByRole("button", { name: "Bereken" }).click();
  await expect(page).toHaveURL(/\/advies\//);

  const questionCounts = counted.filter((name) =>
    name.startsWith("funnel_question_"),
  );
  expect(questionCounts).toEqual([
    "funnel_question_1",
    "funnel_question_2",
    "funnel_question_3",
    "funnel_question_4",
  ]);
});
