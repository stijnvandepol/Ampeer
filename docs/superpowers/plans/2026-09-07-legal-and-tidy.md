# De juridische pagina's, het register en de restschuld: implementatieplan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Status:** delivered

> **Status op 2026-09-08: opgeleverd.** Elk bestand dat dit plan noemt staat
> in de boom. `tests/test_plans.py` controleert dat voor alle plannen in
> `docs/superpowers/plans/`, en het wordt rood op de dag dat een van hen
> niet meer klopt. Wat die test niet kan zeggen is of elke stap is
> uitgevoerd zoals hij hier staat; daar zijn de commitgeschiedenis en de
> suite voor.

**Goal:** `/privacy/` zegt weer wat vandaag waar is (toestemming, Resend, dertien logsoorten, een verwijderknop op `/account/`), er komt een pagina `/voorwaarden/` met de gebruiksvoorwaarden en de adviesdisclaimer, `docs/verwerkersregister.md` legt artikel 30 AVG vast en is aan de code gebonden, en vijf stuks opgetekende code-schuld uit de drie accountcycli worden betaald: de 401 die uit `nl.py` antwoordt, een grens op de mail-batch, drie verouderde zinnen in gesloten documenten, en branch-dekking met een eigen vloer.

**Architecture:** Geen nieuwe component. `frontend/src/app/privacy/identity.ts` blijft de ene plek die weet wie er achter Ampeer zit, en draagt er een veld bij (`privacyEmail`) en verandert een waarde (`legalBasis`); `/voorwaarden/` is een derde servercomponent naast `/privacy/` en `/over-ons/` die dezelfde `requireCompleteIdentity`-poort gebruikt en dezelfde `legal.module.css` hergebruikt. Het register is proza, niet code, en wordt aan de code gebonden op dezelfde manier als `docs/dpia.md`: een test die het document als tekst leest en beweringen erin toetst aan een module, een instelling of een AST-boom. De drie backend-restpunten zijn elk een enkele methode of een enkel argument op bestaand gedrag, geen nieuwe route.

**Tech Stack:** Django 5.2 + DRF, Python 3.12; Next 16, React 19, TypeScript 5.9 strict, Tailwind 4, Vitest, Playwright, pnpm; pytest + pytest-cov met `--cov-branch`.

**Spec:** docs/superpowers/specs/2026-09-07-legal-and-tidy-design.md

## Global Constraints

- Nederlands is wat een gebruiker leest; Engels is code, identifiers, comments, docstrings, testnamen en commitboodschappen.
- Geen em-dash (U+2014), nergens: niet in gebruikersgerichte tekst, niet in `docs/`, niet in dit plan.
- Geld is `Decimal`, energie is float. Deze cyclus raakt geen van beide.
- `frontend/src/lib/api.ts` wordt niet gewijzigd. Geen taak noemt dat bestand in zijn Files-blok.
- Elke zin die een gebruiker leest staat in `frontend/src/**` en daarmee in `frontend/tests/ui-strings.txt`, dat `e2e/language.spec.ts` byte voor byte in beide richtingen vergelijkt. Regenereren met `UPDATE_UI_STRINGS=1 pnpm e2e language`, de diff lezen, elke toegevoegde regel is een zin die deze cyclus schreef of een element-id-kop.
- De Python-dekkingsdrempel staat vandaag op `fail_under = 99.15` met `precision = 2` en statement-only. Deze cyclus zet `branch = true` aan en meet de vloer opnieuw, zonder `data/nedu-profiles-2025.csv`; de vloer mag alleen omhoog ten opzichte van wat diezelfde boom onder dezelfde conditie meet, nooit omlaag ten opzichte van bescherming, en het commentaar zegt met zoveel woorden dat dit een nieuwe maat is (hoofdstuk 7.4 van de spec, taak 8 hieronder). `MINIMUM_COVERAGE_FLOOR = 98` in `tests/test_pipeline_contract.py` blijft de ondergrens die geen enkele meting onderschrijdt.
- De vier Vitest-dekkingsdrempels (97 / 94 / 96 / 98) mogen omhoog en nooit omlaag; deze cyclus raakt ze niet doelbewust aan.
- De jobnamen `quality`, `test`, `dependencies`, `sast` en `secrets` zijn een interface met de rulesets. Geen taak hernoemt er een; `scripts/setup_rulesets.sh` blijft onaangeraakt.
- Beoordeel elke poort op de exitcode, nooit op een grep over de uitvoer van een tool.
- Elk test- en poortcommando draait op de voorgrond, nooit met een achtergrondoptie en nooit door een pipe naar `head` of `tail`.
- `backend/accounts/mailer.py` blijft de enige module onder `backend/` die `requests` importeert; `OUTBOUND_MODULES` in `tests/test_boundaries.py` blijft de vaste lijst van drie en deze cyclus voegt er geen vierde aan toe.
- Werk op `feat/legal-and-tidy`. Nooit direct op `main`.
- Voor elke nieuwe controle geldt: toon aan dat hij rood kan worden, met het transcript erbij. Elke taak zegt per controle hoe.
- Python-code in dit document staat in `text`-fences, ook complete bestanden: de `ruff-format` pre-commit hook herschrijft `python`-fences in markdown.

---

## Het werkmodel

1. **Het plan draait serieel**, taak 1 tot en met 10, in deze volgorde en nooit twee tegelijk. superpowers:subagent-driven-development is hier de uitvoeringsautoriteit en zegt met zoveel woorden "Never dispatch multiple implementation subagents in parallel (conflicts)". Vier taken schrijven in `frontend/tests/app/LegalPages.test.tsx`, twee in `frontend/tests/ui-strings.txt`, twee in `tests/test_accounts_api.py`, twee in `frontend/src/app/over-ons/page.tsx` is niet waar (dat is een taak); wat wel waar is: `docs/dpia.md`, `docs/decisions.md` en dit plan zelf zijn elk maar in een taak in schrijvende vorm aan de orde, maar `LegalPages.test.tsx` alleen al is reden genoeg om nooit te vertakken.
2. **Een taak bezit paden exclusief zolang hij draait.** Twee taken die in hetzelfde bestand schrijven kunnen nooit tegelijk. De tabel hieronder zegt per taak welke paden dat zijn.
3. **Uitvoerende agents committen, en niets daarbuiten.** Elke taak commit op `feat/legal-and-tidy`, met alleen de bestanden gestaged die zijn eigen Files-blok noemt, en met de boodschap die de taak voorschrijft. Nooit `push`, nooit `rebase`, nooit `checkout`, nooit `amend`, nooit een andere branch aanraken. En nooit `git checkout --`, `git restore`, `git stash` of `git reset`: een tijdelijke bewerking voor een rode-proef wordt met de hand teruggezet, want die commando's gooien ook het werk weg dat er nog niet in zit.
4. **Elk test- en poortcommando draait op de voorgrond.** Nooit een achtergrondoptie, nooit een pipe naar `tail` of `head`: de exitcode die je leest hoort van het gereedschap zelf te komen en niet van het laatste programma in een pijp.
5. **Poorten draaien na de taken**, niet erin, behalve de gerichte commando's die een taak zelf voorschrijft.
6. **Een taak die niet verder kan zonder een bestand aan te raken dat hij niet bezit, stopt en meldt dat.** Hij reikt niet over de lijn heen.
7. **Geen commit draagt een test die het plan zelf rood weet.** Elke taak levert een boom op waarin alles groen is wat die taak zelf heeft aangeraakt of nieuw heeft gemaakt.

### Volgorde

| Taak | Hangt af van |
|---|---|
| 1. Het plan en zijn markering | niets |
| 2. `identity.ts` en de omgedraaide identiteitstest | 1 |
| 3. De privacyverklaring herschreven | 2 |
| 4. `/voorwaarden/`, de voettekst, de sitemap, `/over-ons/` | 3 |
| 5. De twee e2e-routelijsten, axe, de taalspec | 4 |
| 6. Het verwerkingsregister | 5 |
| 7. De 401, de mail-grens, de eerste vier branch-gaten | 6 |
| 8. Branch-dekking aan, de vloer opnieuw gemeten | 7 |
| 9. DPIA, `decisions.md`, de drie verouderde zinnen | 8 |
| 10. De status omzetten en de poorten draaien | 9 |

### Bestandsbezit

| Taak | Bezit exclusief |
|---|---|
| 1 | `docs/superpowers/plans/2026-09-07-legal-and-tidy.md` |
| 2 | `frontend/src/app/privacy/identity.ts`, `frontend/tests/app/LegalPages.test.tsx` |
| 3 | `frontend/src/app/privacy/page.tsx`, `frontend/tests/app/LegalPages.test.tsx`, `frontend/tests/ui-strings.txt` |
| 4 | `frontend/src/app/voorwaarden/page.tsx`, `frontend/src/app/over-ons/page.tsx`, `frontend/src/app/_shell/SiteFooter.tsx`, `frontend/src/app/_shell/site.ts`, `frontend/tests/app/LegalPages.test.tsx`, `frontend/tests/ui-strings.txt` |
| 5 | `frontend/e2e/privacy.spec.ts`, `frontend/e2e/rules.spec.ts`, `frontend/e2e/theme.spec.ts`, `frontend/tests/app/LegalPages.test.tsx` |
| 6 | `docs/verwerkersregister.md`, `tests/test_verwerkersregister.py` |
| 7 | `backend/accounts/views.py`, `backend/accounts/nl.py`, `backend/accounts/management/commands/send_outbound_mail.py`, `infra/README.md`, `tests/test_accounts_api.py`, `tests/test_accounts_mail.py`, `tests/test_assets.py`, `tests/test_accounts_lockout_callables.py`, `tests/test_accounts_models.py` |
| 8 | `pyproject.toml`, `tests/test_pipeline_contract.py` |
| 9 | `docs/dpia.md`, `docs/decisions.md`, `docs/superpowers/specs/2026-09-04-accounts-auth-design.md`, `docs/superpowers/specs/2026-09-05-accounts-frontend-design.md`, `docs/superpowers/plans/2026-09-04-accounts-auth.md`, `tests/test_dpia.py` |
| 10 | `docs/superpowers/plans/2026-09-07-legal-and-tidy.md` |

Gedeelde bestanden en de keten die ze veilig houdt: `frontend/tests/app/LegalPages.test.tsx` door 2, 3, 4 en 5, in die volgorde; `frontend/tests/ui-strings.txt` door 3 en 4; `docs/superpowers/plans/2026-09-07-legal-and-tidy.md` door 1 en 10, met acht taken ertussen die het niet aanraken. Elk paar staat in die volgorde achter elkaar in de serie, en geen twee ervan lopen ooit tegelijk.

---

## Tien dingen die dit plan vastlegt en die de spec impliciet liet

**`ui-strings.txt` regenereert twee keer, niet een.** Taak 3 herschrijft de privacypagina en taak 4 voegt een hele nieuwe pagina toe; allebei veranderen wat `e2e/language.spec.ts` uit `frontend/src/**` haalt. Regenereren aan het eind van de cyclus in een keer zou de tussenliggende diff onleesbaar maken (twee pagina's door elkaar) en zou taak 4 laten draaien op een taalspec die taak 3 al rood had kunnen laten staan. Beide taken draaien `UPDATE_UI_STRINGS=1 pnpm e2e language`, lezen de diff, en committen het bestand in hun eigen commit.

**De derde pagina in de identiteitstest komt in taak 4, niet in taak 3.** `frontend/tests/app/LegalPages.test.tsx:141-157` ("puts both pages behind that guard") loopt vandaag over `["privacy", "over-ons"]`. Spec 4.1 zegt dat die lus over drie pagina's gaat zodra `/voorwaarden/` bestaat, en `/voorwaarden/` bestaat pas na taak 4. Taak 3 laat die lus met rust; taak 4 breidt hem uit naar `["privacy", "over-ons", "voorwaarden"]` en doet hetzelfde met de lus in "the two default exports" (`:463-480`), die `[PrivacyPage, OverOnsPage]` afloopt en met taak 4 `VoorwaardenPage` erbij krijgt.

**`legalBasis: "toestemming"` breekt in taak 2 niets, omdat de bestaande tests hun eigen `FILLED` gebruiken.** `LegalPages.test.tsx` rendert de privacypagina altijd met de lokale constanten `FILLED` (`legalBasis: "overeenkomst"`) en `FILLED_CONSENT` (`legalBasis: "toestemming"`), nooit met de echte `IDENTITY`. De asserties over welke grondslagalinea rendert blijven dus in taak 2 groen; wat verandert is alleen dat de geëxporteerde site straks, bij een echte `next build`, de toestemmingstak toont. Taak 3 is waar dat zichtbaar wordt, in de rood-bewijzen van de nieuwe asserties.

**De twee reciproke links tussen `/privacy/` en `/voorwaarden/` splitsen over twee taken.** Spec 3.2 (sectie "Over deze verklaring") zet de link van privacy naar voorwaarden; die tekst bestaat pas als onderdeel van de herschreven pagina en hoort dus in taak 3, ook al bestaat `/voorwaarden/` als route dan nog niet. Een `<Link href="/voorwaarden/">` in JSX faalt niet op een route die nog niet bestaat: Next controleert dat pas bij `next build`, en de eerste keer dat deze boom bouwt is aan het eind van taak 5. Taak 4 zet de omgekeerde link (`/over-ons/` en `/voorwaarden/` allebei genoemd in de slotsectie van `/over-ons/`) en de vijfde voettekstlink. Beide losse aanrakingen worden in taak 4's rode-proef nogmaals gelezen om te bevestigen dat de link uit taak 3 nu ergens naartoe wijst.

**De axe-dekking voor `/voorwaarden/` in beide paletten is twee bewerkingen in een taak, niet een test.** Spec 8.3 vraagt "axe op `/voorwaarden/` in beide paletten". `frontend/e2e/rules.spec.ts` draait `every route passes axe` over `ALL_PATHS` in het standaardpalet (licht); `frontend/e2e/theme.spec.ts` draait een eigen, kortere `ALL_PATHS` in het donkere palet via `every route passes axe in the dark palette too`. Taak 5 voegt `/voorwaarden/` aan beide lijsten toe; samen geven de twee bestaande tests de twee paletten, zonder een nieuwe test te schrijven.

**`frontend/e2e/privacy.spec.ts` en `frontend/e2e/rules.spec.ts` groeien naar dezelfde negen routes, `theme.spec.ts` niet.** Spec 4.3 zegt met zoveel woorden "beide lijsten worden compleet" over de twee lijsten die het net heeft ingeleid, `PAGES` (privacy.spec.ts) en `ALL_PATHS` (rules.spec.ts). `theme.spec.ts` draagt een derde, ongenoemde lijst die vandaag al een andere vorm heeft (`/`, `/berekenen/`, de advieslink, `/methodologie/`, `/account/`, geen `/einde-saldering/`); die krijgt alleen `/voorwaarden/` erbij en blijft voor de rest zoals hij is, want de spec vraagt daar niet om een volledige sweep, alleen om de ene nieuwe pagina in het donkere palet.

**De bindingstest die de twee lijsten aan de routeboom legt, komt in taak 5, niet in taak 4.** Spec 4.3's laatste alinea beschrijft een Vitest-test die `PAGES` en `ALL_PATHS` uit de twee e2e-bestanden leest en naast `SITEMAP_ROUTES` en de mappen onder `src/app/` legt. Die test kan pas iets zinnigs beweren zodra de twee lijsten compleet zijn, en dat gebeurt in taak 5. Hij komt daarom in taak 5's deel van `LegalPages.test.tsx`, na de twee e2e-bestanden in dezelfde taak zijn bijgewerkt.

**Taak 10 doet de stack-smoke niet als eigen taak.** De spec vraagt in deze cyclus geen wijziging aan de live laag: geen nieuwe omgevingsvariabele, geen nieuwe compose-dienst, geen nieuwe timer. `scripts/gates.sh` draait `tests/test_stack_smoke.py` al als onderdeel van zijn `test`-groep tegen de compose-teststack, en dat is precies de proef dat deze branch de 28 bestaande live-checks niet heeft gebroken. Een aparte taak die dezelfde stack nog een keer optuigt zou een tweede plek zijn waar `infra/compose.test.yml` bezit wordt genomen zonder dat er iets aan verandert. Taak 10 start en stopt de stack daarom zelf, als onderdeel van de volledige `scripts/gates.sh`-run, met `infra/compose.test.yml` in het commando zoals rule 7 van het herstelplan voorschrijft, en niet als een aparte, vroegere taak.

**Twee commits in taak 10, en de reden is `ruff-format`.** CLAUDE.md's eigen instructie ("de `ruff-format` pre-commit hook herschrijft `python`-fences in markdown en heeft in de vorige cyclus een `urlpatterns`-fragment tot een tuple gevouwen") is niet een waarschuwing over dit plan, het is een waarschuwing over de negen Python-bestanden die taken 6 tot en met 9 aanraken. `scripts/gates.sh`'s `pre-commit`-groep is de eerste keer in deze cyclus dat die hook over de hele boom draait; treft hij iets, dan is dat een werkelijke wijziging die een eigen commit nodig heeft voordat de marker mag kantelen, want de marker belooft dat de boom is wat het plan zegt en niet wat de hook er nog van moest maken. Taak 10 committeert dus, in volgorde: eerst wat `pre-commit` corrigeert (als er iets is; is er niets, dan zegt de commitboodschap van de tweede commit dat met zoveel woorden en blijft het bij een commit), dan pas de statusregel.

**`tests/test_pipeline_contract.py` staat in taak 8's Files-blok voor het geval, niet omdat er zeker iets verandert.** `MINIMUM_COVERAGE_FLOOR = 98` staat er al en de nieuwe vloer (verwacht rond 98,5) blijft daarboven, dus de kans is groot dat dit bestand ongewijzigd blijft. Het staat toch in het Files-blok, want spec 7.4 vraagt uitdrukkelijk om het te lezen en de reden te noteren als er wel iets moet veranderen, en een taak die een bestand zou moeten aanraken zonder het in zijn eigen blok te hebben staan, reikt over de lijn heen (regel 6 van het werkmodel).

**Geen enkele taak schrijft in `.github/workflows/`.** De vijf jobnamen blijven de interface die ze zijn; deze cyclus voegt geen gate, geen job en geen stap toe aan CI. `scripts/setup_rulesets.sh` blijft onaangeraakt, met zoveel woorden, in geen enkel taak's Files-blok.

---

### Taak 1: Het plan en zijn markering

**Hangt af van:** niets.

**Files:**
- Create: `docs/superpowers/plans/2026-09-07-legal-and-tidy.md`

**Interfaces:**
- Consumes: `docs/superpowers/specs/2026-09-07-legal-and-tidy-design.md`, `docs/superpowers/plans/2026-09-06-accounts-recovery.md` (het model voor de vorm).
- Produces: dit document, en de marker `**Status:** in progress` op regel 5 die `tests/test_plans.py` leest.

- [ ] **Step 1: Schrijf het plan**

Dit document zelf: het skeletblok, de Global Constraints, het werkmodel, de Volgorde- en
Bestandsbezit-tabellen, de tien impliciete beslissingen, tien taken met Files, Interfaces en
genummerde stappen, en de zelfevaluatie aan het eind. Elke taak citeert het hoofdstuk van de
spec waar hij uit komt, zodat een lezer die het niet eens is met een keuze terugvindt waar hij
vandaan komt.

- [ ] **Step 2: Rode proef, dat de marker echt iets doet**

`tests/test_plans.py` behandelt een plan met `**Status:** in progress` uitzonderlijk soepel
(`test_every_file_a_finished_plan_names_exists` slaat het over) en een plan zonder die exacte
tekst streng (elk genoemd bestand moet al bestaan). Dit plan noemt op dit moment negen
bestanden die nog niet in de boom staan (`frontend/src/app/voorwaarden/page.tsx`,
`docs/verwerkersregister.md`, `tests/test_verwerkersregister.py`, en zes die pas in latere
taken ontstaan), dus de marker moet aan staan of de strenge test valt.

Zet de regel tijdelijk een letter anders, `**Status:** in progres` (een s te weinig), en draai:

```text
uv run --no-sync pytest tests/test_plans.py -q
```

Verwacht: rood, `test_every_file_a_finished_plan_names_exists[2026-09-07-legal-and-tidy.md]`
faalt en somt de negen ontbrekende bestanden op, want een marker met een tikfout is voor
`_is_in_progress` geen marker. Zet de regel terug naar exact `**Status:** in progress` en draai
de test opnieuw: groen, want de strenge test slaat dit plan nu over en de losse test die een
"in progress"-plan dwingt om echt iets te missen (`test_a_plan_marked_in_progress_is_actually_unfinished`)
vindt negen missende bestanden en niet nul.

- [ ] **Step 3: Commit**

```text
git add docs/superpowers/plans/2026-09-07-legal-and-tidy.md
git commit -m "$(cat <<'EOF'
docs(plans): the legal and tidy plan, marked unfinished

Ten tasks, serial, from docs/superpowers/specs/2026-09-07-legal-and-tidy-design.md:
the privacy statement rewritten for phase 1, a new /voorwaarden/ page, the
article 30 register as a bound document, and five pieces of recorded debt
from the three account cycles paid off.

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
EOF
)"
```

---

### Taak 2: `identity.ts` en de omgedraaide identiteitstest

**Hangt af van:** taak 1.

**Files:**
- Modify: `frontend/src/app/privacy/identity.ts`, `frontend/tests/app/LegalPages.test.tsx`

**Interfaces:**
- Consumes: niets nieuws; blijft binnen `identity.ts`.
- Produces: `privacyEmail` op `Identity` en `CompleteIdentity`; `legalBasis: "toestemming"` in `IDENTITY`; `IDENTITY_FIELDS` met vijf velden in plaats van vier (`legalName`, `kvkNumber`, `postalAddress`, `contactEmail`, `privacyEmail`, `legalBasis`, zes in totaal; `vatNumber` blijft optioneel en dus buiten de lijst); `IDENTITY_FIELD_HELP["privacyEmail"]`.

Spec 2.1 en 2.2.

- [ ] **Step 1: `privacyEmail` op de twee interfaces en in de geschreven lijst**

In `frontend/src/app/privacy/identity.ts`, op `Identity`, direct na `contactEmail`:

```text
export interface Identity {
  readonly legalName: string;
  readonly kvkNumber: string;
  readonly vatNumber?: string;
  readonly postalAddress: string;
  readonly contactEmail: string;
  /**
   * The address a request about personal data goes to, distinct from
   * `contactEmail`. The AVG gives a month to answer an access or deletion
   * request, and a request arriving in a general inbox is one that can be
   * read as ordinary mail and left. `contactEmail` still names the comment
   * above it; this field is the cheap fix that comment already pointed at,
   * supplied rather than deferred.
   */
  readonly privacyEmail: string;
  readonly legalBasis: LegalBasis | typeof NOG_IN_TE_VULLEN | string;
}
```

Dezelfde regel op `CompleteIdentity`, tussen `contactEmail` en `legalBasis`:

```text
export interface CompleteIdentity {
  readonly legalName: string;
  readonly kvkNumber: string;
  readonly vatNumber?: string;
  readonly postalAddress: string;
  readonly contactEmail: string;
  readonly privacyEmail: string;
  readonly legalBasis: LegalBasis;
}
```

`IDENTITY_FIELDS`, met het nieuwe veld na `contactEmail` en voor `legalBasis`, in de volgorde
waarin een bouwfout ze moet noemen:

```text
export const IDENTITY_FIELDS = [
  "legalName",
  "kvkNumber",
  "postalAddress",
  "contactEmail",
  "privacyEmail",
  "legalBasis",
] as const satisfies readonly (keyof Identity)[];
```

`IDENTITY_FIELD_HELP`, een regel erbij:

```text
export const IDENTITY_FIELD_HELP: Readonly<Record<IdentityField, string>> = {
  legalName:
    "the registered name of the controller, including its legal form, or the full name of the natural person",
  kvkNumber: "the Chamber of Commerce number, eight digits",
  postalAddress: "a postal address a letter can reach",
  contactEmail: "the address that answers questions about personal data",
  privacyEmail: "the address a request about personal data goes to, answered within a month",
  legalBasis: `either "${LEGAL_BASES[0]}" or "${LEGAL_BASES[1]}"; see chapter 10 point 2 of docs/dpia.md`,
};
```

Omdat `IDENTITY_FIELDS` `satisfies readonly (keyof Identity)[]` draagt, is een veld dat wel op
het type staat en niet in de lijst een typefout die `pnpm typecheck` vangt voordat een test dat
hoeft te doen; dat is het bestaande mechanisme en dit stap voegt er geen nieuw aan toe.

- [ ] **Step 2: `contactEmail`'s commentaar wordt korter, `privacyEmail` krijgt zijn eigen regel, en `legalBasis` wordt `"toestemming"`**

`contactEmail`'s commentaar in `IDENTITY` verliest de laatste twee zinnen (die nu bij
`privacyEmail` horen) en houdt alleen wat nog waar is:

```text
  // The general address, for everything other than a request about
  // personal data; those go to privacyEmail below.
  contactEmail: "info@ampeer.nl",
  privacyEmail: "privacy@ampeer.nl",
```

`legalBasis`'s commentaar wordt vervangen, niet aangevuld (spec 2.1: "een pagina die twee
redeneringen naast elkaar draagt zegt niets"):

```text
  // Chosen on 2026-09-07, which retires the 2026-09-02 choice for a
  // contract. The DPIA picks consent in chapter 10, item 2, on the article
  // 7(4) GDPR argument: RegisterSerializer accepts a registration with or
  // without METER_LINK, so the service does not depend on a consent it does
  // not itself need. The code already executes that, with two separate,
  // unticked consents that carry their own timestamp and text version. What
  // it costs: consent must be as easy to withdraw as to give, and for the
  // account itself withdrawing equals deleting, which the button on
  // /account/ does.
  legalBasis: "toestemming",
```

- [ ] **Step 3: `isUnfilled` doet mee zonder wijziging, `missingIdentityFields` ook**

`isUnfilled` leest `identity[field]` generiek en `field === "legalBasis"` is de enige
uitzondering; `privacyEmail` valt in de algemene tak (`value === NOG_IN_TE_VULLEN ||
value.trim().length === 0`) precies zoals `contactEmail` dat al doet. Geen wijziging nodig aan
`isUnfilled`, `missingIdentityFields` of `requireCompleteIdentity`: dat is het punt van spec
2.1's "de bewaking verandert niet van vorm".

- [ ] **Step 4: De omgedraaide identiteitstest**

Vervang in `frontend/tests/app/LegalPages.test.tsx` de test "ships with every fact still
unfilled, and says which" (`:69-77`):

```text
  it("ships with both addresses filled and consent as the legal basis", () => {
    // Sinds 2026-09-03 stond deze lijst leeg en liep de oude versie van deze
    // test nul keer door zijn eigen lus, wat de rode-proefregel verbiedt: een
    // controle die groen leest omdat hij niets leest. Omgedraaid naar wat
    // vandaag waar is.
    expect(missingIdentityFields(IDENTITY)).toEqual([]);
    expect(IDENTITY.contactEmail).toBe("info@ampeer.nl");
    expect(IDENTITY.privacyEmail).toBe("privacy@ampeer.nl");
    expect(IDENTITY.legalBasis).toBe("toestemming");
  });
```

Voeg twee `FILLED`-achtige constanten toe die het nieuwe veld dragen, zodat de rest van de
suite (die `FILLED` en `FILLED_CONSENT` al gebruikt) blijft werken zonder dat elke aanroep
verandert:

```text
const FILLED: CompleteIdentity = {
  legalName: "TESTNAAM",
  kvkNumber: "TESTKVK",
  vatNumber: "TESTBTW",
  postalAddress: "TESTADRES",
  contactEmail: "test@example.invalid",
  privacyEmail: "privacy@example.invalid",
  legalBasis: "overeenkomst",
};

const FILLED_CONSENT: CompleteIdentity = {
  ...FILLED,
  legalBasis: "toestemming",
};
```

Dit is de tweede sentinel die spec 3.4 noemt (`privacy@example.invalid`), hier al neergezet
zodat taak 3's nieuwe asserties er meteen op kunnen bouwen zonder deze suite opnieuw te
bezoeken. `FILLED`, `FILLED_CONSENT`, alle overige tests in deze suite blijven ongewijzigd
werken: `missingIdentityFields(FILLED)` was al leeg en blijft leeg met het extra veld erin.

- [ ] **Step 5: Rood bewijs**

Zet `privacyEmail: "privacy@ampeer.nl"` in `IDENTITY` tijdelijk op
`privacyEmail: NOG_IN_TE_VULLEN` en draai:

```text
cd frontend && pnpm vitest run tests/app/LegalPages.test.tsx
```

Verwacht: rood, de nieuwe test "ships with both addresses filled and consent as the legal
basis" faalt op `expect(missingIdentityFields(IDENTITY)).toEqual([])`, want `privacyEmail`
staat nu in de lijst van wat nog ontbreekt. Zet de waarde terug naar `"privacy@ampeer.nl"` en
draai opnieuw: groen.

- [ ] **Step 6: `pnpm typecheck` en de rest van de suite**

```text
cd frontend && pnpm typecheck && pnpm vitest run tests/app/LegalPages.test.tsx
```

Verwacht: beide groen. `pnpm typecheck` bevestigt dat geen andere plek in de boom `Identity`
of `CompleteIdentity` object-literal zonder `privacyEmail` construeert; als dat wel zo was,
zou dat hier rood worden en niet pas bij `next build`.

- [ ] **Step 7: Commit**

```text
git add frontend/src/app/privacy/identity.ts frontend/tests/app/LegalPages.test.tsx
git commit -m "$(cat <<'EOF'
feat(privacy): add privacyEmail and switch the legal basis to consent

Chapter 10 point 2 of the DPIA settles on consent, argued from article 7(4):
registration already accepts METER_LINK refused, so the service does not
depend on a consent it does not need. The 2026-09-02 choice for a contract
is reversed. privacyEmail gives an access or deletion request its own
address instead of the general inbox contactEmail already warned about.

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
EOF
)"
```

---

### Taak 3: De privacyverklaring herschreven

**Hangt af van:** taak 2.

**Files:**
- Modify: `frontend/src/app/privacy/page.tsx`, `frontend/tests/app/LegalPages.test.tsx`, `frontend/tests/ui-strings.txt`

**Interfaces:**
- Consumes: `IDENTITY.privacyEmail`, `IDENTITY.legalBasis` uit taak 2; `AMPEER_ADVICE_TTL_DAYS` uit `backend/ampeer/settings/base.py` (ongewijzigd, 90); `AuditEvent`'s dertien constanten in `backend/advice/models.py` (ongewijzigd, geteld en al zo genoemd in `tests/test_dpia.py`).
- Produces: geen nieuwe export; `PrivacyStatement` en `LegalBasisParagraphs` renderen nieuwe secties en een nieuwe grondslagtak.

Spec hoofdstuk 3.

- [ ] **Step 1: Herschrijf `frontend/src/app/privacy/page.tsx`**

Acht bestaande secties veranderen van inhoud en er komen twee nieuwe secties bij (`account` en
`resend`), in de volgorde die spec 3.1 vastlegt. De hele `PrivacyStatement`-functie en
`LegalBasisParagraphs`:

```tsx
export function PrivacyStatement({
  identity,
}: {
  readonly identity: CompleteIdentity;
}) {
  return (
    <div className={styles.page}>
      <PageJsonLd path={PATH} name={TITLE} description={DESCRIPTION} />

      <header className={styles.hero}>
        <p className={styles.eyebrow}>Privacy</p>
        <h1 className={styles.title}>Privacyverklaring</h1>
        <p className={styles.lead}>
          Ampeer stelt u een paar vragen en rekent daar een antwoord mee uit.
          Deze pagina zegt wat wij daarvan bewaren, hoe lang, en wie het verder
          kan zien. Wij hebben het zo kort mogelijk opgeschreven.
        </p>
      </header>

      <section className={styles.section} aria-labelledby="verantwoordelijk">
        <h2 id="verantwoordelijk" className={styles.heading}>
          Wie verantwoordelijk is
        </h2>
        <p className={styles.body}>
          {identity.legalName} is verantwoordelijk voor de gegevens die via
          ampeer.nl worden verwerkt. Heeft u een vraag over uw gegevens, mail
          dan naar {identity.privacyEmail}. Wij antwoorden binnen een maand.
        </p>
        <dl className={styles.register}>
          <dt className={styles.term}>Naam</dt>
          <dd className={styles.detail}>{identity.legalName}</dd>
          <dt className={styles.term}>KvK-nummer</dt>
          <dd className={styles.detail}>{identity.kvkNumber}</dd>
          <dt className={styles.term}>Postadres</dt>
          <dd className={styles.detail}>{identity.postalAddress}</dd>
          <dt className={styles.term}>E-mail</dt>
          <dd className={styles.detail}>
            <a href={`mailto:${identity.contactEmail}`}>
              {identity.contactEmail}
            </a>
          </dd>
          <dt className={styles.term}>E-mail over uw gegevens</dt>
          <dd className={styles.detail}>
            <a href={`mailto:${identity.privacyEmail}`}>
              {identity.privacyEmail}
            </a>
          </dd>
        </dl>
      </section>

      <section className={styles.section} aria-labelledby="watwijvragen">
        <h2 id="watwijvragen" className={styles.heading}>
          Wat wij van u vragen
        </h2>
        <p className={styles.body}>
          U vult alles zelf in. Wij halen niets op bij uw meter, uw netbeheerder
          of uw leverancier. Er gebeurt niets voordat u op berekenen klikt.
        </p>
        <p className={styles.body}>De eerste ronde stelt vier vragen:</p>
        <ul className={styles.points}>
          <li className={styles.point}>
            De eerste vier cijfers van uw postcode.
          </li>
          <li className={styles.point}>Uw jaarverbruik in kilowattuur.</li>
          <li className={styles.point}>
            Het vermogen van uw zonnepanelen, in wattpiek.
          </li>
          <li className={styles.point}>
            Hoe uw dak ligt: de richting en de hellingshoek.
          </li>
        </ul>
        <p className={styles.body}>
          Wilt u een scherper antwoord, dan volgen er vijf vragen bij. Of u
          overdag thuis bent bijvoorbeeld, of u een elektrische auto heeft, en
          of u een warmtepomp heeft. Die vragen zijn vrijwillig.
        </p>
        <p className={styles.body}>
          Voor het advies vragen wij nog steeds geen van die dingen, en de
          rekenmachine werkt zonder account. Wie een account aanmaakt, geeft
          een e-mailadres en kiest een wachtwoord, en meer niet. Geen naam,
          geen telefoonnummer, geen huisnummer.
        </p>
      </section>

      <section className={styles.section} aria-labelledby="postcode">
        <h2 id="postcode" className={styles.heading}>
          Van uw postcode bewaren wij vier cijfers
        </h2>
        <p className={styles.body}>
          Het invoerveld accepteert alleen vier cijfers. Typt u er zes, dan
          wordt de invoer geweigerd. Hij wordt niet stilletjes afgekapt.
        </p>
        <p className={styles.body}>
          Dat verschil is belangrijk. Afkappen zou betekenen dat uw volledige
          postcode ons wel had bereikt. Nu bereikt hij ons nooit.
        </p>
        <p className={styles.body}>
          Voor de zonopbrengst gebruiken wij zelfs maar de eerste twee cijfers.
          Daarmee zoeken wij de instraling van uw regio op.
        </p>
      </section>

      <section className={styles.section} aria-labelledby="waarom">
        <h2 id="waarom" className={styles.heading}>
          Waarom wij dit vragen
        </h2>
        <p className={styles.body}>
          Elk antwoord is nodig voor de berekening. Uw postcodegebied kiest de
          zonnereeks. Uw jaarverbruik schaalt uw verbruiksprofiel. Wattpiek en
          dakligging bepalen uw opbrengst.
        </p>
        <p className={styles.body}>
          Er is geen vraag die wij alleen voor de statistiek stellen. Er is ook
          geen tweede doel: geen advertenties, geen profiel en geen doorverkoop.
        </p>
      </section>

      <section className={styles.section} aria-labelledby="grondslag">
        <h2 id="grondslag" className={styles.heading}>
          Op welke grondslag wij dit doen
        </h2>
        <LegalBasisParagraphs identity={identity} />
      </section>

      <section className={styles.section} aria-labelledby="account">
        <h2 id="account" className={styles.heading}>
          Uw account
        </h2>
        <p className={styles.body}>
          Maakt u een account, dan bewaren wij meer dan voor een berekening
          alleen.
        </p>
        <p className={styles.body}>
          Uw wachtwoord maken wij met Argon2id onleesbaar voordat het de
          database bereikt. Wij kunnen het niet lezen en niet teruggeven.
        </p>
        <p className={styles.body}>
          Wij bewaren het tijdstip van uw laatste keer inloggen. Wij bewaren
          ook het tijdstip waarop u uw adres bevestigde. Dat veld blijft leeg
          zolang u dat niet deed.
        </p>
        <p className={styles.body}>
          Een bevestigd adres is straks nodig om een slimme meter te koppelen.
          Vandaag is het nergens voor nodig.
        </p>
        <p className={styles.body}>
          Op uw accountpagina zet u twee toestemmingen apart aan of uit. Wij
          zetten er nooit een vooraf aan. Elke keuze bewaren wij met het
          tijdstip en de tekstversie die u toen las. Intrekken kost u een klik.
        </p>
        <p className={styles.body}>
          Herstel en bevestiging gaan per mail, met een link die eenmalig
          werkt. Een herstellink werkt een uur, een bevestigingslink zeven
          dagen.
        </p>
      </section>

      <section className={styles.section} aria-labelledby="bewaren">
        <h2 id="bewaren" className={styles.heading}>
          Wat wij bewaren, en hoe lang
        </h2>
        <p className={styles.body}>
          Wij bewaren uw antwoorden en uw uitkomst achter de link die u krijgt.
          Zo kunt u er later nog bij. Die link is de enige sleutel. Wie hem
          heeft, ziet uw uitkomst. Deel hem dus alleen met mensen die hem mogen
          zien.
        </p>
        <p className={styles.body}>
          Na 90 dagen verwijderen wij uw advies. Dat gebeurt automatisch, elke
          dag opnieuw. Daarna werkt de link niet meer. U krijgt dan dezelfde
          melding als bij een link die nooit heeft bestaan.
        </p>
        <p className={styles.body}>
          Uw account bewaren wij tot u het verwijdert. Een herstel- of
          bevestigingslink bewaren wij als onomkeerbare afdruk tot hij
          verloopt. Een mail die wij nog moeten versturen staat in een
          wachtrij zonder uw adres erin. Die rij verdwijnt zodra de mail weg
          is, of zeven dagen nadat het versturen definitief mislukte.
        </p>
        <p className={styles.body}>
          Wij maken elke dag een reservekopie van onze database. Die kopieën
          bewaren wij zeven dagen. Een verwijderd advies of een verwijderd
          account kan daardoor nog hoogstens acht dagen in zo&apos;n bestand
          staan. Die bestanden staan op dezelfde server en zijn alleen voor
          ons leesbaar.
        </p>
      </section>

      <section className={styles.section} aria-labelledby="logboek">
        <h2 id="logboek" className={styles.heading}>
          Wat er in ons logboek komt
        </h2>
        <p className={styles.body}>
          Bij elk advies schrijven wij één regel in een logboek. Daarin staan
          het tijdstip, uw postcodegebied, hoe zeker het antwoord was, en de
          versienummers van onze rekenmodule.
        </p>
        <p className={styles.body}>
          Sinds er accounts zijn schrijven wij ook een regel bij dertien
          soorten handelingen: aanmaken, inloggen, mislukt inloggen, uitloggen,
          een toestemming geven of intrekken, exporteren, verwijderen, een
          herstel aanvragen of afronden, een adres bevestigen en een mail
          versturen.
        </p>
        <p className={styles.body}>
          In die regels staat een nummer dat naar uw account wijst, en nooit
          uw e-mailadres. Na verwijdering wijst dat nummer nergens meer naar.
          Bij een herstelverzoek voor een adres dat wij niet kennen schrijven
          wij niets.
        </p>
        <p className={styles.body}>
          Uw link zetten wij er niet in. Wij zetten er een onomkeerbare afdruk
          van in. Uit die afdruk is uw link niet terug te rekenen. Zo blijft een
          oude logregel geen werkende sleutel naar een advies dat allang weg is.
        </p>
        <p className={styles.body}>
          Dit logboek ruimen wij niet op. Zodra uw advies weg is, wijst die
          afdruk nergens meer naar. Wat overblijft is een postcodegebied, een
          tijdstip en twee versienummers.
        </p>
      </section>

      <section className={styles.section} aria-labelledby="ipadres">
        <h2 id="ipadres" className={styles.heading}>
          Uw IP-adres bewaren wij niet
        </h2>
        <p className={styles.body}>
          Wij tellen hoeveel verzoeken er per bezoeker binnenkomen. Dat is nodig
          om misbruik te stoppen. Uw IP-adres wordt daarvoor eerst onomkeerbaar
          versleuteld.
        </p>
        <p className={styles.body}>
          Er is geen tabel bij ons met een IP-adres erin. Er is ook geen
          logregel die er een bewaart.
        </p>
        <p className={styles.body}>
          Een hulpprogramma tegen inbrekers brengt drie tabellen mee die een
          IP-adres zouden kunnen bevatten. Die blijven leeg, want wij tellen
          dat in het geheugen. Gemeten: na zes mislukte inlogpogingen staan
          alle drie op nul rijen.
        </p>
      </section>

      <section className={styles.section} aria-labelledby="cloudflare">
        <h2 id="cloudflare" className={styles.heading}>
          Cloudflare ziet uw verzoek langskomen
        </h2>
        <p className={styles.body}>
          Het verkeer naar deze site loopt via Cloudflare Inc. Dat bedrijf is
          onze verwerker. Cloudflare beveiligt de verbinding en beëindigt die
          aan de rand van hun netwerk.
        </p>
        <p className={styles.body}>
          Daardoor ziet Cloudflare bij elk verzoek twee dingen. Uw IP-adres, en
          het webadres van de pagina die u opvraagt. In dat webadres staat ook
          uw link naar uw advies.
        </p>
        <p className={styles.body}>
          Uit onze eigen logboeken houden wij die link weg. Bij Cloudflare
          kunnen wij dat niet. Er is een oplossing voor, namelijk de link niet
          meer in het webadres zetten. Die is nog niet gebouwd.
        </p>
      </section>

      <section className={styles.section} aria-labelledby="resend">
        <h2 id="resend" className={styles.heading}>
          Resend verstuurt onze mail
        </h2>
        <p className={styles.body}>
          Wij sturen alleen mail om een wachtwoord te herstellen of een adres
          te bevestigen. Nergens anders voor. Die mail vertrekt via Resend,
          Inc., onze tweede verwerker.
        </p>
        <p className={styles.body}>
          Resend ziet uw adres, dat er een account bij hoort of dat er herstel
          is gevraagd, en de tekst van de mail met de link erin.
        </p>
        <p className={styles.body}>
          Resend bewaart een eigen verzendlog met adres, onderwerp en tekst.
          Dat log staat in de Verenigde Staten, ook al versturen wij vanuit de
          Europese regio.
        </p>
        <p className={styles.body}>
          Die doorgifte rust op de standaardbepalingen van de Europese
          Commissie in Resends verwerkersovereenkomst, en op Resends
          certificering onder het Data Privacy Framework.
        </p>
        <p className={styles.body}>
          Wat Resend niet ziet: waarom u herstel vroeg, uw wachtwoord, uw
          toestemmingen of uw advies.
        </p>
      </section>

      <section className={styles.section} aria-labelledby="derden">
        <h2 id="derden" className={styles.heading}>
          Verder gaat er niets naar buiten
        </h2>
        <ul className={styles.points}>
          <li className={styles.point}>
            Het openen van een pagina van Ampeer doet geen enkel verzoek aan een
            ander bedrijf.
          </li>
          <li className={styles.point}>
            Wij gebruiken geen Google Analytics en geen ander meetprogramma.
          </li>
          <li className={styles.point}>
            Wij plaatsen geen advertenties en verkopen geen advertentieruimte.
          </li>
          <li className={styles.point}>
            Wij volgen uw gedrag niet en bouwen geen profiel van u op.
          </li>
          <li className={styles.point}>
            Onze lettertypen staan op onze eigen server. Er is geen extern
            lettertype en geen extern script.
          </li>
        </ul>
        <p className={styles.body}>
          Dit is geen belofte maar een test. Bij elke wijziging leest een test
          alle verzoeken mee die een pagina doet. Gaat er één naar een ander
          bedrijf, dan gaat die test rood en komt de wijziging er niet in.
        </p>
      </section>

      <section className={styles.section} aria-labelledby="cookies">
        <h2 id="cookies" className={styles.heading}>
          Drie cookies, en geen enkele om u te volgen
        </h2>
        <p className={styles.body}>
          Zonder account zetten wij geen cookie.
        </p>
        <p className={styles.body}>
          Logt u in, dan zetten wij twee cookies die uw sessie zijn. Een werkt
          een kwartier, de andere veertien dagen. Een derde cookie beschermt
          de pagina tegen verzoeken die niet van u komen.
        </p>
        <p className={styles.body}>
          Alle drie zijn nodig om ingelogd te zijn, en voor niets anders. Ze
          volgen u niet, ze meten niets en ze gaan naar geen ander bedrijf.
        </p>
        <p className={styles.body}>
          Daarom is er geen cookiemelding. De wet vraagt geen toestemming voor
          cookies die alleen doen wat u zelf vroeg.
        </p>
        <p className={styles.body}>
          Uw antwoorden op de vragen staan in de opslag van uw eigen browser.
          Die verlaten uw browser niet. Uw keuze voor licht of donker ook niet.
        </p>
      </section>

      <section className={styles.section} aria-labelledby="rechten">
        <h2 id="rechten" className={styles.heading}>
          Wat u met uw gegevens kunt
        </h2>

        <h3 className={styles.subheading}>Inzien</h3>
        <p className={styles.body}>
          Uw link is uw inzage. Open hem en u ziet wat wij hebben uitgerekend.
          Daar hoeft u niets voor aan te vragen. Wij bewaren daarnaast de
          antwoorden die u invulde. Die staan niet op het scherm. Wilt u ze
          zien, vraag ze dan op via het adres bovenaan.
        </p>
        <p className={styles.body}>
          Heeft u een account, dan staat op uw accountpagina uw adres en de
          stand van beide toestemmingen. De knop exporteren geeft alles wat
          wij over uw account hebben, als bestand dat een computer kan lezen.
        </p>

        <h3 className={styles.subheading}>Meenemen</h3>
        <p className={styles.body}>
          Het antwoord achter uw link is een bestand dat een computer kan lezen.
          U kunt het dus meenemen naar iemand anders.
        </p>
        <p className={styles.body}>
          Dat exportbestand van uw account is de overdracht voor uw account.
        </p>

        <h3 className={styles.subheading}>Corrigeren</h3>
        <p className={styles.body}>
          Heeft u iets verkeerd ingevuld, dan kunt u dat niet wijzigen. Reken
          opnieuw en u krijgt een nieuw advies met een nieuwe link. Het oude
          blijft staan tot het na 90 dagen verdwijnt.
        </p>
        <p className={styles.body}>
          Een toestemming kunt u altijd omzetten. Wij bewaren de oude keuze
          naast de nieuwe.
        </p>

        <h3 className={styles.subheading}>Laten verwijderen</h3>
        <p className={styles.body}>
          Op uw accountpagina staat een knop die uw account verwijdert. Hij
          vraagt uw wachtwoord opnieuw.
        </p>
        <p className={styles.body}>
          Weg zijn dan uw adres, uw wachtwoord, beide toestemmingen en alle
          adviezen die aan uw account hingen. Wat blijft is een logregel met
          een nummer dat nergens meer naar wijst.
        </p>
        <p className={styles.body}>
          Bent u uw wachtwoord kwijt, dan herstelt u het eerst via de mail.
          Daarna verwijdert u uw account.
        </p>

        <h3 className={styles.subheading}>Bezwaar maken</h3>
        <p className={styles.body}>
          Bent u het niet eens met wat wij doen, laat het ons weten. U kunt uw
          bezwaar sturen naar {identity.privacyEmail}.
        </p>
      </section>

      <section className={styles.section} aria-labelledby="klagen">
        <h2 id="klagen" className={styles.heading}>
          Klagen kan bij de toezichthouder
        </h2>
        <p className={styles.body}>
          Komt u er met ons niet uit, dan kunt u een klacht indienen bij de
          Nederlandse toezichthouder. Dat kan altijd en het kost u niets.
        </p>
        <p className={styles.body}>
          <a href="https://www.autoriteitpersoonsgegevens.nl/">
            Autoriteit Persoonsgegevens
          </a>
        </p>
      </section>

      <section className={styles.section} aria-labelledby="verklaring">
        <h2 id="verklaring" className={styles.heading}>
          Over deze verklaring
        </h2>
        <p className={styles.body}>
          Deze verklaring hoort bij de dienst met accounts, herstel en
          bevestiging, zoals die vandaag draait. Komt er een koppeling met uw
          meter, dan verandert er veel en schrijven wij deze pagina opnieuw
          voordat dat gebeurt.
        </p>
        <p className={styles.body}>
          Wie wij zijn en waarvan Ampeer betaald wordt, staat op{" "}
          <Link href="/over-ons/">de pagina over ons</Link>. Hoe wij rekenen,
          staat in <Link href="/methodologie/">onze methodologie</Link>. De
          regels voor het gebruik staan in{" "}
          <Link href="/voorwaarden/">onze gebruiksvoorwaarden</Link>.
        </p>
        <p className={styles.note}>Laatst gewijzigd op 7 september 2026.</p>
      </section>
    </div>
  );
}

/**
 * The lawful basis, and the paragraph that follows from it.
 *
 * Two texts rather than one that covers both, because the two bases give the
 * visitor different rights. Consent can be withdrawn and performance of a
 * contract cannot; writing a sentence that is vague enough to fit either would
 * be hiding the one thing this section is for.
 */
function LegalBasisParagraphs({
  identity,
}: {
  readonly identity: CompleteIdentity;
}) {
  if (identity.legalBasis === "toestemming") {
    return (
      <>
        <p className={styles.body}>
          Wij verwerken uw antwoorden met uw toestemming. Die geeft u door de
          vragen in te vullen en op berekenen te klikken.
        </p>
        <p className={styles.body}>
          U mag uw toestemming intrekken wanneer u wilt. Stuur ons dan een
          bericht met uw link erbij. Wat wij tot dat moment deden blijft
          rechtmatig.
        </p>
        <p className={styles.body}>
          Wij verwerken ook uw account met uw toestemming. Die geeft u door
          het account aan te maken.
        </p>
        <p className={styles.body}>
          U trekt die toestemming in door uw account te verwijderen. Dat kan
          altijd, zonder ons iets te vragen. Voor doorgeven aan een
          installateur en voor het koppelen van uw meter vragen wij apart
          toestemming.
        </p>
      </>
    );
  }
  return (
    <>
      <p className={styles.body}>
        Wij verwerken uw antwoorden om de berekening te maken waar u zelf om
        vraagt. Dat is de uitvoering van de overeenkomst die u met ons aangaat
        door de vragen te beantwoorden.
      </p>
      <p className={styles.body}>
        Zonder die antwoorden kunnen wij geen antwoord geven. Er is geen andere
        grondslag en er is geen tweede doel.
      </p>
    </>
  );
}
```

De `metadata`, de import-regels en `PrivacyPage` onderaan het bestand blijven ongewijzigd.

- [ ] **Step 2: De nieuwe en gewijzigde asserties**

In `frontend/tests/app/LegalPages.test.tsx`, binnen `describe("the privacy statement", ...)`:

Verander "says everything article 13 has to say" niet: alle elf woorden in die lijst staan nog
op de pagina. Voeg een nieuwe test toe direct erna:

```ts
  it("says what changed since fase 1 shipped accounts", () => {
    const text = privacyText();
    for (const claim of [
      "Resend",
      "Argon2id",
      "dertien",
      "7 september 2026",
    ]) {
      expect(text, `the statement never says "${claim}"`).toContain(claim);
    }
    // The two session cookies, named by function rather than by name: the
    // page never spells out ampeer_access or ampeer_refresh, it says what
    // they are for.
    expect(text).toContain("kwartier");
    expect(text).toContain("veertien dagen");
    expect(text).toContain("geen cookiemelding");
    // The privacy address from FILLED, and not only the general one.
    expect(text).toContain("privacy@example.invalid");
    // The old claims are gone.
    expect(text).not.toContain("Er is geen account");
    expect(text).not.toContain("Wij plaatsen geen cookies");
    expect(text).not.toContain("Er is nog geen knop waarmee u uw advies zelf weggooit");
  });

  it("says a household can delete its own account, not only wait for a link to expire", () => {
    expect(privacyText()).toContain("verwijdert");
  });
```

Verander de bestaande grondslagtest ("renders one legal basis paragraph") niet inhoudelijk,
maar voeg een tweede test toe die de twee nieuwe alinea's op de toestemmingstak dekt:

```ts
  it("adds two paragraphs about the account to the consent branch only", () => {
    const consent = privacyText(FILLED_CONSENT);
    const contract = privacyText(FILLED);
    expect(consent).toContain("Wij verwerken ook uw account met uw toestemming");
    expect(contract).not.toContain("Wij verwerken ook uw account met uw toestemming");
  });
```

- [ ] **Step 3: Rode bewijzen, een voor een**

Voor elke nieuwe assertie: haal de zin tijdelijk uit de pagina, draai de suite, zet terug.

```bash
cd frontend && pnpm vitest run tests/app/LegalPages.test.tsx
```

Concreet, drie stuks als voorbeeld van de methode (de rest volgt hetzelfde patroon):

1. Verwijder tijdelijk de zin "Die mail vertrekt via Resend, Inc., onze tweede verwerker." uit
   de nieuwe `resend`-sectie. Verwacht: rood op `expect(text).toContain("Resend")` in de nieuwe
   test hierboven, want de pagina noemt het woord verder nergens. Zet de zin terug.
2. Verwijder tijdelijk de zin "Wij verwerken ook uw account met uw toestemming." uit de
   toestemmingstak van `LegalBasisParagraphs`. Verwacht: rood op de nieuwe test "adds two
   paragraphs about the account to the consent branch only". Zet de zin terug.
3. Verander tijdelijk "Laatst gewijzigd op 7 september 2026." terug naar "Laatst gewijzigd op
   2 september 2026." Verwacht: rood op `expect(text).toContain("7 september 2026")`. Zet de
   datum terug.

- [ ] **Step 4: `ui-strings.txt` regenereren**

```bash
cd frontend && UPDATE_UI_STRINGS=1 pnpm e2e language
```

Verwacht: het commando faalt met zoveel woorden (dat is hoe deze regeneratie altijd eindigt),
en `frontend/tests/ui-strings.txt` is herschreven. Lees de diff. Elke toegevoegde regel is een
zin uit de herschreven pagina of een van de nieuwe `id`-koppen (`account`, `resend`); elke
verwijderde regel is een zin die net vervangen is ("Wij plaatsen geen cookies", "Er is geen
account en er is geen wachtwoord", "Er is nog geen knop waarmee u uw advies zelf weggooit", de
oude datumregel). Draai daarna de echte spec op de voorgrond:

```bash
cd frontend && pnpm e2e language
```

Verwacht: groen, `A` (de allowlist-vergelijking) en `B` (de sentinel-sweep) allebei.

- [ ] **Step 5: De volledige Vitest-suite en de typecheck**

```bash
cd frontend && pnpm typecheck && pnpm vitest run tests/app/LegalPages.test.tsx
```

Verwacht: beide groen.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/app/privacy/page.tsx frontend/tests/app/LegalPages.test.tsx frontend/tests/ui-strings.txt
git commit -m "$(cat <<'EOF'
docs(privacy): rewrite the statement for phase 1

The page said "there is no account" and "we place no cookies" after PR #49
shipped both. It now describes the account section by section: Argon2id,
the two session cookies and why no cookie notice follows from that, the
thirteen audit kinds, Resend as the second processor, and the delete button
that replaced "there is no button yet". Dated 7 September 2026.

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
EOF
)"
```

---

### Taak 4: `/voorwaarden/`, de voettekst, de sitemap, `/over-ons/`

**Hangt af van:** taak 3.

**Files:**
- Create: `frontend/src/app/voorwaarden/page.tsx`
- Modify: `frontend/src/app/over-ons/page.tsx`, `frontend/src/app/_shell/SiteFooter.tsx`, `frontend/src/app/_shell/site.ts`, `frontend/tests/app/LegalPages.test.tsx`, `frontend/tests/ui-strings.txt`

**Interfaces:**
- Consumes: `IDENTITY`, `requireCompleteIdentity`, `CompleteIdentity` uit `../privacy/identity`; `legal.module.css` uit `../privacy/`; `PageJsonLd`.
- Produces: route `/voorwaarden/`, default export `VoorwaardenPage`, named export `TermsPage` en `metadata`; `SITEMAP_ROUTES` met een zevende regel; de vijfde voettekstlink.

Spec hoofdstuk 4.1 tot en met 4.3.

- [ ] **Step 1: `frontend/src/app/voorwaarden/page.tsx`**

```tsx
import type { Metadata } from "next";
import Link from "next/link";

import { PageJsonLd } from "../_shell/JsonLd";
import {
  IDENTITY,
  requireCompleteIdentity,
  type CompleteIdentity,
} from "../privacy/identity";
import styles from "../privacy/legal.module.css";

const PATH = "/voorwaarden/";
const TITLE = "Gebruiksvoorwaarden";
const DESCRIPTION =
  "Wat de rekenmachine van Ampeer is en niet is, waarvan Ampeer betaald wordt, en waar u zelf voor instaat als u de dienst gebruikt.";

export const metadata: Metadata = {
  title: TITLE,
  description: DESCRIPTION,
  alternates: { canonical: PATH },
  // Deliberately absent: `openGraph`, the reason privacy/page.tsx gives.
};

/**
 * The terms of use, and the disclaimer the advice needs.
 *
 * WHY ITS OWN PAGE. A disclaimer that sat on a methodology page would be one
 * nobody finds at the moment it matters. The owner chose a dedicated route
 * over a section, on 2026-09-07.
 *
 * WHY THE ORDER. `/over-ons/`'s principle: what a reader has to know before
 * trusting the advice comes first, then who Ampeer is, then the rules. A page
 * that opened with the rules would have buried the disclaimer.
 *
 * WHAT IT MAY NOT CARRY. No countdown, no scarcity, no social proof and no
 * call to action, the five rules `frontend/CLAUDE.md` states for the whole
 * site. A third kind of call to action on top of the two the spec allows
 * would turn a disclaimer into a funnel.
 */
export function TermsPage({
  identity,
}: {
  readonly identity: CompleteIdentity;
}) {
  return (
    <div className={styles.page}>
      <PageJsonLd path={PATH} name={TITLE} description={DESCRIPTION} />

      <header className={styles.hero}>
        <p className={styles.eyebrow}>Voorwaarden</p>
        <h1 className={styles.title}>Gebruiksvoorwaarden</h1>
        <p className={styles.lead}>
          Deze pagina zegt wat Ampeer is en niet is, waarvan het betaald
          wordt, en waar u zelf voor instaat.
        </p>
      </header>

      <section className={styles.section} aria-labelledby="wataimpeer">
        <h2 id="wataimpeer" className={styles.heading}>
          Wat Ampeer is
        </h2>
        <p className={styles.body}>
          Ampeer is een rekenmachine. Met uw antwoorden en met
          standaardprofielen rekent hij uit wat het einde van de
          salderingsregeling u kost.
        </p>
        <p className={styles.body}>
          Hij zegt ook welke van drie routes voor u het beste past. Elk bedrag
          komt met een bandbreedte, want wij rekenen de hele berekening
          243 keer door, met aannames die wij niet zeker weten.
        </p>
        <p className={styles.body}>
          Het woord bij uw advies (indicatief, goed of precies) zegt hoeveel u
          ons verteld heeft. Precies kunt u vandaag niet krijgen.
        </p>
        <p className={styles.body}>
          Dit is de samenvatting. De volledige methode staat in{" "}
          <Link href="/methodologie/">onze methodologie</Link>.
        </p>
      </section>

      <section className={styles.section} aria-labelledby="watietniet">
        <h2 id="watietniet" className={styles.heading}>
          Wat Ampeer niet is
        </h2>
        <p className={styles.body}>
          Ampeer geeft geen financieel advies, geen installatieadvies en geen
          advies over een energiecontract.
        </p>
        <p className={styles.body}>
          Onze getallen zijn een schatting op een verzonnen jaar met
          standaardprofielen. Uw dak, uw apparaten en het tarief van 2027
          kennen wij niet.
        </p>
        <p className={styles.body}>
          U beslist zelf. Een beslissing over een batterij of panelen neemt u
          met een offerte in de hand, niet met dit scherm.
        </p>
      </section>

      <section className={styles.section} aria-labelledby="betaald">
        <h2 id="betaald" className={styles.heading}>
          Waarvan Ampeer betaald wordt
        </h2>
        <p className={styles.body}>
          Wij verkopen geen panelen, geen batterijen en geen energiecontract,
          en plaatsen geen advertenties. Niemand betaalt ons voor de uitkomst
          die u krijgt.
        </p>
        <p className={styles.body}>
          Vandaag verdienen wij niets aan uw advies. Verandert dat, dan staat
          het hier en op <Link href="/over-ons/">de pagina over ons</Link>{" "}
          voordat het gebeurt.
        </p>
        <p className={styles.body}>
          Gaat Ampeer ooit doorverwijzen, dan vragen wij daar apart
          toestemming voor. Uw advies verandert er niet door.
        </p>
      </section>

      <section className={styles.section} aria-labelledby="accountvoorwaarden">
        <h2 id="accountvoorwaarden" className={styles.heading}>
          Uw account
        </h2>
        <p className={styles.body}>
          Een account per e-mailadres. U kiest en bewaart uw wachtwoord; wij
          kunnen het niet lezen en geven het niet terug. Bent u het kwijt, dan
          herstelt u het via de mail.
        </p>
        <p className={styles.body}>
          Verwijderen is definitief en doet u zelf, met uw wachtwoord erbij.
          Vandaag bewaart een account uw toestemmingen en kunt u exporteren.
          Straks koppelt het, met een bevestigd adres, een slimme meter.
        </p>
      </section>

      <section className={styles.section} aria-labelledby="niet-instaan">
        <h2 id="niet-instaan" className={styles.heading}>
          Waarvoor wij niet instaan
        </h2>
        <p className={styles.body}>
          De uitkomst is een schatting en geen belofte. Wij zijn niet
          aansprakelijk voor een beslissing die u op die schatting neemt, voor
          zover de wet ons toestaat dat uit te sluiten.
        </p>
        <p className={styles.body}>
          De dienst kan er even niet zijn. Wij beloven geen beschikbaarheid.
        </p>
      </section>

      <section className={styles.section} aria-labelledby="watwijvragenvoorwaarden">
        <h2 id="watwijvragenvoorwaarden" className={styles.heading}>
          Wat wij van u vragen
        </h2>
        <p className={styles.body}>
          Gebruik de dienst voor uw eigen huishouden, of voor iemand die u
          daarom vroeg. Probeer niet in te breken, te overbelasten of om de
          tempolimieten heen te werken. Maak geen account op een adres dat
          niet van u is.
        </p>
        <p className={styles.body}>Meer regels zijn er niet.</p>
      </section>

      <section className={styles.section} aria-labelledby="rechtenklachten">
        <h2 id="rechtenklachten" className={styles.heading}>
          Recht en klachten
        </h2>
        <p className={styles.body}>Nederlands recht is van toepassing.</p>
        <p className={styles.body}>
          Een klacht over de dienst gaat naar {identity.contactEmail}. Een
          vraag of klacht over uw gegevens gaat naar {identity.privacyEmail}.
        </p>
        <p className={styles.body}>
          Over uw gegevens kunt u ook terecht bij de{" "}
          <a href="https://www.autoriteitpersoonsgegevens.nl/">
            Autoriteit Persoonsgegevens
          </a>
          .
        </p>
      </section>

      <section className={styles.section} aria-labelledby="overdezevoorwaarden">
        <h2 id="overdezevoorwaarden" className={styles.heading}>
          Over deze voorwaarden
        </h2>
        <p className={styles.body}>
          Een wijziging komt op deze pagina te staan, met een nieuwe datum. Een
          wijziging die u iets kost komt hier te staan voordat hij ingaat.
        </p>
        <p className={styles.body}>
          Zie ook <Link href="/privacy/">onze privacyverklaring</Link>,{" "}
          <Link href="/over-ons/">de pagina over ons</Link> en{" "}
          <Link href="/methodologie/">onze methodologie</Link>.
        </p>
        <p className={styles.note}>Laatst gewijzigd op 7 september 2026.</p>
      </section>
    </div>
  );
}

/**
 * The route.
 *
 * Same gate as `/privacy/` and `/over-ons/`, for the same reason: this page
 * names the entity behind Ampeer twice, in the colophon-free form of two
 * email addresses, and a fact nobody has supplied must stop the build.
 */
export default function VoorwaardenPage() {
  return <TermsPage identity={requireCompleteIdentity(IDENTITY)} />;
}
```

- [ ] **Step 2: `SITEMAP_ROUTES` en de voettekst**

In `frontend/src/app/_shell/site.ts`, na de `/privacy/`-regel:

```ts
export const SITEMAP_ROUTES: readonly {
  readonly path: string;
  readonly changeFrequency: "monthly" | "yearly";
  readonly priority: number;
}[] = [
  { path: "/", changeFrequency: "monthly", priority: 1 },
  { path: "/einde-saldering/", changeFrequency: "monthly", priority: 0.9 },
  { path: "/berekenen/", changeFrequency: "yearly", priority: 0.8 },
  { path: "/methodologie/", changeFrequency: "monthly", priority: 0.6 },
  { path: "/over-ons/", changeFrequency: "yearly", priority: 0.5 },
  { path: "/privacy/", changeFrequency: "yearly", priority: 0.3 },
  { path: "/voorwaarden/", changeFrequency: "yearly", priority: 0.3 },
];
```

In `frontend/src/app/_shell/SiteFooter.tsx`, een vijfde `Link` tussen Privacy en Account:

```tsx
          <Link href="/privacy/" className="underline underline-offset-4">
            Privacy
          </Link>
          <Link href="/voorwaarden/" className="underline underline-offset-4">
            Voorwaarden
          </Link>
          <Link href="/account/" className="underline underline-offset-4">
            Account
          </Link>
```

De docstring boven `SiteFooter` noemt "There are now four" en "the fourth is the only entrance
to the account"; werk die twee zinnen bij naar vijf en naar "the fifth is the only entrance to
the account", zonder de rest van de tekst te herschrijven.

- [ ] **Step 3: `/over-ons/` krijgt de reciproke link**

In `frontend/src/app/over-ons/page.tsx`, in de sectie "Wat wij met uw gegevens doen":

```tsx
        <p className={styles.body}>
          Alles daarover staat in{" "}
          <Link href="/privacy/">onze privacyverklaring</Link>. De regels voor
          het gebruik staan in{" "}
          <Link href="/voorwaarden/">onze gebruiksvoorwaarden</Link>.
        </p>
```

- [ ] **Step 4: `LegalPages.test.tsx`, drie bewerkingen**

**4a. De identiteitstest gaat over drie pagina's.** Voeg `VoorwaardenPage` en `TermsPage` toe
aan de imports:

```ts
import VoorwaardenPage, {
  TermsPage,
  metadata as voorwaardenMetadata,
} from "@/app/voorwaarden/page";
```

In de test "puts both pages behind that guard rather than beside it" (`:141-157`), verander de
lus:

```ts
    for (const route of ["privacy", "over-ons", "voorwaarden"]) {
```

In "the two default exports" (`:463-480`), verander de lijst:

```ts
    for (const page of [PrivacyPage, OverOnsPage, VoorwaardenPage]) {
```

**4b. Een nieuwe suite voor `/voorwaarden/`,** naar het model van de privacy-suite:

```ts
function termsText(identity: CompleteIdentity = FILLED): string {
  const { container } = render(<TermsPage identity={identity} />);
  return container.textContent ?? "";
}

describe("the terms page", () => {
  it("has one first-level heading and a title and description of its own", () => {
    const { container } = render(<TermsPage identity={FILLED} />);
    expect(container.querySelectorAll("h1")).toHaveLength(1);
    expect(
      screen.getByRole("heading", { level: 1, name: "Gebruiksvoorwaarden" }),
    ).toBeInTheDocument();
    expect(voorwaardenMetadata.title).toBe("Gebruiksvoorwaarden");
    expect(String(voorwaardenMetadata.description).length).toBeGreaterThan(50);
    expect(voorwaardenMetadata.alternates?.canonical).toBe("/voorwaarden/");
    expect(voorwaardenMetadata.openGraph).toBeUndefined();
  });

  it("says what a reader needs before trusting the advice", () => {
    const text = termsText();
    for (const claim of [
      "schatting",
      "bandbreedte",
      "geen financieel",
      "verkopen geen",
      "Niemand betaalt ons",
      "account per e-mailadres",
      "Nederlands recht",
      "Autoriteit Persoonsgegevens",
    ]) {
      expect(text, `the terms page never says "${claim}"`).toContain(claim);
    }
  });

  it("carries exactly one external link, the regulator", () => {
    const { container } = render(<TermsPage identity={FILLED} />);
    const hrefs = [...container.querySelectorAll("a[href]")].map((element) =>
      element.getAttribute("href"),
    );
    expect(hrefs.filter((href) => /^https?:/.test(href ?? ""))).toEqual([
      "https://www.autoriteitpersoonsgegevens.nl/",
    ]);
  });

  it("carries no em-dash and no euro amount", () => {
    expect(termsText()).not.toContain("\u2014");
    expect(termsText()).not.toMatch(/€|\d+\s*euro/);
  });

  it("says 7 september 2026", () => {
    expect(termsText()).toContain("7 september 2026");
  });

  it("refuses to render while a fact is missing", () => {
    const missing = missingIdentityFields(IDENTITY);
    if (missing.length > 0) {
      expect(() => VoorwaardenPage()).toThrow(NOG_IN_TE_VULLEN);
    } else {
      expect(VoorwaardenPage()).toBeTruthy();
    }
  });
});
```

De test "een account per" leest de tekst "Een account per e-mailadres." met een kleine letter
vanwege `container.textContent`'s samenvoeging; controleer dat de assertie de zin die er echt
staat citeert (hoofdlettergebruik telt mee in `toContain`), en gebruik zo nodig een deelstring
die zeker matcht (`"account per e-mailadres"`).

**4c. De voettekst op vijf.** In `describe("the footer, ...")`:

```ts
  it("reaches all five pages that explain the product rather than sell it", () => {
    const { container } = render(<SiteFooter />);
    const hrefs = [...container.querySelectorAll("a[href]")].map((element) =>
      element.getAttribute("href"),
    );
    for (const path of [
      /^\/methodologie\/?$/,
      /^\/over-ons\/?$/,
      /^\/privacy\/?$/,
      /^\/voorwaarden\/?$/,
      /^\/account\/?$/,
    ]) {
      expect(hrefs.some((href) => path.test(href ?? ""))).toBe(true);
    }
    // Five, and a sixth is a finding rather than a detail: the fifth is the
    // page that says what Ampeer does not stand behind, and it stands next
    // to the page that says what Ampeer keeps, because a reader looking for
    // one wants the other too.
    expect(hrefs).toHaveLength(5);
    expect(hrefs.filter((href) => /^https?:/.test(href ?? ""))).toEqual([]);
  });
```

Vervang de bestaande `toHaveLength(4)`-test hiermee (de test-naam verandert van "reaches all
four" naar "reaches all five", zodat een grep op de oude naam niets meer vindt).

**4d. `sitemap()` krijgt zeven regels.** In "names both routes in the sitemap, absolutely":

```ts
    expect(urls).toContain(`${SITE_ORIGIN}/voorwaarden/`);
```

erbij, naast de bestaande `toContain`-regels, en de `toHaveLength(SITEMAP_ROUTES.length)`-
assertie blijft zoals hij is (hij leest de lengte af in plaats van hem te herhalen, dus hij
klopt vanzelf).

- [ ] **Step 5: Rode bewijzen**

```bash
cd frontend && pnpm vitest run tests/app/LegalPages.test.tsx
```

1. Verwijder tijdelijk de vijfde `Link` uit `SiteFooter.tsx`. Verwacht: rood op "reaches all
   five pages", `hrefs` telt vier. Zet de link terug.
2. Verwijder tijdelijk de `/voorwaarden/`-regel uit `SITEMAP_ROUTES`. Verwacht: rood op de
   nieuwe `toContain`-assertie in "names both routes in the sitemap, absolutely" (de test-naam
   blijft ongewijzigd, spec 4.1 vraagt daar niet om). Zet de regel terug.
3. Verwijder tijdelijk de zin "Nederlands recht is van toepassing." uit de voorwaardenpagina.
   Verwacht: rood op "says what a reader needs before trusting the advice". Zet de zin terug.
4. Verander tijdelijk `requireCompleteIdentity(IDENTITY)` in `voorwaarden/page.tsx` naar een
   directe `IDENTITY`-doorgifte zonder poort. Verwacht: `pnpm typecheck` rood (`CompleteIdentity`
   verwacht, `Identity` gegeven), wat bevestigt dat de typebarrière ook op de derde pagina staat.
   Zet de aanroep terug.

- [ ] **Step 6: `ui-strings.txt` opnieuw**

```bash
cd frontend && UPDATE_UI_STRINGS=1 pnpm e2e language
cd frontend && pnpm e2e language
```

Verwacht: het eerste commando faalt na het herschrijven (zoals altijd), het tweede is groen.
Lees de diff: elke toegevoegde regel komt uit `voorwaarden/page.tsx` of is een van de acht
nieuwe `id`-koppen, plus "Voorwaarden" uit de voettekst.

- [ ] **Step 7: De volledige Vitest-suite en de typecheck**

```bash
cd frontend && pnpm typecheck && pnpm vitest run
```

Verwacht: beide groen. `pnpm vitest run` zonder pad, omdat deze taak vier bestanden buiten
`LegalPages.test.tsx` aanraakt (`site.ts`, `SiteFooter.tsx`, `over-ons/page.tsx`) die ook door
andere suites gelezen worden (bijvoorbeeld een test die `SITEMAP_ROUTES.length` elders gebruikt).

- [ ] **Step 8: Commit**

```bash
git add frontend/src/app/voorwaarden/page.tsx frontend/src/app/over-ons/page.tsx frontend/src/app/_shell/SiteFooter.tsx frontend/src/app/_shell/site.ts frontend/tests/app/LegalPages.test.tsx frontend/tests/ui-strings.txt
git commit -m "$(cat <<'EOF'
feat(voorwaarden): add the terms page and the disclaimer the advice needs

A dedicated route rather than a section on the methodology page, so the
disclaimer is where a reader looks for it. Linked from the footer, the
sitemap, /over-ons/ and /privacy/, and gated behind requireCompleteIdentity
like the other two pages that name the entity behind Ampeer.

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
EOF
)"
```

---

### Taak 5: De twee e2e-routelijsten, axe, de taalspec

**Hangt af van:** taak 4.

**Files:**
- Modify: `frontend/e2e/privacy.spec.ts`, `frontend/e2e/rules.spec.ts`, `frontend/e2e/theme.spec.ts`, `frontend/tests/app/LegalPages.test.tsx`

**Interfaces:**
- Consumes: `SITEMAP_ROUTES` uit `_shell/site.ts`; de mappen onder `frontend/src/app/`.
- Produces: geen nieuwe export; `PAGES` en `ALL_PATHS` in de twee e2e-bestanden dekken alle negen routes; een bindingstest in `LegalPages.test.tsx`.

Spec hoofdstuk 4.3, 4.4, 8.2, 8.3.

- [ ] **Step 1: `frontend/e2e/privacy.spec.ts`, `PAGES` compleet**

```ts
import fixture from "../tests/fixtures/advice-response.json";

const TOKEN = fixture.token;
const ADVICE_PATH = `/advies/${TOKEN}/`;

/**
 * Every page a visitor can reach, plus the one behind a bearer token, plus
 * /voorwaarden/. Nine, and the sweep this file runs is the proof that no
 * page a visitor actually loads asks anything of a third party; a list that
 * left out /privacy/ or /over-ons/ was a sweep that promised that and did
 * not load the two pages that make the promise.
 */
const PAGES = [
  "/",
  "/einde-saldering/",
  "/berekenen/",
  ADVICE_PATH,
  "/methodologie/",
  "/over-ons/",
  "/privacy/",
  "/voorwaarden/",
  "/account/",
];
```

En de bestaande sweep krijgt de advies-fixture gemockt voordat hij `ADVICE_PATH` laadt, op
dezelfde manier als `rules.spec.ts` dat doet:

```ts
test.beforeEach(async ({ page }) => {
  await page.route("**/api/advice/**", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      headers: { "access-control-allow-origin": "*" },
      body: JSON.stringify(fixture),
    }),
  );
});
```

De laatste test in het bestand:

```ts
test("checks exactly the nine pages this list names, not more and not fewer", () => {
  expect(PAGES).toHaveLength(9);
});
```

- [ ] **Step 2: `frontend/e2e/rules.spec.ts`, `ALL_PATHS` compleet**

```ts
const ALL_PATHS = [
  "/",
  "/einde-saldering/",
  "/berekenen/",
  ADVICE_PATH,
  "/methodologie/",
  "/over-ons/",
  "/privacy/",
  "/voorwaarden/",
  "/account/",
] as const;
```

Voeg een lengte-test toe, naar het model van `privacy.spec.ts`'s eigen versie, direct na de
definitie van `ALL_PATHS` of bij de andere losse `test(...)`-aanroepen onderaan het bestand:

```ts
test("checks exactly the nine routes this list names, not more and not fewer", () => {
  expect(ALL_PATHS).toHaveLength(9);
});
```

`every route passes axe` en `every route has exactly one first-level heading` lopen al over
`ALL_PATHS` en hoeven zelf niet te veranderen; met de langere lijst dekken ze automatisch de
vier nieuwe routes, inclusief `/voorwaarden/` in het lichte palet.

- [ ] **Step 3: `frontend/e2e/theme.spec.ts`, alleen `/voorwaarden/` erbij**

```ts
const ALL_PATHS = [
  "/",
  "/berekenen/",
  ADVICE_PATH,
  "/methodologie/",
  "/account/",
  "/voorwaarden/",
] as const;
```

De assertie op regel 163 (`expect(ALL_PATHS).toHaveLength(5)`) wordt:

```ts
  expect(ALL_PATHS).toHaveLength(6);
```

`serveFixture` in dit bestand mockt `me/` als 401 en `refresh/` als 401 zodat het account-
scherm zonder sessie rendert; `/voorwaarden/` heeft geen van beide nodig (geen `me/`-aanroep
op die pagina) en draait onder dezelfde `serveFixture`-aanroep zonder wijziging.

- [ ] **Step 4: De bindingstest in `LegalPages.test.tsx`**

Nieuwe suite, aan het eind van het bestand:

```ts
// ---------------------------------------------------------------------------
// The two hand-written route lists, laid against the route tree
// ---------------------------------------------------------------------------

/** Every array literal string this file's own regex can find, in order. */
function stringArrayNamed(source: string, name: string): string[] {
  const match = new RegExp(`const ${name}[^=]*=\\s*\\[([\\s\\S]*?)\\]`).exec(source);
  if (!match) throw new Error(`${name} was not found`);
  return [...match[1]!.matchAll(/"([^"]+)"/g)].map((found) => found[1]!);
}

describe("the two hand-written e2e route lists stay complete", () => {
  it("names every route under src/app/, or the token template that stands for it", () => {
    const appDir = resolve(process.cwd(), "src/app");
    const routes = readdirSync(appDir, { withFileTypes: true })
      .filter((entry) => entry.isDirectory() && !entry.name.startsWith("_"))
      .filter((entry) => existsSync(join(appDir, entry.name, "page.tsx")))
      .map((entry) => `/${entry.name}/`)
      .sort();

    // The route tree, minus the one entry the e2e lists write differently:
    // /advies/ is a bearer-token page and both lists name the templated
    // ADVICE_PATH instead of the bare directory.
    const expected = routes.filter((route) => route !== "/advies/");

    // Deliberate exceptions to the sitemap, named so a reader does not have
    // to guess why these two routes are in the e2e lists but not in
    // SITEMAP_ROUTES: /advies/ has one URL per visitor and nothing a search
    // engine could usefully index, /account/ carries a noindex tag of its own.
    const NOT_IN_SITEMAP = ["/advies/", "/account/"];
    for (const route of routes) {
      if (NOT_IN_SITEMAP.includes(route)) continue;
      expect(
        SITEMAP_ROUTES.map((entry) => entry.path),
        `${route} is a real route, is not one of the two named exceptions, and is missing from SITEMAP_ROUTES`,
      ).toContain(route);
    }

    for (const [file, name] of [
      ["frontend/e2e/privacy.spec.ts", "PAGES"],
      ["frontend/e2e/rules.spec.ts", "ALL_PATHS"],
    ] as const) {
      const source = readFileSync(resolve(process.cwd(), "..", file), "utf-8");
      const listed = stringArrayNamed(source, name);
      for (const route of expected) {
        expect(
          listed.some((entry) => entry === route || entry.startsWith("/advies/")),
          `${file}'s ${name} does not name ${route}`,
        ).toBe(true);
      }
    }
  });
});
```

Deze test leest de twee e2e-bestanden vanaf de herhaalde repository-root (`../`, want Vitest
draait vanuit `frontend/`), precies zoals de bestaande test op `:283-308` `../backend/advice/models.py`
leest. Een zesde route die later bijkomt en in geen van de twee lijsten belandt, laat deze test
rood gaan voordat een e2e-run het zou moeten ontdekken.

- [ ] **Step 5: Rode bewijzen**

1. Verwijder tijdelijk `/privacy/` uit `PAGES` in `privacy.spec.ts`. Draai:

```bash
cd frontend && pnpm vitest run tests/app/LegalPages.test.tsx
```

Verwacht: rood op "names every route under src/app/, or the token template that stands for
it", met de boodschap "privacy.spec.ts's PAGES does not name /privacy/". Zet de regel terug.

2. Verwijder tijdelijk `/voorwaarden/` uit `SITEMAP_ROUTES` (zoals taak 4 dat al aantoonde) en
   draai dezelfde suite. Verwacht: rood op dezelfde test, nu met de boodschap dat `/voorwaarden/`
   in de sitemap ontbreekt. Zet de regel terug.
3. Verander `expect(PAGES).toHaveLength(9)` tijdelijk naar `toHaveLength(8)` in
   `privacy.spec.ts`. Draai:

```bash
cd frontend && pnpm e2e privacy
```

Verwacht: rood. Zet de negen terug.

- [ ] **Step 6: De volle e2e-suite**

```bash
cd frontend && pnpm build && pnpm e2e
```

Verwacht: groen, alle bestanden onder `frontend/e2e/`, inclusief `account.spec.ts`,
`carpet.spec.ts`, `day.spec.ts`, `form.spec.ts`, `gap.spec.ts`, `happy-path.spec.ts`,
`language.spec.ts`, `privacy.spec.ts`, `rules.spec.ts` en `theme.spec.ts`. Dit is het punt in
de cyclus waarop de spec vraagt dat de volle `pnpm e2e` groen is; een falende suite hier stopt
de taak in plaats van door te lopen naar taak 6.

- [ ] **Step 7: Commit**

```bash
git add frontend/e2e/privacy.spec.ts frontend/e2e/rules.spec.ts frontend/e2e/theme.spec.ts frontend/tests/app/LegalPages.test.tsx
git commit -m "$(cat <<'EOF'
test(e2e): complete the two hand-written route lists

PAGES and ALL_PATHS named five routes each and both missed /privacy/ and
/over-ons/, which is exactly backwards for a sweep that promises no page
asks anything of a third party. Both now cover every route under src/app/
plus the advice link, with a Vitest test that lays them against
SITEMAP_ROUTES and the route tree so a sixth route cannot go quietly
missing again.

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
EOF
)"
```

---

### Taak 6: Het verwerkingsregister

**Hangt af van:** taak 5.

**Files:**
- Create: `docs/verwerkersregister.md`, `tests/test_verwerkersregister.py`

**Interfaces:**
- Consumes: `backend/accounts/models.py`, `backend/advice/models.py` (de negen modelklassen); `OUTBOUND_MODULES` uit `tests/test_boundaries.py`; `AMPEER_ADVICE_TTL_DAYS` uit `backend/ampeer/settings/base.py`; `KEEP_DAYS` uit `scripts/backup_db.sh`; `OneTimeToken.LIFETIMES` uit `backend/accounts/models.py`; `AuditEvent`'s constanten; `frontend/src/app/privacy/identity.ts`; `_DUTCH_NUMERALS` uit `tests/test_dpia.py`.
- Produces: `docs/verwerkersregister.md`, tien hoofdstukken (0 tot en met 9); acht tests die het aan de code binden.

Spec hoofdstuk 5.

Een kanttekening bij het aantal: spec 5.3's genummerde lijst noemt acht testnamen (twee ervan
in een gedeelde regel, "dezelfde twee als de DPIA heeft"); spec hoofdstuk 11 (Definition of
done) telt dat samen als "zeven tests". Dat is dezelfde soort telfout die
`tests/test_dpia.py::test_the_chapter_of_open_decisions_states_how_many_there_are` ooit ving in
hoofdstuk 10 van de DPIA zelf ("Vier" boven vijf genummerde punten): een samenvattend getal dat
niet is afgeleid van de lijst waar het boven staat. De itemlijst is het gezag, dus dit plan
bouwt acht tests, niet zeven.

- [ ] **Step 1: `docs/verwerkersregister.md`**

```text
# Verwerkingsregister

Datum: 7 september 2026
Betreft: het register van verwerkingsactiviteiten dat artikel 30 AVG vraagt.

## 0. De verantwoordelijke

Stijn IT, eenmanszaak. KvK 42015984. Snavelbiesstraat 8, 5445 NV Landhorst.
Algemeen adres: info@ampeer.nl. Adres voor verzoeken over persoonsgegevens:
privacy@ampeer.nl.

Geen functionaris gegevensbescherming en geen vertegenwoordiger. Geen van
beide is verplicht voor deze verwerking, en er is er geen.

## 1. Het advies

**Doel.** Uitrekenen wat het einde van de salderingsregeling een huishouden
kost.

**Betrokkenen.** Bezoekers van ampeer.nl.

**Categorieën gegevens.** De vijf antwoorden uit de eerste ronde en de acht
uit de tweede ronde, het berekende advies, en een token van 22 tekens dat
naar dat advies wijst.

**Grondslag.** Toestemming, gegeven door te rekenen.

**Ontvangers.** Cloudflare Inc., als verwerker voor al het verkeer naar
ampeer.nl.

**Doorgifte buiten de EER.** Geen, door Ampeer zelf. Cloudflare beeindigt de
verbinding aan zijn eigen rand.

**Bewaartermijn.** negentig dagen, dagelijks opgeruimd. Een reservekopie
bewaart een verwijderd advies nog hoogstens zeven dagen langer.

**Maatregelen.** De postcode wordt op vier cijfers geweigerd, niet afgekapt.
Het token komt nooit in een logregel. Er geldt een tempolimiet per gehasht
IP-adres.

**Tabellen.** `StoredAdvice`, `ProductionCache`, `DailyCounter`, in
`backend/advice/models.py`.

## 2. Het account

**Doel.** Een huishouden laten inloggen, zijn toestemmingen bewaren, en zijn
gegevens laten exporteren of verwijderen.

**Betrokkenen.** Wie een account aanmaakt.

**Categorieën gegevens.** E-mailadres, wachtwoord als Argon2id-hash,
tijdstip van de laatste keer inloggen, tijdstip van adresbevestiging.

**Grondslag.** Toestemming, gegeven door registratie (DPIA hoofdstuk 10,
punt 2).

**Ontvangers.** Geen buiten Cloudflare (hoofdstuk 1) voor het verkeer zelf.

**Doorgifte buiten de EER.** Geen.

**Bewaartermijn.** Tot verwijdering van het account. Een reservekopie
bewaart een verwijderd account nog hoogstens zeven dagen langer.

**Maatregelen.** Argon2id. httpOnly-cookies met SameSite=Strict, een voor
een kwartier en een voor veertien dagen. Refresh-tokens als digest, nooit
als geldig token. Inbraakbeveiliging in het geheugen, zonder een tabel met
een IP-adres erin. Het wachtwoord wordt opnieuw gevraagd voordat een account
wordt verwijderd.

**Tabellen.** `User`, `RefreshSession`, in `backend/accounts/models.py`.

## 3. De toestemmingen

**Doel.** Vastleggen welke toestemming een huishouden gaf of introk, en
wanneer.

**Betrokkenen.** Wie een account heeft.

**Categorieën gegevens.** Soort toestemming, handeling (geven of intrekken),
tijdstip, versie van de tekst die op dat moment gold.

**Grondslag.** Toestemming; dit is de toestemming zelf.

**Ontvangers.** Geen.

**Doorgifte buiten de EER.** Geen.

**Bewaartermijn.** Tot verwijdering van het account. Elke rij blijft staan;
intrekken is een nieuwe rij en geen wijziging van de oude.

**Maatregelen.** Nooit voorgevinkt. Een label narrowt nooit verder dan de
tekst onder dezelfde versie toestaat.

**Tabellen.** `Consent`, in `backend/accounts/models.py`.

## 4. Herstel en bevestiging per mail

**Doel.** Een wachtwoord herstellen of een e-mailadres bevestigen.

**Betrokkenen.** Wie een account heeft en een link aanvraagt of ontvangt.

**Categorieën gegevens.** Het e-mailadres, de soort mail (herstel of
bevestiging), de sha256-afdruk van een link.

**Grondslag.** Noodzaak voor de dienst (DPIA hoofdstuk 10, bij punt 5):
zonder bevestigd adres kan de dienst geen wachtwoord herstellen en straks
geen meter koppelen.

**Ontvangers.** Resend, Inc., als verwerker voor het versturen van de mail.

**Doorgifte buiten de EER.** Verenigde Staten, voor Resends eigen
verzendlog. De standaardbepalingen van de Europese Commissie in Resends
verwerkersovereenkomst en Resends certificering onder het Data Privacy
Framework zijn de grondslag voor die doorgifte. De verzendregio is de
Europese Unie.

**Bewaartermijn.** De afdruk van een link tot hij verloopt: een uur voor
herstel, zeven dagen voor bevestiging. De rij in de wachtrij tot verzending,
of zeven dagen na een definitief mislukte poging.

**Maatregelen.** Het ruwe token bestaat alleen in het geheugen van het
verstuurcommando en in de mail zelf; de database bewaart alleen de
sha256-afdruk. Geen e-mailadres in de wachtrij. Een link werkt precies een
keer. `backend/accounts/mailer.py` is de enige module die Resend bereikt, en
een test dwingt dat af.

**Tabellen.** `OneTimeToken`, `OutboundMail`, in `backend/accounts/models.py`.

## 5. Het auditlogboek

**Doel.** Vastleggen wat er gebeurde, zodat de dienst controleerbaar is.

**Betrokkenen.** Iedereen van wie de dienst iets vastlegt: een advies, een
account, een toestemming, een mail.

**Categorieën gegevens.** Soort handeling, tijdstip, een accountnummer of
niets, een onomkeerbare afdruk van een advieslink, een postcodegebied,
versienummers. Nooit een e-mailadres.

**Grondslag.** Gerechtvaardigd belang van de verantwoordelijke bij een
controleerbaar systeem, en artikel 5 lid 2 AVG (verantwoordingsplicht).

**Ontvangers.** Geen.

**Doorgifte buiten de EER.** Geen.

**Bewaartermijn.** Geen opruiming. Na verwijdering van een account of een
advies wijst het nummer in een regel nergens meer naar.

**Maatregelen.** Alleen toevoegen; nooit wijzigen of verwijderen. Dertien
soorten handelingen worden vastgelegd, en niet meer dan dat.

**Tabellen.** `AuditEvent`, in `backend/advice/models.py`.

## 6. De tempolimiet

**Doel.** Misbruik tegengaan: te veel verzoeken van een en dezelfde
bezoeker.

**Betrokkenen.** Elke bezoeker.

**Categorieën gegevens.** Een teller per gehasht IP-adres, in het geheugen.

**Grondslag.** Gerechtvaardigd belang: misbruik tegengaan.

**Ontvangers.** Geen.

**Doorgifte buiten de EER.** Geen.

**Bewaartermijn.** Een uur, in het geheugen. Nooit in een tabel.

**Maatregelen.** HMAC onder de geheime sleutel. Gemeten: de drie tabellen
die het inbraakbeveiligingsprogramma zou kunnen vullen blijven leeg.

## 7. De reservekopieen

**Doel.** Herstel mogelijk maken na een fout of een storing.

**Betrokkenen.** Iedereen van wie de database op dat moment een gegeven
draagt.

**Categorieën gegevens.** Een dump van de hele database.

**Grondslag.** Dezelfde als de verwerking die in de dump staat.

**Ontvangers.** Geen.

**Doorgifte buiten de EER.** Geen.

**Bewaartermijn.** zeven dagen. Een verwijderd gegeven kan daardoor nog
hoogstens acht dagen in een kopie staan.

**Maatregelen.** Bestanden op modus 0600, in een map op modus 0700,
dagelijks. De deploy weigert een kopie gezond te noemen die breder leesbaar
is dan dat.

## 8. De verwerkers

| Verwerker | Verwerking | Ziet | Verwerkersovereenkomst |
|---|---|---|---|
| Cloudflare Inc. | Al het verkeer naar ampeer.nl | IP-adres, pad | De standaardovereenkomst bij het account; aanvaarding niet vastgelegd; bij de verantwoordelijke (DPIA hoofdstuk 10, punt 5). |
| Resend, Inc. | Herstel- en bevestigingsmail | E-mailadres, inhoud | De voorgetekende DPA uit het dashboard; beoordeling bij de verantwoordelijke (DPIA hoofdstuk 10, punt 5). |

Geen derde verwerker.

## 9. Wat er verandert bij fase 2

Zodra kwartierdata van een slimme meter binnenkomt, ontstaat een achtste
verwerking, met een eigen bewaartermijn: negentig dagen ruw, daarna alleen
uuraggregaten. Dit register wordt dan herschreven, samen met de DPIA.
```

- [ ] **Step 2: `tests/test_verwerkersregister.py`**

```text
"""The article 30 register must describe the service that actually runs.

Same idea as tests/test_dpia.py, applied to a second document: a table this
project processes personal data through belongs in this register by name, a
retention window quoted here is a number the code actually enforces, and a
number that drifts from the code should turn this suite red rather than sit
unnoticed in prose.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest
from helpers.shell import shell_int

from test_dpia import ACCOUNT_MODELS, MODELS, SETTINGS, _DUTCH_NUMERALS, _int_constant

REPO_ROOT = Path(__file__).resolve().parent.parent
REGISTER = REPO_ROOT / "docs" / "verwerkersregister.md"
DPIA = REPO_ROOT / "docs" / "dpia.md"
BACKUP = REPO_ROOT / "scripts" / "backup_db.sh"
TEXT = REGISTER.read_text(encoding="utf-8")

NUMBER_WORDS = {90: "negentig dagen", 7: "zeven dagen"}


def _model_class_names(source: Path) -> list[str]:
    """Every models.Model subclass declared in one file, by name.

    The same reading test_dpia.py's test_no_table_has_a_column_for_an_address
    already does over these two files, pulled out here so both suites read the
    same tree the same way rather than keeping two slightly different parsers.
    """
    tree = ast.parse(source.read_text(encoding="utf-8"))
    names = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        bases = {base.attr if isinstance(base, ast.Attribute) else getattr(base, "id", "") for base in node.bases}
        if "Model" in bases:
            names.append(node.name)
    return names


def test_the_register_names_every_table_the_service_has() -> None:
    """Red-proof: remove OutboundMail from the document by hand and rerun."""
    tables = _model_class_names(MODELS) + _model_class_names(ACCOUNT_MODELS)
    assert tables, "the AST reader found no models at all, so it read the wrong file"
    missing = [name for name in tables if name not in TEXT]
    assert not missing, f"the register never names {missing}"


def test_the_register_names_both_processors_and_no_third() -> None:
    """The allowlist test_boundaries.py enforces is the outer bound on what a
    document about processors may claim exists."""
    from test_boundaries import OUTBOUND_MODULES

    assert "Cloudflare" in TEXT
    assert "Resend" in TEXT
    hosts = {host for allowed in OUTBOUND_MODULES.values() for host in allowed}
    # energiedatawijzer.nl is a deliberate exception: a by-hand ingest run,
    # never a processing of personal data, so it does not belong in a
    # register of processing activities and this test says so by name rather
    # than asserting every host in OUTBOUND_MODULES appears here.
    assert "energiedatawijzer.nl" not in TEXT
    assert hosts == {"re.jrc.ec.europa.eu", "energiedatawijzer.nl", "api.resend.com"}


def test_the_register_quotes_the_retention_the_service_applies() -> None:
    from datetime import timedelta
    from backend.accounts.models import OneTimeToken

    days = _int_constant(SETTINGS, "AMPEER_ADVICE_TTL_DAYS")
    assert NUMBER_WORDS[days] in TEXT
    kept = shell_int(BACKUP, "KEEP_DAYS")
    assert NUMBER_WORDS[kept] in TEXT

    # Map timedeltas to Dutch words for OneTimeToken.LIFETIMES
    LIFETIME_WORDS = {
        timedelta(hours=1): "een uur",
        timedelta(days=7): "zeven dagen",
    }

    for kind, lifetime in OneTimeToken.LIFETIMES.items():
        dutch_text = LIFETIME_WORDS.get(lifetime)
        if dutch_text:
            assert dutch_text in TEXT


def test_the_register_counts_the_audit_kinds() -> None:
    tree = ast.parse(MODELS.read_text(encoding="utf-8"))
    audit = next(
        node for node in ast.walk(tree) if isinstance(node, ast.ClassDef) and node.name == "AuditEvent"
    )
    count = sum(
        1
        for statement in audit.body
        if isinstance(statement, ast.Assign)
        and isinstance(statement.value, ast.Constant)
        and isinstance(statement.value.value, str)
        and statement.value.value.isupper()
    )
    assert count in _DUTCH_NUMERALS
    assert f"{_DUTCH_NUMERALS[count].lower()} soorten" in TEXT


def test_the_register_carries_no_em_dashes() -> None:
    assert "\u2014" not in TEXT


def test_every_section_is_numbered_consecutively() -> None:
    numbers = [int(match) for match in re.findall(r"^## (\d+)\.", TEXT, re.MULTILINE)]
    assert numbers == list(range(len(numbers))), numbers


def test_the_register_names_the_controller_the_site_names() -> None:
    identity = (REPO_ROOT / "frontend" / "src" / "app" / "privacy" / "identity.ts").read_text(
        encoding="utf-8"
    )
    kvk = re.search(r'kvkNumber:\s*"(\d+)"', identity)
    assert kvk, "identity.ts no longer assigns kvkNumber as a plain string"
    assert kvk.group(1) in TEXT
    for field in ("contactEmail", "privacyEmail"):
        match = re.search(rf'{field}:\s*"([^"]+)"', identity)
        assert match, f"identity.ts no longer assigns {field} as a plain string"
        assert match.group(1) in TEXT


def test_the_dpia_no_longer_says_there_is_no_register() -> None:
    dpia = DPIA.read_text(encoding="utf-8")
    assert "geen verwerkersregister" not in dpia
    assert "verwerkersregister.md" in dpia
```

Voeg `_DUTCH_NUMERALS`, `_int_constant`, `MODELS`, `ACCOUNT_MODELS`, `SETTINGS` toe aan wat
`tests/test_dpia.py` exporteert (ze bestaan al als moduleniveau-namen in dat bestand; niets
verandert daar, dit bestand importeert ze alleen).

- [ ] **Step 3: Rode bewijzen, per test**

```bash
uv run --no-sync pytest tests/test_verwerkersregister.py -v
```

Voer voor elke test uit wat spec 5.3 voorschrijft, met de hand teruggezet na elke proef:

1. Haal de regel `**Tabellen.** \`OneTimeToken\`, \`OutboundMail\`, ...` tijdelijk uit hoofdstuk
   4. Verwacht: rood op `test_the_register_names_every_table_the_service_has`, de boodschap
   noemt `OutboundMail` (en `OneTimeToken`). Zet de regel terug.
2. Verander tijdelijk "Resend, Inc." naar "Resend BV" in hoofdstuk 4 en hoofdstuk 8. Verwacht:
   rood op `test_the_register_names_both_processors_and_no_third`. Zet terug.
3. Verander tijdelijk "negentig dagen" naar "90 dagen" in hoofdstuk 1. Verwacht: rood op
   `test_the_register_quotes_the_retention_the_service_applies`. Zet terug.
4. Verander tijdelijk "Dertien soorten" naar "Veertien soorten" in hoofdstuk 5. Verwacht: rood
   op `test_the_register_counts_the_audit_kinds`. Zet terug.
5. Voeg tijdelijk een em-dash toe aan een willekeurige zin. Verwacht: rood op
   `test_the_register_carries_no_em_dashes`. Zet terug.
6. Verander tijdelijk `## 5.` naar `## 6.` (zodat twee hoofdstukken `## 6.` heten en er geen
   `## 5.` meer is). Verwacht: rood op `test_every_section_is_numbered_consecutively`. Zet
   terug.
7. Verander tijdelijk `42015984` naar `42015985` in hoofdstuk 0. Verwacht: rood op
   `test_the_register_names_the_controller_the_site_names`. Zet terug.
8. Zet in `docs/dpia.md` tijdelijk de oude zin "Er is verder geen ... verwerkersregister ..."
   terug (taak 9 heeft die dan al herschreven; voor deze rode proef volstaat het de nieuwe zin
   tijdelijk te vervangen door een zin die letterlijk "geen verwerkersregister" bevat).
   Verwacht: rood op `test_the_dpia_no_longer_says_there_is_no_register`. Zet terug. Deze proef
   loopt logisch vooruit op taak 9's wijziging aan `docs/dpia.md`; voer hem daarom pas uit nadat
   taak 9 is afgerond, en noteer dat in de PR-boodschap van deze taak als een bekende volgorde
   die niet omkeerbaar is zonder taak 9 eerst te doen. Tot die tijd faalt deze ene test
   voorspelbaar rood, en dat is de enige test in deze suite die tussen taak 6 en taak 9 rood
   mag staan: hij test een belofte die pas in taak 9 wordt ingelost. Voeg voor de duur van die
   periode `@pytest.mark.xfail(reason="docs/dpia.md still says the sentence this cycle removes in taak 9", strict=True)`
   toe aan deze ene test, en verwijder die marker in taak 9 zodra de DPIA-zin is herschreven.

- [ ] **Step 4: Groen, met de marker eraf**

```bash
uv run --no-sync pytest tests/test_verwerkersregister.py -v
```

Verwacht na Step 3: alles groen behalve `test_the_dpia_no_longer_says_there_is_no_register`,
die `xfail` (strict) is en dus als slagend telt in de samenvatting zolang hij inderdaad faalt.
`uv run --no-sync pytest tests/ -q` (de volle suite) blijft ondertussen groen, want een
`strict=True` xfail die faalt telt niet als een falende test.

- [ ] **Step 5: Commit**

```bash
git add docs/verwerkersregister.md tests/test_verwerkersregister.py
git commit -m "$(cat <<'EOF'
docs(privacy): add the article 30 processing register

docs/dpia.md chapter 10 has said "no register" since phase 1, and everything
a register needs was already in this repository. Bound to the code the way
test_dpia.py binds the assessment: every table by name, both processors and
no third, the retention figures read from settings and scripts, the audit
kind count read from AuditEvent. One test stays xfail until taak 9 rewrites
the DPIA sentence this register makes untrue.

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
EOF
)"
```

---

### Taak 7: De 401, de mail-grens, de eerste vier branch-gaten

**Hangt af van:** taak 6.

**Files:**
- Modify: `backend/accounts/views.py`, `backend/accounts/nl.py`, `backend/accounts/management/commands/send_outbound_mail.py`, `infra/README.md`, `tests/test_accounts_api.py`, `tests/test_accounts_mail.py`, `tests/test_assets.py`, `tests/test_accounts_lockout_callables.py`, `tests/test_accounts_models.py`

**Interfaces:**
- Consumes: `NL` uit `nl.py`; `_AuthAPIView.get_authenticate_header`; `Command._deliver`, `Command._report_what_is_stuck` uit `send_outbound_mail.py`.
- Produces: `_AuthAPIView.permission_denied`; `NL["forbidden"]`; `--max` op `send_outbound_mail`; vier nieuwe tests die een branch dekken die vandaag geen enkele test neemt.

Spec hoofdstuk 7.1, 7.2, 7.4 (de eerste vier van de vijf gaten daar; het vijfde, de
branch-dekking zelf aanzetten, is taak 8).

- [ ] **Step 1: `permission_denied` in `backend/accounts/views.py`**

Direct na `get_authenticate_header` (voor de `user`-property), binnen `_AuthAPIView`:

```text
    def permission_denied(self, request: Request, message: str | None = None, code: str | None = None) -> NoReturn:
        """Answer in this project's own Dutch, not DRF's default catalogue.

        DRF's own version:

            def permission_denied(self, request, message=None, code=None):
                if request.authenticators and not request.successful_authenticator:
                    raise exceptions.NotAuthenticated()
                raise exceptions.PermissionDenied(detail=message, code=code)

        `NotAuthenticated()` with no detail reads DRF's Dutch catalogue, which
        carries no translation, so under nl-nl the sentence a stranger reads on
        every one of the six signed-in routes is English: "Authentication
        credentials were not provided." Every stub in the frontend and every
        e2e mock already answers with NL["not_signed_in"], "u bent niet
        ingelogd" (`describeAuthError` shows a 401 literally), so each of them
        disagreed with the real server until this override existed.

        The PermissionDenied branch below is not reached by any route today:
        DeleteView raises its own PermissionDenied(NL["credentials_invalid"])
        rather than calling this method, and no other view withholds a
        permission once a caller is authenticated. It stays here anyway,
        because a permission that starts checking something in a later cycle
        should not silently reach DRF's English "You do not have permission to
        perform this action." on the way in.
        """
        if request.authenticators and not request.successful_authenticator:
            raise NotAuthenticated(NL["not_signed_in"])
        raise PermissionDenied(NL["forbidden"] if message is None else message, code=code)
```

In `backend/accounts/nl.py`, in de tweede categorie (berichten over de lezer zelf, naast
`not_signed_in` en `session_expired`):

```text
    "not_signed_in": "u bent niet ingelogd",
    "session_expired": "uw sessie is verlopen, log opnieuw in",
    "forbidden": "u mag dit niet doen",
```

Werk de moduledocstring van `nl.py` bij: de tweede categorie noemt nu `not_signed_in`,
`session_expired` en `forbidden` in plaats van alleen de eerste twee.

- [ ] **Step 2: De twee tests in `tests/test_accounts_api.py`**

Direct na `test_me_answers_401_to_a_stranger_and_still_hands_out_a_csrf_token`:

```text
@pytest.mark.django_db
def test_a_stranger_reads_the_projects_own_sentence(client: Any) -> None:
    """The sentence a stranger actually reads on any of the six signed-in
    routes, not only me/. Red-proof: remove the permission_denied override;
    this test then reads DRF's English default."""
    response = client.get("/api/auth/me/")
    assert response.status_code == 401
    assert response.json() == {"detail": NL["not_signed_in"]}
    assert "csrftoken" in response.cookies


def test_permission_denied_without_a_message_reads_the_projects_own_sentence() -> None:
    """The PermissionDenied branch no route reaches today, built the way
    test_the_user_property_raises_rather_than_returning_none_under_dash_o
    builds a view directly rather than waiting for a route to exercise it."""
    view = _AuthAPIView()
    view.request = Request(APIRequestFactory().get("/"))
    view.request.successful_authenticator = object()  # type: ignore[attr-defined]
    with pytest.raises(PermissionDenied) as excinfo:
        view.permission_denied(view.request)
    assert str(excinfo.value.detail) == NL["forbidden"]
```

Importeer `PermissionDenied` uit `rest_framework.exceptions` in dit testbestand als hij daar
nog niet stond (`views.py` importeert hem al; het testbestand mogelijk niet).

- [ ] **Step 3: Rood bewijs voor de 401**

Zet `permission_denied` tijdelijk terug naar niets (verwijder de override, zodat `_AuthAPIView`
op DRF's eigen versie terugvalt), en draai:

```bash
uv run --no-sync pytest tests/test_accounts_api.py -k "reads_the_projects_own_sentence" -v
```

Verwacht: rood, `test_a_stranger_reads_the_projects_own_sentence` faalt op
`response.json() == {"detail": "Authentication credentials were not provided."}` in plaats van
`NL["not_signed_in"]`. Zet de override terug en draai opnieuw: groen.

- [ ] **Step 4: `--max` op `send_outbound_mail`**

In `backend/accounts/management/commands/send_outbound_mail.py`, `add_arguments`:

```text
    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            "--check",
            action="store_true",
            help=(
                "Send nothing; exit non-zero if an unsent mail is older than fifteen "
                "minutes or a mail was given up on in the last day."
            ),
        )
        parser.add_argument(
            "--max",
            type=int,
            default=50,
            help="Stop after sending this many rows in one run. Default 50.",
        )
```

`handle` geeft de grens door:

```text
    def handle(self, *args: Any, **options: Any) -> None:
        if not options["check"]:
            sent, deferred, faulted, capped = self._deliver(options["max"])
            suffix = f", stopped at the cap of {options['max']}" if capped else ""
            self.stdout.write(f"sent {sent} messages, deferred {deferred}{suffix}")
            if faulted:
                raise CommandError(
                    f"{faulted} row(s) raised something other than a transport failure; "
                    "deferred like any other and left for the next run"
                )
        self._report_what_is_stuck()
```

`_deliver` stopt na `max` verzonden rijen en zegt of dat de reden was dat de lus stopte:

```text
    def _deliver(self, max_rows: int) -> tuple[int, int, int, bool]:
        sender = mailer.transport()
        sent = deferred = faulted = 0
        while sent < max_rows:
            with transaction.atomic():
                row = (
                    OutboundMail.objects.select_for_update(skip_locked=True)
                    .filter(failed_at__isnull=True, next_attempt_at__lte=timezone.now())
                    .order_by("id")
                    .first()
                )
                if row is None:
                    return sent, deferred, faulted, False
                try:
                    with transaction.atomic():
                        raw = recovery.mint(row.user, row.kind)
                        provider_id = sender.send(_compose(row, raw))
                except mailer.TransportError as error:
                    self._defer(row, error.status)
                    deferred += 1
                    continue
                except Exception as error:  # noqa: BLE001
                    self.stdout.write(f"row {row.pk} deferred after {type(error).__name__}")
                    self._defer(row, 0)
                    deferred += 1
                    faulted += 1
                    continue
                AuditEvent.record(
                    AuditEvent.MAIL_SENT,
                    user_id=row.user_id,
                    kind=row.kind,
                    provider_id=provider_id,
                )
                row.delete()
                sent += 1
        return sent, deferred, faulted, True
```

`_report_what_is_stuck` blijft ongewijzigd: spec 7.2 legt uit waarom (wat de grens laat liggen
wordt na `OVERDUE_AFTER` geteld, en dat is precies goed voor een timer die vaak vijftig
verstuurt en toch achterloopt).

- [ ] **Step 5: De test in `tests/test_accounts_mail.py`**

```text
@pytest.mark.django_db
def test_the_cap_stops_the_run_and_leaves_the_rest_for_the_next_tick(_account: User) -> None:
    """Three rows, --max 2: two sent, one left with attempts == 0, and the
    output names the cap."""
    other = User.objects.create_user(email="tweede@voorbeeld.nl", password=TEST_PASSWORD)
    third = User.objects.create_user(email="derde@voorbeeld.nl", password=TEST_PASSWORD)
    for user in (_account, other, third):
        recovery.enqueue(user, OneTimeToken.PASSWORD_RESET)
    out = StringIO()
    call_command("send_outbound_mail", "--max", "2", stdout=out)
    assert OutboundMail.objects.count() == 1
    assert OutboundMail.objects.get().attempts == 0
    assert "stopped at the cap of 2" in out.getvalue()
```

Controleer de bestaande drierijentest voor de vergiftigde rij
(`test_a_poison_row_is_deferred_and_the_others_still_send`): die roept `call_command` zonder
`--max` aan, dus de standaard van 50 verandert er niets aan en de test blijft groen zonder
wijziging.

- [ ] **Step 6: Rood bewijs voor de grens**

Verander `while sent < max_rows:` tijdelijk naar `while True:` (de grens genegeerd). Draai:

```bash
uv run --no-sync pytest tests/test_accounts_mail.py -k cap_stops -v
```

Verwacht: rood, alle drie de rijen zijn verzonden (`OutboundMail.objects.count() == 0`) in
plaats van een die achterblijft. Zet `while sent < max_rows:` terug en draai opnieuw: groen.

- [ ] **Step 7: `infra/README.md`, sectie 3**

Een zin in de sectie "The outbox timer is installed the same way" (of de subsectie eronder die
beschrijft wat het command per run doet):

```text
Every run of `send_outbound_mail` sends at most fifty rows (`--max`, tunable), so a large
backlog drains over several ticks of the timer rather than holding one transaction open for
the whole queue at once.
```

- [ ] **Step 8: De eerste vier branch-gaten**

Elk gat krijgt een test die de tak neemt die vandaag geen enkele test neemt, met een
`--cov-branch`-transcript ervoor en erna dat laat zien dat de pijl uit `Missing` verdwijnt.

**8a. `ampeer_sim/profiles/assets.py:52->48`.** In `tests/test_assets.py`, een dag met een
kleine dagbehoefte en een grote laadcapaciteit, zodat de eerste laadpositie de hele behoefte
al dekt en de `break` op regel 53 vroeg valt in plaats van dat de lus alle posities in het
venster doorloopt:

```text
def test_a_day_that_needs_little_stops_charging_after_the_first_position() -> None:
    """The 52->48 branch: `_allocate_daily`'s inner for-loop exhausting the
    window without ever reaching remaining <= 0.0 is the arm every existing
    test already takes. A day whose need is met on the very first position
    inverts that, and the positions after the first stay at zero."""
    grid = YearGrid(days=1)
    daily_need = np.array([0.5])
    window = (0, QUARTERS_PER_DAY)
    series = _allocate_daily(daily_need, grid, window, cap=4.0)
    assert series[0, 0] == pytest.approx(0.5)
    assert series[0, 1:].sum() == pytest.approx(0.0)
```

Pas de argumenten aan (importnaam van `YearGrid`, `QUARTERS_PER_DAY`, de precieze signatuur van
`_allocate_daily`) aan wat `tests/test_assets.py` al importeert; de test hierboven volgt het
patroon van de andere tests in dat bestand.

**8b. `backend/accounts/lockout.py:64->66`.** In `tests/test_accounts_lockout_callables.py`,
een `username` die geen string is:

```text
def test_a_non_string_username_hashes_the_empty_string() -> None:
    """The `isinstance(value, str)` branch's false arm: axes can hand this
    callable whatever a request's credentials dict happens to carry."""
    request = HttpRequest()
    digest = username(request, {"username": 123})
    assert digest == username(request, {"username": ""})
```

**8c. `backend/accounts/models.py:102->104`.** In `tests/test_accounts_models.py`, `User.save`
met een lege `email`:

```text
@pytest.mark.django_db
def test_saving_a_user_with_no_email_does_not_touch_it() -> None:
    """The `if self.email:` branch's false arm. Normalising an empty string is
    create_user's job (it already refuses one with its own test); this is
    only about what save() itself does when there is nothing to normalise."""
    user = User(email="")
    user.set_unusable_password()
    user.save()
    assert user.email == ""
```

**8d. `backend/accounts/views.py:347->352`.** In `tests/test_accounts_api.py`, uitloggen zonder
refresh-cookie:

```text
@pytest.mark.django_db
def test_logging_out_without_a_refresh_cookie_still_ends_the_session(client: Any) -> None:
    """The `if raw:` branch's false arm in LogoutView.post: an access cookie
    with no refresh cookie beside it, which a client that only ever reads
    ampeer_access can produce."""
    client.post("/api/auth/register/", BODY, content_type="application/json", **_csrf(client))
    client.cookies.pop(settings.AMPEER_REFRESH_COOKIE, None)
    lines_before = AuditEvent.objects.filter(event_type=AuditEvent.LOGOUT).count()
    response = client.post(
        "/api/auth/logout/", content_type="application/json", **_csrf(client)
    )
    assert response.status_code == 204
    assert AuditEvent.objects.filter(event_type=AuditEvent.LOGOUT).count() == lines_before + 1
```

Gebruik de bestaande `_register`- en `_csrf`-helpers uit dit testbestand; pas de namen aan als
ze anders heten.

- [ ] **Step 9: `--cov-branch` voor en na, de vier gaten**

```bash
uv run --no-sync pytest --cov=ampeer_sim --cov=backend --cov-branch --cov-report=term-missing tests/test_assets.py tests/test_accounts_lockout_callables.py tests/test_accounts_models.py tests/test_accounts_api.py -q
```

Verwacht voor de vier nieuwe tests, tijdelijk uitgecommentarieerd: `Missing` noemt
`52->48` bij `ampeer_sim/profiles/assets.py`, `64->66` bij `backend/accounts/lockout.py`,
`102->104` bij `backend/accounts/models.py`, `347->352` bij `backend/accounts/views.py`. Zet de
vier tests terug aan en draai opnieuw: geen van de vier pijlen staat nog in `Missing`.

- [ ] **Step 10: De volle Python-suite**

```bash
uv run --no-sync pytest tests/ -q
```

Verwacht: groen (statement-only dekking; `branch = true` komt pas in taak 8).

- [ ] **Step 11: Commit**

```bash
git add backend/accounts/views.py backend/accounts/nl.py backend/accounts/management/commands/send_outbound_mail.py infra/README.md tests/test_accounts_api.py tests/test_accounts_mail.py tests/test_assets.py tests/test_accounts_lockout_callables.py tests/test_accounts_models.py
git commit -m "$(cat <<'EOF'
fix(accounts): answer 401 in Dutch, cap the outbox batch, close four branch gaps

_AuthAPIView.permission_denied now answers NL["not_signed_in"] instead of
DRF's English default, which every frontend stub and e2e mock already
assumed. send_outbound_mail stops after fifty rows per run (--max) so a
backlog drains over several ticks instead of holding one transaction open
for the whole queue. Four branch arms that statement coverage could not see
(a ternary read as one statement) each get a direct test.

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
EOF
)"
```

---

### Taak 8: Branch-dekking aan, de vloer opnieuw gemeten

**Hangt af van:** taak 7.

**Files:**
- Modify: `pyproject.toml`, `tests/test_pipeline_contract.py`

**Interfaces:**
- Consumes: `[tool.coverage.run]`, `[tool.coverage.report]` in `pyproject.toml`; `MINIMUM_COVERAGE_FLOOR` in `tests/test_pipeline_contract.py`.
- Produces: `branch = true`; een nieuwe `fail_under`, gemeten zonder `data/nedu-profiles-2025.csv`.

Spec hoofdstuk 7.4, tweede helft (de vier branch-gaten zelf zijn taak 7).

- [ ] **Step 1: Zet `data/nedu-profiles-2025.csv` opzij**

```bash
mv data/nedu-profiles-2025.csv data/nedu-profiles-2025.csv.setaside
```

Twee tests wijken uit zonder dat bestand (spec 7.4: zes statements in `nedu.py:87-95`), wat
precies de conditie is die de runner meet. Bevestig dat de map na deze stap geen `.csv` meer
bevat:

```bash
ls data/
```

- [ ] **Step 2: Zet `branch = true` en meet**

In `pyproject.toml`, `[tool.coverage.run]`:

```text
[tool.coverage.run]
source = ["ampeer_sim", "ampeer_advice", "tools", "backend"]
# Branch coverage, aan sinds 2026-09-07, gemeten onder de conditie van de
# runner (zonder data/nedu-profiles-2025.csv). Statement coverage reads a
# multi-line ternary as one statement, which is how the wait is None arm of
# _AuthAPIView.throttled stayed invisible until a reviewer found it with a
# scratch reproduction (decision 40's follow-up, "Whether branch = true
# belongs in the coverage configuration" in docs/decisions.md). Turning it
# on may only happen together with a floor re-measured under it, never by
# lowering the floor; see fail_under below for that measurement.
branch = true
omit = ["backend/manage.py", "backend/ampeer/wsgi.py"]
```

Draai de meting die telt, precies zoals de runner het zou doen:

```bash
uv run --no-sync pytest --cov --cov-branch --cov-report=term-missing:skip-covered -q
```

Lees de laatste regel (`TOTAL ... NN.NN%`) en de statement/branch-tellingen erboven. Noteer het
exacte gecombineerde percentage met twee decimalen.

- [ ] **Step 3: `fail_under`, een honderdste onder de meting**

In `[tool.coverage.report]`:

```text
[tool.coverage.report]
precision = 2
# Measured at two decimals, not read off the rounded TOTAL row. Raised from
# 97 to 98 on 2026-08-20, from 98 to 99.05 on 2026-09-06, from 99.05 to
# 99.15 on 2026-09-07 at the end of the accounts recovery branch, and from
# 99.15 to <GEMETEN_FAIL_UNDER> on 2026-09-07 at the end of the legal and
# tidy branch, the first measurement with branch = true on. This is a new
# measure, statement plus branch together, and it therefore sits below what
# the statement-only figure on the same tree reports; the statement-only
# number stays above 99.15 on this tree, and no protection has been removed
# by the drop in the number reported here. May be raised, never lowered.
#
# The floor sits one hundredth under the measurement, for the reason
# pytest-cov compares round(total, precision) with fail_under and a floor
# equal to the rounded measurement can round up on a machine that measures a
# hair lower.
#
# The measurement that counts is the CI runner's, not a developer machine's:
# set the floor from a run without data/, or from the runner itself.
fail_under = <GEMETEN_FAIL_UNDER>
show_missing = true
```

Vervang `<GEMETEN_FAIL_UNDER>` in beide plekken (het commentaar en de waarde) door het cijfer
uit Step 2 min 0,01, op twee decimalen. Spec 7.4 verwacht dit rond de 98,5; het exacte cijfer
komt van de meting op de machine die deze taak uitvoert, nooit van een schatting vooraf.

- [ ] **Step 4: `tests/test_pipeline_contract.py`, gelezen en zo nodig aangepast**

```bash
uv run --no-sync pytest tests/test_pipeline_contract.py -k coverage -v
```

`MINIMUM_COVERAGE_FLOOR = 98` staat er al en `test_the_coverage_floor_is_not_lowered` eist
`fail_under >= 98`; het nieuwe cijfer uit Step 3 blijft daarboven, dus deze test hoeft niet te
veranderen. `test_the_coverage_comparison_is_not_rounded_away` eist `precision >= 2`, wat
`precision = 2` blijft. De omit-lijst in `pyproject.toml` verandert niet, dus
`test_the_coverage_omit_list_stays_short_and_justified` blijft ook ongewijzigd. Is een van de
drie toch rood na Step 2 en Step 3 (bijvoorbeeld omdat de meting op deze machine onder 98 komt),
dan stopt deze taak en meldt dat met het gemeten cijfer erbij: de vloer gaat niet onder het
minimum, de oplossing is meer dekking en geen ander minimum.

- [ ] **Step 5: Rood bewijs, twee kanten**

Zet `fail_under` tijdelijk een vol procentpunt hoger dan het gemeten cijfer (bijvoorbeeld
`fail_under = 99.50` als de meting 98,51 was) en draai:

```bash
uv run --no-sync pytest --cov --cov-branch -q
```

Verwacht: rood, pytest-cov meldt "FAIL Required test coverage of 99.50% not reached" en de
exitcode is niet nul. Zet `fail_under` terug op het echte, gemeten cijfer. Draai vervolgens:

```bash
uv run --no-sync pytest tests/test_pipeline_contract.py -k test_the_coverage_floor_is_not_lowered -v
```

Zet `fail_under` tijdelijk op `97.00` (onder `MINIMUM_COVERAGE_FLOOR`). Verwacht: rood op deze
ene test. Zet `fail_under` terug op het echte cijfer.

- [ ] **Step 6: Zet het NEDU-bestand terug**

```bash
mv data/nedu-profiles-2025.csv.setaside data/nedu-profiles-2025.csv
```

Bevestig dat de meting op deze machine met het bestand terug hoger uitvalt of gelijk blijft,
nooit lager (de zes extra statements in `nedu.py:87-95` kunnen alleen dekking toevoegen):

```bash
uv run --no-sync pytest --cov --cov-branch --cov-report=term -q
```

- [ ] **Step 7: De volle Python-suite, op de voorgrond**

```bash
uv run --no-sync pytest tests/ -q
```

Verwacht: groen, exitcode 0. Dit is ook de eerste keer in deze cyclus dat de volle suite draait
onder `branch = true`; blijft er iets anders rood dan wat taak 7 al dekte, dan onthult dat een
vijfde branch-gat dat spec 7.4's meting op 2026-09-07 niet vond (de meting is een momentopname
van die dag op die machine) en deze taak krijgt er dan een test bij op dezelfde manier als
taak 7's vier, met zijn eigen rode bewijs, voordat hij verder gaat.

- [ ] **Step 8: Commit**

```bash
git add pyproject.toml tests/test_pipeline_contract.py
git commit -m "$(cat <<'EOF'
build(coverage): turn branch coverage on, with a floor measured under it

Statement coverage reads a multi-line ternary as one statement, so an arm
no test takes still counts as covered; that is how the wait is None arm of
_AuthAPIView.throttled stayed invisible until found by hand. branch = true
now, with fail_under set one hundredth under a fresh measurement taken
without data/nedu-profiles-2025.csv, the condition the CI runner measures
under. MINIMUM_COVERAGE_FLOOR in test_pipeline_contract.py already covers
the new figure, so that file's assertions hold without change.

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
EOF
)"
```

Is `tests/test_pipeline_contract.py` in Step 4 toch gewijzigd, staged dat bestand dan mee in
deze commit en zegt de boodschap erbij welke assertie is aangepast en waarom.

---

### Taak 9: DPIA, `decisions.md`, de drie verouderde zinnen

**Hangt af van:** taak 8.

**Files:**
- Modify: `docs/dpia.md`, `docs/decisions.md`, `docs/superpowers/specs/2026-09-04-accounts-auth-design.md`, `docs/superpowers/specs/2026-09-05-accounts-frontend-design.md`, `docs/superpowers/plans/2026-09-04-accounts-auth.md`, `tests/test_dpia.py`

**Interfaces:**
- Consumes: `docs/verwerkersregister.md` (taak 6); `identity.ts`'s toestemming (taak 2).
- Produces: DPIA hoofdstuk 5 en 10 herschreven; `docs/decisions.md` entries 49 tot en met 55; drie gedateerde correcties; een test erbij in `tests/test_dpia.py`.

Spec hoofdstuk 6 en 7.3.

- [ ] **Step 1: DPIA hoofdstuk 10, punt 2**

Vervang het huidige punt 2 (dat begint met "Voorlopig gekozen: **toestemming**...") door:

```text
2. **De grondslag.** Beantwoord op 2026-09-07: toestemming. De privacyverklaring
   beschrijft het zo, en `identity.ts` draagt het. De keuze van 2026-09-02 voor
   overeenkomst is daarmee vervallen.
```

Het aantal genummerde punten blijft vijf en het openingswoord "Vijf dingen kan dit document
niet..." blijft ongewijzigd: `tests/test_dpia.py::test_the_chapter_of_open_decisions_states_how_many_there_are`
telt de punten en dit punt blijft op de lijst staan, beantwoord in plaats van verwijderd
(anders dan het verwijderpunt eerder, dat volledig uit de lijst verdween).

- [ ] **Step 2: DPIA hoofdstuk 10, de slotalinea**

Vervang de alinea die begint met "Er is verder geen privacyverklaring..." door:

```text
Er is een privacyverklaring op `/privacy/`, herschreven op 2026-09-07 voor fase 1.
Er is een register in `docs/verwerkersregister.md`, gebonden door
`tests/test_verwerkersregister.py`. Wat er niet is en bij de
verwerkingsverantwoordelijke blijft: de vastgelegde aanvaarding van Cloudflares
verwerkersovereenkomst en de beoordeling van Resends DPA (punt 5).
```

De instructiezinnen "Voor het register: ..." en "Voor de privacyverklaring: ..." die in de
oude alinea stonden, verdwijnen mee: ze zijn uitgevoerd.

- [ ] **Step 3: DPIA hoofdstuk 5, een verwijzing naar het register**

Na de laatste zin van de Resend-alinea ("... geen enkel verzoek van een bezoeker doet dat."),
een nieuwe zin:

```text
Beide verwerkers staan ook in `docs/verwerkersregister.md`, hoofdstuk 8.
```

- [ ] **Step 4: `tests/test_dpia.py`, een test erbij**

```text
def test_the_document_points_at_the_register_and_the_statement() -> None:
    """Chapter 10's closing paragraph and chapter 5's Resend paragraph both
    point at the register this cycle added; red-proof: remove either sentence
    by hand and rerun."""
    assert "verwerkersregister.md" in TEXT
    chapter_10 = TEXT.split("## 10. Wat bij Stijn ligt", 1)[1]
    assert "verwerkersregister.md" in chapter_10
    chapter_5 = TEXT.split("## 5. Wie erbij kan", 1)[1].split("## 6.", 1)[0]
    assert "verwerkersregister.md" in chapter_5
```

- [ ] **Step 5: Rode bewijzen voor de DPIA**

```bash
uv run --no-sync pytest tests/test_dpia.py -v
```

1. Verwijder tijdelijk de zin uit hoofdstuk 5 (Step 3). Verwacht: rood op
   `test_the_document_points_at_the_register_and_the_statement`. Zet terug.
2. Verwijder tijdelijk `docs/verwerkersregister.md` uit de slotalinea van hoofdstuk 10 (Step
   2). Verwacht: rood op dezelfde test. Zet terug.
3. Verander tijdelijk "Vijf dingen" in de openingszin van hoofdstuk 10 naar "Vier dingen".
   Verwacht: rood op `test_the_chapter_of_open_decisions_states_how_many_there_are`. Zet terug.

Draai vervolgens de rode proef die taak 6 opende:

```bash
uv run --no-sync pytest tests/test_verwerkersregister.py -v
```

Verwacht: `test_the_dpia_no_longer_says_there_is_no_register` is niet langer `xfail`; verwijder
de `@pytest.mark.xfail(...)`-decorator die taak 6 erop zette, en de test slaagt zelf. Draai
opnieuw zonder de decorator: groen.

- [ ] **Step 6: `docs/decisions.md`, zeven nieuwe entries**

Na entry 48, voor "## What was not decided here":

```text
### 49. The legal basis for the account is consent, and the 2026-09-02 choice for a contract is reversed

**Decided:** `identity.ts`'s `legalBasis` is `"toestemming"`; chapter 10 point 2 of
`docs/dpia.md` answers the same way, dated 2026-09-07.

**Because:** article 7(4) AVG: `RegisterSerializer` accepts registration with or
without `METER_LINK` consent, so the service does not depend on a consent it does
not need, which is what a consent basis requires and a contract basis does not.
The code already runs two separate, unchecked consents with their own timestamp
and text version, which a consent basis needs and a contract basis has no use
for. The owner confirmed the choice on 2026-09-07.

**Lives in:** `legalBasis` in `frontend/src/app/privacy/identity.ts`, chapter 10
point 2 of `docs/dpia.md`.

**To reverse:** set `legalBasis` back to `"overeenkomst"` and rewrite the DPIA
point and `identity.ts`'s comment. Nothing in `Consent`, `RegisterSerializer` or
the account flow changes, because none of it depended on which basis this text
names.

### 50. The site has a terms page, and it carries the disclaimer the advice needs

**Decided:** `/voorwaarden/` exists, is a server component gated by
`requireCompleteIdentity` like `/privacy/` and `/over-ons/`, and holds the
disclaimer that the advice is an estimate and not a promise.

**Because:** a disclaimer that sat on a methodology page is one nobody finds at
the moment it matters. The owner chose a dedicated route over a section, on
2026-09-07.

**Lives in:** `frontend/src/app/voorwaarden/page.tsx`.

**To reverse:** fold the eight sections back into `/methodologie/` or
`/over-ons/` and remove the route from `SITEMAP_ROUTES`, the footer and the two
e2e route lists.

### 51. The article 30 register is a document in this repository, bound by a test

**Decided:** `docs/verwerkersregister.md`, ten chapters, bound by
`tests/test_verwerkersregister.py` the way `tests/test_dpia.py` binds the
assessment.

**Because:** everything a register needs was already in this repository, in the
DPIA's assessment form rather than a register's form. `docs/dpia.md` chapter 10
said "no register" since phase 1, which stopped being true the day the content
existed to write one from.

**Lives in:** `docs/verwerkersregister.md`, `tests/test_verwerkersregister.py`.

**To reverse:** delete both and put the sentence back in chapter 10.

### 52. A 401 on `/api/auth/` answers in Dutch from this project's own table, like the 429

**Decided:** `_AuthAPIView.permission_denied` raises `NotAuthenticated(NL["not_signed_in"])`
rather than letting DRF's own version answer with its untranslated default.

**Because:** decision 40 already did this for a 429; a 401 was the same gap.
Every frontend stub and e2e mock already answered `NL["not_signed_in"]`, so each
one disagreed with the real server on every one of the six signed-in routes
until this override existed.

**Lives in:** `permission_denied` in `backend/accounts/views.py`,
`NL["forbidden"]` in `backend/accounts/nl.py`.

**To reverse:** delete the override and update every frontend stub and e2e mock
to expect DRF's English default instead.

### 53. The outbox command sends at most fifty mails per run

**Decided:** `send_outbound_mail --max` defaults to 50; a run stops after
sending that many rows and says so in its output.

**Because:** `_deliver`'s `while True` loop was theoretical at two mails a day
and a real liability at a backlog of hundreds, where one run would hold a
transaction open hundreds of times for ten seconds each. `_report_what_is_stuck`
still counts what the cap leaves behind after `OVERDUE_AFTER`, which is exactly
right for a timer that sends fifty a minute and still falls behind.

**Lives in:** `add_arguments`, `_deliver` in
`backend/accounts/management/commands/send_outbound_mail.py`.

**To reverse:** drop `--max` and go back to draining the whole outbox in one
run.

### 54. Branch coverage is on, with a floor measured under it

**Decided:** `branch = true` in `[tool.coverage.run]`; `fail_under` set one
hundredth under a fresh measurement taken without
`data/nedu-profiles-2025.csv`.

**Because:** statement coverage reads a multi-line ternary as one statement,
which is how the `wait is None` arm of `_AuthAPIView.throttled` stayed
invisible until a reviewer found it by hand, recorded as an open question after
decision 40. Four such gaps were found and closed on 2026-09-07 before the
floor was measured.

**Lives in:** `[tool.coverage.run]`, `[tool.coverage.report]` in
`pyproject.toml`.

**To reverse:** set `branch = false` and return `fail_under` to the
statement-only figure; `MINIMUM_COVERAGE_FLOOR` in
`tests/test_pipeline_contract.py` stays the floor under either.

### 55. Registration says when an address is taken, and the reset route does not; recorded as a choice

**Decided:** `register/` keeps answering 400 with `NL["email_taken"]` for an
address that already has an account; `reset/request/` keeps answering the same
202 for every address.

**Because:** registration logs a household in immediately and shows the account
view, and an answer for a taken address cannot be made identical to that
without giving up the immediate sign-in, which would cost every new household
an extra step and need a third kind of mail. `auth-register` sits at five an
hour per caller, which makes an address book slow to run; and reset, the route
an attacker could use one, stays closed.

**Lives in:** `RegisterSerializer.validate_email` in
`backend/accounts/serializers.py`, `request_password_reset` in
`backend/accounts/recovery.py`.

**To reverse:** if phase 2 drops the immediate sign-in after registration, for
instance because a meter may only hang off a confirmed address, this is the
moment to make the two routes agree.
```

- [ ] **Step 7: De twee open lijsten in `docs/decisions.md`**

In "## What was not decided here", na de zin over de deletion-vraag die al eerder is
beantwoord, een nieuwe zin:

```text
A second point that used to stand there the same way, the legal basis, is
answered without being dropped: chapter 10 point 2 of `docs/dpia.md` stays on
that numbered list of five and says so, and decision 49 above is the same
answer stated as a decision.
```

Verwijder de bullet "Whether `branch = true` belongs in the coverage configuration
(`pyproject.toml`)." uit de lijst die opent met "Nine sit outside that document." Tel de
overgebleven bullets (acht) en verander de openingszin in:

```text
Eight sit outside that document.
```

- [ ] **Step 8: De drie verouderde zinnen**

In elk van de drie documenten, direct onder de genoemde zin, een nieuwe alinea die begint met
"Gecorrigeerd op 2026-09-07:". Dezelfde tekst in de twee specs; het plan krijgt de correctie als
tekst na het codeblok, met het blok zelf ongewijzigd (spec 7.3: "een plan is een verslag van wat
er is voorgeschreven").

`docs/superpowers/specs/2026-09-04-accounts-auth-design.md`, na regel 657 (de zin over
`localhost:3000` naar `127.0.0.1:8000`):

```text
Gecorrigeerd op 2026-09-07: sinds commit `2109901` staat `localhost:3000` niet
meer in `CORS_ALLOWED_ORIGINS` van `backend/ampeer/settings/dev.py`. Een cookie
hoort bij een site, en `localhost` en `127.0.0.1` zijn twee sites; het aantal
oorsprongen dat `dev.py` toestaat is sindsdien geen drie meer. Zie beslissing
104 in `docs/decisions.md` en `tests/test_backend_settings.py`.
```

`docs/superpowers/specs/2026-09-05-accounts-frontend-design.md`, na regel 102 (dezelfde zin,
"Op een ontwikkelmachine is..."):

```text
Gecorrigeerd op 2026-09-07: dezelfde correctie als in
`2026-09-04-accounts-auth-design.md`. `localhost:3000` staat sinds commit
`2109901` niet meer in `CORS_ALLOWED_ORIGINS` van `backend/ampeer/settings/dev.py`;
het commentaar boven die lijst zegt waarom, en
`tests/test_backend_settings.py` houdt het vast.
```

`docs/superpowers/plans/2026-09-04-accounts-auth.md`, na het codeblok op regel 1132-1143 (het
codeblok zelf blijft ongewijzigd):

```text
Gecorrigeerd op 2026-09-07: dit codeblok is een verslag van wat destijds is
voorgeschreven en blijft daarom staan, maar de tekst erboven ("localhost:3000
naar 127.0.0.1:8000 is cross-site") klopt sinds commit `2109901` niet meer voor
het aantal oorsprongen: `localhost:3000` is uit `CORS_ALLOWED_ORIGINS` van
`backend/ampeer/settings/dev.py`. De reden staat in het commentaar boven
`CORS_ALLOWED_ORIGINS` in dat bestand, en `tests/test_backend_settings.py`
houdt hem vast.
```

- [ ] **Step 9: `tests/test_decisions.py` en `tests/test_dpia.py`, ongewijzigd getoetst**

```bash
uv run --no-sync pytest tests/test_decisions.py tests/test_dpia.py -v
```

Verwacht: groen. `tests/test_decisions.py` eist dat elk pad achter "Lives in" bestaat en elk
symbool in die bestanden voorkomt; controleer dat handmatig voor de zeven nieuwe entries voordat
je de suite draait, want een test die slaagt op een pad dat toevallig ook ergens anders bestaat
is geen bewijs dat het juiste pad is geciteerd.

- [ ] **Step 10: Rood bewijs voor de nieuwe entries**

Verander tijdelijk het pad in entry 50's "Lives in" naar `frontend/src/app/voorwaarden/pagina.tsx`
(een tikfout). Draai:

```bash
uv run --no-sync pytest tests/test_decisions.py -v
```

Verwacht: rood, `test_every_lives_in_path_exists` (of de vergelijkbare naam in dat bestand)
faalt op het niet-bestaande pad. Zet het pad terug.

- [ ] **Step 11: De volle Python-suite**

```bash
uv run --no-sync pytest tests/ -q
```

Verwacht: groen.

- [ ] **Step 12: Commit**

```bash
git add docs/dpia.md docs/decisions.md docs/superpowers/specs/2026-09-04-accounts-auth-design.md docs/superpowers/specs/2026-09-05-accounts-frontend-design.md docs/superpowers/plans/2026-09-04-accounts-auth.md tests/test_dpia.py
git commit -m "$(cat <<'EOF'
docs(dpia): answer the legal basis, add the register, close three stale corrections

DPIA chapter 10 point 2 now says consent, dated 2026-09-07, and its closing
paragraph names the privacy statement and the register that now exist.
docs/decisions.md records seven entries, 49 through 55, for what this cycle
settled: the legal basis, the terms page, the register, the Dutch 401, the
outbox cap, branch coverage, and the enumeration on register/. Three closed
documents that said localhost:3000 was still cross-site (obsolete since
commit 2109901) each carry a dated correction rather than a rewrite.

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
EOF
)"
```

---

### Taak 10: De status omzetten en de poorten draaien

**Hangt af van:** taak 9.

**Files:**
- Modify: `docs/superpowers/plans/2026-09-07-legal-and-tidy.md`

**Interfaces:**
- Consumes: alles wat taak 1 tot en met 9 hebben opgeleverd.
- Produces: `**Status:** delivered` op regel 5; de bevestiging dat elke poortgroep van
  `scripts/gates.sh` exit 0 geeft op de eindboom.

Spec hoofdstuk 8.4 en de Definition of done (hoofdstuk 11).

- [ ] **Step 1: De volledige `scripts/gates.sh`, op de voorgrond, terwijl de marker nog aan staat**

```bash
scripts/gates.sh
```

Alle groepen: `sync`, `ruff`, `ruff-format`, `mypy`, `django-deploy-check`, `pre-commit`,
`bandit`, `semgrep`, `pip-audit`, `sbom`, en de groepen die de Python-tests, de frontend-build,
`pnpm e2e` en de compose-teststack draaien (`test`, waaronder `tests/test_stack_smoke.py`, dat
`infra/compose.test.yml` zelf opstart en afbreekt zoals rule 7 van het herstelplan voorschrijft).
Beoordeel elke gate op zijn eigen exitcode; het script zegt aan het eind welke gates NOT RUN
waren en dat telt niet als geslaagd.

De marker staat hier nog op `in progress`: als iets rood is, is dat precies wanneer je het wilt
weten, voordat de statusregel iets belooft dat niet waar is.

- [ ] **Step 2: Corrigeer wat `pre-commit` verandert, als er iets is**

`pre-commit`'s `ruff-format`-hook herschrijft geformatteerde Python-bestanden in de werkboom
zonder dat dat een aparte foutmelding geeft; `git status` na Step 1 laat zien of er iets
gewijzigd is in een bestand dat deze cyclus al aanraakte (met name `tests/test_verwerkersregister.py`,
`backend/accounts/views.py`, `backend/accounts/nl.py`,
`backend/accounts/management/commands/send_outbound_mail.py`, en de vier nieuwe
branch-gattests uit taak 7).

```bash
git status --short
git diff --stat
```

Is er een diff, staged en commit die apart:

```bash
git add -A
git commit -m "$(cat <<'EOF'
style: apply what pre-commit reformatted across the branch

scripts/gates.sh's pre-commit group is the first run of ruff-format over
the whole tree in this cycle; this commit is exactly its output.

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
EOF
)"
```

Is er geen diff, sla deze commit over en zeg dat met zoveel woorden in de boodschap van Step 4.

- [ ] **Step 3: Draai `scripts/gates.sh` opnieuw als Step 2 iets committede**

```bash
scripts/gates.sh
```

Verwacht: groen, elke gate exit 0, geen enkele NOT RUN die wel had kunnen draaien op deze
machine.

- [ ] **Step 4: Flip de marker**

Regel 5 van dit document, en alleen die regel:

```text
**Status:** delivered
```

Voeg direct erna, zoals `2026-09-06-accounts-recovery.md` dat doet, een gedateerde
bevestigingsalinea toe, op kolom 0 en niet ingesprongen (de `> `-markering houdt hem
al buiten het bereik van de tripwire in `tests/test_plans.py`; vier spaties inspringen
zou hem juist als codeblok laten renderen in plaats van als citaat):

```text
> **Status op 2026-09-07: opgeleverd.** Elk bestand dat dit plan noemt staat
> in de boom. `tests/test_plans.py` controleert dat voor alle plannen in
> `docs/superpowers/plans/`, en het wordt rood op de dag dat een van hen
> niet meer klopt. Wat die test niet kan zeggen is of elke stap is
> uitgevoerd zoals hij hier staat; daar zijn de commitgeschiedenis en de
> suite voor.
```

- [ ] **Step 5: Bevestig dat de strenge lezing nu van toepassing is, en groen is**

```bash
uv run --no-sync pytest tests/test_plans.py -q
```

Verwacht: groen. Met `**Status:** delivered` valt dit plan onder
`test_every_file_a_finished_plan_names_exists`, die nu elk genoemd bestand in de boom moet
vinden; is er een gemist bestand (een tikfout in een pad, bijvoorbeeld), dan meldt deze test dat
met de naam van het ontbrekende bestand, en dat is de reden om `test_plans.py` hier te draaien
voordat de laatste commit wordt gemaakt en niet erna.

- [ ] **Step 6: Commit**

```bash
git add docs/superpowers/plans/2026-09-07-legal-and-tidy.md
git commit -m "$(cat <<'EOF'
docs(plans): mark the legal and tidy plan delivered

Every gate in scripts/gates.sh passed on the foreground run, including the
compose-backed stack smoke suite, which is the proof this branch did not
break the 28 live checks it did not otherwise touch. tests/test_plans.py
now holds this plan to its strict reading: every file it names exists.

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
EOF
)"
```

Geen pull request in deze taak: de PR naar `dev` is een handeling van de eigenaar, niet van dit
plan.

---

## Zelfcontrole na het schrijven

### Dekking van de spec, hoofdstuk voor hoofdstuk

| Spec | Eis | Taak |
|---|---|---|
| 1 | binnen scope: privacy herschrijven, `/voorwaarden/`, register, code-schuld; buiten scope: fase 2, Resend-account/DNS/host, aanvaarding Cloudflare-overeenkomst, Resend-DPA-beoordeling, cookiemelding, analyseprogramma, `register/`-wijziging, nieuwe afhankelijkheid, `api.ts` | 2 tot en met 9; geen taak raakt `frontend/src/lib/api.ts`, geen taak voegt een afhankelijkheid toe, geen taak wijzigt `register/` |
| 2.1 | `privacyEmail` erbij, `legalBasis: "toestemming"`, `IDENTITY_FIELDS`/`IDENTITY_FIELD_HELP` bijgewerkt, bewaking ongewijzigd van vorm | 2 |
| 2.2 | de omgedraaide identiteitstest, rood bewijs met een tijdelijke sentinel | 2 |
| 3.1 | drie principes blijven (DPIA-bron, tien tot vijftien woorden, geen ongefundeerde claim) | 3 |
| 3.2 | acht secties herschreven, twee secties nieuw (account, Resend) | 3 |
| 3.3 | precies de drie Resend-feiten, niet meer | 3 |
| 3.4 | de tests op `:222-326`, blijft/verandert/komt erbij/gaat weg | 3 |
| 4.1 | de route, metadata, `SITEMAP_ROUTES`, `legal.module.css` hergebruikt, de identiteitstest over drie pagina's | 4 (route, metadata, sitemap, css), 4 (identiteitstest, samen met de default-exports lus) |
| 4.2 | acht secties in de vastgelegde volgorde, de vijf regels van `frontend/CLAUDE.md` | 4 |
| 4.3 | de vijfde voettekstlink met het commentaar, de reciproke links, de twee complete routelijsten, de bindingstest | 4 (voettekst, links), 5 (routelijsten, bindingstest) |
| 4.4 | axe in beide paletten, `/voorwaarden/` in de axe-sweep | 5 |
| 5.1 | het document bestaat, gebonden zoals de DPIA | 6 |
| 5.2 | tien hoofdstukken, acht kopjes per verwerking, de negen tabellen bij naam | 6 |
| 5.3 | acht tests (spec noemt zeven als samenvattend getal; de itemlijst telt acht, zie de kanttekening in taak 6), elk met rood bewijs | 6 |
| 6.1 | DPIA hoofdstuk 10 punt 2 beantwoord, de slotalinea herschreven, hoofdstuk 5 wijst naar het register, een test erbij | 9 |
| 6.2 | zeven entries in `docs/decisions.md`, de twee open lijsten bijgewerkt | 9 |
| 7.1 | `permission_denied`, `NL["forbidden"]`, twee tests, rood bewijs | 7 |
| 7.2 | `--max`, de test, de `infra/README.md`-zin | 7 |
| 7.3 | drie gedateerde correcties, geen herschrijving van het plan-codeblok | 9 |
| 7.4 | vier branch-gaten met test, `branch = true`, de vloer opnieuw gemeten zonder `data/` | 7 (vier gaten), 8 (`branch = true`, de vloer) |
| 7.5 | beslissing zonder code, vastgelegd | 9 (decision 55) |
| 8.1 | laag 1 (Python) | 2, 6, 7, 8, 9 |
| 8.2 | laag 2 (Vitest) | 2, 3, 4 |
| 8.3 | laag 3 (Playwright) | 5 |
| 8.4 | de poorten, op de eindboom, op exitcode | 10 |
| 9 | wat expliciet niet in deze cyclus zit | geen taak bouwt dit; taak 9's decision 55 noemt `register/` met zoveel woorden als bewust ongewijzigd |
| 10 | de bestandenlijst | elk bestand daaruit staat in precies een Files-blok, behalve de gedeelde die de Bestandsbezit-tabel en de "Gedeelde bestanden"-alinea noemen |
| 11 | definition of done | taak 10 draait wat elk punt afdwingt (`scripts/gates.sh`, `tests/test_plans.py`) |
| 12 | de zeven beslissingen | 9 |

### Plaatshouders

Doorzocht op `TBD`, `TODO`, `vergelijkbaar met taak`, `similar to task`, `naar behoefte`, `nader
te bepalen`, `appropriate` en `...`. Geen van de eerste zeven komt voor. De negentien treffers
op `...` zijn stuk voor stuk ofwel JSX-spread-syntax in TypeScript-codevoorbeelden (`{...FILLED}`,
`[...container.querySelectorAll(...)]`), ofwel de manier waarop dit plan, net als
`2026-09-06-accounts-recovery.md` op zijn regel 5167, een bestaande zin citeert door het begin en
het eind ervan te noemen met een weglating ertussen ("Vervang de alinea die begint met '...'
door:"). Geen enkele stap zegt "doe hetzelfde als hierboven" of "zie de vorige taak" zonder de
concrete inhoud erbij te zetten.

### Namen die over taakgrenzen heen moeten kloppen

Gecontroleerd op elke plek waar ze voorkomen: `privacyEmail`, `IDENTITY_FIELDS`,
`IDENTITY_FIELD_HELP`, `requireCompleteIdentity`, `CompleteIdentity`, `FILLED`, `FILLED_CONSENT`,
`legalBasis`, `LegalBasisParagraphs`, `TermsPage`, `VoorwaardenPage`, `voorwaardenMetadata`,
`SITEMAP_ROUTES`, `SiteFooter`, `PAGES`, `ALL_PATHS`, `ADVICE_PATH`, `stringArrayNamed`,
`_model_class_names`, `NUMBER_WORDS`, `_DUTCH_NUMERALS`, `_int_constant`, `MODELS`,
`ACCOUNT_MODELS`, `SETTINGS`, `OUTBOUND_MODULES`, `permission_denied`, `NL["forbidden"]`,
`NL["not_signed_in"]`, `_AuthAPIView`, `--max`, `_deliver`, `_report_what_is_stuck`,
`MINIMUM_COVERAGE_FLOOR`, `fail_under`, `branch`, `AuditEvent`, `docs/verwerkersregister.md`,
`tests/test_verwerkersregister.py`, de zeven decision-nummers 49 tot en met 55. Een ding dat
tijdens deze doorloop is rechtgetrokken: taak 6's `_model_class_names` wordt door taak 9's
DPIA-test niet hergebruikt (die leest `docs/dpia.md`, niet de modellen), dus er is geen
afhankelijkheid van taak 6 naar taak 9 anders dan via `docs/verwerkersregister.md`'s bestaan,
wat de Volgorde-tabel al vastlegt.

### Kan elke rode-proef echt vuren

Per taak nagelopen. Taak 1: een letter in de marker laat de strenge lezing negen ontbrekende
bestanden vinden. Taak 2: `privacyEmail` op de sentinel zetten raakt de omgedraaide
identiteitstest. Taak 3: elke nieuwe zin tijdelijk verwijderen raakt de bijbehorende nieuwe
assertie, en de toestemmingstak-alinea verwijderen raakt de nieuwe grondslagtest. Taak 4: de
vijfde voettekstlink verwijderen raakt de "reaches all five"-test, de sitemap-regel verwijderen
raakt de sitemap-test, een zin uit de voorwaardenpagina verwijderen raakt de nieuwe suite, en
`requireCompleteIdentity` omzeilen raakt `pnpm typecheck`. Taak 5: een route uit `PAGES` of
`ALL_PATHS` verwijderen raakt de nieuwe bindingstest in `LegalPages.test.tsx`, de lengte
veranderen raakt de eigen lengtetest. Taak 6: elke tabel, elke verwerker, elk getal, elk telwoord,
elke em-dash, elke hoofdstuknummering en de KvK apart tijdelijk gewijzigd raakt precies een van
de acht tests; de negende proef (de DPIA-zin) is bewust `xfail` tot taak 9. Taak 7: de override
weghalen laat DRF's Engelse zin terug, de grens negeren laat alle drie de rijen verzenden, elk
van de vier branch-tests tijdelijk uitschakelen laat de bijbehorende pijl terugkeren in
`--cov-branch`'s `Missing`. Taak 8: `fail_under` boven de meting zetten geeft exit 1, eronder
zetten onder het minimum raakt `test_the_coverage_floor_is_not_lowered`. Taak 9: elke
DPIA-verwijzing en elk decision-pad apart tijdelijk verminkt raakt de bijbehorende test. Taak 10:
dit is de taak die de rode proeven van de vorige negen bevestigt door ze allemaal tegelijk te
laten slagen; zijn eigen proef is `tests/test_plans.py` die van rood (marker aan, negen missende
bestanden) naar groen gaat zodra de marker omslaat en alles bestaat.

### Zijn de afhankelijkheden eerlijk over gedeelde bestanden

`frontend/tests/app/LegalPages.test.tsx` wordt door taak 2, 3, 4 en 5 geschreven, in die
volgorde: taak 2 de identiteitssuite, taak 3 de privacy-suite, taak 4 de voorwaarden-suite plus
de voettekst- en sitemaptests, taak 5 de e2e-bindingstest. `frontend/tests/ui-strings.txt` door
taak 3 en taak 4, elk met zijn eigen regeneratie en zijn eigen diff. `docs/superpowers/plans/2026-09-07-legal-and-tidy.md`
door taak 1 en taak 10, met acht taken ertussen die het niet aanraken. Geen enkel bestand wordt
door twee taken geschreven die niet in de volgorde van de serie op elkaar volgen, en de keten is
de serie zelf: dit plan draait serieel, dus "in die volgorde" is hetzelfde als "nooit tegelijk".

### De markering

De regel `**Status:** in progress` staat op regel 5, op kolom 0, en komt in die vorm precies een
keer in dit document voor. Taak 10 stap 4 toont een tweede `**Status:** delivered` op kolom 0, in
een codeblok, die laat zien wat er komt te staan; `_STATUS.search` in `tests/test_plans.py` geeft
alleen de eerste treffer terug en die staat op regel 5, dus deze latere, voorbeeldmatige regel
verandert niets aan wat de tripwire leest. De bevestigingsalinea daarna staat vier spaties
ingesprongen, zoals het commentaar in `tests/test_plans.py` voorschrijft voor een voorbeeld dat
niet als tweede marker gelezen mag worden. De omzetting in taak 10 stap 4 is een gerichte
bewerking van die ene regel, nooit een replace-all.
