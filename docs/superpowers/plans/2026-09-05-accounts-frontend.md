# Frontend accounts: implementatieplan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Status:** delivered

> **Status op 2026-09-06: opgeleverd.** Elk bestand dat dit plan noemt staat in
> de boom, wat `tests/test_plans.py` voor alle acht plannen controleert en wat
> rood wordt op de dag dat een ervan niet meer klopt. Wat die test niet kan
> zeggen is of elke stap is uitgevoerd zoals hij hier staat; daar zijn de
> commitgeschiedenis en de suite voor.

**Goal:** Een bezoeker komt via de voettekst op `/account/`, maakt daar een account aan met beide toestemmingen geweigerd, ziet zijn account, zet een toestemming aan, exporteert zijn gegevens en verwijdert zijn account, zonder dat de anonieme rekenmachine iets van dat alles merkt.

**Architecture:** Eén statisch geëxporteerde route `/account/` met drie weergaven op één pagina, waarvan de toestand uitsluitend uit `GET /api/auth/me/` komt. Een tweede API-client `frontend/src/lib/accounts.ts` naast `api.ts`, met `credentials: "include"` en de `X-CSRFToken`-header op elke onveilige methode, terwijl `api.ts` ongewijzigd blijft met zijn `credentials: "omit"`. De ene backend-wijziging is een negende route `GET /api/auth/consent-texts/` plus het veld `text_version` op `register/` en `consent/`, zodat de getoonde toestemmingstekst en de vastgelegde rij niet uiteen kunnen lopen.

**Tech Stack:** Next 16, React 19, TypeScript 5.9 strict, Tailwind 4, Vitest, Playwright, pnpm; Django 5.2 + DRF voor het ene endpoint.

**Spec:** docs/superpowers/specs/2026-09-05-accounts-frontend-design.md

## Global Constraints

- De site wordt statisch geëxporteerd (`output: "export"`). Er rendert niets per verzoek, er is geen `middleware.ts` en er kan er geen zijn: `out/account/index.html` is een bestand dat iedereen kan opvragen.
- De browser praat rechtstreeks met de API. Geen fetch vanaf een server, in geen enkele richting.
- `frontend/src/lib/api.ts` wordt niet gewijzigd, en `credentials: "omit"` staat er na de spread. Geen taak in dit plan noemt dat bestand in zijn Files-blok.
- Geen retry, op geen enkele status, met één uitzondering: de ene tokenwissel bij het laden van `/account/` (spec 2.1). Die staat in `_account/session.ts` en nergens anders.
- Bedragen zijn strings en blijven strings. Het exportlichaam wordt één keer als tekst gelezen en ongewijzigd aan de download gegeven.
- Elke string in `src/**` die een DOM-tekstknoop of een toegankelijke naam kan worden, is één regel in `frontend/tests/ui-strings.txt`. `e2e/language.spec.ts` vergelijkt byte voor byte in beide richtingen.
- Geen adviestekst in de frontend. De twee toestemmingsteksten en elke validatiemelding komen uit de API.
- Nederlands is wat een gebruiker leest; Engels is code, identifiers, comments, testnamen en commitboodschappen.
- Geen em-dashes in gebruikersgerichte teksten en niet in de documenten in `docs/`.
- pnpm, niet npm. `corepack enable` en `pnpm install --frozen-lockfile`.
- De vijf frontend-poorten zijn `pnpm lint`, `pnpm typecheck`, `pnpm format:check`, `pnpm test` en `pnpm build`, plus `pnpm e2e`.
- axe schoon op elke route, in beide toestanden en beide paletten, met `wcag2a`, `wcag2aa` en `wcag22aa`.
- `prefers-reduced-motion` wordt gerespecteerd, en betekenis zit nooit alleen in beweging.
- De Python-dekkingsdrempel is 98,00 met `precision = 2`, en mag alleen omhoog. De vier frontend-drempels (96 / 93 / 96 / 97) volgen dezelfde regel.
- De jobnamen `quality`, `test`, `dependencies`, `sast` en `secrets` zijn een interface met de rulesets. Hernoem er nooit een zonder `scripts/setup_rulesets.sh` in dezelfde commit mee te wijzigen.
- Beoordeel elke poort op de exitcode, nooit op een grep over de uitvoer van een tool.
- Werk op `feat/accounts-frontend`. Nooit direct op `main`.
- Voor elke nieuwe controle geldt: toon aan dat hij rood kán worden, met het transcript erbij. Elke taak zegt per controle hoe.

---

## Het werkmodel

1. **Het plan draait serieel**, taak 1 tot en met 13, in deze volgorde en nooit twee tegelijk. superpowers:subagent-driven-development is hier de uitvoeringsautoriteit en zegt met zoveel woorden "Never dispatch multiple implementation subagents in parallel (conflicts)". Daarnaast delen zes taken `frontend/tests/ui-strings.txt` en drie taken `frontend/src/app/_account/AccountPage.tsx`: twee daarvan naast elkaar botsen gegarandeerd.
2. **Een taak bezit paden exclusief zolang hij draait.** Twee taken die in hetzelfde bestand schrijven kunnen nooit tegelijk. De tabel hieronder zegt per taak welke paden dat zijn.
3. **Uitvoerende agents committen, en niets daarbuiten.** Elke taak commit op `feat/accounts-frontend`, met alleen de bestanden gestaged die zijn eigen Files-blok noemt, en met de boodschap die de taak voorschrijft. Nooit `push`, nooit `rebase`, nooit `checkout`, nooit `amend`, nooit een andere branch aanraken. En nooit `git checkout --`, `git restore`, `git stash` of `git reset`: een tijdelijke bewerking voor een rode-proef wordt met de hand teruggezet, want die commando's gooien ook het werk weg dat er nog niet in zit.
4. **Elk test- en poortcommando draait op de voorgrond.** Nooit een achtergrondoptie, nooit een pipe naar `tail` of `head`: de exitcode die je leest hoort van het gereedschap zelf te komen en niet van het laatste programma in een pijp.
5. **Poorten draaien na de taken**, niet erin, behalve de gerichte commando's die een taak zelf voorschrijft.
6. **Een taak die niet verder kan zonder een bestand aan te raken dat hij niet bezit, stopt en meldt dat.** Hij reikt niet over de lijn heen.

### Volgorde

| Taak | Hangt af van |
|---|---|
| 1. Het plan en zijn markering | niets |
| 2. Backend: `consent-texts/` en de `text_version`-grendel | 1 |
| 3. De Python-contractlaag en de drie fixtures | 2 |
| 4. `frontend/src/lib/accounts.ts` | 3 |
| 5. `_account/session.ts` en `_account/messages.ts` | 4 |
| 6. `ConsentRow`, `SignInForm`, `RegisterForm` | 5 |
| 7. De route `/account/` en de toestandsschakeling | 6 |
| 8. De accountweergave en `_account/download.ts` | 7 |
| 9. De voettekst en de twee bestaande e2e-specs | 8 |
| 10. `e2e/account.spec.ts` | 9 |
| 11. De stack-smoke tegen de echte stack | 2 (draait als elfde omdat de serie serieel is) |
| 12. De documenten | 11 |
| 13. De status omzetten en de poorten draaien | 12 |

### Bestandsbezit

| Taak | Bezit exclusief |
|---|---|
| 1 | `docs/superpowers/plans/2026-09-05-accounts-frontend.md` |
| 2 | `backend/accounts/views.py`, `backend/accounts/urls.py`, `backend/accounts/serializers.py`, `backend/accounts/nl.py`, `tests/test_accounts_api.py`, `tests/test_accounts_deletion.py`, `tests/test_accounts_privacy.py`, `docs/dpia.md` |
| 3 | `tests/helpers/consent_texts_fixture.py`, `frontend/tests/fixtures/consent-texts.json`, `frontend/tests/fixtures/me-response.json`, `frontend/tests/fixtures/export-response.json`, `tests/test_frontend_contract.py`, `tests/test_accounts_api.py` |
| 4 | `frontend/src/lib/accounts.ts`, `frontend/tests/lib/accounts.test.ts`, `tests/test_frontend_contract.py` |
| 5 | `frontend/src/app/_account/session.ts`, `frontend/src/app/_account/messages.ts`, `frontend/tests/account/session.test.ts`, `frontend/tests/account/messages.test.ts`, `frontend/tests/ui-strings.txt` |
| 6 | `frontend/src/app/_account/ConsentRow.tsx`, `frontend/src/app/_account/SignInForm.tsx`, `frontend/src/app/_account/RegisterForm.tsx`, `frontend/tests/account/SignInForm.test.tsx`, `frontend/tests/account/RegisterForm.test.tsx`, `frontend/tests/ui-strings.txt` |
| 7 | `frontend/src/app/account/page.tsx`, `frontend/src/app/_account/AccountPage.tsx`, `frontend/tests/account/AccountPage.test.tsx`, `frontend/tests/ui-strings.txt` |
| 8 | `frontend/src/app/_account/AccountPage.tsx`, `frontend/src/app/_account/download.ts`, `frontend/tests/account/AccountPage.test.tsx`, `frontend/tests/ui-strings.txt` |
| 9 | `frontend/src/app/_shell/SiteFooter.tsx`, `frontend/tests/app/LegalPages.test.tsx`, `frontend/e2e/theme.spec.ts`, `frontend/e2e/privacy.spec.ts`, `frontend/tests/ui-strings.txt` |
| 10 | `frontend/e2e/account.spec.ts` |
| 11 | `tests/test_stack_smoke.py` |
| 12 | `docs/decisions.md`, `docs/superpowers/specs/2026-09-04-accounts-auth-design.md`, `docs/superpowers/specs/2026-09-05-accounts-frontend-design.md` |
| 13 | `docs/superpowers/plans/2026-09-05-accounts-frontend.md` |

Taak 7 en taak 8 schrijven allebei in `AccountPage.tsx` en in `AccountPage.test.tsx`. Taak 3 en taak 4 schrijven allebei in `tests/test_frontend_contract.py`, en taak 2 en taak 3 allebei in `tests/test_accounts_api.py`. Zes taken schrijven in `ui-strings.txt`. De serie hierboven is precies wat dat zonder botsing houdt.

---

## Zeven dingen die dit plan vastlegt en die de spec impliciet liet

**`ConsentRow.tsx` draagt twee componenten en niet een.** Hoofdstuk 8 van de spec vraagt om "een selectievakje met een zin ernaast en een rij met een schakelaar", en de bestandenlijst in hoofdstuk 11 noemt één bestand. Dat wordt dus één bestand met twee exports, `ConsentCheckbox` (de registratieweergave) en `ConsentRow` (de accountweergave). Ze delen het label per soort en de regel dat de zin uit de API komt, en ze verschillen in wat er gebeurt als je erop drukt. Eén component met een `mode`-prop zou die twee gedragingen in één functie verstoppen.

**Een ontbrekende `text_version` op een `GRANTED` leest als een verouderde.** De spec vraagt om precies één nieuwe sleutel in `nl.py` en zegt dat ontbreken een 400 is. `ConsentSerializer` kan het veld niet onvoorwaardelijk verplicht maken, want bij `WITHDRAWN` mag het weg, dus DRF's eigen `required`-melding is daar niet beschikbaar. Afwezig en verkeerd worden daarom door dezelfde vergelijking beantwoord: de client stuurde niet de versie die op het scherm stond. Eén tak, één sleutel, `consent_text_stale`. Op `register/` is het veld wel gewoon verplicht en is ontbreken DRF's eigen 400.

**Alleen `readErrorBody` wordt gekopieerd, `fieldMessages` niet.** Spec 4.1 legt de kopie van de foutreductie vast en noemt daarbij dat twee `ApiError`-klassen `fieldMessages` uit `_flow/messages.ts` stilletjes leeg zouden maken. Daaruit volgt dat `_account/messages.ts` diezelfde `fieldMessages` importeert in plaats van er een tweede van te maken: één `ApiError`, één lezer van `error.fields`, en alleen de reductie van het foutlichaam bestaat twee keer, met de vergelijkende test uit spec 9.1 eromheen.

**Een `ApiError` uit `accounts.ts` draagt de zin van de API als `message`, en een lege `message` als de API er geen stuurde.** `api.ts` laat de standaardboodschap staan, en die is Engels: `advice API returned 401`. Die aan een huishouden tonen is de taalgrens van de verkeerde kant overschrijden. `accounts.ts` geeft daarom `detail ?? ""` mee, en `describeAuthError` leest die lengte: is hij nul, dan schrijft de frontend zelf een zin.

**De prosa in `docs/dpia.md` verandert in taak 2 en niet in taak 12.** Spec 5.1 zegt "in dezelfde commit" over regel 358, en dat is de commit die de negende route toevoegt. Dezelfde bewerking corrigeert de moduledocstring van `backend/accounts/views.py`, die met "Eight of them" opent.

**`_shape` wordt geïmporteerd uit `tests/test_frontend_contract.py` en niet gekopieerd.** Spec 9.4 zegt dat de `me`- en `export`-fixtures worden vastgezet "langs dezelfde `_shape`-functie die de adviesfixture al gebruikt". Dat is letterlijk dezelfde functie: `tests/` staat op het zoekpad (daar leunt `from helpers.accounts import ...` al op), dus `from test_frontend_contract import _shape` werkt. Een tweede kopie van die functie zou precies het soort verschil kunnen krijgen dat het document nergens noemt.

**`account/page.tsx` is een servercomponent en er komt geen `account/layout.tsx`.** De bestandenlijst van de spec noemt er geen, en er is er ook geen nodig: `page.tsx` exporteert `metadata`, rendert de `<h1>` en de alinea, en zet `<AccountPage />` eronder. Dat kan omdat alleen `AccountPage.tsx` `"use client"` draagt. `berekenen/` heeft wel een layout, maar om een andere reden: daar is `page.tsx` zelf een clientcomponent en die kan geen `metadata` exporteren.

---

## Fase 0: de poort die dit plan zelf openzet

### Taak 1: Een plan mag onaf zijn, en dit is het bewijs dat de markering hem dekt

**Hangt af van:** niets.

**Files:**
- Create: `docs/superpowers/plans/2026-09-05-accounts-frontend.md`

**Interfaces:**
- Consumes: `_is_in_progress(plan: Path) -> bool` en de constante `IN_PROGRESS` in `tests/test_plans.py`, allebei sinds 2026-09-04 aanwezig; `_plan_that_speaks_for(path: Path) -> Path` in `tests/test_pipeline_contract.py`.
- Produces: de statusregel op regel 5 van dit bestand, die taak 13 omzet.

Het mechanisme uit het vorige plan staat er al, dus deze taak bouwt niets. Wat hij wel moet doen is aantonen dat het hier ook echt aangaat, want een markering waarvan niemand heeft gezien dat hij iets doet is een markering die net zo goed een typefout kan bevatten.

Eén ding is hier anders dan bij het vorige plan en het is de moeite waard om het op te schrijven in plaats van het te kopiëren: **`tests/test_pipeline_contract.py::test_every_test_file_named_in_a_comment_exists` is voor dit plan niet in het geding.** `_TEST_REFERENCE` is `tests/test_[a-z0-9_]+\.py`, en elk Python-testbestand dat dit plan noemt bestaat vandaag al. De vrijstelling via `_plan_that_speaks_for` zou dus niets doen, en een rode-proef die hem probeert te laten vuren zou niet kunnen vuren. Dat is precies het soort stap dat in het vorige plan twee keer misging, dus hij staat hier niet.

- [ ] **Step 1: Draai de twee poorten die dit bestand raakt**

```bash
uv run --no-sync pytest tests/test_plans.py tests/test_pipeline_contract.py -q
```

Verwacht: alles groen. `test_every_file_a_finished_plan_names_exists[2026-09-05-accounts-frontend.md]` valt door de vroege `return` heen, en `test_a_plan_marked_in_progress_is_actually_unfinished[2026-09-05-accounts-frontend.md]` vindt de bestanden die dit plan nog moet maken. Noteer welke: de lijst begint bij `frontend/src/app/_account/AccountPage.tsx` en telt vandaag twintig namen die niet in de boom staan, gemeten op 2026-09-05.

- [ ] **Step 2: Toon aan dat de strenge lezing dit bestand echt zou pakken**

Haal de regel op regel 5 tijdelijk weg (de regel die met `**Status:**` begint) en draai opnieuw:

```bash
uv run --no-sync pytest tests/test_plans.py -q
```

Verwacht: rood op `test_every_file_a_finished_plan_names_exists[2026-09-05-accounts-frontend.md]`, met dezelfde lijst als in stap 1 en de zin "Either the work is not done, or something was renamed". Zet de regel met de hand terug, precies zoals hij was, en draai stap 1 nog eens om te zien dat het weer groen is.

De andere tak van hetzelfde paar, "een afgerond plan dat nog in progress zegt", wordt niet hier aangetoond maar in taak 13 stap 1: dat is diezelfde controle die dan uit zichzelf rood staat omdat het werk klaar is. Twee takken, twee bewijzen, geen van beide met een kunstgreep.

- [ ] **Step 3: Commit**

```bash
git add docs/superpowers/plans/2026-09-05-accounts-frontend.md
git commit
```

Boodschap: `docs(plans): the frontend accounts plan, marked unfinished`.

---

## Fase 1: de kant waar de tekst vandaan komt

### Taak 2: De negende route, en de grendel op de versie

**Hangt af van:** taak 1.

**Files:**
- Modify: `backend/accounts/views.py`, `backend/accounts/urls.py`, `backend/accounts/serializers.py`, `backend/accounts/nl.py`, `docs/dpia.md`
- Test: `tests/test_accounts_api.py`, `tests/test_accounts_deletion.py`, `tests/test_accounts_privacy.py`

**Interfaces:**
- Consumes: `accounts.nl.NL` en `accounts.nl.CONSENT_TEXT_VERSION`; `accounts.models.Consent.KINDS`, `Consent.GRANTED`, `Consent.WITHDRAWN`; `accounts.views._AuthAPIView`.
- Produces:
  - route `GET /api/auth/consent-texts/`, naam `auth-consent-texts`, `throttle_scope = "auth-read"`, `AllowAny`, geen authenticatieklasse
  - antwoordvorm `{"text_version": str, "texts": {"LEAD_GENERATION": str, "METER_LINK": str}}`
  - `NL["consent_text_stale"]`
  - `RegisterSerializer.text_version`, verplicht
  - `ConsentSerializer.text_version`, optioneel, verplicht en gecontroleerd bij `action == "GRANTED"`

Geen migratie: er verandert niets aan een model. `Consent.record` stempelt `CONSENT_TEXT_VERSION` zoals het dat al deed; het verzoekveld is uitsluitend een grendel.

Twee bestaande poorten moeten groen blijven en allebei om een reden die niet vanzelf spreekt. `tests/test_backend_settings.py::test_every_public_route_is_rate_limited` loopt de resolver af en eist een scope met een tarief, en de nieuwe route noemt `auth-read`, dezelfde emmer als `me/`. `tests/test_dpia.py::test_the_api_answers_only_the_verbs_the_document_describes` leest `backend/accounts/views.py` mee sinds taak 12 van het vorige plan, en de nieuwe view beantwoordt alleen `get`. En let op de derde: `tests/test_advise.py` heeft een Nederlandse-woordenscanner over `backend/**` met `wachtwoord` erin, en die staat aan. Geen Nederlands buiten `nl.py`.

- [ ] **Step 1: Schrijf de falende test voor de negende route**

Voeg onderaan `tests/test_accounts_api.py` toe:

```python
def test_the_consent_texts_are_public_and_come_from_nl_py(client: Any) -> None:
    """The one route on this API that describes nobody.

    No account, no cookie, no CSRF token: a visitor who has never been here
    has to be able to read the sentence before agreeing to it, and the
    registration form cannot be shown until it has. Asserted against nl.py
    rather than against a literal, because the whole point of chapter 5 of
    the design is that there is one copy of these sentences.
    """
    response = client.get("/api/auth/consent-texts/")
    assert response.status_code == 200, response.content
    assert response.json() == {
        "text_version": CONSENT_TEXT_VERSION,
        "texts": {
            "LEAD_GENERATION": NL["CONSENT_LEAD_GENERATION"],
            "METER_LINK": NL["CONSENT_METER_LINK"],
        },
    }


def test_the_consent_text_keys_are_the_consent_kinds(client: Any) -> None:
    """A third kind of consent that the frontend never shows is drift, and it
    falls over here, on the side where it was added."""
    texts = client.get("/api/auth/consent-texts/").json()["texts"]
    assert sorted(texts) == sorted(Consent.KINDS)
    for kind, sentence in texts.items():
        assert sentence == NL[f"CONSENT_{kind}"]
        assert sentence.strip(), f"{kind} carries an empty sentence"


def test_the_consent_texts_are_not_cached_by_anything_in_between(client: Any) -> None:
    """`_AuthAPIView` puts `private, no-store` on every answer under /api/auth/.

    Strictly too strong for this one, which describes no household. It stays
    because an exception on the base class for one route makes the base class
    weaker than it is now, and a cache that does not keep this costs nothing.
    """
    response = client.get("/api/auth/consent-texts/")
    assert response.headers["Cache-Control"] == "private, no-store"
```

Voeg bovenin dat bestand `CONSENT_TEXT_VERSION` toe aan de import uit `accounts.nl`:

```text
from accounts.nl import CONSENT_TEXT_VERSION, NL
```

- [ ] **Step 2: Draai en zie hem falen op een 404**

```bash
uv run --no-sync pytest tests/test_accounts_api.py -q -k consent_text
```

Verwacht: rood, `assert 404 == 200`. De route bestaat nog niet, dus de resolver antwoordt niets.

- [ ] **Step 3: Voeg de view en de route toe**

In `backend/accounts/views.py`, onder `RefreshView` en boven `MeView`:

```python
class ConsentTextsView(_AuthAPIView):
    """The sentences a household agrees to, and the version they are agreed under.

    Public, because the registration form may not be shown until it has them:
    a `true` sent for a sentence nobody read is not consent. On `auth-read`
    rather than a scope of its own, for the same reason `me/` is: this is a
    call at the start of a page load, and 120 an hour is the measure for that.
    A seventh `auth` rate for an answer that touches no database and is the
    same for everybody would be a number nobody derived from anything.

    The view composes nothing and formats nothing. The keys are
    `sorted(Consent.KINDS)` and the values are `NL["CONSENT_" + kind]`,
    literally, which is what makes the sentence on the screen and the sentence
    behind the recorded version the same string.
    """

    authentication_classes: Sequence[type[BaseAuthentication]] = ()
    permission_classes: Sequence[type[BasePermission]] = (AllowAny,)
    throttle_scope = "auth-read"

    def get(self, request: Request) -> Response:
        return Response(
            {
                "text_version": CONSENT_TEXT_VERSION,
                "texts": {kind: NL[f"CONSENT_{kind}"] for kind in sorted(Consent.KINDS)},
            }
        )
```

Breid de import bovenin uit naar `from accounts.nl import CONSENT_TEXT_VERSION, NL`.

In `backend/accounts/urls.py`, één regel in `urlpatterns` en `ConsentTextsView` in de import. De fence staat op `text` en niet op `python`, om dezelfde reden als in taak 10 en 11 van het vorige plan: dit is één element uit een lijst en geen module, en de formatter die over dit document loopt maakt er anders `(path(...),)` van. Zet deze fence niet terug op `python`.

```text
    path("consent-texts/", ConsentTextsView.as_view(), name="auth-consent-texts"),
```

- [ ] **Step 4: Draai en zie de drie tests groen worden**

```bash
uv run --no-sync pytest tests/test_accounts_api.py tests/test_backend_settings.py tests/test_dpia.py -q
```

Verwacht: alles groen, inclusief `test_every_public_route_is_rate_limited` (de nieuwe route noemt `auth-read`) en de werkwoordtest (de nieuwe view beantwoordt alleen `get`).

- [ ] **Step 5: Toon aan dat de scopecontrole deze route ook echt leest**

Haal `throttle_scope = "auth-read"` tijdelijk uit `ConsentTextsView` en draai:

```bash
uv run --no-sync pytest tests/test_backend_settings.py::test_every_public_route_is_rate_limited -q
```

Verwacht: rood, met `api/auth/consent-texts/ is served by ConsentTextsView with throttle_scope=None`. Zet de regel met de hand terug. Zonder deze stap zegt stap 4 alleen dat er iets gedraaid heeft.

- [ ] **Step 6: Schrijf de falende tests voor de grendel**

Drie dingen tegelijk, en ze moeten samen: `text_version` wordt verplicht op `register/` en op `consent/` bij `GRANTED`, dus elk bestaand `BODY` in de suite dat zonder dat veld post wordt een 400. Dat is de valstrik en hij wordt gehoorzaamd, niet omzeild.

In `tests/test_accounts_api.py`, `tests/test_accounts_deletion.py` en `tests/test_accounts_privacy.py`: voeg `"text_version": CONSENT_TEXT_VERSION` toe aan het registratielichaam, met de import erbij. In `tests/test_accounts_api.py`:

```python
BODY = {
    "email": "iemand@voorbeeld.nl",
    "password": PASSWORD,
    "consent_meter_link": True,
    "consent_lead_generation": False,
    # Required since the consent text got a lock: a body without it is a page
    # that did not read the sentence it is agreeing to.
    "text_version": CONSENT_TEXT_VERSION,
}
```

De valstrik slaat ook toe op een bestaande test die het plan tot nu toe niet noemt: `test_a_consent_can_be_withdrawn_and_given_again` post, na de withdraw, `{"kind": "METER_LINK", "action": "GRANTED"}` zonder `text_version` en verwacht 200. Voeg het veld toe aan die tweede POST, in dezelfde vorm als de `register/`-fix hierboven:

```text
    again = client.post(
        "/api/auth/consent/",
        {
            "kind": "METER_LINK",
            "action": "GRANTED",
            "text_version": CONSENT_TEXT_VERSION,
        },
        content_type="application/json",
        **_csrf(client),
    )
```

Voeg daarna in `tests/test_accounts_api.py` de vijf tests toe die de grendel vastleggen:

```python
@pytest.mark.django_db
def test_registering_under_a_stale_consent_text_is_refused(client: Any) -> None:
    """The gap chapter 5.2 closes: a tab left open for an hour while the text
    is rewritten and rolled out, after which `Consent.record` stamps the new
    version on a row whose owner read the old sentence."""
    body = BODY | {"text_version": "1999-01-01"}
    response = client.post(
        "/api/auth/register/", body, content_type="application/json", **_csrf(client)
    )
    assert response.status_code == 400
    assert response.json()["text_version"] == [NL["consent_text_stale"]]
    assert User.objects.count() == 0


@pytest.mark.django_db
def test_registering_without_a_text_version_is_refused(client: Any) -> None:
    """Required on this serializer, so a missing field is DRF's own 400 and
    never a silent registration under whatever version happens to be current."""
    body = {key: value for key, value in BODY.items() if key != "text_version"}
    response = client.post(
        "/api/auth/register/", body, content_type="application/json", **_csrf(client)
    )
    assert response.status_code == 400
    assert "text_version" in response.json()


@pytest.mark.django_db
def test_granting_a_consent_under_a_stale_text_is_refused(client: Any) -> None:
    client.post("/api/auth/register/", BODY, content_type="application/json", **_csrf(client))
    response = client.post(
        "/api/auth/consent/",
        {"kind": "LEAD_GENERATION", "action": "GRANTED", "text_version": "1999-01-01"},
        content_type="application/json",
        **_csrf(client),
    )
    assert response.status_code == 400
    assert response.json()["text_version"] == [NL["consent_text_stale"]]
    user = User.objects.get(email="iemand@voorbeeld.nl")
    assert Consent.current(user, Consent.LEAD_GENERATION) is False


@pytest.mark.django_db
def test_granting_a_consent_without_a_text_version_is_refused(client: Any) -> None:
    """Absent and wrong are answered by the same comparison, and the message is
    the same one: either way the client did not send the version it displayed.
    One branch, one key, which is what chapter 5.2 asks for."""
    client.post("/api/auth/register/", BODY, content_type="application/json", **_csrf(client))
    response = client.post(
        "/api/auth/consent/",
        {"kind": "LEAD_GENERATION", "action": "GRANTED"},
        content_type="application/json",
        **_csrf(client),
    )
    assert response.status_code == 400
    assert response.json()["text_version"] == [NL["consent_text_stale"]]


@pytest.mark.django_db
def test_withdrawing_a_consent_needs_no_text_version_at_all(client: Any) -> None:
    """Article 7(3): withdrawing has to be as easy as giving. Refusing a
    withdrawal because the wording changed in the meantime is exactly that
    not being true, so the field is ignored here rather than merely optional."""
    client.post("/api/auth/register/", BODY, content_type="application/json", **_csrf(client))
    user = User.objects.get(email="iemand@voorbeeld.nl")
    response = client.post(
        "/api/auth/consent/",
        {"kind": "METER_LINK", "action": "WITHDRAWN"},
        content_type="application/json",
        **_csrf(client),
    )
    assert response.status_code == 200
    assert Consent.current(user, Consent.METER_LINK) is False


@pytest.mark.django_db
def test_withdrawing_with_a_stale_text_version_is_still_accepted(client: Any) -> None:
    """The other half of ignoring it. A field that is merely optional would
    still be validated when present, and a tab that has been open since the
    last rewrite is precisely the tab somebody withdraws from."""
    client.post("/api/auth/register/", BODY, content_type="application/json", **_csrf(client))
    response = client.post(
        "/api/auth/consent/",
        {"kind": "METER_LINK", "action": "WITHDRAWN", "text_version": "1999-01-01"},
        content_type="application/json",
        **_csrf(client),
    )
    assert response.status_code == 200
```

- [ ] **Step 7: Draai ze en zie ze falen**

```bash
uv run --no-sync pytest tests/test_accounts_api.py -q
```

Verwacht: de vier grendeltests falen met een 201 respectievelijk een 200 waar een 400 hoort, en de twee `WITHDRAWN`-tests zijn nu al groen. Dat laatste is geen probleem: ze houden vanaf stap 8 een uitzondering vast die er dan echt is, en stap 9 toont aan dat ze rood kunnen worden.

- [ ] **Step 8: Voeg het veld en de melding toe**

In `backend/accounts/nl.py`, één sleutel in de eerste categorie, naast `csrf_failed`: dat is de categorie waar het bestand zijn eigen docstring op na leest (`email_taken`, `email_invalid`, `credentials_invalid`, `password_required`, `csrf_failed`, `consent_kind_unknown`, `consent_action_unknown`), niet de tweede (`not_signed_in`, `session_expired`).

```text
    "consent_text_stale": (
        "de toestemmingstekst is gewijzigd, herlaad de pagina en probeer het opnieuw"
    ),
```

De docstring van dat bestand somt de eerste categorie op met name; voeg `consent_text_stale` toe aan die opsomming, met de zin dat hij niet over een ingetypte waarde gaat maar over een pagina die te oud is.

In `backend/accounts/serializers.py`, op `RegisterSerializer`:

```text
    #: The version whose text the visitor actually read, sent back so it can be
    #: compared with the one `Consent.record` is about to stamp. Required here:
    #: a registration with no version is a form that showed a sentence from
    #: somewhere else, or none at all.
    text_version = serializers.CharField()

    def validate_text_version(self, value: str) -> str:
        if value != CONSENT_TEXT_VERSION:
            raise serializers.ValidationError(NL["consent_text_stale"])
        return value
```

en op `ConsentSerializer`:

```text
    #: Not required, and that asymmetry is article 7(3) rather than a
    #: convenience: a withdrawal may never be harder than a grant, so the field
    #: is ignored entirely when the action is WITHDRAWN.
    text_version = serializers.CharField(required=False)

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        if attrs["action"] != Consent.GRANTED:
            return attrs
        if attrs.get("text_version") != CONSENT_TEXT_VERSION:
            # Absent and wrong, answered by one comparison. Either way the
            # client did not send the version it displayed, and the reader's
            # next move is the same: reload the page.
            raise serializers.ValidationError({"text_version": NL["consent_text_stale"]})
        return attrs
```

Voeg `CONSENT_TEXT_VERSION` toe aan de import uit `accounts.nl` bovenin dat bestand.

- [ ] **Step 9: Draai en toon aan dat beide takken rood kunnen worden**

```bash
uv run --no-sync pytest tests/test_accounts_api.py tests/test_accounts_deletion.py tests/test_accounts_privacy.py -q
```

Verwacht: alles groen.

Twee tijdelijke bewerkingen, allebei met de hand terugzetten:

1. Haal in `ConsentSerializer.validate` de regel `if attrs["action"] != Consent.GRANTED: return attrs` weg en draai `uv run --no-sync pytest tests/test_accounts_api.py -q -k withdrawing`. Verwacht: allebei de `WITHDRAWN`-tests rood met een 400 waar een 200 hoort. Dat is de uitzondering die aantoonbaar iets doet.
2. Vervang in `RegisterSerializer.validate_text_version` het lichaam door `return value` en draai `uv run --no-sync pytest tests/test_accounts_api.py -q -k stale`. Verwacht: `test_registering_under_a_stale_consent_text_is_refused` rood met een 201.

- [ ] **Step 10: Schrijf de twee documenten bij die nu onwaar zijn**

`backend/accounts/views.py`, de eerste regel van de moduledocstring: "Eight of them" wordt "Nine of them", en de zin erachter blijft staan: alleen `get` en `post`.

`docs/dpia.md` regel 358: "met acht routes die geen van alle meer dan `get` of `post` beantwoorden" wordt "met negen routes", met erachter de zin dat de negende publiek is en geen persoonsgegeven teruggeeft: hij levert de toestemmingsteksten en de versie ervan, voor iedereen hetzelfde. Let op de tests die letterlijke zinnen uit dat document lezen: `test_every_section_is_numbered_consecutively`, `test_the_document_carries_no_em_dashes` en `test_the_chapter_of_open_decisions_states_how_many_there_are` blijven gelden en de wijziging raakt geen van drieën.

```bash
uv run --no-sync pytest tests/test_dpia.py -q
```

- [ ] **Step 11: Draai de hele suite met dekking**

```bash
uv run --no-sync pytest -q --cov --cov-report=term-missing
```

Verwacht: exitcode 0, dus de drempel van 98,00 is gehaald over een boom met vier nieuwe takken erbij (de stale-400 op `register/`, de stale-400 op `consent/`, de `WITHDRAWN`-uitzondering, en de nieuwe view). Ligt het gemeten percentage erboven, verhoog de drempel dan naar dat getal op twee decimalen. Omlaag mag nooit. Beoordeel op de exitcode en niet op het getoonde percentage. Rood op `test_a_plan_marked_in_progress_is_actually_unfinished` hoort hier niet te staan: dit plan noemt nog twintig bestanden die niet bestaan.

- [ ] **Step 12: Commit**

```bash
git add backend/accounts/views.py backend/accounts/urls.py backend/accounts/serializers.py backend/accounts/nl.py docs/dpia.md tests/test_accounts_api.py tests/test_accounts_deletion.py tests/test_accounts_privacy.py
git commit
```

Boodschap: `feat(accounts): serve the consent text, and lock the version it was agreed under`.

---

### Taak 3: De contractlaag, en de drie fixtures waar de frontend op bouwt

**Hangt af van:** taak 2.

**Files:**
- Create: `tests/helpers/consent_texts_fixture.py`, `frontend/tests/fixtures/consent-texts.json`, `frontend/tests/fixtures/me-response.json`, `frontend/tests/fixtures/export-response.json`
- Modify: `tests/test_frontend_contract.py`, `tests/test_accounts_api.py`

**Interfaces:**
- Consumes: `GET /api/auth/consent-texts/` en `CONSENT_TEXT_VERSION` uit taak 2; `_shape(node: Any) -> Any` in `tests/test_frontend_contract.py`; `helpers.accounts.TEST_PASSWORD`.
- Produces:
  - `helpers.consent_texts_fixture.build_consent_texts_payload() -> dict[str, Any]` en `write_fixture() -> int`
  - `frontend/tests/fixtures/consent-texts.json`, gegenereerd en byte voor byte vergeleken
  - `frontend/tests/fixtures/me-response.json`, met de hand geschreven, op vorm vastgezet
  - `frontend/tests/fixtures/export-response.json`, idem, met één `Consent`-rij en een lege `advices`

Twee soorten fixture, want er zijn twee soorten antwoord. `consent-texts/` raakt geen database, dus die kan gegenereerd worden zoals `advice_fixture.py` dat doet en byte voor byte vergeleken. `me/` en `export/` vragen een gebruikersrij, dus die worden met de hand geschreven en in `tests/test_accounts_api.py` op **vorm** vastgezet, waar een testdatabase wel bestaat. Waarden verschillen dan (een e-mailadres, een tijdstempel) en sleutels niet, en het zijn de sleutels waar de frontend op bouwt.

- [ ] **Step 1: Schrijf de generator**

Maak `tests/helpers/consent_texts_fixture.py`:

```python
"""The consent texts the frontend is built against, produced by the real table.

The same arrangement as advice_fixture.py one file over, for the one auth
response that touches no database: there is one function, it reads nl.py, and
both this generator and tests/test_frontend_contract.py go through it. A
fixture written by hand is a description of a response that may never have
existed, and for these two sentences that is worse than usual: the whole
guarantee in chapter 5 of the design is that what a household reads and what
the Consent row records are one string.

Run as a script to rewrite the fixture:

    uv run --no-sync python tests/helpers/consent_texts_fixture.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
FIXTURE = REPO_ROOT / "frontend" / "tests" / "fixtures" / "consent-texts.json"

# backend/ is a Django project run from its own directory rather than a package
# anybody installs. Under pytest `pythonpath` in pyproject.toml puts it on the
# path; running this module as a script does not go through pytest.
if str(REPO_ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "backend"))


def build_consent_texts_payload() -> dict[str, Any]:
    """Exactly what ConsentTextsView answers, from the same two sources."""
    from accounts.models import Consent
    from accounts.nl import CONSENT_TEXT_VERSION, NL

    return {
        "text_version": CONSENT_TEXT_VERSION,
        "texts": {kind: NL[f"CONSENT_{kind}"] for kind in sorted(Consent.KINDS)},
    }


def write_fixture() -> int:
    """Rewrite the committed fixture and report its size in bytes."""
    payload = build_consent_texts_payload()
    FIXTURE.parent.mkdir(parents=True, exist_ok=True)
    # newline pinned to a line feed, for the reason advice_fixture.py gives:
    # on Windows the default writes carriage return pairs, pre-commit's
    # mixed-line-ending hook rewrites the file, and the commit fails.
    with FIXTURE.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    return len(json.dumps(payload))


if __name__ == "__main__":
    print(f"wrote {write_fixture()} bytes to {FIXTURE}")
```

Eén ding is hier anders dan bij `advice_fixture.py`: deze generator importeert `accounts.models`, en dat vraagt een geconfigureerde Django. Onder pytest doet pytest-django dat. Als script leunt het commando hierboven op de `DJANGO_SETTINGS_MODULE` die `pyproject.toml` voor deze repository al vastlegt. Werkt dat niet, dan is dat een bevinding over de configuratie en geen reden om de import naar de modulekop te halen.

- [ ] **Step 2: Genereer de fixture en lees hem na**

```bash
uv run --no-sync python tests/helpers/consent_texts_fixture.py
```

Verwacht: een bestand met drie sleutels, `text_version` op `2026-09-04` en twee zinnen. Lees het na en controleer met het oog dat de zinnen letterlijk die uit `nl.py` zijn, inclusief de punt aan het eind.

- [ ] **Step 3: Schrijf de contracttests die die fixture vasthouden**

Voeg toe aan `tests/test_frontend_contract.py`, onder de bestaande fixtureblokken:

```python
CONSENT_TEXTS_FIXTURE = REPO_ROOT / "frontend" / "tests" / "fixtures" / "consent-texts.json"
FRONTEND_SOURCE = REPO_ROOT / "frontend" / "src"


def test_the_consent_texts_fixture_is_byte_for_byte_what_the_generator_writes() -> None:
    """The same claim advice-response.json carries, for the sentences a
    household agrees to.

    A hand-edited word here would be a fixture describing a consent nobody
    ever gave, and every frontend test that renders it would then agree with
    a sentence the API does not send.
    """
    import sys

    sys.path.insert(0, str(REPO_ROOT / "tests"))
    from helpers.consent_texts_fixture import build_consent_texts_payload

    written = json.dumps(build_consent_texts_payload(), indent=2, ensure_ascii=False) + "\n"
    committed = CONSENT_TEXTS_FIXTURE.read_text(encoding="utf-8")
    assert committed == written, (
        "frontend/tests/fixtures/consent-texts.json is not what "
        "tests/helpers/consent_texts_fixture.py produces. Regenerate it with\n"
        "    uv run --no-sync python tests/helpers/consent_texts_fixture.py\n"
        "rather than editing it, and do not run a formatter over it."
    )


def test_the_fixture_keys_are_the_consent_kinds() -> None:
    """Two copies of one list: the model, and the fixture the browser builds
    against. A third kind of consent has to fall over on the side where it was
    added, not in a browser where the row simply never appears."""
    import sys

    sys.path.insert(0, str(REPO_ROOT / "backend"))
    from accounts.models import Consent

    payload = json.loads(CONSENT_TEXTS_FIXTURE.read_text(encoding="utf-8"))
    assert sorted(payload["texts"]) == sorted(Consent.KINDS)
    for kind, sentence in payload["texts"].items():
        assert sentence.strip(), f"{kind} carries an empty sentence"


def test_no_consent_text_lives_in_the_frontend() -> None:
    """Chapter 5, checked rather than promised.

    If the frontend carried its own copy of either sentence, the text_version
    column would prove nothing: there would be two texts, the row would point
    at one and the screen would have shown the other, and nothing could see
    the difference. Read out of nl.py rather than restated, so this cannot
    pass by agreeing with a copy of itself.
    """
    import sys

    sys.path.insert(0, str(REPO_ROOT / "backend"))
    from accounts.nl import NL

    sentences = {key: NL[key] for key in ("CONSENT_METER_LINK", "CONSENT_LEAD_GENERATION")}
    offenders: list[str] = []
    for path in sorted(FRONTEND_SOURCE.rglob("*.ts*")):
        text = path.read_text(encoding="utf-8")
        for key, sentence in sentences.items():
            # The first clause of each sentence, so a copy a formatter reflowed
            # over two lines is still found. A whole-sentence search would be
            # defeated by the one edit somebody would actually make.
            if sentence.split(".")[0] in text:
                offenders.append(f"{path.relative_to(REPO_ROOT).as_posix()} carries {key}")
    assert not offenders, (
        "the consent text lives in the frontend as well as in nl.py:\n  " + "\n  ".join(offenders)
    )
```

De vierde vergelijking die hier logisch bij hoort, tussen `Consent.KINDS` en `CONSENT_KINDS` in `accounts.ts`, staat met opzet niet in deze taak: dat bestand bestaat pas in taak 4, en een test die tot dan rood staat is een taak die niet groen afsluit. Hij staat in taak 4, stap 7.

- [ ] **Step 4: Draai ze en toon aan dat de laatste rood kan worden**

```bash
uv run --no-sync pytest tests/test_frontend_contract.py -q
```

Verwacht: groen.

De laatste is groen omdat de frontend vandaag niets van dit alles heeft, en dat is precies de uitslag die niets bewijst. Maak daarom tijdelijk `frontend/src/lib/_redproof_consent.ts` met de eerste zin van `NL["CONSENT_METER_LINK"]` erin als string, draai alleen die test opnieuw, verwacht rood met de naam van dat bestand, en verwijder het bestand daarna met de hand. Een bestaand bronbestand tijdelijk bewerken kan hier niet: `api.ts` mag niet aangeraakt worden en deze taak bezit geen enkel ander frontend-bronbestand.

- [ ] **Step 5: Schrijf de twee handgeschreven fixtures**

`frontend/tests/fixtures/me-response.json`:

```json
{
  "email": "iemand@voorbeeld.nl",
  "consents": {
    "LEAD_GENERATION": false,
    "METER_LINK": true
  }
}
```

`frontend/tests/fixtures/export-response.json`, met één `Consent`-rij en een lege `advices`, want dat is wat fase 1 oplevert:

```json
{
  "email": "iemand@voorbeeld.nl",
  "date_joined": "2026-09-05T09:12:44.512000Z",
  "consents": [
    {
      "kind": "METER_LINK",
      "action": "GRANTED",
      "occurred_at": "2026-09-05T09:12:44.611000Z",
      "text_version": "2026-09-04"
    }
  ],
  "advices": []
}
```

- [ ] **Step 6: Zet ze op vorm vast tegen de echte views**

Voeg toe aan `tests/test_accounts_api.py`:

```python
@pytest.mark.django_db
def test_the_me_fixture_has_the_shape_the_view_answers(client: Any) -> None:
    """The frontend builds against a file; this is what makes that file a
    description of this response.

    Shape and not values: an address and a timestamp differ between a fixture
    and a test database and always will. The keys do not, and the keys are
    what the browser reads. Along the same `_shape` the advice fixture uses,
    imported rather than copied: a second definition of that function is a
    second thing that can drift.
    """
    from test_frontend_contract import _shape

    client.post("/api/auth/register/", BODY, content_type="application/json", **_csrf(client))
    live = client.get("/api/auth/me/").json()
    committed = json.loads(ME_FIXTURE.read_text(encoding="utf-8"))
    assert _shape(live) == _shape(committed), (
        "GET me/ no longer has the shape frontend/tests/fixtures/me-response.json "
        "describes; update the fixture and the shape check in accounts.ts together"
    )


@pytest.mark.django_db
def test_the_export_fixture_has_the_shape_the_view_answers(client: Any) -> None:
    """The same claim for the heaviest answer on this API, and the one the
    browser hands straight to a file the visitor keeps."""
    from test_frontend_contract import _shape

    client.post("/api/auth/register/", BODY, content_type="application/json", **_csrf(client))
    live = client.post("/api/auth/export/", content_type="application/json", **_csrf(client)).json()
    committed = json.loads(EXPORT_FIXTURE.read_text(encoding="utf-8"))
    assert _shape(live) == _shape(committed), (
        "POST export/ no longer has the shape "
        "frontend/tests/fixtures/export-response.json describes"
    )


def test_the_export_fixture_carries_the_consent_row_that_makes_it_worth_pinning() -> None:
    """A fixture with an empty `consents` would pin `list` and nothing else,
    and the four keys inside a row are exactly what the download is for."""
    committed = json.loads(EXPORT_FIXTURE.read_text(encoding="utf-8"))
    assert committed["consents"], "the export fixture no longer exercises a consent row"
    assert set(committed["consents"][0]) == {"kind", "action", "occurred_at", "text_version"}
    assert committed["advices"] == [], "phase 1 stores no advice against an account"
```

Voeg bovenin `tests/test_accounts_api.py` `import json`, `from pathlib import Path` en de twee padconstanten toe:

```text
REPO_ROOT = Path(__file__).resolve().parent.parent
ME_FIXTURE = REPO_ROOT / "frontend" / "tests" / "fixtures" / "me-response.json"
EXPORT_FIXTURE = REPO_ROOT / "frontend" / "tests" / "fixtures" / "export-response.json"
```

- [ ] **Step 7: Draai, en toon aan dat de vormvergelijking rood kan worden**

```bash
uv run --no-sync pytest tests/test_accounts_api.py tests/test_frontend_contract.py -q
```

Verwacht: groen. Hernoem daarna in `frontend/tests/fixtures/me-response.json` de sleutel `consents` tijdelijk naar `consent`, draai `uv run --no-sync pytest tests/test_accounts_api.py -q -k me_fixture` en verwacht rood met een verschil in sleutels. Zet de sleutel met de hand terug.

- [ ] **Step 8: Commit**

```bash
git add tests/helpers/consent_texts_fixture.py tests/test_frontend_contract.py tests/test_accounts_api.py frontend/tests/fixtures/consent-texts.json frontend/tests/fixtures/me-response.json frontend/tests/fixtures/export-response.json
git commit
```

Boodschap: `test(contract): pin the three auth responses the browser is built against`.

---

## Fase 2: de client

### Taak 4: `frontend/src/lib/accounts.ts`, negen aanroepen met hun vormcontrole

**Hangt af van:** taak 3.

**Files:**
- Create: `frontend/src/lib/accounts.ts`, `frontend/tests/lib/accounts.test.ts`
- Modify: `tests/test_frontend_contract.py`, `frontend/tests/ui-strings.txt`

**Interfaces:**
- Consumes: `ApiError` uit `@/lib/api`; de drie fixtures uit taak 3; de negen paden uit `backend/accounts/urls.py`.
- Produces, en elke latere taak gebruikt deze namen letterlijk:
  - `CONSENT_KINDS: readonly ["LEAD_GENERATION", "METER_LINK"]`
  - `type ConsentKind = "LEAD_GENERATION" | "METER_LINK"`
  - `type ConsentAction = "GRANTED" | "WITHDRAWN"`
  - `interface ConsentTexts { readonly text_version: string; readonly texts: Readonly<Record<ConsentKind, string>> }`
  - `interface Me { readonly email: string; readonly consents: Readonly<Record<ConsentKind, boolean>> }`
  - `interface ConsentResult { readonly kind: ConsentKind; readonly granted: boolean }`
  - `interface SignInInput { readonly email: string; readonly password: string }`
  - `interface RegisterInput extends SignInInput { readonly consent_meter_link: boolean; readonly consent_lead_generation: boolean; readonly text_version: string }`
  - `interface ConsentInput { readonly kind: ConsentKind; readonly action: ConsentAction; readonly text_version?: string | undefined }`
  - `getConsentTexts(): Promise<ConsentTexts>`
  - `register(input: RegisterInput): Promise<void>`
  - `login(input: SignInInput): Promise<void>`
  - `refresh(): Promise<void>`
  - `getMe(): Promise<Me>`
  - `postConsent(input: ConsentInput): Promise<ConsentResult>`
  - `exportAccount(): Promise<string>`
  - `logout(): Promise<void>`
  - `deleteAccount(password: string): Promise<void>`

Drie vallen in dit bestand, en ze zijn geen van drieën hypothetisch:

`semgrep` heeft een regel `ampeer-no-url-from-user-input` die elke `fetch` met een template literal afkeurt behalve de vorm `` fetch(`${BASE}...`, ...) ``. Het pad hoort dus achter `${BASE}` te staan en nergens anders, en de poort `sast` leest `frontend/src`.

`response.json()` werpt op een 204. De vier aanroepen die `void` teruggeven lezen het lichaam niet.

`tsconfig` heeft `exactOptionalPropertyTypes` en `noUncheckedIndexedAccess` aan. Een optioneel veld dat `undefined` mag zijn schrijft dat met zoveel woorden (`?: string | undefined`), en elke indexatie levert `| undefined`.

- [ ] **Step 1: Schrijf de falende test voor de eigenschap die de hele module draagt**

Maak `frontend/tests/lib/accounts.test.ts`:

```ts
import { afterEach, describe, expect, it, vi } from "vitest";
import consentTexts from "../fixtures/consent-texts.json";
import me from "../fixtures/me-response.json";
import exportPayload from "../fixtures/export-response.json";
import { ApiError, postEstimate } from "@/lib/api";
import {
  deleteAccount,
  exportAccount,
  getConsentTexts,
  getMe,
  login,
  logout,
  postConsent,
  refresh,
  register,
} from "@/lib/accounts";

const REGISTER_INPUT = {
  email: "iemand@voorbeeld.nl",
  password: "een-heel-lang-wachtwoord",
  consent_meter_link: false,
  consent_lead_generation: false,
  text_version: consentTexts.text_version,
};

afterEach(() => {
  vi.unstubAllGlobals();
  document.cookie = "csrftoken=; max-age=0";
});

/** A fresh Response per call: a body can only be read once. */
function stub(status: number, body: unknown) {
  const fetchMock = vi.fn<typeof fetch>(async () =>
    status === 204
      ? new Response(null, { status })
      : new Response(JSON.stringify(body), {
          status,
          headers: { "content-type": "application/json" },
        }),
  );
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

/** The nine calls, each with the status and body its own route answers with. */
const CALLS: readonly {
  readonly name: string;
  readonly status: number;
  readonly body: unknown;
  readonly method: "GET" | "POST";
  readonly run: () => Promise<unknown>;
}[] = [
  {
    name: "consent-texts",
    status: 200,
    body: consentTexts,
    method: "GET",
    run: getConsentTexts,
  },
  {
    name: "register",
    status: 201,
    body: null,
    method: "POST",
    run: () => register(REGISTER_INPUT),
  },
  {
    name: "login",
    status: 200,
    body: null,
    method: "POST",
    run: () =>
      login({ email: "iemand@voorbeeld.nl", password: "een-heel-lang-wachtwoord" }),
  },
  { name: "refresh", status: 200, body: null, method: "POST", run: refresh },
  { name: "me", status: 200, body: me, method: "GET", run: getMe },
  {
    name: "consent",
    status: 200,
    body: { kind: "METER_LINK", granted: true },
    method: "POST",
    run: () =>
      postConsent({
        kind: "METER_LINK",
        action: "GRANTED",
        text_version: consentTexts.text_version,
      }),
  },
  {
    name: "export",
    status: 200,
    body: exportPayload,
    method: "POST",
    run: exportAccount,
  },
  { name: "logout", status: 204, body: null, method: "POST", run: logout },
  {
    name: "delete",
    status: 204,
    body: null,
    method: "POST",
    run: () => deleteAccount("een-heel-lang-wachtwoord"),
  },
];

describe("the account client", () => {
  it.each(CALLS)(
    "sends the session cookie on $name, without which every answer is a 401",
    async ({ status, body, run }) => {
      const fetchMock = stub(status, body);
      await run();
      const init = fetchMock.mock.calls[0]?.[1] as RequestInit;
      expect(init.credentials).toBe("include");
    },
  );
});
```

- [ ] **Step 2: Draai en zie hem falen op de ontbrekende module**

```bash
cd frontend && pnpm test
```

Verwacht: rood, `Failed to resolve import "@/lib/accounts"`. Alle negen gevallen falen, wat de bedoeling is: de eigenschap geldt voor alle negen of voor geen.

- [ ] **Step 3: Schrijf de module**

Maak `frontend/src/lib/accounts.ts`:

```ts
import { ApiError } from "@/lib/api";

/**
 * The account API, which is the opposite of the advice API in the one way that
 * matters.
 *
 * `api.ts` sets `credentials: "omit"` and says why: there is no session there,
 * so there is nothing to send and nothing to steal. Here there is a session, it
 * lives in two httpOnly cookies, and every single call has to carry them, the
 * GETs included. That is why this is a second module rather than an option on
 * the first: an option is something a caller can get wrong.
 *
 * THERE IS NO RETRY HERE EITHER, ON ANY STATUS. The one exchange the design
 * allows, a 401 on `me/` at page load followed by one `refresh/` and one more
 * `me/`, is not in this file. It lives in `app/_account/session.ts`, so there
 * is exactly one place where it can happen and it is the load function.
 *
 * Every answer is checked for shape before it becomes a value, for the reason
 * `isAdvice` gives one module over: there is no error boundary above this page,
 * so a renamed field produces no message, it produces an empty screen.
 */
const BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://127.0.0.1:8000";

/**
 * The two kinds, in the order the API sends them.
 *
 * `sorted(Consent.KINDS)` on the Python side, and
 * `tests/test_frontend_contract.py` compares this list with that one, so a
 * third kind falls over on the side where it was added rather than becoming a
 * row the browser silently never shows.
 */
export const CONSENT_KINDS = ["LEAD_GENERATION", "METER_LINK"] as const;

export type ConsentKind = (typeof CONSENT_KINDS)[number];
export type ConsentAction = "GRANTED" | "WITHDRAWN";

export interface ConsentTexts {
  readonly text_version: string;
  readonly texts: Readonly<Record<ConsentKind, string>>;
}

export interface Me {
  readonly email: string;
  readonly consents: Readonly<Record<ConsentKind, boolean>>;
}

export interface ConsentResult {
  readonly kind: ConsentKind;
  readonly granted: boolean;
}

export interface SignInInput {
  readonly email: string;
  readonly password: string;
}

export interface RegisterInput extends SignInInput {
  readonly consent_meter_link: boolean;
  readonly consent_lead_generation: boolean;
  /** The version whose sentences were on the screen. Never a constant here. */
  readonly text_version: string;
}

export interface ConsentInput {
  readonly kind: ConsentKind;
  readonly action: ConsentAction;
  /** Sent on GRANTED, absent on WITHDRAWN. Chapter 5.2 of the design. */
  readonly text_version?: string | undefined;
}

/**
 * DRF's error bodies, reduced to one shape.
 *
 * A deliberate copy of the function of the same name in `api.ts`, which does
 * not export it. Chapter 4.1 of the design weighs the three options and takes
 * this one: exporting it would edit the file frontend/CLAUDE.md puts under
 * lock, and a third module both read from would do the same. The copy is not
 * kept in step by a promise but by a test, "the duplicated error reduction" in
 * tests/lib/accounts.test.ts, which runs one table of bodies through both.
 */
function readErrorBody(body: unknown): {
  fields: Record<string, string[]>;
  detail?: string;
} {
  if (typeof body !== "object" || body === null) return { fields: {} };
  const fields: Record<string, string[]> = {};
  let detail: string | undefined;
  for (const [key, value] of Object.entries(body as Record<string, unknown>)) {
    if (Array.isArray(value)) {
      const messages = value.filter(
        (entry): entry is string => typeof entry === "string",
      );
      if (messages.length > 0) fields[key] = messages;
    } else if (typeof value === "string") {
      if (key === "detail") detail = value;
      else fields[key] = [value];
    }
  }
  return detail === undefined ? { fields } : { fields, detail };
}

/**
 * The double submit token, read from the cookie the API set.
 *
 * `CSRF_COOKIE_HTTPONLY = False` is what makes this possible, and that is not
 * a weakening: a token JavaScript cannot read is a token JavaScript cannot
 * send back. Null when there is none, in which case nothing is sent and the
 * API answers 403 with a sentence saying to reload, which is the truth.
 */
function csrfToken(): string | null {
  for (const entry of document.cookie.split(";")) {
    const [name, ...rest] = entry.trim().split("=");
    if (name === "csrftoken") return decodeURIComponent(rest.join("="));
  }
  return null;
}

interface CallOptions {
  readonly method: "GET" | "POST";
  readonly body?: unknown;
}

/**
 * One request, and the error it raises when the answer is not a success.
 *
 * The `ApiError` this throws carries the API's own sentence as its message, and
 * an empty message when the API sent none. `_account/messages.ts` reads that
 * difference, because `ApiError`'s own default message is English ("advice API
 * returned 401") and showing that to a household would be the language
 * boundary crossed from the wrong side.
 */
async function call(path: string, options: CallOptions): Promise<Response> {
  const token = options.method === "GET" ? null : csrfToken();
  const response = await fetch(`${BASE}${path}`, {
    method: options.method,
    ...(options.body === undefined
      ? {}
      : { body: JSON.stringify(options.body) }),
    headers: {
      ...(options.body === undefined
        ? {}
        : { "content-type": "application/json" }),
      ...(token === null ? {} : { "X-CSRFToken": token }),
    },
    // The session, in both directions, on every call including the GETs. Set
    // after the spread so no caller can turn it off by accident, which is the
    // same placement and the same argument as `omit` in api.ts.
    credentials: "include",
  });
  if (!response.ok) {
    // No retry. See the note at the top of this file.
    const { fields, detail } = readErrorBody(
      await response.json().catch(() => null),
    );
    throw new ApiError(response.status, fields, detail ?? "");
  }
  return response;
}

type JsonObject = Record<string, unknown>;

function isObject(value: unknown): value is JsonObject {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isString(value: unknown): value is string {
  return typeof value === "string";
}

/** Both kinds present and neither empty. A third key is left alone on purpose. */
function isConsentTexts(value: unknown): value is ConsentTexts {
  if (!isObject(value)) return false;
  const version = value["text_version"];
  if (!isString(version) || version.length === 0) return false;
  const texts = value["texts"];
  if (!isObject(texts)) return false;
  return CONSENT_KINDS.every((kind) => {
    const sentence = texts[kind];
    return isString(sentence) && sentence.length > 0;
  });
}

function isMe(value: unknown): value is Me {
  if (!isObject(value) || !isString(value["email"])) return false;
  const consents = value["consents"];
  if (!isObject(consents)) return false;
  return CONSENT_KINDS.every((kind) => typeof consents[kind] === "boolean");
}

/** The answer is about the kind that was sent, or it is about nothing. */
function isConsentResult(value: unknown, kind: ConsentKind): boolean {
  return (
    isObject(value) &&
    value["kind"] === kind &&
    typeof value["granted"] === "boolean"
  );
}

/**
 * The export, checked no deeper than "an object with inputs and advice".
 *
 * A second copy of `isAdvice` here could refuse a valid export because this
 * file does not yet know about a field the engine started sending, and that is
 * the wrong side to drop that error on: the download is the visitor's own data
 * and the frontend renders none of it.
 */
function isExport(value: unknown): boolean {
  if (!isObject(value) || !isString(value["email"])) return false;
  if (!isString(value["date_joined"])) return false;
  const consents = value["consents"];
  const advices = value["advices"];
  if (!Array.isArray(consents) || !Array.isArray(advices)) return false;
  return (
    consents.every(
      (row) =>
        isObject(row) &&
        isString(row["kind"]) &&
        isString(row["action"]) &&
        isString(row["occurred_at"]) &&
        isString(row["text_version"]),
    ) &&
    advices.every((row) => isObject(row) && "inputs" in row && "advice" in row)
  );
}

/** A success whose body is not what this route answers with. */
function unreadable(response: Response, what: string): ApiError {
  return new ApiError(response.status, {}, `auth API returned ${what}`);
}

export async function getConsentTexts(): Promise<ConsentTexts> {
  const response = await call("/api/auth/consent-texts/", { method: "GET" });
  const body: unknown = await response.json().catch(() => null);
  if (!isConsentTexts(body)) throw unreadable(response, "no consent texts");
  return body;
}

export async function register(input: RegisterInput): Promise<void> {
  await call("/api/auth/register/", { method: "POST", body: input });
}

export async function login(input: SignInInput): Promise<void> {
  await call("/api/auth/login/", { method: "POST", body: input });
}

export async function refresh(): Promise<void> {
  await call("/api/auth/refresh/", { method: "POST" });
}

export async function getMe(): Promise<Me> {
  const response = await call("/api/auth/me/", { method: "GET" });
  const body: unknown = await response.json().catch(() => null);
  if (!isMe(body)) throw unreadable(response, "no account");
  return body;
}

export async function postConsent(input: ConsentInput): Promise<ConsentResult> {
  const response = await call("/api/auth/consent/", {
    method: "POST",
    body: input,
  });
  const body: unknown = await response.json().catch(() => null);
  if (!isConsentResult(body, input.kind)) {
    throw unreadable(response, "an answer about another consent");
  }
  return body as ConsentResult;
}

/**
 * The export, as the text the API sent.
 *
 * Read once, as text, and handed to the download unchanged. Not parsed and
 * re-serialised: every amount inside an advice is a string because JSON has
 * only floats, and a second trip through a parser is exactly the mistake this
 * project avoids everywhere else. The shape check runs on `JSON.parse` of that
 * same text, and the parsed value is then thrown away.
 */
export async function exportAccount(): Promise<string> {
  const response = await call("/api/auth/export/", { method: "POST" });
  const text = await response.text();
  let parsed: unknown = null;
  try {
    parsed = JSON.parse(text);
  } catch {
    throw unreadable(response, "an export that is not JSON");
  }
  if (!isExport(parsed)) throw unreadable(response, "no export");
  return text;
}

export async function logout(): Promise<void> {
  // 204, so there is no body. `response.json()` throws on one.
  await call("/api/auth/logout/", { method: "POST" });
}

export async function deleteAccount(password: string): Promise<void> {
  await call("/api/auth/delete/", { method: "POST", body: { password } });
}
```

- [ ] **Step 4: Draai en zie de negen groen worden**

```bash
cd frontend && pnpm test
```

Verwacht: de negen gevallen uit stap 1 slagen.

- [ ] **Step 5: Schrijf de rest van laag 1**

Voeg toe aan `frontend/tests/lib/accounts.test.ts`:

```ts
describe("the CSRF header", () => {
  it.each(CALLS.filter((entry) => entry.method === "POST"))(
    "rides on $name, with the value out of the cookie",
    async ({ status, body, run }) => {
      document.cookie = "csrftoken=een-token-uit-de-cookie";
      const fetchMock = stub(status, body);
      await run();
      const init = fetchMock.mock.calls[0]?.[1] as RequestInit;
      expect(new Headers(init.headers).get("X-CSRFToken")).toBe(
        "een-token-uit-de-cookie",
      );
    },
  );

  it.each(CALLS.filter((entry) => entry.method === "GET"))(
    "is not sent on $name, because a safe method does not need one",
    async ({ status, body, run }) => {
      document.cookie = "csrftoken=een-token-uit-de-cookie";
      const fetchMock = stub(status, body);
      await run();
      const init = fetchMock.mock.calls[0]?.[1] as RequestInit;
      expect(new Headers(init.headers).get("X-CSRFToken")).toBeNull();
    },
  );

  it("sends no header at all when there is no cookie yet", async () => {
    // The API then answers 403 with `csrf_failed`, whose sentence says to
    // reload. An empty header instead would be a request claiming to carry a
    // token, which is a different and less honest failure.
    const fetchMock = stub(200, null);
    await refresh();
    const init = fetchMock.mock.calls[0]?.[1] as RequestInit;
    expect(new Headers(init.headers).has("X-CSRFToken")).toBe(false);
  });

  it("finds the token in a cookie jar that holds other cookies too", async () => {
    document.cookie = "ampeer-thema=dark";
    document.cookie = "csrftoken=tweede";
    const fetchMock = stub(204, null);
    await logout();
    const init = fetchMock.mock.calls[0]?.[1] as RequestInit;
    expect(new Headers(init.headers).get("X-CSRFToken")).toBe("tweede");
  });
});

describe("the shape checks", () => {
  it("refuses consent texts that are missing one of the two kinds", async () => {
    stub(200, { text_version: "2026-09-04", texts: { METER_LINK: "een zin" } });
    await expect(getConsentTexts()).rejects.toBeInstanceOf(ApiError);
  });

  it("refuses a consent text that is present and empty", async () => {
    // The plausible wrong body: a key that exists and says nothing, which
    // would put a blank label beside a checkbox somebody then ticks.
    stub(200, {
      text_version: "2026-09-04",
      texts: { LEAD_GENERATION: "", METER_LINK: "een zin" },
    });
    await expect(getConsentTexts()).rejects.toBeInstanceOf(ApiError);
  });

  it("refuses an account whose consents are strings rather than booleans", async () => {
    // "false" is truthy, so this is the body that turns a refusal into a row
    // that says yes.
    stub(200, {
      email: "iemand@voorbeeld.nl",
      consents: { LEAD_GENERATION: "false", METER_LINK: "true" },
    });
    await expect(getMe()).rejects.toBeInstanceOf(ApiError);
  });

  it("refuses a consent answer about the other kind", async () => {
    // The quietest wrong body on this API: a 200 that updates the wrong row on
    // the screen, with every value of the right type.
    stub(200, { kind: "LEAD_GENERATION", granted: true });
    await expect(
      postConsent({
        kind: "METER_LINK",
        action: "GRANTED",
        text_version: "2026-09-04",
      }),
    ).rejects.toBeInstanceOf(ApiError);
  });

  it("refuses an export whose consent rows have lost the version", async () => {
    stub(200, {
      ...exportPayload,
      consents: [
        { kind: "METER_LINK", action: "GRANTED", occurred_at: "2026-09-05T09:12:44Z" },
      ],
    });
    await expect(exportAccount()).rejects.toBeInstanceOf(ApiError);
  });

  it("hands back the export as the exact text the API sent", async () => {
    // Byte for byte, because this string becomes the file. A parse and a
    // re-serialise would round every amount inside an advice.
    const text = JSON.stringify(exportPayload);
    vi.stubGlobal(
      "fetch",
      vi.fn<typeof fetch>(async () => new Response(text, { status: 200 })),
    );
    await expect(exportAccount()).resolves.toBe(text);
  });

  it("accepts an export carrying an advice it knows nothing about", async () => {
    stub(200, {
      ...exportPayload,
      advices: [{ inputs: { postcode4: "5401" }, advice: { iets_nieuws: 1 } }],
    });
    await expect(exportAccount()).resolves.toContain("iets_nieuws");
  });

  it("refuses an export that is not JSON at all", async () => {
    // A proxy's error page with a 200 on it, which is the way this arrives in
    // practice.
    vi.stubGlobal(
      "fetch",
      vi.fn<typeof fetch>(async () => new Response("<html>oeps</html>", { status: 200 })),
    );
    await expect(exportAccount()).rejects.toBeInstanceOf(ApiError);
  });
});

describe("what this module refuses to do", () => {
  it("makes exactly one request on a 500", async () => {
    const fetchMock = stub(500, {});
    await getMe().catch(() => {});
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("makes exactly one request on a 401, because the exchange is not here", async () => {
    const fetchMock = stub(401, { detail: "u bent niet ingelogd" });
    await getMe().catch(() => {});
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("reads no body on a 204, which would throw", async () => {
    stub(204, null);
    await expect(logout()).resolves.toBeUndefined();
    stub(204, null);
    await expect(
      deleteAccount("een-heel-lang-wachtwoord"),
    ).resolves.toBeUndefined();
  });

  it("carries the API's own sentence as the message", async () => {
    stub(429, {
      detail: "Request was throttled. Expected available in 1800 seconds.",
    });
    await getMe().catch((error: ApiError) => {
      expect(error.message).toContain("throttled");
      expect(error.status).toBe(429);
    });
  });

  it("leaves the message empty when the API sent no sentence of its own", async () => {
    // The difference `_account/messages.ts` reads. ApiError's own default
    // message is English, and a household never sees it.
    stub(400, { text_version: ["de toestemmingstekst is gewijzigd"] });
    await register(REGISTER_INPUT).catch((error: ApiError) => {
      expect(error.message).toBe("");
      expect(error.fields["text_version"]).toEqual([
        "de toestemmingstekst is gewijzigd",
      ]);
    });
  });
});

/**
 * The two reductions, on one table.
 *
 * `readErrorBody` exists twice on purpose and this is the whole of what keeps
 * the copies together: the same bodies go through `postEstimate` from api.ts
 * and through `getMe` from this module, and the `fields` that come out have to
 * be equal. If one drifts, this is red.
 */
const ERROR_BODIES: readonly unknown[] = [
  { email: ["geen geldig e-mailadres"] },
  { colour: "onbekend veld" },
  { detail: "Request was throttled." },
  { password: ["te kort", "te simpel"] },
  { nested: { niet: "een lijst" } },
  { empty: [] },
  { mixed: ["een zin", 4, null] },
  null,
  "een string",
  [1, 2, 3],
];

const ESTIMATE_INPUT = {
  postcode4: "5401",
  peak_power_wp: 3500,
  azimuth_deg: 0,
  tilt_deg: 35,
  annual_consumption_kwh: 3500,
};

describe("the duplicated error reduction", () => {
  it.each(ERROR_BODIES.map((body, index) => ({ index, body })))(
    "agrees with the one in api.ts on body $index",
    async ({ body }) => {
      stub(400, body);
      const fromAdvice = (await postEstimate(ESTIMATE_INPUT).catch(
        (error: ApiError) => error,
      )) as ApiError;
      stub(400, body);
      const fromAccounts = (await getMe().catch(
        (error: ApiError) => error,
      )) as ApiError;
      expect(fromAccounts.fields).toEqual(fromAdvice.fields);
    },
  );
});
```

- [ ] **Step 6: Draai, en toon aan dat de twee dragende controles rood kunnen worden**

```bash
cd frontend && pnpm test
```

Verwacht: groen, en de vier dekkingsdrempels gehaald.

Haal daarna in `accounts.ts` de regel `credentials: "include"` tijdelijk weg en draai `pnpm test` opnieuw. Verwacht: negen rode gevallen, `expected undefined to be 'include'`. Zet de regel met de hand terug.

Haal daarna in `call` de `X-CSRFToken`-spread tijdelijk weg en draai opnieuw. Verwacht: zeven rode gevallen op de POST-parametrisatie en op de cookiejar-test. Zet hem terug. Zonder deze twee bewerkingen zegt de groene uitslag hierboven alleen dat er iets gedraaid heeft.

- [ ] **Step 7: Verbreed de padcontrole naar de tweede client**

`tests/test_frontend_contract.py::test_every_path_the_frontend_calls_is_one_the_backend_serves` leest vandaag `advice.urls` en `api.ts`. Maak er een geparametriseerd paar van. Dit is de eerste plek in dat bestand waar `@pytest.mark.parametrize` gebruikt wordt, dus voeg `import pytest` toe aan de imports bovenin (naast `ast`, `json`, `re`, `Path`, `Any`); zonder die import faalt de collectie met `NameError: name 'pytest' is not defined` voor het hele bestand. Vervang `_api_prefix()` en `_api_routes()` door een versie die de gevraagde module opzoekt:

```python
def _api_prefix(module: str) -> str:
    """Where Django mounts one of the two APIs, from the root URL configuration.

    Django is the only place that decides this. nginx forwards it and the
    frontend asks for it, and both of those are copies.
    """
    tree = ast.parse(ROOT_URLS.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and getattr(node.func, "id", "") == "path"):
            continue
        if len(node.args) < 2 or not isinstance(node.args[0], ast.Constant):
            continue
        included = node.args[1]
        if (
            isinstance(included, ast.Call)
            and getattr(included.func, "id", "") == "include"
            and included.args
            and isinstance(included.args[0], ast.Constant)
            and included.args[0].value == module
        ):
            return "/" + str(node.args[0].value)
    raise AssertionError(f"{ROOT_URLS.name} no longer mounts {module} anywhere")


def _api_routes(urls: Path) -> set[str]:
    """Every fixed route under that prefix, from one app's URL configuration."""
    tree = ast.parse(urls.read_text(encoding="utf-8"))
    return {
        str(node.args[0].value)
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and getattr(node.func, "id", "") == "path"
        and node.args
        and isinstance(node.args[0], ast.Constant)
    }
```

Voeg twee padconstanten toe naast `ADVICE_URLS` en `API_TS`:

```python
ACCOUNTS_URLS = REPO_ROOT / "backend" / "accounts" / "urls.py"
ACCOUNTS_TS = REPO_ROOT / "frontend" / "src" / "lib" / "accounts.ts"
```

en parametriseer de test:

```python
@pytest.mark.parametrize(
    ("module", "urls", "client"),
    [
        ("advice.urls", ADVICE_URLS, API_TS),
        ("accounts.urls", ACCOUNTS_URLS, ACCOUNTS_TS),
    ],
    ids=["advice", "accounts"],
)
def test_every_path_the_frontend_calls_is_one_the_backend_serves(
    module: str, urls: Path, client: Path
) -> None:
    """The shape was checked and the address was not.

    ...(the existing docstring stays, with this paragraph added)...

    Parametrised since the second client arrived. accounts.ts calls nine paths
    under /api/auth/ and not one of them is reachable by reverse(), by a Vitest
    mock or by a page.route fixture: all three answer whatever they are asked.
    Only this reads the URL configuration Django actually serves.
    """
    prefix = _api_prefix(module)
    routes = _api_routes(urls)
    assert routes, f"{urls.name} declares no routes at all"

    called = {
        _INTERPOLATION.sub("<dynamic>", path)
        for path in _CALLED_PATH.findall(client.read_text(encoding="utf-8"))
    }
    assert called, f"{client.name} asks the API for nothing; this test read nothing"

    wrong = []
    for path in sorted(called):
        if not path.startswith(prefix):
            wrong.append(f"{path} is not under {prefix}")
            continue
        rest = path[len(prefix) :]
        if rest == "<dynamic>/" or rest in routes:
            continue
        wrong.append(f"{path} asks for {rest!r}, which is not one of {sorted(routes)}")
    assert not wrong, "the frontend calls addresses the backend does not serve:\n  " + "\n  ".join(
        wrong
    )
```

Pas ook `test_nginx_forwards_the_prefix_django_answers_on` aan, die `_api_prefix()` zonder argument aanriep: geef hem `"advice.urls"` mee, want die assertie gaat over het adviesblok met zijn eigen logformaat.

Voeg daarna de derde kopie van de soortenlijst toe, die nu pas gelezen kan worden:

```python
def test_the_frontend_knows_exactly_the_two_kinds_the_api_has() -> None:
    """`CONSENT_KINDS` in accounts.ts is what every shape check and both consent
    rows iterate, so a kind missing there is a consent the API records and the
    browser never shows, and a kind too many is a row that renders `undefined`.
    """
    import sys

    sys.path.insert(0, str(REPO_ROOT / "backend"))
    from accounts.models import Consent

    declared = _quoted(ACCOUNTS_TS.read_text(encoding="utf-8"), "export const CONSENT_KINDS =")
    assert declared == sorted(Consent.KINDS), (
        f"accounts.ts declares {declared} and Consent.KINDS is {sorted(Consent.KINDS)}"
    )
```

- [ ] **Step 8: Draai, en toon aan dat de twee nieuwe helften rood kunnen worden**

```bash
uv run --no-sync pytest tests/test_frontend_contract.py -q
```

Verwacht: beide parametrisaties groen, negen paden onder `/api/auth/`, en de soortenlijst gelijk aan `Consent.KINDS`.

Vervang daarna in `accounts.ts` tijdelijk `"/api/auth/consent-texts/"` door `"/api/auth/consent-text/"` en draai opnieuw. Verwacht: rood op `[accounts]` met `asks for 'consent-text/', which is not one of [...]`. Zet het pad met de hand terug.

Haal daarna `"LEAD_GENERATION"` tijdelijk uit `CONSENT_KINDS` en draai opnieuw. Verwacht: rood met `accounts.ts declares ['METER_LINK']`. Zet hem terug.

- [ ] **Step 9: Werk `ui-strings.txt` bij**

`CONSENT_KINDS` is een array-literal in een variabele-initialisatie in `src/lib/`, en `e2e/language.spec.ts` haalt zulke posities eruit ongeacht of er al een component is die de waarden op het scherm zet. Deze taak voegt dat bestand toe en niet een latere: laat het ongeregenereerd, dan staat `pnpm e2e` (taal) rood vanaf deze commit tot taak 6, en de regel hierboven is per commit en niet per feature.

```bash
cd frontend && pnpm build && UPDATE_UI_STRINGS=1 pnpm e2e language
```

Verwacht: die run herschrijft het bestand en faalt met opzet. Lees de diff: precies twee nieuwe regels, `LEAD_GENERATION` en `METER_LINK`, allebei uit de array-literal van `CONSENT_KINDS`. Geen andere positie in `accounts.ts` is extraheerbaar: `BASE`'s standaardwaarde `"http://127.0.0.1:8000"` staat al in het bestand via `api.ts`, en de tekst in `unreadable()` is een aanroepargument, niet een variabele-initialisatie of een return-expressie, dus die telt niet mee. Draai daarna `pnpm e2e language` zonder de vlag opnieuw en verwacht groen.

- [ ] **Step 10: Draai de frontend-poorten en de sast-poort**

```bash
cd frontend && pnpm lint && pnpm typecheck && pnpm format:check && pnpm test
```

Verwacht: alle vier groen. Draai daarna vanaf de repositorywortel:

```bash
uv run --no-sync semgrep --config .semgrep/frontend.yml --error --quiet frontend/src
```

Verwacht: exitcode 0. De `fetch` in `accounts.ts` staat in de vorm die `ampeer-no-url-from-user-input` toestaat; elke andere vorm van een template literal daar is een bevinding en geen reden om de regel te onderdrukken.

- [ ] **Step 11: Commit**

```bash
git add frontend/src/lib/accounts.ts frontend/tests/lib/accounts.test.ts tests/test_frontend_contract.py frontend/tests/ui-strings.txt
git commit
```

Boodschap: `feat(frontend): a second API client, for the API that has a session`.

---

## Fase 3: de pagina

Vier dingen gelden voor elke taak in deze fase en staan hier één keer.

**Elke nieuwe zin gaat in dezelfde commit in `frontend/tests/ui-strings.txt`.** De regeneratie is:

```bash
cd frontend && pnpm build && UPDATE_UI_STRINGS=1 pnpm e2e language
```

Die run herschrijft het bestand en faalt daarna met opzet, zodat een regeneratie nooit het ding kan zijn dat een build groen maakte. Draai daarna `pnpm e2e language` zonder de vlag en lees de diff. In die diff staan meer regels dan de zinnen die u schreef: de extractor oordeelt op positie en niet op betekenis, dus toestandsnamen (`signed_out`, `GRANTED`), klasselijsten en een bestandsnaam komen er ook in. Dat is de prijs die de kop van dat bestand beschrijft. Wat u leest is: staat elke regel die een zin is in de lijst die de taak hieronder noemt, en is er geen zin bij die een huishouden vertelt wat het met zijn stroom moet doen.

**De dekking mag niet zakken.** `pnpm test` draait met vier drempels (96 statements, 93 branches, 96 functions, 97 lines). Elke foutpad in deze componenten is een tak, dus elke taak test er ook een.

**Toegankelijkheid zit in de component en niet in een controle achteraf.** Elke fout staat in een `role="alert"` binnen `main`, elke veldfout hangt met `aria-describedby` aan zijn eigen veld, en alles is met het toetsenbord te bedienen.

**Geen enkele component leest de klok.** `ampeer-no-reading-the-clock` in `.semgrep/frontend.yml` verbiedt `Date.now()`, `new Date(...)` en `Intl.DateTimeFormat` in deze boom. De export draagt tijdstempels en de frontend toont er geen.

### Taak 5: De laadvolgorde, de ene wissel, en wat er op het scherm komt als het misgaat

**Hangt af van:** taak 4.

**Files:**
- Create: `frontend/src/app/_account/session.ts`, `frontend/src/app/_account/messages.ts`, `frontend/tests/account/session.test.ts`, `frontend/tests/account/messages.test.ts`
- Modify: `frontend/tests/ui-strings.txt`

**Interfaces:**
- Consumes: `getMe`, `refresh`, `type Me` uit `@/lib/accounts`; `ApiError` uit `@/lib/api`; `fieldMessages` uit `../_flow/messages`.
- Produces:
  - `type AccountState = { readonly status: "loading" } | { readonly status: "signed_out"; readonly notice: string | null } | { readonly status: "signed_in"; readonly me: Me }`
  - `const LOADING: AccountState`
  - `signedOut(notice: string | null): AccountState`
  - `loadSession(): Promise<AccountState>`
  - `describeAuthError(error: unknown): string`

Drie nieuwe zinnen, alle drie interfacetekst:

- `Wij konden de server niet bereiken. Controleer uw verbinding en probeer het opnieuw.`
- `De server had een storing. Probeer het straks opnieuw.`
- `De server gaf een antwoord dat wij niet konden lezen.`

- [ ] **Step 1: Schrijf de falende test voor de wissel, geteld op verzoeken**

Maak `frontend/tests/account/session.test.ts`:

```ts
import { afterEach, describe, expect, it, vi } from "vitest";
import me from "../fixtures/me-response.json";
import { loadSession } from "@/app/_account/session";

afterEach(() => vi.unstubAllGlobals());

interface Answer {
  readonly status: number;
  readonly body?: unknown;
  readonly throws?: boolean;
}

/**
 * One answer per request, in order, and the URLs that were asked for.
 *
 * Counted on requests rather than on what ends up on the screen, because the
 * property under test is "exactly one exchange" and a screen cannot show the
 * difference between one refresh and three.
 */
function stubSequence(answers: readonly Answer[]): { readonly seen: string[] } {
  const seen: string[] = [];
  let index = 0;
  vi.stubGlobal(
    "fetch",
    vi.fn<typeof fetch>(async (input: RequestInfo | URL) => {
      seen.push(String(input));
      const answer = answers[index];
      index += 1;
      if (answer === undefined) {
        throw new Error(`request ${index} was not planned for: ${String(input)}`);
      }
      if (answer.throws === true) throw new TypeError("Failed to fetch");
      return answer.status === 204
        ? new Response(null, { status: answer.status })
        : new Response(JSON.stringify(answer.body ?? null), {
            status: answer.status,
            headers: { "content-type": "application/json" },
          });
    }),
  );
  return { seen };
}

describe("loading the account page", () => {
  it("shows the account when me/ answers 200, and asks nothing else", async () => {
    const { seen } = stubSequence([{ status: 200, body: me }]);
    const state = await loadSession();
    expect(state).toEqual({ status: "signed_in", me });
    expect(seen).toHaveLength(1);
    expect(seen[0]).toContain("/api/auth/me/");
  });

  it("exchanges exactly once on a 401, and then shows the account", async () => {
    const { seen } = stubSequence([
      { status: 401, body: { detail: "u bent niet ingelogd" } },
      { status: 200 },
      { status: 200, body: me },
    ]);
    const state = await loadSession();
    expect(state).toEqual({ status: "signed_in", me });
    expect(seen).toHaveLength(3);
    expect(seen[1]).toContain("/api/auth/refresh/");
    expect(seen[2]).toContain("/api/auth/me/");
  });

  it("stops after a second 401, rather than rotating again", async () => {
    // A 401 after a successful rotation means the cookie the server just set
    // is not accepted, which no further attempt fixes. Going on would empty
    // the auth-refresh bucket and, once a spent token is offered again, ends
    // every session this account has. Counted on requests: a fourth would be
    // the bug and the screen would look the same either way.
    const { seen } = stubSequence([
      { status: 401, body: { detail: "u bent niet ingelogd" } },
      { status: 200 },
      { status: 401, body: { detail: "u bent niet ingelogd" } },
    ]);
    const state = await loadSession();
    expect(state).toEqual({ status: "signed_out", notice: null });
    expect(seen).toHaveLength(3);
  });

  it("stops when the exchange itself is refused", async () => {
    const { seen } = stubSequence([
      { status: 401, body: { detail: "u bent niet ingelogd" } },
      { status: 401, body: { detail: "uw sessie is verlopen, log opnieuw in" } },
    ]);
    const state = await loadSession();
    expect(state).toEqual({ status: "signed_out", notice: null });
    expect(seen).toHaveLength(2);
  });

  it("says the connection failed and exchanges nothing at all", async () => {
    // Chapter 6.5. A request that never arrived is not a 401: nothing came
    // back, so nothing was said about who is signed in, and there is nothing
    // to exchange. e2e/privacy.spec.ts opens this page with no mock at all,
    // so this is the state that runs there.
    const { seen } = stubSequence([{ status: 0, throws: true }]);
    const state = await loadSession();
    expect(state.status).toBe("signed_out");
    expect(state).toHaveProperty(
      "notice",
      "Wij konden de server niet bereiken. Controleer uw verbinding en probeer het opnieuw.",
    );
    expect(seen).toHaveLength(1);
  });

  it("passes a throttle message through as the API wrote it", async () => {
    const { seen } = stubSequence([
      { status: 429, body: { detail: "Probeer het over een uur opnieuw." } },
    ]);
    const state = await loadSession();
    expect(state).toEqual({
      status: "signed_out",
      notice: "Probeer het over een uur opnieuw.",
    });
    expect(seen).toHaveLength(1);
  });

  it("says a server fault in its own words, because the API sent none", async () => {
    stubSequence([{ status: 500, body: {} }]);
    const state = await loadSession();
    expect(state).toEqual({
      status: "signed_out",
      notice: "De server had een storing. Probeer het straks opnieuw.",
    });
  });
});
```

- [ ] **Step 2: Draai en zie hem falen op de ontbrekende module**

```bash
cd frontend && pnpm test
```

Verwacht: rood, `Failed to resolve import "@/app/_account/session"`.

- [ ] **Step 3: Schrijf de twee modules**

Maak `frontend/src/app/_account/messages.ts`:

```ts
import { ApiError } from "@/lib/api";
import { fieldMessages } from "../_flow/messages";

/**
 * `ApiError`'s own default, from `api.ts`, word for word.
 *
 * `accounts.ts`'s `call()` always passes an explicit third argument
 * (`detail ?? ""`), so this file never receives this text from that path.
 * The check exists anyway, as the second of two layers: the client contract
 * is the real fix, and this is what keeps a future `ApiError` built with the
 * constructor's own default parameters from putting English on a Dutch
 * screen.
 */
const API_ERROR_DEFAULT_MESSAGE = /^advice API returned \d+$/;

/**
 * What to put on the screen when the account API said no.
 *
 * Almost every sentence here comes from the API, and that is the design rather
 * than laziness: the validation messages live in `backend/accounts/nl.py`
 * keyed by an English id, and a second table in the frontend is a second table
 * that can drift from the first. So a 401, a 403 and a 429 are shown literally,
 * word for word, including the one that says how long to wait, which the API
 * knows and this page does not.
 *
 * `fieldMessages` is imported from the question flow rather than written again
 * here, and that is load bearing. It tests `error instanceof ApiError`, so a
 * second class of that name would make it silently return nothing for an error
 * that does have field messages. One class, one reader.
 *
 * The three sentences below are the cases where the API said nothing a reader
 * can use: no answer at all, a fault with no body, and a body this frontend
 * could not read.
 */
export function describeAuthError(error: unknown): string {
  if (!(error instanceof ApiError)) {
    // fetch() rejects rather than resolving when the network is gone, the
    // origin is unreachable, or CORS refused the response. The browser
    // deliberately does not say which, so neither does this.
    return "Wij konden de server niet bereiken. Controleer uw verbinding en probeer het opnieuw.";
  }
  // The API's own sentence, when it sent one. `accounts.ts` leaves the message
  // empty when it did not, and a message equal to ApiError's own default is
  // treated the same way, precisely so this line cannot print that English
  // sentence at a household.
  const hasOwnMessage =
    error.message.length > 0 && !API_ERROR_DEFAULT_MESSAGE.test(error.message);
  if (hasOwnMessage) return error.message;
  const messages = fieldMessages(error);
  if (messages.length > 0) return messages.join(" ");
  if (error.status >= 500) {
    return "De server had een storing. Probeer het straks opnieuw.";
  }
  return "De server gaf een antwoord dat wij niet konden lezen.";
}
```

Maak `frontend/src/app/_account/session.ts`:

```ts
import { ApiError } from "@/lib/api";
import { getMe, refresh, type Me } from "@/lib/accounts";
import { describeAuthError } from "./messages";

/**
 * Which of the three views is on the screen, and why.
 *
 * There is no flag in localStorage and none in sessionStorage saying somebody
 * is signed in. The cookies are httpOnly on purpose, so the frontend cannot
 * know: `GET me/` is the only source of this, on every load, and a local flag
 * that said "signed in" while the access token had expired would be a screen
 * promising something the next call contradicts.
 */
export type AccountState =
  | { readonly status: "loading" }
  | { readonly status: "signed_out"; readonly notice: string | null }
  | { readonly status: "signed_in"; readonly me: Me };

export const LOADING: AccountState = { status: "loading" };

export function signedOut(notice: string | null): AccountState {
  return { status: "signed_out", notice };
}

/**
 * One `me/`, and what its answer means.
 *
 * Null is reserved for the single outcome that earns the exchange below: a
 * 401. Everything else, a request that never arrived included, is a state of
 * its own and never a reason to spend a refresh token.
 */
async function askWhoIsSignedIn(): Promise<AccountState | null> {
  try {
    return { status: "signed_in", me: await getMe() };
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) return null;
    return signedOut(describeAuthError(error));
  }
}

/**
 * The one exception to "no retry", and it is not a retry.
 *
 * The access token lives fifteen minutes and the refresh token fourteen days,
 * so without this exchange a fourteen day token is worthless from minute
 * sixteen. The second request also asks a different question from the first,
 * because a different credential sits under it.
 *
 * Why a second 401 is the end rather than a third attempt: after a successful
 * rotation the server has just set a new access cookie, so a 401 on it means
 * that cookie is not being accepted, which is a fault in the configuration or
 * the server and not something another attempt repairs. Going on would rotate
 * once per page load, which empties the auth-refresh bucket of 60 an hour and,
 * the moment an already exchanged token is offered again, revokes every
 * session this account has. A client that keeps trying signs the visitor out
 * everywhere.
 *
 * This is the only place the exchange exists. `accounts.ts` has no retry on
 * any status at all.
 */
export async function loadSession(): Promise<AccountState> {
  const first = await askWhoIsSignedIn();
  if (first !== null) return first;
  try {
    await refresh();
  } catch {
    // No sentence above the sign-in form. "Your session expired" for somebody
    // who never had one is a message about something that did not happen.
    return signedOut(null);
  }
  return (await askWhoIsSignedIn()) ?? signedOut(null);
}
```

- [ ] **Step 4: Draai en zie de zeven groen worden**

```bash
cd frontend && pnpm test
```

Verwacht: groen.

- [ ] **Step 5: Schrijf de tests voor de meldingen zelf**

Maak `frontend/tests/account/messages.test.ts`:

```ts
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
    expect(describeAuthError(error)).toBe("e-mailadres of wachtwoord klopt niet");
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
```

- [ ] **Step 6: Draai, en toon aan dat de laatste twee rood kunnen worden**

```bash
cd frontend && pnpm test
```

Verwacht: groen, inclusief `never prints ApiError's own English default, even sent by hand`. Dat laatste is nu echt waar en niet alleen een claim: met de tweede laag in `hasOwnMessage` verwerpt de functie de Engelse standaardzin voordat hij ooit op het scherm kan komen.

Vervang daarna in `describeAuthError` de regel

```text
  const hasOwnMessage =
    error.message.length > 0 && !API_ERROR_DEFAULT_MESSAGE.test(error.message);
```

tijdelijk door

```text
  const hasOwnMessage = error.message.length > 0;
```

en draai opnieuw. Verwacht: precies één test rood, `never prints ApiError's own English default, even sent by hand`, met de Engelse zin erin. De andere acht blijven groen, want hun `error.message` is expliciet leeg en de tweede laag raakt daar niet aan. Zet de regel met de hand terug.

Vervang daarna in `loadSession` de regel `return (await askWhoIsSignedIn()) ?? signedOut(null);` tijdelijk door een tweede wissel (`await refresh(); return (await askWhoIsSignedIn()) ?? signedOut(null);`) en draai `pnpm test` opnieuw. Verwacht: `stops after a second 401` rood, met `request 4 was not planned for`. Dat is de telling op verzoeken die zijn werk doet, en zonder deze bewerking is die telling een assertie waarvan niemand weet of hij ooit iets ziet. Zet de regel met de hand terug.

- [ ] **Step 7: Werk `ui-strings.txt` bij en lees de diff**

```bash
cd frontend && pnpm build && UPDATE_UI_STRINGS=1 pnpm e2e language
cd frontend && pnpm e2e language
```

Verwacht: de eerste run herschrijft het bestand en faalt met "ui-strings.txt rewritten"; de tweede is groen. In de diff staan de drie zinnen uit de kop van deze taak, plus de toestandsnamen (`loading`, `signed_out`, `signed_in`) die de extractor uit de objectliteralen haalt. Meer hoort er niet in te staan; staat er wel meer, lees dan waarom voordat u commit.

- [ ] **Step 8: Toon aan dat de taalpoort rood kan worden**

Zet in `messages.ts` tijdelijk een extra zin in de laatste `return` (bijvoorbeeld `"Een tweede zin."`), draai `pnpm build && pnpm e2e language` en verwacht rood met "new user-visible strings in src/" en die zin erin. Haal de zin met de hand weg. Dit is de poort waar elke volgende frontendtaak van afhangt, dus hij wordt hier één keer aantoonbaar gemaakt in plaats van in elke taak opnieuw.

- [ ] **Step 9: Commit**

```bash
git add frontend/src/app/_account/session.ts frontend/src/app/_account/messages.ts frontend/tests/account/session.test.ts frontend/tests/account/messages.test.ts frontend/tests/ui-strings.txt
git commit
```

Boodschap: `feat(frontend): one exchange at load, and the sentences for everything else`.

---

### Taak 6: De twee formulieren en de toestemmingsrij

**Hangt af van:** taak 5.

**Files:**
- Create: `frontend/src/app/_account/ConsentRow.tsx`, `frontend/src/app/_account/SignInForm.tsx`, `frontend/src/app/_account/RegisterForm.tsx`, `frontend/tests/account/SignInForm.test.tsx`, `frontend/tests/account/RegisterForm.test.tsx`
- Modify: `frontend/tests/ui-strings.txt`

**Interfaces:**
- Consumes: `getConsentTexts`, `login`, `register`, `getMe`, `type ConsentAction`, `type ConsentKind`, `type ConsentTexts`, `type Me` uit `@/lib/accounts`; `describeAuthError` uit `./messages`.
- Produces:
  - `CONSENT_LABELS: Readonly<Record<ConsentKind, string>>` in `ConsentRow.tsx`
  - `ConsentCheckbox({ kind, text, checked, onChange }: { readonly kind: ConsentKind; readonly text: string; readonly checked: boolean; readonly onChange: (checked: boolean) => void })`
  - `ConsentRow({ kind, text, granted, busy, onToggle }: { readonly kind: ConsentKind; readonly text: string | null; readonly granted: boolean; readonly busy: boolean; readonly onToggle: (action: ConsentAction) => void })`
  - `SignInForm({ onSignedIn, onRegister }: { readonly onSignedIn: (me: Me) => void; readonly onRegister: () => void })`
  - `RegisterForm({ onRegistered, onSignIn }: { readonly onRegistered: (me: Me) => void; readonly onSignIn: () => void })`

Twee componenten in `ConsentRow.tsx` en niet een: hoofdstuk 8 van de spec vraagt om een selectievakje met een zin ernaast en om een rij met een schakelaar, en de bestandenlijst noemt één bestand. Ze delen het label per soort en de regel dat de zin uit de API komt, en ze verschillen in wat er gebeurt als je erop drukt.

De nieuwe zinnen van deze taak, alle interfacetekst:

- `E-mailadres`, `Wachtwoord`, `Inloggen`, `Account aanmaken`
- `Nog geen account? Account aanmaken`, `Ik heb al een account. Inloggen`
- `Bent u uw wachtwoord kwijt, dan kunnen wij het niet herstellen. Er is nog geen wachtwoordherstel, en zonder uw wachtwoord komt u ook niet meer bij de knop waarmee u uw account verwijdert.`
- `De toestemmingsteksten worden opgehaald.`
- `De toestemmingsteksten konden niet worden opgehaald. Herlaad de pagina om een account aan te maken.`
- `Kwartiergegevens van uw slimme meter`, `Doorgeven aan een installateur`
- `Toestemming geven`, `Toestemming intrekken`, `Toestemming gegeven`, `Geen toestemming gegeven`
- `De toestemmingstekst kon niet worden opgehaald. Intrekken kan wel, aanzetten niet.`

- [ ] **Step 1: Schrijf de falende tests voor de inlogweergave**

Maak `frontend/tests/account/SignInForm.test.tsx`:

```tsx
import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import me from "../fixtures/me-response.json";
import { SignInForm } from "@/app/_account/SignInForm";

afterEach(() => vi.unstubAllGlobals());

function stub(answers: readonly { status: number; body?: unknown }[]) {
  let index = 0;
  const fetchMock = vi.fn<typeof fetch>(async () => {
    const answer = answers[index];
    index += 1;
    if (answer === undefined) throw new Error(`request ${index} was not planned for`);
    return new Response(JSON.stringify(answer.body ?? null), {
      status: answer.status,
      headers: { "content-type": "application/json" },
    });
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

describe("the sign-in view", () => {
  it("asks for an address and a password, and says so to a screen reader", () => {
    render(<SignInForm onSignedIn={vi.fn()} onRegister={vi.fn()} />);
    const email = screen.getByLabelText("E-mailadres");
    const password = screen.getByLabelText("Wachtwoord");
    expect(email).toHaveAttribute("type", "email");
    expect(email).toHaveAttribute("autocomplete", "email");
    expect(password).toHaveAttribute("type", "password");
    expect(password).toHaveAttribute("autocomplete", "current-password");
  });

  it("says out loud that a lost password cannot be recovered", () => {
    // Chapter 10 of the auth design calls this the weakest place in that
    // design and names the consequence: somebody who loses their password
    // also loses the delete endpoint. That belongs on the screen where
    // somebody needs it and not in a document.
    render(<SignInForm onSignedIn={vi.fn()} onRegister={vi.fn()} />);
    expect(
      screen.getByText(/wij het niet herstellen/i),
    ).toBeInTheDocument();
  });

  it("asks me/ after a 200, because login/ answers with no body", async () => {
    const fetchMock = stub([
      { status: 200 },
      { status: 200, body: me },
    ]);
    const onSignedIn = vi.fn();
    render(<SignInForm onSignedIn={onSignedIn} onRegister={vi.fn()} />);
    await userEvent.type(screen.getByLabelText("E-mailadres"), "iemand@voorbeeld.nl");
    await userEvent.type(screen.getByLabelText("Wachtwoord"), "een-heel-lang-wachtwoord");
    await userEvent.click(screen.getByRole("button", { name: "Inloggen" }));
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(onSignedIn).toHaveBeenCalledWith(me);
  });

  it("shows the API's own sentence on a wrong password", async () => {
    stub([{ status: 401, body: { detail: "e-mailadres of wachtwoord klopt niet" } }]);
    render(<SignInForm onSignedIn={vi.fn()} onRegister={vi.fn()} />);
    await userEvent.type(screen.getByLabelText("E-mailadres"), "iemand@voorbeeld.nl");
    await userEvent.type(screen.getByLabelText("Wachtwoord"), "verkeerd");
    await userEvent.click(screen.getByRole("button", { name: "Inloggen" }));
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("e-mailadres of wachtwoord klopt niet");
  });

  it("does not call onSignedIn when the second request fails", async () => {
    // The half a test that only checks the first call would miss: login
    // succeeded, so the cookies are set, and the view still may not claim to
    // know who is signed in.
    stub([{ status: 200 }, { status: 500, body: {} }]);
    const onSignedIn = vi.fn();
    render(<SignInForm onSignedIn={onSignedIn} onRegister={vi.fn()} />);
    await userEvent.type(screen.getByLabelText("E-mailadres"), "iemand@voorbeeld.nl");
    await userEvent.type(screen.getByLabelText("Wachtwoord"), "een-heel-lang-wachtwoord");
    await userEvent.click(screen.getByRole("button", { name: "Inloggen" }));
    expect(await screen.findByRole("alert")).toBeInTheDocument();
    expect(onSignedIn).not.toHaveBeenCalled();
  });

  it("offers the way to the registration view", async () => {
    const onRegister = vi.fn();
    render(<SignInForm onSignedIn={vi.fn()} onRegister={onRegister} />);
    await userEvent.click(
      screen.getByRole("button", { name: "Nog geen account? Account aanmaken" }),
    );
    expect(onRegister).toHaveBeenCalledTimes(1);
  });
});
```

- [ ] **Step 2: Draai en zie het falen**

```bash
cd frontend && pnpm test
```

Verwacht: rood, `Failed to resolve import "@/app/_account/SignInForm"`.

- [ ] **Step 3: Schrijf `ConsentRow.tsx` en `SignInForm.tsx`**

Maak `frontend/src/app/_account/ConsentRow.tsx`:

```tsx
"use client";

import type { ConsentAction, ConsentKind } from "@/lib/accounts";

/**
 * What each consent is about, in three or four words.
 *
 * Interface text and not the consent itself: this names the row so a reader can
 * see at a glance which one they are looking at. The sentence they agree to is
 * the one from the API, underneath, and it is the only one that is recorded.
 */
export const CONSENT_LABELS: Readonly<Record<ConsentKind, string>> = {
  LEAD_GENERATION: "Doorgeven aan een installateur",
  METER_LINK: "Kwartiergegevens van uw slimme meter",
};

/**
 * One consent as a checkbox, for the registration form.
 *
 * No `required`, and that is a rule rather than an omission: article 7(4) says
 * a service made conditional on consent it does not need is a service whose
 * consent is not freely given. The API accepts a registration with both
 * refused, so the form may not refuse it either, and a test asserts this
 * attribute is absent.
 *
 * The two look identical and are the same size. Rule 4 of the frontend design
 * forbids scarcity and social proof on the advice page; here it means there is
 * no visual preference for yes over no.
 */
export function ConsentCheckbox({
  kind,
  text,
  checked,
  onChange,
}: {
  readonly kind: ConsentKind;
  readonly text: string;
  readonly checked: boolean;
  readonly onChange: (checked: boolean) => void;
}) {
  const id = `toestemming-${kind.toLowerCase()}`;
  return (
    <div className="flex gap-3">
      <input
        id={id}
        type="checkbox"
        className="mt-1"
        checked={checked}
        onChange={(event) => onChange(event.target.checked)}
      />
      <label htmlFor={id} className="max-w-[60ch] text-sm">
        <span className="block font-medium">{CONSENT_LABELS[kind]}</span>
        <span className="block text-ink-muted">{text}</span>
      </label>
    </div>
  );
}

/**
 * One consent as a row with a switch, for the account view.
 *
 * The asymmetry is chapter 6.3 and it is article 7(3) in a component: taking a
 * consent back may never be harder than giving it, so withdrawing works even
 * when the sentence could not be fetched, and granting does not. Granting with
 * no sentence on the screen would be agreeing to something nobody read.
 */
export function ConsentRow({
  kind,
  text,
  granted,
  busy,
  onToggle,
}: {
  readonly kind: ConsentKind;
  readonly text: string | null;
  readonly granted: boolean;
  readonly busy: boolean;
  readonly onToggle: (action: ConsentAction) => void;
}) {
  const action: ConsentAction = granted ? "WITHDRAWN" : "GRANTED";
  const unavailable = !granted && text === null;
  return (
    <div className="flex flex-col gap-2 border-t border-hairline pt-4">
      <p className="font-medium">{CONSENT_LABELS[kind]}</p>
      {text !== null && (
        <p className="max-w-[60ch] text-sm text-ink-muted">{text}</p>
      )}
      <p className="text-sm">
        {granted ? "Toestemming gegeven" : "Geen toestemming gegeven"}
      </p>
      {unavailable && (
        <p className="text-sm text-ink-muted">
          De toestemmingstekst kon niet worden opgehaald. Intrekken kan wel,
          aanzetten niet.
        </p>
      )}
      <p>
        <button
          type="button"
          className="button-quiet"
          disabled={busy || unavailable}
          aria-busy={busy}
          onClick={() => onToggle(action)}
        >
          {granted ? "Toestemming intrekken" : "Toestemming geven"}
        </button>
      </p>
    </div>
  );
}
```

Maak `frontend/src/app/_account/SignInForm.tsx`:

```tsx
"use client";

import { useId, useState } from "react";
import { getMe, login, type Me } from "@/lib/accounts";
import { describeAuthError } from "./messages";

/**
 * Signing in, and the one honest sentence underneath it.
 *
 * `me/` is asked after the 200 because `login/` answers with no body at all,
 * and that second call is not a retry: it is the question that fills the
 * account view. The order is also forced from the other side, by chapter 2 of
 * the design: nothing is posted anywhere before the first `me/` has come back,
 * because that is the response that carries the CSRF cookie.
 */
export function SignInForm({
  onSignedIn,
  onRegister,
}: {
  readonly onSignedIn: (me: Me) => void;
  readonly onRegister: () => void;
}) {
  const emailId = useId();
  const passwordId = useId();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [failure, setFailure] = useState<string | null>(null);

  async function submit(): Promise<void> {
    setBusy(true);
    setFailure(null);
    try {
      await login({ email, password });
      onSignedIn(await getMe());
    } catch (error) {
      setFailure(describeAuthError(error));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section aria-labelledby="inloggen" className="flex flex-col gap-6">
      <h2 id="inloggen" className="text-2xl">
        Inloggen
      </h2>
      <form
        noValidate
        className="flex flex-col gap-4"
        onSubmit={(event) => {
          event.preventDefault();
          if (!busy) void submit();
        }}
      >
        <div className="flex flex-col gap-1">
          <label htmlFor={emailId}>E-mailadres</label>
          <input
            id={emailId}
            type="email"
            autoComplete="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
          />
        </div>
        <div className="flex flex-col gap-1">
          <label htmlFor={passwordId}>Wachtwoord</label>
          <input
            id={passwordId}
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />
        </div>
        <p>
          <button
            type="submit"
            className="button-accent"
            disabled={busy}
            aria-busy={busy}
          >
            Inloggen
          </button>
        </p>
      </form>
      {failure !== null && (
        <p role="alert" className="text-danger">
          {failure}
        </p>
      )}
      <p className="max-w-[60ch] text-sm text-ink-muted">
        Bent u uw wachtwoord kwijt, dan kunnen wij het niet herstellen. Er is nog
        geen wachtwoordherstel, en zonder uw wachtwoord komt u ook niet meer bij
        de knop waarmee u uw account verwijdert.
      </p>
      <p>
        <button type="button" className="button-quiet" onClick={onRegister}>
          Nog geen account? Account aanmaken
        </button>
      </p>
    </section>
  );
}
```

- [ ] **Step 4: Draai en zie de inlogweergave groen worden**

```bash
cd frontend && pnpm test
```

Verwacht: de zes tests uit stap 1 slagen.

- [ ] **Step 5: Schrijf de falende tests voor de registratieweergave**

Maak `frontend/tests/account/RegisterForm.test.tsx`:

```tsx
import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import consentTexts from "../fixtures/consent-texts.json";
import me from "../fixtures/me-response.json";
import { RegisterForm } from "@/app/_account/RegisterForm";

afterEach(() => vi.unstubAllGlobals());

function stub(answers: readonly { status: number; body?: unknown }[]) {
  let index = 0;
  const fetchMock = vi.fn<typeof fetch>(async () => {
    const answer = answers[index];
    index += 1;
    if (answer === undefined) throw new Error(`request ${index} was not planned for`);
    return new Response(JSON.stringify(answer.body ?? null), {
      status: answer.status,
      headers: { "content-type": "application/json" },
    });
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

async function fillIn(): Promise<void> {
  await userEvent.type(screen.getByLabelText("E-mailadres"), "iemand@voorbeeld.nl");
  await userEvent.type(screen.getByLabelText("Wachtwoord"), "een-heel-lang-wachtwoord");
}

describe("the registration view", () => {
  it("shows the sentence the API sent, byte for byte", async () => {
    stub([{ status: 200, body: consentTexts }]);
    render(<RegisterForm onRegistered={vi.fn()} onSignIn={vi.fn()} />);
    expect(
      await screen.findByText(consentTexts.texts.METER_LINK),
    ).toBeInTheDocument();
    expect(
      screen.getByText(consentTexts.texts.LEAD_GENERATION),
    ).toBeInTheDocument();
  });

  it("starts with both boxes unticked and neither one required", async () => {
    // Not pre-ticked is a property of this line and of the serializer, which
    // gives the fields no default. Not required is article 7(4): the API
    // creates the account with both refused, so the form may not refuse it.
    stub([{ status: 200, body: consentTexts }]);
    render(<RegisterForm onRegistered={vi.fn()} onSignIn={vi.fn()} />);
    const boxes = await screen.findAllByRole("checkbox");
    expect(boxes).toHaveLength(2);
    for (const box of boxes) {
      expect(box).not.toBeChecked();
      expect(box).not.toBeRequired();
    }
  });

  it("cannot be submitted while the consent texts have not come back", () => {
    // A `true` sent for a sentence nobody read is not consent, so there is
    // nothing to press until the sentences are on the screen.
    vi.stubGlobal(
      "fetch",
      vi.fn<typeof fetch>(() => new Promise(() => {})),
    );
    render(<RegisterForm onRegistered={vi.fn()} onSignIn={vi.fn()} />);
    expect(
      screen.queryByRole("button", { name: "Account aanmaken" }),
    ).not.toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent(
      "De toestemmingsteksten worden opgehaald.",
    );
  });

  it("says so, and offers no button, when the texts could not be fetched", async () => {
    stub([{ status: 500, body: {} }]);
    render(<RegisterForm onRegistered={vi.fn()} onSignIn={vi.fn()} />);
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "De toestemmingsteksten konden niet worden opgehaald.",
    );
    expect(
      screen.queryByRole("button", { name: "Account aanmaken" }),
    ).not.toBeInTheDocument();
  });

  it("registers with both consents refused, which the API accepts", async () => {
    const fetchMock = stub([
      { status: 200, body: consentTexts },
      { status: 201 },
      { status: 200, body: me },
    ]);
    const onRegistered = vi.fn();
    render(<RegisterForm onRegistered={onRegistered} onSignIn={vi.fn()} />);
    await screen.findAllByRole("checkbox");
    await fillIn();
    await userEvent.click(screen.getByRole("button", { name: "Account aanmaken" }));
    const body = JSON.parse(
      String((fetchMock.mock.calls[1]?.[1] as RequestInit).body),
    );
    expect(body).toEqual({
      email: "iemand@voorbeeld.nl",
      password: "een-heel-lang-wachtwoord",
      consent_meter_link: false,
      consent_lead_generation: false,
      text_version: consentTexts.text_version,
    });
    expect(onRegistered).toHaveBeenCalledWith(me);
  });

  it("sends the version the sentences on the screen came with", async () => {
    // Not a constant in the frontend: that would be a second place the version
    // lives, and the 400 in chapter 5.2 exists precisely to close the window
    // in which those two can disagree.
    const fetchMock = stub([
      { status: 200, body: { ...consentTexts, text_version: "2027-01-01" } },
      { status: 201 },
      { status: 200, body: me },
    ]);
    render(<RegisterForm onRegistered={vi.fn()} onSignIn={vi.fn()} />);
    await screen.findAllByRole("checkbox");
    await fillIn();
    await userEvent.click(screen.getByRole("button", { name: "Account aanmaken" }));
    const body = JSON.parse(
      String((fetchMock.mock.calls[1]?.[1] as RequestInit).body),
    );
    expect(body.text_version).toBe("2027-01-01");
  });

  it("shows the API's Dutch message on a stale version", async () => {
    stub([
      { status: 200, body: consentTexts },
      {
        status: 400,
        body: {
          text_version: [
            "de toestemmingstekst is gewijzigd, herlaad de pagina en probeer het opnieuw",
          ],
        },
      },
    ]);
    render(<RegisterForm onRegistered={vi.fn()} onSignIn={vi.fn()} />);
    await screen.findAllByRole("checkbox");
    await fillIn();
    await userEvent.click(screen.getByRole("button", { name: "Account aanmaken" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "de toestemmingstekst is gewijzigd",
    );
  });

  it("offers the way back to the sign-in view", async () => {
    stub([{ status: 200, body: consentTexts }]);
    const onSignIn = vi.fn();
    render(<RegisterForm onRegistered={vi.fn()} onSignIn={onSignIn} />);
    await userEvent.click(
      await screen.findByRole("button", { name: "Ik heb al een account. Inloggen" }),
    );
    expect(onSignIn).toHaveBeenCalledTimes(1);
  });
});
```

- [ ] **Step 6: Schrijf `RegisterForm.tsx`**

```tsx
"use client";

import { useEffect, useId, useState } from "react";
import {
  CONSENT_KINDS,
  getConsentTexts,
  getMe,
  register,
  type ConsentTexts,
  type Me,
} from "@/lib/accounts";
import { ConsentCheckbox } from "./ConsentRow";
import { describeAuthError } from "./messages";

/**
 * Making an account, which is two fields and two questions that may both be no.
 *
 * The consent texts are fetched when this view opens and not on every page
 * load: `auth-read` is one bucket of 120 an hour shared with `me/`, and
 * somebody who only signs in never sees these sentences and should not pay for
 * them.
 *
 * While they have not come back there is no submit button at all, which is
 * stronger than a disabled one and says the same thing: a `true` sent for a
 * sentence nobody has read is not consent.
 */
export function RegisterForm({
  onRegistered,
  onSignIn,
}: {
  readonly onRegistered: (me: Me) => void;
  readonly onSignIn: () => void;
}) {
  const emailId = useId();
  const passwordId = useId();
  const [texts, setTexts] = useState<ConsentTexts | null>(null);
  const [textsFailed, setTextsFailed] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [given, setGiven] = useState<Record<string, boolean>>({});
  const [busy, setBusy] = useState(false);
  const [failure, setFailure] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    getConsentTexts()
      .then((answer) => {
        if (alive) setTexts(answer);
      })
      .catch(() => {
        if (alive) setTextsFailed(true);
      });
    return () => {
      alive = false;
    };
  }, []);

  async function submit(current: ConsentTexts): Promise<void> {
    setBusy(true);
    setFailure(null);
    try {
      await register({
        email,
        password,
        consent_meter_link: given["METER_LINK"] === true,
        consent_lead_generation: given["LEAD_GENERATION"] === true,
        // The version the sentences above came with, never a constant here.
        text_version: current.text_version,
      });
      onRegistered(await getMe());
    } catch (error) {
      setFailure(describeAuthError(error));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section aria-labelledby="registreren" className="flex flex-col gap-6">
      <h2 id="registreren" className="text-2xl">
        Account aanmaken
      </h2>
      {texts === null && !textsFailed && (
        <p role="status">De toestemmingsteksten worden opgehaald.</p>
      )}
      {textsFailed && (
        <p role="alert" className="text-danger">
          De toestemmingsteksten konden niet worden opgehaald. Herlaad de pagina
          om een account aan te maken.
        </p>
      )}
      {texts !== null && (
        <form
          noValidate
          className="flex flex-col gap-4"
          onSubmit={(event) => {
            event.preventDefault();
            if (!busy) void submit(texts);
          }}
        >
          <div className="flex flex-col gap-1">
            <label htmlFor={emailId}>E-mailadres</label>
            <input
              id={emailId}
              type="email"
              autoComplete="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
            />
          </div>
          <div className="flex flex-col gap-1">
            <label htmlFor={passwordId}>Wachtwoord</label>
            <input
              id={passwordId}
              type="password"
              autoComplete="new-password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
            />
          </div>
          {CONSENT_KINDS.map((kind) => (
            <ConsentCheckbox
              key={kind}
              kind={kind}
              text={texts.texts[kind]}
              checked={given[kind] === true}
              onChange={(checked) =>
                setGiven((current) => ({ ...current, [kind]: checked }))
              }
            />
          ))}
          <p>
            <button
              type="submit"
              className="button-accent"
              disabled={busy}
              aria-busy={busy}
            >
              Account aanmaken
            </button>
          </p>
        </form>
      )}
      {failure !== null && (
        <p role="alert" className="text-danger">
          {failure}
        </p>
      )}
      <p>
        <button type="button" className="button-quiet" onClick={onSignIn}>
          Ik heb al een account. Inloggen
        </button>
      </p>
    </section>
  );
}
```

- [ ] **Step 7: Draai en zie alles groen worden**

```bash
cd frontend && pnpm test
```

Verwacht: groen, en de vier dekkingsdrempels gehaald.

- [ ] **Step 8: Toon aan dat de drie dragende controles rood kunnen worden**

Drie tijdelijke bewerkingen, allemaal met de hand terugzetten:

1. Zet `required` op het `input` in `ConsentCheckbox` en draai `pnpm test`. Verwacht: `starts with both boxes unticked and neither one required` rood. Dat is artikel 7 lid 4 in een assertie.
2. Vervang `text={texts.texts[kind]}` door `text={CONSENT_LABELS[kind]}` en draai opnieuw. Verwacht: `shows the sentence the API sent, byte for byte` rood, omdat de getoonde zin dan niet meer de geleverde is.
3. Vervang in `submit` `text_version: current.text_version` door `text_version: "2026-09-04"` en draai opnieuw. Verwacht: `sends the version the sentences on the screen came with` rood met `2026-09-04` waar `2027-01-01` hoort. Dat is de tweede plek waar de versie zou wonen, en dit is de test die dat verbiedt.

- [ ] **Step 9: Werk `ui-strings.txt` bij**

```bash
cd frontend && pnpm build && UPDATE_UI_STRINGS=1 pnpm e2e language
cd frontend && pnpm e2e language
```

Verwacht: de eerste run herschrijft en faalt, de tweede is groen. Lees de diff tegen de lijst in de kop van deze taak. De twee toestemmingsteksten horen er **niet** in te staan: die komen uit de API en staan nergens in `src/**`. Staat er een van beide wel in, dan is dat dezelfde bevinding als `test_no_consent_text_lives_in_the_frontend` uit taak 3 en de zin hoort uit de broncode weg.

- [ ] **Step 10: Commit**

```bash
git add frontend/src/app/_account/ConsentRow.tsx frontend/src/app/_account/SignInForm.tsx frontend/src/app/_account/RegisterForm.tsx frontend/tests/account/SignInForm.test.tsx frontend/tests/account/RegisterForm.test.tsx frontend/tests/ui-strings.txt
git commit
```

Boodschap: `feat(frontend): sign in, register, and two consents that may both be no`.

---

### Taak 7: De route, en de schakeling tussen de drie weergaven

**Hangt af van:** taak 6.

**Files:**
- Create: `frontend/src/app/account/page.tsx`, `frontend/src/app/_account/AccountPage.tsx`, `frontend/tests/account/AccountPage.test.tsx`
- Modify: `frontend/tests/ui-strings.txt`

**Interfaces:**
- Consumes: `LOADING`, `loadSession`, `type AccountState` uit `./session`; `SignInForm` en `RegisterForm` uit taak 6; `type Me` uit `@/lib/accounts`.
- Produces: `AccountPage()` in `_account/AccountPage.tsx`; `AccountRoute()`, de defaultexport van `account/page.tsx`; en de statische `<h1>` en alinea die de geëxporteerde HTML draagt.

`page.tsx` is een servercomponent en er komt geen `account/layout.tsx`: alleen `AccountPage.tsx` draagt `"use client"`, dus `page.tsx` kan zelf `metadata` exporteren, de `<h1>` neerzetten en de client eronder hangen.

`/account/` komt **niet** in `SITEMAP_ROUTES` en er verandert niets aan `robots.ts`. Een inlogformulier is geen antwoord op een zoekvraag; de twee tests die de sitemaplengte vergelijken lezen die constante en blijven zonder wijziging groen.

Nieuwe zinnen: `Uw account`, `Uw gegevens`, `Uw gegevens worden opgehaald.`, de alinea onder de `<h1>` en de `description` in de metadata.

- [ ] **Step 1: Schrijf de falende tests voor de schakeling**

Maak `frontend/tests/account/AccountPage.test.tsx`:

```tsx
import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import me from "../fixtures/me-response.json";
import consentTexts from "../fixtures/consent-texts.json";
import { AccountPage } from "@/app/_account/AccountPage";

afterEach(() => vi.unstubAllGlobals());

/** One answer per request, in order, plus the addresses that were asked for. */
function stub(answers: readonly { status: number; body?: unknown; throws?: boolean }[]) {
  const seen: string[] = [];
  let index = 0;
  const fetchMock = vi.fn<typeof fetch>(async (input: RequestInfo | URL) => {
    seen.push(String(input));
    const answer = answers[index];
    index += 1;
    if (answer === undefined) throw new Error(`request ${index} was not planned for`);
    if (answer.throws === true) throw new TypeError("Failed to fetch");
    return answer.status === 204
      ? new Response(null, { status: answer.status })
      : new Response(JSON.stringify(answer.body ?? null), {
          status: answer.status,
          headers: { "content-type": "application/json" },
        });
  });
  vi.stubGlobal("fetch", fetchMock);
  return { fetchMock, seen };
}

describe("which of the three views is on the screen", () => {
  it("says the data is being fetched, rather than showing an empty element", () => {
    // Chapter 3. `/berekenen/` shipped zero headings and 32 words of body text
    // on 2026-09-02, all of it header and footer, and a blank `main` is the
    // wrong answer for a visitor on a slow connection as well as for a crawler.
    vi.stubGlobal("fetch", vi.fn<typeof fetch>(() => new Promise(() => {})));
    render(<AccountPage />);
    expect(screen.getByRole("status")).toHaveTextContent(
      "Uw gegevens worden opgehaald.",
    );
  });

  it("shows the account when me/ answers 200", async () => {
    stub([{ status: 200, body: me }, { status: 200, body: consentTexts }]);
    render(<AccountPage />);
    expect(await screen.findByText(me.email)).toBeInTheDocument();
  });

  it("shows the sign-in view when me/ answers 401 twice around one exchange", async () => {
    stub([
      { status: 401, body: { detail: "u bent niet ingelogd" } },
      { status: 200 },
      { status: 401, body: { detail: "u bent niet ingelogd" } },
    ]);
    render(<AccountPage />);
    expect(
      await screen.findByRole("button", { name: "Inloggen" }),
    ).toBeInTheDocument();
    expect(screen.queryByText(me.email)).not.toBeInTheDocument();
  });

  it("shows the sign-in view with a message when nothing came back at all", async () => {
    // Chapter 6.5, and this is not a hypothetical: e2e/privacy.spec.ts opens
    // every page a visitor can reach without an advice and mocks nothing, so
    // this is the state this route is in there.
    stub([{ status: 0, throws: true }]);
    render(<AccountPage />);
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Wij konden de server niet bereiken.",
    );
    expect(screen.getByRole("button", { name: "Inloggen" })).toBeInTheDocument();
  });

  it("switches to the registration view and back without leaving the route", async () => {
    const userEvent = (await import("@testing-library/user-event")).default;
    stub([
      { status: 401, body: { detail: "u bent niet ingelogd" } },
      { status: 401, body: { detail: "uw sessie is verlopen, log opnieuw in" } },
      { status: 200, body: consentTexts },
    ]);
    render(<AccountPage />);
    await userEvent.click(
      await screen.findByRole("button", { name: "Nog geen account? Account aanmaken" }),
    );
    expect(
      await screen.findByRole("heading", { name: "Account aanmaken" }),
    ).toBeInTheDocument();
    await userEvent.click(
      screen.getByRole("button", { name: "Ik heb al een account. Inloggen" }),
    );
    expect(
      screen.getByRole("heading", { name: "Inloggen" }),
    ).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Draai en zie het falen**

```bash
cd frontend && pnpm test
```

Verwacht: rood, `Failed to resolve import "@/app/_account/AccountPage"`.

- [ ] **Step 3: Schrijf de schakelaar**

Maak `frontend/src/app/_account/AccountPage.tsx`:

```tsx
"use client";

import { useEffect, useState } from "react";
import type { Me } from "@/lib/accounts";
import { RegisterForm } from "./RegisterForm";
import { SignInForm } from "./SignInForm";
import { LOADING, loadSession, type AccountState } from "./session";

/** Which of the two signed-out forms is showing. State, not an address. */
type SignedOutView = "sign_in" | "register";

/**
 * One route, three views, and the state comes from `me/`.
 *
 * `/account/inloggen/` and `/account/registreren/` would be two statically
 * exported pages that both ask `me/` the same question in order to find out
 * which of the two they are allowed to show, plus a third that does the same.
 * The choice between the three views is state and not an address.
 *
 * Only a 200 on `me/` produces the account view. Every other outcome, a request
 * that never arrived included, produces the sign-in view, because nothing is
 * then known about who is signed in.
 */
export function AccountPage() {
  const [state, setState] = useState<AccountState>(LOADING);
  const [view, setView] = useState<SignedOutView>("sign_in");

  useEffect(() => {
    // `alive` rather than an abort: the answer decides what is on the screen,
    // and setting state on a component that has gone is a warning in
    // development and a leak in a test that renders this twice.
    let alive = true;
    void loadSession().then((next) => {
      if (alive) setState(next);
    });
    return () => {
      alive = false;
    };
  }, []);

  function signedIn(who: Me): void {
    setState({ status: "signed_in", me: who });
  }

  if (state.status === "loading") {
    // A visible sentence and not an empty element. See the test above for the
    // measurement that made this a rule rather than a nicety.
    return <p role="status">Uw gegevens worden opgehaald.</p>;
  }

  if (state.status === "signed_in") {
    return (
      <section aria-labelledby="uw-gegevens" className="flex flex-col gap-4">
        <h2 id="uw-gegevens" className="text-2xl">
          Uw gegevens
        </h2>
        <p>{state.me.email}</p>
      </section>
    );
  }

  return (
    <div className="flex flex-col gap-8">
      {state.notice !== null && (
        <p role="alert" className="text-danger">
          {state.notice}
        </p>
      )}
      {view === "sign_in" ? (
        <SignInForm onSignedIn={signedIn} onRegister={() => setView("register")} />
      ) : (
        <RegisterForm onRegistered={signedIn} onSignIn={() => setView("sign_in")} />
      )}
    </div>
  );
}
```

Maak `frontend/src/app/account/page.tsx`:

```tsx
import type { Metadata } from "next";

import { AccountPage } from "../_account/AccountPage";

const PATH = "/account/";
const TITLE = "Uw account";
const DESCRIPTION =
  "Inloggen of een account aanmaken, uw toestemmingen bekijken en omzetten, uw gegevens downloaden of uw account verwijderen.";

export const metadata: Metadata = {
  title: TITLE,
  description: DESCRIPTION,
  // A string and not a URL instance, for the reason privacy/page.tsx gives:
  // Next treats a URL here as a base and canonicalises the page to the root.
  alternates: { canonical: PATH },
};

/**
 * The account route, and the half of it that is in the file on disk.
 *
 * A server component, so the heading and the paragraph below are in
 * `out/account/index.html` whether or not any JavaScript runs. The three views
 * are underneath in a client component, because the only way to know who is
 * signed in is to ask the API, and the cookies that answer that are httpOnly.
 *
 * This route is deliberately absent from SITEMAP_ROUTES: a sign-in form is not
 * an answer to a search, and the sitemap is the list this product says it wants
 * indexed.
 */
export default function AccountRoute() {
  return (
    <div className="mx-auto w-full max-w-[var(--shell-max)] px-6 py-16">
      <div className="flex w-full max-w-2xl flex-col gap-10">
        <div className="flex flex-col gap-3">
          <h1 className="text-3xl">{TITLE}</h1>
          <p className="text-ink-muted">
            Hier logt u in of maakt u een account aan. In uw account ziet u welke
            toestemmingen u heeft gegeven, kunt u ze omzetten, uw gegevens
            downloaden en uw account verwijderen. Voor de rekenmachine is geen
            account nodig.
          </p>
        </div>
        <AccountPage />
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Draai en zie de vijf groen worden**

```bash
cd frontend && pnpm test && pnpm typecheck && pnpm build
```

Verwacht: alle drie groen. `pnpm build` schrijft `out/account/index.html`; controleer met het oog dat daar een `<h1>` in staat en de alinea eronder.

- [ ] **Step 5: Toon aan dat de schakeling rood kan worden**

Vervang tijdelijk `if (state.status === "signed_in")` door `if (state.status !== "loading")` en draai `pnpm test`. Verwacht: `shows the sign-in view when me/ answers 401` rood met een ontbrekende knop. Zet de regel met de hand terug.

Vervang daarna de laadtak door `return null` en draai opnieuw. Verwacht: `says the data is being fetched` rood, `Unable to find role="status"`. Zet hem terug.

- [ ] **Step 6: Werk `ui-strings.txt` bij**

```bash
cd frontend && pnpm build && UPDATE_UI_STRINGS=1 pnpm e2e language
cd frontend && pnpm e2e language
```

Lees de diff tegen de lijst in de kop van deze taak. Naast de zinnen staan er `sign_in`, `register` en de klasselijsten in; dat is de extractor die op positie oordeelt.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/app/account/page.tsx frontend/src/app/_account/AccountPage.tsx frontend/tests/account/AccountPage.test.tsx frontend/tests/ui-strings.txt
git commit
```

Boodschap: `feat(frontend): one route for the account, with three views and one question`.

---

### Taak 8: De accountweergave: toestemmingen, export, uitloggen, verwijderen

**Hangt af van:** taak 7.

**Files:**
- Modify: `frontend/src/app/_account/AccountPage.tsx`, `frontend/tests/account/AccountPage.test.tsx`, `frontend/tests/ui-strings.txt`
- Create: `frontend/src/app/_account/download.ts`

**Interfaces:**
- Consumes: `ConsentRow` uit `./ConsentRow` (niet `CONSENT_LABELS`: die blijft binnen `ConsentRow.tsx`, en importeren om dit blok te laten kloppen zou `eslint --max-warnings 0` op een ongebruikte import laten struikelen); `getConsentTexts`, `postConsent`, `exportAccount`, `logout`, `deleteAccount`, `CONSENT_KINDS`, `type ConsentKind`, `type ConsentAction`, `type ConsentTexts` uit `@/lib/accounts`; `describeAuthError` uit `./messages`; `signedOut` uit `./session`.
- Produces: `EXPORT_FILENAME = "ampeer-gegevens.json"` en `downloadJson(text: string): void` in `download.ts`; de interne component `AccountView` in `AccountPage.tsx`.

De bevestigingsregel na een verwijdering staat in de eigen state van `AccountPage` en niet in `AccountState.notice`. Reden: `notice` wordt in een `role="alert"` getoond omdat hij altijd een mislukking beschrijft, en "uw account is verwijderd" is geen mislukking maar het gevraagde resultaat. Dat is een `role="status"` boven dezelfde uitgelogde weergave.

Nieuwe zinnen: `Gegevens exporteren`, `Uitloggen`, `Account verwijderen`, `Verwijderen bevestigen`, `Uw wachtwoord`, `Uw account is verwijderd.`, en `ampeer-gegevens.json` (een bestandsnaam, die de extractor ook oppikt).

- [ ] **Step 1: Schrijf de falende tests voor de vier handelingen**

Voeg toe aan `frontend/tests/account/AccountPage.test.tsx`:

```tsx
describe("the account view", () => {
  it("shows both consent rows with the sentence from the API beside them", async () => {
    stub([{ status: 200, body: me }, { status: 200, body: consentTexts }]);
    render(<AccountPage />);
    expect(
      await screen.findByText(consentTexts.texts.METER_LINK),
    ).toBeInTheDocument();
    expect(screen.getByText(consentTexts.texts.LEAD_GENERATION)).toBeInTheDocument();
  });

  it("updates one row from the answer, without asking me/ again", async () => {
    // The API has just answered this question. A second me/ would spend an
    // auth-read and could fill the row with an answer that has caught up with
    // a change made somewhere else.
    const userEvent = (await import("@testing-library/user-event")).default;
    const { seen } = stub([
      { status: 200, body: me },
      { status: 200, body: consentTexts },
      { status: 200, body: { kind: "LEAD_GENERATION", granted: true } },
    ]);
    render(<AccountPage />);
    await userEvent.click(
      await screen.findByRole("button", { name: "Toestemming geven" }),
    );
    expect(
      await screen.findAllByText("Toestemming gegeven"),
    ).toHaveLength(2);
    expect(seen.filter((url) => url.includes("/api/auth/me/"))).toHaveLength(1);
  });

  it("sends the version with a grant and nothing with a withdrawal", async () => {
    const userEvent = (await import("@testing-library/user-event")).default;
    const { fetchMock } = stub([
      { status: 200, body: me },
      { status: 200, body: consentTexts },
      { status: 200, body: { kind: "METER_LINK", granted: false } },
    ]);
    render(<AccountPage />);
    await userEvent.click(
      await screen.findByRole("button", { name: "Toestemming intrekken" }),
    );
    const body = JSON.parse(
      String((fetchMock.mock.calls[2]?.[1] as RequestInit).body),
    );
    expect(body).toEqual({ kind: "METER_LINK", action: "WITHDRAWN" });
  });

  it("lets a consent be withdrawn but not granted when the text is missing", async () => {
    // Chapter 6.3, and it is article 7(3) on the screen: granting with no
    // sentence in front of the reader would be consent to something nobody
    // read; refusing a withdrawal for the same reason would make taking it
    // back harder than giving it.
    stub([{ status: 200, body: me }, { status: 500, body: {} }]);
    render(<AccountPage />);
    expect(
      await screen.findByRole("button", { name: "Toestemming intrekken" }),
    ).toBeEnabled();
    expect(screen.getByRole("button", { name: "Toestemming geven" })).toBeDisabled();
  });

  it("offers the export as a file built from the text the API sent", async () => {
    const userEvent = (await import("@testing-library/user-event")).default;
    const raw = JSON.stringify(exportPayload);
    const created: Blob[] = [];
    // jsdom implements neither of these, so both are stubbed rather than
    // spied on. What is asserted is the bytes that reached the Blob.
    vi.stubGlobal("URL", {
      ...URL,
      createObjectURL: (blob: Blob) => {
        created.push(blob);
        return "blob:een-url";
      },
      revokeObjectURL: () => {},
    });
    stub([
      { status: 200, body: me },
      { status: 200, body: consentTexts },
      { status: 200, body: exportPayload },
    ]);
    render(<AccountPage />);
    await userEvent.click(
      await screen.findByRole("button", { name: "Gegevens exporteren" }),
    );
    expect(created).toHaveLength(1);
    await expect(created[0]?.text()).resolves.toBe(raw);
  });

  it("signs out on a 204 and asks nothing afterwards", async () => {
    const userEvent = (await import("@testing-library/user-event")).default;
    const { seen } = stub([
      { status: 200, body: me },
      { status: 200, body: consentTexts },
      { status: 204 },
      { status: 200, body: consentTexts },
    ]);
    render(<AccountPage />);
    await userEvent.click(await screen.findByRole("button", { name: "Uitloggen" }));
    expect(
      await screen.findByRole("button", { name: "Inloggen" }),
    ).toBeInTheDocument();
    expect(seen.filter((url) => url.includes("/api/auth/me/"))).toHaveLength(1);
    expect(seen.filter((url) => url.includes("/api/auth/refresh/"))).toHaveLength(0);
  });

  it("asks for the password again before deleting, and moves focus to it", async () => {
    const userEvent = (await import("@testing-library/user-event")).default;
    stub([{ status: 200, body: me }, { status: 200, body: consentTexts }]);
    render(<AccountPage />);
    const opener = await screen.findByRole("button", { name: "Account verwijderen" });
    expect(opener).toHaveAttribute("aria-expanded", "false");
    await userEvent.click(opener);
    expect(opener).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByLabelText("Uw wachtwoord")).toHaveFocus();
  });

  it("confirms in one line and shows the sign-in view after a 204", async () => {
    const userEvent = (await import("@testing-library/user-event")).default;
    const { seen } = stub([
      { status: 200, body: me },
      { status: 200, body: consentTexts },
      { status: 204 },
      { status: 200, body: consentTexts },
    ]);
    render(<AccountPage />);
    await userEvent.click(
      await screen.findByRole("button", { name: "Account verwijderen" }),
    );
    await userEvent.type(
      screen.getByLabelText("Uw wachtwoord"),
      "een-heel-lang-wachtwoord",
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Verwijderen bevestigen" }),
    );
    expect(await screen.findByRole("status")).toHaveTextContent(
      "Uw account is verwijderd.",
    );
    expect(screen.getByRole("button", { name: "Inloggen" })).toBeInTheDocument();
    // The 204 is the proof. A me/ afterwards would spend an auth-read on a
    // question already answered, and a 401 there is indistinguishable from a
    // session that simply expired. There is also nothing left to exchange:
    // the RefreshSession rows went with the account.
    expect(seen.filter((url) => url.includes("/api/auth/me/"))).toHaveLength(1);
    expect(seen.filter((url) => url.includes("/api/auth/refresh/"))).toHaveLength(0);
  });

  it("shows the API's own sentence when a wrong password is given", async () => {
    const userEvent = (await import("@testing-library/user-event")).default;
    stub([
      { status: 200, body: me },
      { status: 200, body: consentTexts },
      { status: 403, body: { detail: "e-mailadres of wachtwoord klopt niet" } },
    ]);
    render(<AccountPage />);
    await userEvent.click(
      await screen.findByRole("button", { name: "Account verwijderen" }),
    );
    await userEvent.type(screen.getByLabelText("Uw wachtwoord"), "verkeerd");
    await userEvent.click(
      screen.getByRole("button", { name: "Verwijderen bevestigen" }),
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "e-mailadres of wachtwoord klopt niet",
    );
    expect(screen.getByText(me.email)).toBeInTheDocument();
  });
});
```

Voeg `import exportPayload from "../fixtures/export-response.json";` toe aan de imports bovenin dat bestand.

- [ ] **Step 2: Draai en zie het falen**

```bash
cd frontend && pnpm test
```

Verwacht: negen rode tests, allemaal op een knop of een tekst die niet bestaat.

- [ ] **Step 3: Schrijf `download.ts`**

Maak `frontend/src/app/_account/download.ts`:

```ts
/** What the file is called on the visitor's own disk. */
export const EXPORT_FILENAME = "ampeer-gegevens.json";

/**
 * Hand the export to the browser as a file, built from the text the API sent.
 *
 * The text goes into the Blob unchanged. Not `JSON.parse` and `JSON.stringify`
 * around it: every amount inside an advice is a string because JSON has floats
 * and no decimals, and a round trip through a parser is the rounding this
 * project avoids everywhere else. There is a semgrep rule on `parseFloat` over
 * an amount and it would see nothing here, because it would be a
 * `JSON.stringify` of a parsed tree doing it quietly.
 *
 * The object URL is revoked immediately after the click. The browser has
 * already read it by then, and an unrevoked one keeps the whole export alive
 * in memory for as long as the document lives.
 */
export function downloadJson(text: string): void {
  const url = URL.createObjectURL(
    new Blob([text], { type: "application/json" }),
  );
  const link = document.createElement("a");
  link.href = url;
  link.download = EXPORT_FILENAME;
  document.body.append(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}
```

- [ ] **Step 4: Schrijf de accountweergave**

In `frontend/src/app/_account/AccountPage.tsx`: vervang de `signed_in`-tak door een aanroep van `AccountView`, voeg de bevestigingsstate toe, en zet de component eronder. De twee takken staan hieronder voluit.

In `AccountPage`, naast de bestaande state:

```tsx
  const [confirmation, setConfirmation] = useState<string | null>(null);
```

De twee takken worden:

```tsx
  if (state.status === "signed_in") {
    return (
      <AccountView
        me={state.me}
        onSignedOut={(line) => {
          setConfirmation(line);
          setView("sign_in");
          setState(signedOut(null));
        }}
      />
    );
  }

  return (
    <div className="flex flex-col gap-8">
      {confirmation !== null && <p role="status">{confirmation}</p>}
      {state.notice !== null && (
        <p role="alert" className="text-danger">
          {state.notice}
        </p>
      )}
      {view === "sign_in" ? (
        <SignInForm onSignedIn={signedIn} onRegister={() => setView("register")} />
      ) : (
        <RegisterForm onRegistered={signedIn} onSignIn={() => setView("sign_in")} />
      )}
    </div>
  );
```

En eronder, in hetzelfde bestand:

```tsx
/**
 * The account: an address, two consents, and three things you can do with it.
 *
 * The consent texts are fetched here as well as in the registration form, for
 * the reason chapter 6.2 gives: they are fetched when a view that shows those
 * sentences opens, and not on every page load. Somebody who only signs in
 * never opens either view and never spends the request.
 */
function AccountView({
  me,
  onSignedOut,
}: {
  readonly me: Me;
  readonly onSignedOut: (confirmation: string | null) => void;
}) {
  const passwordId = useId();
  const passwordField = useRef<HTMLInputElement>(null);
  const [texts, setTexts] = useState<ConsentTexts | null>(null);
  const [consents, setConsents] = useState<Record<string, boolean>>({
    ...me.consents,
  });
  const [busy, setBusy] = useState<string | null>(null);
  const [failure, setFailure] = useState<string | null>(null);
  const [expanded, setExpanded] = useState(false);
  const [password, setPassword] = useState("");

  useEffect(() => {
    let alive = true;
    getConsentTexts()
      .then((answer) => {
        if (alive) setTexts(answer);
      })
      .catch(() => {
        // Deliberately silent. The rows below say what this costs, in the one
        // place where it changes what a visitor can do: granting.
        if (alive) setTexts(null);
      });
    return () => {
      alive = false;
    };
  }, []);

  // Focus follows the field that appeared, which is what makes the disclosure
  // usable from a keyboard rather than merely operable.
  useEffect(() => {
    if (expanded) passwordField.current?.focus();
  }, [expanded]);

  async function toggle(kind: ConsentKind, action: ConsentAction): Promise<void> {
    setBusy(kind);
    setFailure(null);
    try {
      const result = await postConsent(
        action === "GRANTED" && texts !== null
          ? { kind, action, text_version: texts.text_version }
          : { kind, action },
      );
      // The answer is the new state of that row. No second `me/`.
      setConsents((current) => ({ ...current, [result.kind]: result.granted }));
    } catch (error) {
      setFailure(describeAuthError(error));
    } finally {
      setBusy(null);
    }
  }

  async function download(): Promise<void> {
    setBusy("export");
    setFailure(null);
    try {
      downloadJson(await exportAccount());
    } catch (error) {
      setFailure(describeAuthError(error));
    } finally {
      setBusy(null);
    }
  }

  async function signOut(): Promise<void> {
    setBusy("logout");
    setFailure(null);
    try {
      await logout();
      // 204, view signed out, and no question asked afterwards.
      onSignedOut(null);
    } catch (error) {
      setFailure(describeAuthError(error));
      setBusy(null);
    }
  }

  async function remove(): Promise<void> {
    setBusy("delete");
    setFailure(null);
    try {
      await deleteAccount(password);
      onSignedOut("Uw account is verwijderd.");
    } catch (error) {
      setFailure(describeAuthError(error));
      setBusy(null);
    }
  }

  return (
    <section aria-labelledby="uw-gegevens" className="flex flex-col gap-6">
      <h2 id="uw-gegevens" className="text-2xl">
        Uw gegevens
      </h2>
      <p>{me.email}</p>

      {CONSENT_KINDS.map((kind) => (
        <ConsentRow
          key={kind}
          kind={kind}
          text={texts === null ? null : texts.texts[kind]}
          granted={consents[kind] === true}
          busy={busy === kind}
          onToggle={(action) => void toggle(kind, action)}
        />
      ))}

      {failure !== null && (
        <p role="alert" className="text-danger">
          {failure}
        </p>
      )}

      <div className="flex flex-wrap gap-3 border-t border-hairline pt-4">
        <button
          type="button"
          className="button-quiet"
          disabled={busy !== null}
          onClick={() => void download()}
        >
          Gegevens exporteren
        </button>
        <button
          type="button"
          className="button-quiet"
          disabled={busy !== null}
          onClick={() => void signOut()}
        >
          Uitloggen
        </button>
      </div>

      {/*
        Collapsed, this is a button and not a warning. It is the heaviest thing
        on the page and it should read as neither an offer nor a threat.
      */}
      <div className="flex flex-col gap-3 border-t border-hairline pt-4">
        <p>
          <button
            type="button"
            className="button-quiet"
            aria-expanded={expanded}
            onClick={() => setExpanded(!expanded)}
          >
            Account verwijderen
          </button>
        </p>
        {expanded && (
          <form
            noValidate
            className="flex flex-col gap-3"
            onSubmit={(event) => {
              event.preventDefault();
              if (busy === null) void remove();
            }}
          >
            <div className="flex flex-col gap-1">
              <label htmlFor={passwordId}>Uw wachtwoord</label>
              <input
                id={passwordId}
                ref={passwordField}
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
              />
            </div>
            <p>
              <button
                type="submit"
                className="button-accent"
                disabled={busy !== null}
                aria-busy={busy === "delete"}
              >
                Verwijderen bevestigen
              </button>
            </p>
          </form>
        )}
      </div>
    </section>
  );
}
```

Vul de imports bovenin aan. Dit is aanvullend en niet vervangend: taak 7 zette daar al `RegisterForm`, `SignInForm` en het drietal uit `./session` neer, en die blijven staan naast wat deze taak toevoegt. Het volledige, samengevoegde blok:

```tsx
import { useEffect, useId, useRef, useState } from "react";
import {
  CONSENT_KINDS,
  deleteAccount,
  exportAccount,
  getConsentTexts,
  logout,
  postConsent,
  type ConsentAction,
  type ConsentKind,
  type ConsentTexts,
  type Me,
} from "@/lib/accounts";
import { ConsentRow } from "./ConsentRow";
import { RegisterForm } from "./RegisterForm";
import { SignInForm } from "./SignInForm";
import { downloadJson } from "./download";
import { describeAuthError } from "./messages";
import { LOADING, loadSession, signedOut, type AccountState } from "./session";
```

- [ ] **Step 5: Draai en zie de negen groen worden**

```bash
cd frontend && pnpm test
```

Verwacht: groen, met de vier dekkingsdrempels gehaald.

- [ ] **Step 6: Toon aan dat de vier dragende controles rood kunnen worden**

Vier tijdelijke bewerkingen, allemaal met de hand terugzetten:

1. Voeg aan het eind van `toggle` een `setConsents({ ...(await getMe()).consents })` toe en draai `pnpm test`. Verwacht: `updates one row from the answer, without asking me/ again` rood met twee `me/`-verzoeken. Dat is de tweede vraag die hoofdstuk 6.3 verbiedt.
2. Vervang in `ConsentRow` de regel `disabled={busy || unavailable}` door `disabled={busy}` en draai opnieuw. Verwacht: `lets a consent be withdrawn but not granted when the text is missing` rood, want dan is aanzetten wel mogelijk zonder zin op het scherm.
3. Vervang in `download` de aanroep door `downloadJson(JSON.stringify(JSON.parse(await exportAccount())))` en draai opnieuw. Verwacht: `offers the export as a file built from the text the API sent` rood op de bytes. Dat is precies de ronde door de parser die een bedrag afrondt.
4. Voeg in `remove` na de 204 een `await getMe()` toe en draai opnieuw. Verwacht: `confirms in one line and shows the sign-in view after a 204` rood op de telling van `me/`.

- [ ] **Step 7: Werk `ui-strings.txt` bij en draai de poorten**

```bash
cd frontend && pnpm build && UPDATE_UI_STRINGS=1 pnpm e2e language
cd frontend && pnpm e2e language
cd frontend && pnpm lint && pnpm typecheck && pnpm format:check && pnpm test && pnpm build
```

Verwacht: alles groen. `ampeer-gegevens.json` verschijnt als regel in `ui-strings.txt`; dat is een bestandsnaam in een tekstpositie en de kop van dat bestand beschrijft die categorie.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/app/_account/AccountPage.tsx frontend/src/app/_account/download.ts frontend/tests/account/AccountPage.test.tsx frontend/tests/ui-strings.txt
git commit
```

Boodschap: `feat(frontend): the account view, and the four things it can do`.

---

### Taak 9: De ingang, en de twee bestaande e2e-specs die deze route nu tegenkomen

**Hangt af van:** taak 8.

**Files:**
- Modify: `frontend/src/app/_shell/SiteFooter.tsx`, `frontend/tests/app/LegalPages.test.tsx`, `frontend/e2e/theme.spec.ts`, `frontend/e2e/privacy.spec.ts`, `frontend/tests/ui-strings.txt`

**Interfaces:**
- Consumes: de route `/account/` uit taak 7.
- Produces: de vierde voettekstlink; `/account/` in `ALL_PATHS` van `theme.spec.ts` en in `PAGES` van `privacy.spec.ts`.

De ingang is één stille link in de voettekst, naast "Hoe Ampeer rekent", "Over ons" en "Privacy". De kop van de site verandert niet en op `/advies/` komt niets: regel 5 van het frontend-ontwerp kent precies twee soorten oproep tot actie en "maak een account aan" zou de derde zijn.

Nieuwe zin: `Account`.

- [ ] **Step 1: Schrijf de falende test**

Pas in `frontend/tests/app/LegalPages.test.tsx` de voettekstest aan. De naam noemt drie pagina's en dat worden er vier:

```tsx
  it("reaches all four pages that explain the product rather than sell it", () => {
    const { container } = render(<SiteFooter />);
    const hrefs = [...container.querySelectorAll("a[href]")].map((element) =>
      element.getAttribute("href"),
    );
    for (const path of [
      /^\/methodologie\/?$/,
      /^\/over-ons\/?$/,
      /^\/privacy\/?$/,
      // The one entrance to the account, and the only one: the site header
      // does not change and nothing goes on the advice page.
      /^\/account\/?$/,
    ]) {
      expect(hrefs.some((href) => path.test(href ?? ""))).toBe(true);
    }
    expect(hrefs.filter((href) => /^https?:/.test(href ?? ""))).toEqual([]);
  });
```

- [ ] **Step 2: Draai en zie hem falen**

```bash
cd frontend && pnpm test
```

Verwacht: rood op de vierde regel van de lus, `expected false to be true`.

- [ ] **Step 3: Voeg de link toe**

In `frontend/src/app/_shell/SiteFooter.tsx`, als vierde `Link` in de bestaande `nav`:

```tsx
          <Link href="/account/" className="underline underline-offset-4">
            Account
          </Link>
```

Vul de moduledocstring aan met één zin: er zijn nu vier links, en de vierde is de enige ingang naar het account, omdat een voettekst is waar een bezoeker een account zoekt en een account in fase 1 een voorziening is en geen aanbod.

- [ ] **Step 4: Draai en zie hem groen worden**

```bash
cd frontend && pnpm test
```

- [ ] **Step 5: Laat de twee bestaande e2e-specs deze route meenemen**

In `frontend/e2e/theme.spec.ts`, `/account/` in `ALL_PATHS`:

```ts
const ALL_PATHS = ["/", "/berekenen/", ADVICE_PATH, "/methodologie/", "/account/"] as const;
```

Voeg in de test `"every route passes axe in the dark palette too"`, direct voor de `for (const path of ALL_PATHS)`-lus, een assertie op de lengte toe:

```ts
  // Zonder deze regel is "de lus liep vijf paden af" een aanname: er staat
  // geen controle die zegt hoeveel paden er in ALL_PATHS zitten.
  expect(ALL_PATHS).toHaveLength(5);
```

en in `serveFixture` een 401 op `me/` erbij, zodat het contrast op de inlogweergave gemeten wordt en niet op een toestand die van een netwerkfout afhangt:

```ts
async function serveFixture(page: Page): Promise<void> {
  await page.route("**/api/advice/**", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      headers: { "access-control-allow-origin": "*" },
      body: JSON.stringify(fixture),
    }),
  );
  // The account route answers 401 to a visitor who is not signed in, which is
  // the state the dark palette has to be measured in here. Without this the
  // page would fall into the "nothing came back" state, which is a different
  // screen and one that depends on whether a server happens to be running.
  //
  // The two CORS headers are not decoration. The account client sends
  // `credentials: "include"`, and a browser refuses a credentialed response
  // whose allow-origin is `*`, so the wildcard used above for the advice API
  // would turn every one of these into a network error.
  await page.route("**/api/auth/me/", (route) =>
    route.fulfill({
      status: 401,
      contentType: "application/json",
      headers: {
        "access-control-allow-origin": "http://127.0.0.1:4173",
        "access-control-allow-credentials": "true",
      },
      body: JSON.stringify({ detail: "u bent niet ingelogd" }),
    }),
  );
}
```

In `frontend/e2e/privacy.spec.ts`, `/account/` in `PAGES`:

```ts
/** Every page a visitor can reach without an advice in hand, plus one with. */
const PAGES = ["/", "/einde-saldering/", "/berekenen/", "/methodologie/", "/account/"];
```

Voeg daaronder, buiten de `for (const path of PAGES)`-lus die de losse tests genereert, een eigen test toe die de lengte vastlegt:

```ts
test("checks exactly the five pages this list names, not more and not fewer", () => {
  expect(PAGES).toHaveLength(5);
});
```

Hier wordt met opzet niets gemockt. Dat maakt deze test meteen de proef op hoofdstuk 6.5: de API draait niet, `fetch` werpt, en de pagina hoort de inlogweergave met een melding te tonen in plaats van leeg te blijven. De aanroep naar `127.0.0.1:8000` is deze machine en telt niet als een derde partij, wat precies is wat `OWN_HOSTS` daar zegt.

- [ ] **Step 6: Draai de e2e-poort en toon aan dat de twee toevoegingen iets doen**

```bash
cd frontend && pnpm build && pnpm e2e
```

Verwacht: groen, inclusief `every route passes axe in the dark palette too` met vijf paden, de nieuwe lengteassertie daarin, de vijf privacychecks en de nieuwe test die de lengte van `PAGES` vastlegt.

Haal daarna tijdelijk `/account/` uit `ALL_PATHS` en draai `pnpm e2e theme -g "passes axe"`. Verwacht: rood op `expect(ALL_PATHS).toHaveLength(5)`, met 4 in plaats van 5. Zet de route terug. Doe hetzelfde met `/account/` in `PAGES` en draai `pnpm e2e privacy -g "exactly the five pages"`. Verwacht: rood op dezelfde manier. Zet de route terug. Dit zijn de twee controles die tot deze taak geen aantoonbaar rood hadden: nu is "de lijst bevat vijf paden, inclusief `/account/`" een assertie en geen aanname.

Haal daarna in `serveFixture` de `me/`-route tijdelijk weg en draai `pnpm e2e theme`. Verwacht: het donkere palet wordt op `/account/` dan op de netwerkfoutmelding gemeten in plaats van op het formulier; loopt axe daar toch groen doorheen, dan is dat geen bewijs dat de mock overbodig is maar dat deze meting van een draaiende server af zou hangen, en dat is precies wat hij niet mag. Zet de route terug.

Verwijder daarna tijdelijk de melding uit de uitgelogde weergave in `AccountPage.tsx` (de `role="alert"`-alinea) en draai `pnpm e2e privacy`. Die spec let op verzoeken naar derden en blijft groen; dat is de eerlijke uitkomst en het is de reden dat de 6.5-toestand daarnaast in Vitest en in taak 10 wordt vastgehouden. Zet de alinea terug.

- [ ] **Step 7: Werk `ui-strings.txt` bij en commit**

```bash
cd frontend && pnpm build && UPDATE_UI_STRINGS=1 pnpm e2e language
cd frontend && pnpm e2e language
```

Verwacht: twee nieuwe regels, `Account` en `/account/`, allebei navigatie en allebei wat de kop van dat bestand als eerste categorie noemt.

```bash
git add frontend/src/app/_shell/SiteFooter.tsx frontend/tests/app/LegalPages.test.tsx frontend/e2e/theme.spec.ts frontend/e2e/privacy.spec.ts frontend/tests/ui-strings.txt
git commit
```

Boodschap: `feat(frontend): one quiet way into the account, from the footer`.

---

### Taak 10: `e2e/account.spec.ts`, de stroom in een echte browser

**Hangt af van:** taak 9.

**Files:**
- Create: `frontend/e2e/account.spec.ts`

**Interfaces:**
- Consumes: `frontend/tests/fixtures/consent-texts.json`, `me-response.json` en `export-response.json` uit taak 3; de route en de weergaven uit taak 7 en 8.
- Produces: niets dat een andere taak leest.

Wat deze laag wel en niet bewijst, en het tweede is de reden dat taak 11 bestaat. Hij bewijst de stroom: de schakeling op `me/`, de ene wissel geteld op verzoeken, registreren met beide toestemmingen geweigerd, een toestemming aanzetten, exporteren als bestand, verwijderen, en de toestand uit 6.5. Hij bewijst **niets** over `credentials` en niets over de CSRF-header: `page.route` antwoordt wat er gevraagd wordt, dus een frontend die allebei vergeet komt hier groen doorheen en werkt in productie niet.

Drie dingen die in een gemockte browser anders liggen dan in Vitest, en alle drie kosten een uur als je ze niet vooraf weet:

1. **CORS geldt ook voor een gemockt antwoord.** De site draait op `127.0.0.1:4173` en `NEXT_PUBLIC_API_BASE` is in deze build leeg gelaten noch gezet, dus de client praat met `127.0.0.1:8000`: een andere oorsprong. `route.fulfill` vervangt het netwerk en niet de browser, dus een antwoord op een credentialed verzoek met `access-control-allow-origin: *` wordt geweigerd. Elk antwoord draagt de exacte oorsprong plus `access-control-allow-credentials: true`.
2. **Er komt een preflight.** Elke POST draagt `content-type: application/json` en een `X-CSRFToken`, en dat is geen simple request, dus de browser stuurt eerst een `OPTIONS`. De router hieronder beantwoordt die apart en telt hem niet mee.
3. **Een cookie kent geen poort.** Een `Set-Cookie` voor host `127.0.0.1` uit het gemockte antwoord is leesbaar voor de pagina op poort 4173, dus de `csrftoken`-cookie kan hier echt gezet worden en de client leest hem echt.

**Een bekende onzekerheid, voordat u begint.** Of Playwright de CORS-preflight (de `OPTIONS` die punt 2 hierboven beschrijft) eigenlijk wel aanbiedt aan `page.route` staat nergens in deze repository aangetoond: elke bestaande mock in dit project bedient alleen GET-verzoeken. `serveAuth` hierboven gaat ervan uit dat hij dat wel doet en beantwoordt `request.method() === "OPTIONS"` apart. Meet dit eerst, voordat u een falende Step 2 aan de client toeschrijft: log `request.method()` voor elk verzoek dat `serveAuth` binnenkomt (een tijdelijke `console.log` of een array die u naderhand uitleest) en draai stap 2. Komt er nooit een `OPTIONS` binnen, dan is dat geen fout in `accounts.ts` maar een preflight die Playwright niet doorstuurt naar `page.route`, en dan zijn er twee routes, geen van beide hier gekozen:

1. De mock op dezelfde oorsprong bedienen, via een `serve.json`-rewrite zodat `/api/auth/**` door dezelfde server op poort 4173 wordt beantwoord en er geen cross-origin verzoek en dus geen preflight meer bestaat.
2. `context.route` gebruiken in plaats van `page.route`, met een handler die `OPTIONS` expliciet beantwoordt op het niveau van de browsercontext in plaats van de pagina.

Kies hier geen van beide op voorhand. Meet, en rapporteer welke van de twee van toepassing is voordat u verder werkt: dat antwoord komt vroeg, want stap 2 hieronder oefent het al uit (de `refresh/`-POST draagt `X-CSRFToken` nadat de 401 de cookie heeft gezet).

- [ ] **Step 1: Schrijf de router en de eerste twee tests**

Maak `frontend/e2e/account.spec.ts`:

```ts
import { expect, test, type Page, type Route } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import consentTexts from "../tests/fixtures/consent-texts.json";
import me from "../tests/fixtures/me-response.json";
import exportPayload from "../tests/fixtures/export-response.json";

/**
 * The account flow against a mocked API.
 *
 * What this proves is the flow. What it cannot prove is the two properties the
 * whole client is built around: `credentials: "include"` and the CSRF header.
 * `page.route` answers whatever it is asked, so a frontend that forgot both
 * would pass every test in this file and work nowhere. That is
 * tests/test_stack_smoke.py's job, over a real connection.
 */

const ORIGIN = "http://127.0.0.1:4173";

/** The headers a credentialed cross-origin answer has to carry, or it is refused. */
const CORS = {
  "access-control-allow-origin": ORIGIN,
  "access-control-allow-credentials": "true",
} as const;

interface Answer {
  readonly status: number;
  readonly body?: unknown;
  /** Set the csrftoken cookie along with this answer, as the real API does. */
  readonly setsCsrf?: boolean;
}

/** One or more answers for a path, used in order, the last one repeating. */
type Plan = Readonly<Record<string, Answer | readonly Answer[]>>;

/**
 * Serve /api/auth/ from a plan, and count what was asked for.
 *
 * Counted per path, because three of the tests below are about how many
 * requests were made and not about what ended up on the screen. A screen
 * cannot show the difference between one exchange and three.
 */
async function serveAuth(
  page: Page,
  plan: Plan,
): Promise<Readonly<Record<string, number>>> {
  const counts: Record<string, number> = {};
  await page.route("**/api/auth/**", async (route: Route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    if (request.method() === "OPTIONS") {
      // The preflight every POST here triggers, because of the content type
      // and the CSRF header. Not counted: it is the browser asking, not the
      // page.
      await route.fulfill({
        status: 204,
        headers: {
          ...CORS,
          "access-control-allow-methods": "GET, POST, OPTIONS",
          "access-control-allow-headers": "content-type, x-csrftoken",
        },
      });
      return;
    }
    const seen = (counts[path] ?? 0) + 1;
    counts[path] = seen;
    const planned = plan[path];
    if (planned === undefined) {
      throw new Error(`no answer planned for ${path}`);
    }
    const answers: readonly Answer[] = Array.isArray(planned)
      ? planned
      : [planned as Answer];
    const answer = answers[Math.min(seen - 1, answers.length - 1)];
    if (answer === undefined) throw new Error(`no answer left for ${path}`);
    await route.fulfill({
      status: answer.status,
      contentType: "application/json",
      headers: {
        ...CORS,
        ...(answer.setsCsrf === true
          ? { "set-cookie": "csrftoken=een-e2e-token; Path=/; SameSite=Strict" }
          : {}),
      },
      body: answer.body === undefined ? "" : JSON.stringify(answer.body),
    });
  });
  return counts;
}

const UNAUTHENTICATED: Answer = {
  status: 401,
  body: { detail: "u bent niet ingelogd" },
  setsCsrf: true,
};

test.describe("the three views", () => {
  test("a 200 on me/ shows the account", async ({ page }) => {
    await serveAuth(page, {
      "/api/auth/me/": { status: 200, body: me, setsCsrf: true },
      "/api/auth/consent-texts/": { status: 200, body: consentTexts },
    });
    await page.goto("/account/");
    await expect(page.getByText(me.email)).toBeVisible();
    await expect(page.getByText(consentTexts.texts.METER_LINK)).toBeVisible();
  });

  test("a 401 twice around one exchange shows the sign-in view", async ({
    page,
  }) => {
    const counts = await serveAuth(page, {
      "/api/auth/me/": UNAUTHENTICATED,
      "/api/auth/refresh/": { status: 200, body: null },
    });
    await page.goto("/account/");
    await expect(page.getByRole("button", { name: "Inloggen" })).toBeVisible();
    // Counted on requests and not on what is on the screen: the sign-in view
    // looks identical after one exchange and after five, and five is the
    // version that empties the auth-refresh bucket and, once a spent token is
    // offered again, ends every session this account has.
    expect(counts["/api/auth/me/"]).toBe(2);
    expect(counts["/api/auth/refresh/"]).toBe(1);
  });

  test("one exchange that works ends on the account", async ({ page }) => {
    const counts = await serveAuth(page, {
      "/api/auth/me/": [UNAUTHENTICATED, { status: 200, body: me }],
      "/api/auth/refresh/": { status: 200, body: null },
      "/api/auth/consent-texts/": { status: 200, body: consentTexts },
    });
    await page.goto("/account/");
    await expect(page.getByText(me.email)).toBeVisible();
    expect(counts["/api/auth/refresh/"]).toBe(1);
  });

  test("a request that is aborted shows the sign-in view with a message", async ({
    page,
  }) => {
    // Chapter 6.5. Nothing came back, so nothing was said about who is signed
    // in, and no exchange is attempted: there is nothing to react to.
    let refreshes = 0;
    await page.route("**/api/auth/refresh/", (route) => {
      refreshes += 1;
      return route.abort();
    });
    await page.route("**/api/auth/me/", (route) => route.abort());
    await page.goto("/account/");
    await expect(page.getByRole("alert")).toContainText(
      "Wij konden de server niet bereiken.",
    );
    await expect(page.getByRole("button", { name: "Inloggen" })).toBeVisible();
    expect(refreshes).toBe(0);
  });
});
```

- [ ] **Step 2: Draai deze vier**

```bash
cd frontend && pnpm build && pnpm e2e account
```

Verwacht: groen. Faalt de eerste met een lege pagina en een CORS-melding in de console, lees dan punt 1 hierboven terug: dat is de wildcard-oorsprong en niet de client.

- [ ] **Step 3: Schrijf de stroom die hoofdstuk 12 als klaar beschrijft**

Voeg toe aan `frontend/e2e/account.spec.ts`:

```ts
test.describe("the round the definition of done describes", () => {
  test("register with both consents refused, then see the account", async ({
    page,
  }) => {
    await serveAuth(page, {
      "/api/auth/me/": [UNAUTHENTICATED, { status: 200, body: me }],
      "/api/auth/refresh/": { status: 401, body: { detail: "uw sessie is verlopen, log opnieuw in" } },
      "/api/auth/consent-texts/": { status: 200, body: consentTexts },
      "/api/auth/register/": { status: 201 },
    });
    await page.goto("/account/");
    await page
      .getByRole("button", { name: "Nog geen account? Account aanmaken" })
      .click();
    await expect(
      page.getByText(consentTexts.texts.LEAD_GENERATION),
    ).toBeVisible();
    // Both boxes are left alone, which the API accepts: article 7(4).
    for (const box of await page.getByRole("checkbox").all()) {
      await expect(box).not.toBeChecked();
    }
    await page.getByLabel("E-mailadres").fill("iemand@voorbeeld.nl");
    await page.getByLabel("Wachtwoord").fill("een-heel-lang-wachtwoord");
    await page.getByRole("button", { name: "Account aanmaken" }).click();
    await expect(page.getByText(me.email)).toBeVisible();
  });

  test("turn one consent on, and the row says so", async ({ page }) => {
    await serveAuth(page, {
      "/api/auth/me/": { status: 200, body: me, setsCsrf: true },
      "/api/auth/consent-texts/": { status: 200, body: consentTexts },
      "/api/auth/consent/": {
        status: 200,
        body: { kind: "LEAD_GENERATION", granted: true },
      },
    });
    await page.goto("/account/");
    await page.getByRole("button", { name: "Toestemming geven" }).click();
    await expect(page.getByText("Toestemming gegeven")).toHaveCount(2);
  });

  test("export hands the browser a file", async ({ page }) => {
    await serveAuth(page, {
      "/api/auth/me/": { status: 200, body: me, setsCsrf: true },
      "/api/auth/consent-texts/": { status: 200, body: consentTexts },
      "/api/auth/export/": { status: 200, body: exportPayload },
    });
    await page.goto("/account/");
    const [download] = await Promise.all([
      page.waitForEvent("download"),
      page.getByRole("button", { name: "Gegevens exporteren" }).click(),
    ]);
    expect(download.suggestedFilename()).toBe("ampeer-gegevens.json");
  });

  test("delete asks for the password and confirms in one line", async ({
    page,
  }) => {
    const counts = await serveAuth(page, {
      "/api/auth/me/": { status: 200, body: me, setsCsrf: true },
      "/api/auth/consent-texts/": { status: 200, body: consentTexts },
      "/api/auth/delete/": { status: 204 },
      "/api/auth/refresh/": { status: 401, body: { detail: "uw sessie is verlopen, log opnieuw in" } },
    });
    await page.goto("/account/");
    await page.getByRole("button", { name: "Account verwijderen" }).click();
    await page.getByLabel("Uw wachtwoord").fill("een-heel-lang-wachtwoord");
    await page.getByRole("button", { name: "Verwijderen bevestigen" }).click();
    await expect(page.getByRole("status")).toContainText(
      "Uw account is verwijderd.",
    );
    await expect(page.getByRole("button", { name: "Inloggen" })).toBeVisible();
    // The 204 is the proof. Nothing is asked afterwards, and there is nothing
    // left to exchange: the RefreshSession rows went with the account.
    expect(counts["/api/auth/me/"]).toBe(1);
    expect(counts["/api/auth/refresh/"]).toBeUndefined();
  });

  test("the whole round works from the keyboard alone", async ({ page }) => {
    await serveAuth(page, {
      "/api/auth/me/": { status: 200, body: me, setsCsrf: true },
      "/api/auth/consent-texts/": { status: 200, body: consentTexts },
      "/api/auth/delete/": { status: 204 },
      "/api/auth/refresh/": { status: 401, body: { detail: "uw sessie is verlopen, log opnieuw in" } },
    });
    await page.goto("/account/");
    const opener = page.getByRole("button", { name: "Account verwijderen" });
    await opener.focus();
    await expect(opener).toHaveAttribute("aria-expanded", "false");
    await page.keyboard.press("Enter");
    await expect(opener).toHaveAttribute("aria-expanded", "true");
    // The field that appeared has focus, so typing continues where the reader
    // is looking rather than somewhere above it.
    await expect(page.getByLabel("Uw wachtwoord")).toBeFocused();
    await page.keyboard.type("een-heel-lang-wachtwoord");
    await page.keyboard.press("Enter");
    await expect(page.getByRole("status")).toContainText(
      "Uw account is verwijderd.",
    );
  });
});

test.describe("what the page is without JavaScript, and what axe says with it", () => {
  test.describe("no JavaScript", () => {
    test.use({ javaScriptEnabled: false });

    test("/account/ ships one h1 and a paragraph saying what this page is", async ({
      page,
    }) => {
      // Measured on /berekenen/ on 2026-09-02: zero h1 and 32 words of body
      // text, all of it header and footer. Cheaper here, because nobody has to
      // find this page, and still the wrong answer for a visitor on a slow
      // connection.
      await page.goto("/account/");
      const headings = await page.locator("h1").allTextContents();
      expect(headings).toHaveLength(1);
      expect(headings[0]?.trim()).toBe("Uw account");
      const words = (await page.locator("main").innerText()).split(/\s+/).filter(Boolean);
      expect(words.length).toBeGreaterThan(30);
    });
  });

  for (const scheme of ["light", "dark"] as const) {
    test(`axe finds nothing on the signed-out view in ${scheme}`, async ({
      page,
    }) => {
      await serveAuth(page, {
        "/api/auth/me/": UNAUTHENTICATED,
        "/api/auth/refresh/": { status: 401, body: { detail: "uw sessie is verlopen, log opnieuw in" } },
      });
      await page.emulateMedia({ colorScheme: scheme });
      await page.goto("/account/");
      await page.evaluate(
        (value) => document.documentElement.setAttribute("data-theme", value),
        scheme,
      );
      await expect(page.getByRole("button", { name: "Inloggen" })).toBeVisible();
      const results = await new AxeBuilder({ page })
        .withTags(["wcag2a", "wcag2aa", "wcag22aa"])
        .analyze();
      expect(
        results.violations,
        `signed out in ${scheme}: ${JSON.stringify(results.violations.map((violation) => violation.id))}`,
      ).toEqual([]);
    });

    test(`axe finds nothing on the account view in ${scheme}`, async ({
      page,
    }) => {
      await serveAuth(page, {
        "/api/auth/me/": { status: 200, body: me, setsCsrf: true },
        "/api/auth/consent-texts/": { status: 200, body: consentTexts },
      });
      await page.emulateMedia({ colorScheme: scheme });
      await page.goto("/account/");
      await page.evaluate(
        (value) => document.documentElement.setAttribute("data-theme", value),
        scheme,
      );
      await expect(page.getByText(me.email)).toBeVisible();
      // Expanded as well as collapsed: the delete block is the one part of
      // this page that is not in the tree until somebody presses a button.
      await page.getByRole("button", { name: "Account verwijderen" }).click();
      const results = await new AxeBuilder({ page })
        .withTags(["wcag2a", "wcag2aa", "wcag22aa"])
        .analyze();
      expect(
        results.violations,
        `signed in in ${scheme}: ${JSON.stringify(results.violations.map((violation) => violation.id))}`,
      ).toEqual([]);
    });
  }
});
```

- [ ] **Step 4: Draai alles**

```bash
cd frontend && pnpm build && pnpm e2e
```

Verwacht: groen, de hele suite, inclusief de bestaande specs die taak 9 heeft aangepast.

- [ ] **Step 5: Toon aan dat drie van deze controles rood kunnen worden**

Drie tijdelijke bewerkingen, allemaal met de hand terugzetten:

1. Vervang in `session.ts` `return (await askWhoIsSignedIn()) ?? signedOut(null);` door een lus die blijft wisselen tot er een 200 komt, en draai `pnpm e2e account`. Verwacht: `a 401 twice around one exchange` rood met een teller boven 2. Zet hem terug.
2. Vervang in `download.ts` `link.download = EXPORT_FILENAME` door `link.download = "export.json"` en draai opnieuw. Verwacht: `export hands the browser a file` rood op de bestandsnaam. Zet hem terug.
3. Haal in `AccountView` de focus-effect weg (`if (expanded) passwordField.current?.focus()`) en draai opnieuw. Verwacht: `the whole round works from the keyboard alone` rood op `toBeFocused`, en daarna op de bevestiging, want er is dan niets getypt. Zet hem terug.

- [ ] **Step 6: Commit**

```bash
git add frontend/e2e/account.spec.ts
git commit
```

Boodschap: `test(e2e): the account round in a browser, with the API mocked`.

---

## Fase 4: het bewijs dat een mock niet kan leveren

### Taak 11: De stack-smoke, over een echte verbinding

**Hangt af van:** taak 2 (de negende route en de grendel). Draait als elfde omdat de serie serieel is en omdat de handmatige run de hele stroom wil kunnen naspelen.

**Files:**
- Modify: `tests/test_stack_smoke.py`

**Interfaces:**
- Consumes: `GET /api/auth/consent-texts/`, `POST register/`, `POST export/`, `POST delete/` uit taak 2 en het vorige deelproject; `accounts.nl.NL` en `CONSENT_TEXT_VERSION`.
- Produces: `SMOKE_BASE_URL_ENV = "AMPEER_SMOKE_BASE_URL"`, de marker `needs_stack`, en de klasse `_Session` in dat bestand.

Wat hier bewezen wordt en waarom geen van de vier lagen erboven het kan:

- **De `Set-Cookie`-attributen op de draad.** `tests/test_accounts_api.py` leest morsels uit Django's testclient, wat het object is dat Django zelf bouwde. Hier wordt de kopregel gelezen die door nginx en over HTTP is gegaan, onder `ampeer.settings.prod`, en dat is de tekst die een browser interpreteert.
- **Dat de CSRF-afdwinging in de uitgerolde configuratie aanstaat.** De testclient zet `_dont_enforce_csrf_checks`, dus daar is `APIClient(enforce_csrf_checks=True)` nodig om er iets over te kunnen zeggen. Over de echte stack is er niets om aan te zetten.
- **Dat nginx `/api/auth/` doorstuurt.** Geen enkele test in deze repository verstuurt ooit een verzoek naar dat pad door de proxy heen.
- **Dat de lus sluit.** Getoond, verstuurd en vastgelegd zijn drie plaatsen, en dit is de enige test die alle drie op één echte HTTP-route legt.

Een overgeslagen check is geen bewijs. Deze checks slaan zichzelf over als de omgevingsvariabele er niet is, dus **de uitvoer van de handmatige run gaat in de commit**, precies zoals de zeven checks uit het deploy-ontwerp dat doen. En de vrijstelling zelf wordt bewaakt: er staat een test bij die in CI draait en die eist dat elke `test_live_`-functie de marker draagt.

Let op de tarieven: `auth-register` staat op 5 per uur per beller. Drie runs achter elkaar op dezelfde stack lopen daar tegenaan, en dat is de limiet die werkt en geen storing.

- [ ] **Step 1: Schrijf de poort om de poort**

Voeg `from helpers.accounts import TEST_PASSWORD` toe aan de imports bovenin het bestand: `tests/helpers/accounts.py` centraliseert dat wachtwoord sinds b7c91bf precies zodat geen bestand het meer letterlijk uitschrijft, en deze taak zou anders drie call sites toevoegen op de plek die dat een commit eerder gesloten heeft.

Voeg bovenaan `tests/test_stack_smoke.py` toe, onder de bestaande constanten:

```python
#: The address of a running stack, or nothing. Opt in, because there is no
#: Docker in CI and a check that cannot run must not read as one that passed.
SMOKE_BASE_URL_ENV = "AMPEER_SMOKE_BASE_URL"

STACK = os.environ.get(SMOKE_BASE_URL_ENV)

#: Every live check carries this, and the test below is what keeps that true.
needs_stack = pytest.mark.skipif(
    STACK is None,
    reason=(
        f"{SMOKE_BASE_URL_ENV} is not set. Start the stack per infra/README.md "
        "section 7 and set it to, for example, http://127.0.0.1:8080"
    ),
)
```

en `import os` bij de imports. Voeg de test toe die de vrijstelling zelf vasthoudt:

```python
def test_every_live_check_is_gated_on_the_same_variable() -> None:
    """A skipped check is not proof, and an ungated one is worse.

    Every function whose name begins with `test_live_` talks to a machine that
    is not there in CI. One that lost its marker would not skip, it would fail
    on a refused connection, and the honest reading of that failure is
    "somebody forgot a decorator" rather than "the stack is broken". Read off
    this module rather than listed, so a live check added later is covered
    without anybody remembering this test exists.
    """
    live = [
        (name, value)
        for name, value in sorted(globals().items())
        if name.startswith("test_live_") and callable(value)
    ]
    assert live, "no live checks found at all; this test is reading nothing"
    for name, function in live:
        marks = getattr(function, "pytestmark", [])
        reasons = [
            str(mark.kwargs.get("reason", ""))
            for mark in marks
            if getattr(mark, "name", "") == "skipif"
        ]
        assert any(SMOKE_BASE_URL_ENV in reason for reason in reasons), (
            f"{name} is not gated on {SMOKE_BASE_URL_ENV}, so it fails on a refused "
            "connection in CI instead of saying it did not run"
        )
```

- [ ] **Step 2: Draai hem en zie hem falen op de leegte**

```bash
uv run --no-sync pytest tests/test_stack_smoke.py::test_every_live_check_is_gated_on_the_same_variable -q
```

Verwacht: rood met "no live checks found at all". Dat is de niet-leegheidsassertie die doet wat hij moet: er is nog geen enkele live check, dus deze test mag nog niet groen zijn.

- [ ] **Step 3: Schrijf de HTTP-hulp**

Voeg toe aan `tests/test_stack_smoke.py`:

```python
class _Session:
    """One caller against the running stack, with the raw Set-Cookie kept.

    urllib rather than a new dependency, and deliberately not a client that
    manages cookies for you: the attributes on those headers are half of what
    this file is here to read, and a jar that parsed them away would leave the
    test asserting that a 200 came back.
    """

    def __init__(self, base: str) -> None:
        self.base = base.rstrip("/")
        self.cookies: dict[str, str] = {}
        self.set_cookie: list[str] = []

    def request(
        self,
        method: str,
        path: str,
        body: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> tuple[int, bytes]:
        import json as jsonlib
        import urllib.error
        import urllib.request

        data = None if body is None else jsonlib.dumps(body).encode("utf-8")
        sending = dict(headers or {})
        if data is not None:
            sending["Content-Type"] = "application/json"
        if self.cookies:
            sending["Cookie"] = "; ".join(f"{k}={v}" for k, v in self.cookies.items())
        request = urllib.request.Request(  # noqa: S310 - a fixed http:// base from the env
            f"{self.base}{path}", data=data, headers=sending, method=method
        )
        try:
            with urllib.request.urlopen(request, timeout=10) as response:  # noqa: S310
                status, payload, raw = response.status, response.read(), response.headers
        except urllib.error.HTTPError as error:
            status, payload, raw = error.code, error.read(), error.headers
        self.set_cookie = list(raw.get_all("Set-Cookie") or [])
        for header in self.set_cookie:
            name, _, rest = header.partition("=")
            self.cookies[name.strip()] = rest.split(";", 1)[0]
        return status, payload

    def json(self, method: str, path: str, body: dict[str, Any] | None = None) -> Any:
        import json as jsonlib

        headers = {}
        token = self.cookies.get("csrftoken")
        if method != "GET" and token is not None:
            headers["X-CSRFToken"] = token
        status, payload = self.request(method, path, body, headers)
        assert 200 <= status < 300, f"{method} {path} answered {status}: {payload!r}"
        return jsonlib.loads(payload) if payload else None

    def attributes(self, cookie: str) -> dict[str, str]:
        """The attributes on one Set-Cookie header, lowercased by name."""
        for header in self.set_cookie:
            if not header.startswith(f"{cookie}="):
                continue
            found: dict[str, str] = {}
            for part in header.split(";")[1:]:
                key, _, value = part.strip().partition("=")
                found[key.lower()] = value
            return found
        raise AssertionError(f"{cookie} was not set at all; headers were {self.set_cookie}")
```

- [ ] **Step 4: Schrijf de drie live checks**

```python
def _fresh_email() -> str:
    """A new address per run, so a stack that is reused does not collide."""
    import secrets

    return f"smoke-{secrets.token_hex(6)}@voorbeeld.invalid"


@needs_stack
def test_live_the_session_cookies_carry_the_attributes_a_browser_enforces() -> None:
    """The header on the wire, and not the morsel Django built.

    tests/test_accounts_api.py already reads httponly, SameSite and the two
    paths off `response.cookies`, which is Django's own object in Django's own
    process. This reads the text that travelled through nginx under
    ampeer.settings.prod, which is what a browser actually interprets, and it
    is the only place the deployed settings are the ones being described.
    """
    from accounts.nl import CONSENT_TEXT_VERSION

    assert STACK is not None
    session = _Session(STACK)
    status, _ = session.request("GET", "/api/auth/me/")
    assert status == 401, "a stranger is signed in, which is a different problem"
    assert "csrftoken" in session.cookies, (
        "the 401 did not hand out a CSRF token, so nobody can ever sign in"
    )

    session.json(
        "POST",
        "/api/auth/register/",
        {
            "email": _fresh_email(),
            "password": TEST_PASSWORD,
            "consent_meter_link": False,
            "consent_lead_generation": False,
            "text_version": CONSENT_TEXT_VERSION,
        },
    )
    access = session.attributes("ampeer_access")
    refresh = session.attributes("ampeer_refresh")
    assert "httponly" in access, f"the access cookie is readable from JavaScript: {access}"
    assert "httponly" in refresh, f"the refresh cookie is readable from JavaScript: {refresh}"
    assert access.get("samesite") == "Strict", access
    assert refresh.get("samesite") == "Strict", refresh
    # Two different paths on purpose: the access token reaches every API route
    # and the refresh token only the two that need it, so it does not travel
    # on every request the access token makes.
    assert access.get("path") == "/api/", access
    assert refresh.get("path") == "/api/auth/", refresh
    session.json("POST", "/api/auth/delete/", {"password": TEST_PASSWORD})


@needs_stack
def test_live_a_post_without_the_csrf_header_is_refused() -> None:
    """The half no mock can reach.

    Django's test client sets `_dont_enforce_csrf_checks`, so the check does
    not run there at all unless a test asks for a strict client; page.route in
    Playwright answers whatever it is asked and never checks a header. Over the
    real stack there is nothing to switch on, and this is the request an
    attacker's page would make.
    """
    assert STACK is not None
    session = _Session(STACK)
    session.request("GET", "/api/auth/me/")
    assert "csrftoken" in session.cookies, "no token to leave out"
    status, payload = session.request(
        "POST",
        "/api/auth/login/",
        {"email": "iemand@voorbeeld.invalid", "password": "maakt-niet-uit"},
    )
    assert status == 403, (
        f"a state changing request went through without X-CSRFToken and answered {status}: "
        f"{payload!r}. SameSite would then be the only thing standing between this API "
        "and a cross site POST."
    )


@needs_stack
def test_live_the_consent_text_shown_is_the_text_recorded() -> None:
    """The loop chapter 5 exists to close, over one real HTTP route.

    Shown, sent and recorded are three places. Layer 2 proves that shown equals
    delivered and layer 4 that delivered equals nl.py; only this puts the whole
    loop end to end, and only this does it through the database the service
    actually writes to.
    """
    from accounts.nl import NL

    assert STACK is not None
    session = _Session(STACK)
    session.request("GET", "/api/auth/me/")
    texts = session.json("GET", "/api/auth/consent-texts/")
    version = texts["text_version"]
    assert texts["texts"]["METER_LINK"] == NL["CONSENT_METER_LINK"]

    password = TEST_PASSWORD
    session.json(
        "POST",
        "/api/auth/register/",
        {
            "email": _fresh_email(),
            "password": password,
            "consent_meter_link": True,
            "consent_lead_generation": False,
            "text_version": version,
        },
    )
    exported = session.json("POST", "/api/auth/export/")
    rows = [row for row in exported["consents"] if row["kind"] == "METER_LINK"]
    assert rows, f"the export carries no METER_LINK row: {exported['consents']}"
    assert rows[0]["text_version"] == version, (
        f"the row records {rows[0]['text_version']} and the screen showed {version}, "
        "which is the exact drift the text_version field exists to prevent"
    )
    session.json("POST", "/api/auth/delete/", {"password": password})


@needs_stack
def test_live_a_stale_version_is_refused_over_the_real_route() -> None:
    """The lock, through nginx and the deployed serializer rather than through
    a serializer imported in the same process as the test."""
    assert STACK is not None
    session = _Session(STACK)
    session.request("GET", "/api/auth/me/")
    status, payload = session.request(
        "POST",
        "/api/auth/register/",
        {
            "email": _fresh_email(),
            "password": TEST_PASSWORD,
            "consent_meter_link": True,
            "consent_lead_generation": False,
            "text_version": "1999-01-01",
        },
        {"X-CSRFToken": session.cookies["csrftoken"]},
    )
    assert status == 400, f"a stale version was accepted, answering {status}: {payload!r}"
    assert b"text_version" in payload
```

- [ ] **Step 5: Draai zonder stack en zie de vier overslaan**

```bash
uv run --no-sync pytest tests/test_stack_smoke.py -q -rs
```

Verwacht: vier `SKIPPED` met de reden die de omgevingsvariabele noemt, en `test_every_live_check_is_gated_on_the_same_variable` groen. Lees de skipreden: dat `-rs` staat er zodat de overgeslagen checks zichtbaar zijn en niet als een punt in de uitvoer verdwijnen.

- [ ] **Step 6: Toon aan dat de poort om de poort rood kan worden**

Haal `@needs_stack` tijdelijk van `test_live_a_post_without_the_csrf_header_is_refused` en draai:

```bash
uv run --no-sync pytest tests/test_stack_smoke.py::test_every_live_check_is_gated_on_the_same_variable -q
```

Verwacht: rood met "is not gated on AMPEER_SMOKE_BASE_URL". Zet de decorator met de hand terug. Zonder deze stap is de vrijstelling een afspraak en geen controle.

- [ ] **Step 7: Draai ze tegen de echte stack en zet de uitvoer in de commit**

Start de stack zoals `infra/README.md` sectie 7 beschrijft, met de override, en dan:

```bash
uv run --no-sync python tests/test_stack_smoke.py
AMPEER_SMOKE_BASE_URL=http://127.0.0.1:8080 uv run --no-sync pytest tests/test_stack_smoke.py -q -rs
```

Verwacht: vier keer `PASSED` en geen skip. Plak de volledige uitvoer in het commitbericht, met de datum en het adres erbij. Slaat er een over terwijl de variabele gezet is, dan is dat een bevinding en geen groene run: lees waarom voordat u commit.

Loopt `auth-register` tegen zijn tarief van 5 per uur aan, dan is dat de limiet die werkt. Wacht of gebruik een verse stack; verhoog het tarief niet om de test te laten slagen.

- [ ] **Step 8: Commit**

```bash
git add tests/test_stack_smoke.py
git commit
```

Boodschap: `test(smoke): read the cookie attributes off the wire, and close the consent loop`, met de uitvoer uit stap 7 in het lichaam van het bericht.

---

## Fase 5: de documenten en de poorten

### Taak 12: De documenten

**Hangt af van:** taak 11.

**Files:**
- Modify: `docs/decisions.md`, `docs/superpowers/specs/2026-09-04-accounts-auth-design.md`, `docs/superpowers/specs/2026-09-05-accounts-frontend-design.md`

**Interfaces:**
- Consumes: alles uit taak 2 tot en met 11.
- Produces: twee entries in `docs/decisions.md`, in het Engels en in het bestaande formaat.

`docs/dpia.md` is in taak 2 al bijgewerkt, want spec 5.1 zegt "in dezelfde commit" over regel 358, en die commit is de commit die de negende route toevoegt. Hier is niets meer aan dat document te doen: er komt geen nieuw persoonsgegeven bij, geen nieuwe bewaartermijn en geen nieuwe verwerker. Wat er wel bij komt is een publieke route die geen persoonsgegeven teruggeeft, en dat staat er dan al.

`docs/decisions.md` is Engels. De rest van dit plan is Nederlands; dat bestand niet, en dat is geen slordigheid maar de conventie van dat bestand.

- [ ] **Step 1: Schrijf de twee entries**

Voeg onder "The decisions" toe, met de nummers die daar volgen:

```text
### N. The version of the consent text travels in the request

**Decided:** `RegisterSerializer` and `ConsentSerializer` carry a `text_version`
field, and a value that is not `CONSENT_TEXT_VERSION` is a 400 under that field
name. On a withdrawal the field is ignored entirely.

**Because:** the column exists to answer article 7(1), which is to demonstrate
what was agreed to. Without this lock the window is small and real: a tab left
open for an hour while the text is rewritten and rolled out, after which
`Consent.record` stamps the new version on a row whose owner read the old
sentence. Nothing anywhere could then see the difference. The withdrawal
exception is article 7(3): taking consent back may never be harder than giving
it, and refusing a withdrawal because the wording changed is exactly that.

**Lives in:** `backend/accounts/serializers.py`, with the message in
`backend/accounts/nl.py` under `consent_text_stale`.

**To reverse:** drop the two validators. The cost is that the guarantee in
chapter 5 of the frontend design becomes a claim nothing checks, and
`test_live_the_consent_text_shown_is_the_text_recorded` is the test that would
then be measuring an agreement rather than a mechanism.

### N+1. One token exchange at page load, and it is not a retry

**Decided:** a 401 on `me/` while `/account/` is loading is followed by exactly
one `POST refresh/` and one more `GET me/`. A second 401 ends it. A 401 later in
the session exchanges nothing. `api.ts`'s rule that nothing is ever retried on
any status stays as it is, and this exchange lives in one function.

**Because:** the access token lives fifteen minutes and the refresh token
fourteen days, so without the exchange a fourteen day token is worthless from
minute sixteen. It is not a repetition of the same request: a different
credential sits under the second one. A second 401 after a successful rotation
means the cookie the server has just set is not being accepted, which no further
attempt repairs, and continuing would rotate once per page load, empty the
auth-refresh bucket of 60 an hour and, once an already exchanged token is
offered again, revoke every session that account has. A client that keeps trying
signs the visitor out everywhere.

**Lives in:** `frontend/src/app/_account/session.ts`.

**To reverse:** the sentence to change is the one in `accounts.ts`'s header
saying the exchange is not in that module. Moving it there is what would make
this a retry.
```

Vervang `N` en `N+1` door de nummers die op de laatste bestaande entry volgen. `tests/test_decisions.py` leest elk pad achter "Lives in" en eist dat het bestaat, dus die drie paden moeten kloppen.

- [ ] **Step 2: Draai de controle op dat bestand**

```bash
uv run --no-sync pytest tests/test_decisions.py -q
```

Verwacht: groen. Verander daarna tijdelijk een van de drie paden in `docs/decisions.md` in `backend/accounts/serializer.py` (zonder s) en draai opnieuw. Verwacht: rood met dat pad. Zet het met de hand terug.

- [ ] **Step 3: Werk het auth-ontwerp bij**

`docs/superpowers/specs/2026-09-04-accounts-auth-design.md`, hoofdstuk 5.1: de routetabel krijgt een negende rij en de zin "Acht routes" eronder wordt "Negen routes", met een verwijzing naar `docs/superpowers/specs/2026-09-05-accounts-frontend-design.md` erbij, want die route is daar ontworpen en niet hier:

```text
| `GET /api/auth/consent-texts/` | publiek | `auth-read` | de twee toestemmingsteksten en hun versie |
```

- [ ] **Step 4: Werk het frontend-ontwerp bij waar dit plan ervan afweek**

`docs/superpowers/specs/2026-09-05-accounts-frontend-design.md`, hoofdstuk 11, drie regels die het plan preciezer heeft gemaakt dan het document ze liet:

- bij `_account/ConsentRow.tsx`: dat het bestand twee componenten draagt, `ConsentCheckbox` voor 6.2 en `ConsentRow` voor 6.3, wat de twee kleine componenten uit hoofdstuk 8 zijn
- bij `account/page.tsx`: dat dit een servercomponent is die `metadata`, de `<h1>` en de alinea draagt, en dat er geen `account/layout.tsx` komt omdat alleen `AccountPage.tsx` een clientcomponent is
- bij `tests/helpers/`: de naam van de generator, `tests/helpers/consent_texts_fixture.py`

Voeg aan hoofdstuk 4.1 één zin toe: `fieldMessages` wordt geïmporteerd uit `_flow/messages.ts` en niet gekopieerd, want dat is de functie waar de redenering over één `ApiError` over gaat; alleen `readErrorBody` bestaat twee keer. En aan 4.2 één zin: een `ApiError` uit `accounts.ts` draagt een lege `message` als de API geen `detail` stuurde, zodat `describeAuthError` de Engelse standaardboodschap van `ApiError` nooit aan een huishouden toont.

- [ ] **Step 5: Draai de documentcontroles**

```bash
uv run --no-sync pytest tests/test_plans.py tests/test_decisions.py tests/test_dpia.py tests/test_pipeline_contract.py -q
```

Verwacht: alles groen behalve `test_a_plan_marked_in_progress_is_actually_unfinished[2026-09-05-accounts-frontend.md]`, die nu rood is omdat elk bestand dat dit plan noemt bestaat. Dat is de zelfvervallende marker uit taak 1 die zijn werk doet, en taak 13 zet hem om. Is hij niet rood, dan noemt dit plan nog een bestand dat niet bestaat en dat is de vraag om te beantwoorden voordat u verder gaat.

- [ ] **Step 6: Commit**

```bash
git add docs/decisions.md docs/superpowers/specs/2026-09-04-accounts-auth-design.md docs/superpowers/specs/2026-09-05-accounts-frontend-design.md
git commit
```

Boodschap: `docs(decisions): the version lock, and the one exchange that is not a retry`.

---

### Taak 13: De status omzetten en de poorten draaien

**Hangt af van:** taak 12.

**Files:**
- Modify: `docs/superpowers/plans/2026-09-05-accounts-frontend.md`

**Interfaces:**
- Consumes: de statusregel uit taak 1.
- Produces: niets.

- [ ] **Step 1: Zie de rode test**

```bash
uv run --no-sync pytest tests/test_plans.py -q
```

Verwacht: `2026-09-05-accounts-frontend.md is marked 'in progress' and every file it names is in the tree. The work is done`. Dit is meteen het bewijs voor de tweede tak van het paar uit taak 1: die tak wordt rood zodra het werk af is, uit zichzelf, zonder kunstgreep.

- [ ] **Step 2: Zet de status om**

Vervang bovenin dit bestand de regel

    **Status:** in progress

(hierboven met vier spaties ingesprongen weergegeven en niet als codeblok op kolom 0: `_STATUS` in `tests/test_plans.py` is met `^` verankerd in MULTILINE, dus een voorbeeld op kolom 0 zou een tweede treffer zijn en een replace-all zou het voorbeeld met de echte markering meeschrijven) door:

```
**Status:** delivered

> **Status op 2026-09-05: opgeleverd.** Elk bestand dat dit plan noemt staat in
> de boom, wat `tests/test_plans.py` voor alle acht plannen controleert en wat
> rood wordt op de dag dat een ervan niet meer klopt. Wat die test niet kan
> zeggen is of elke stap is uitgevoerd zoals hij hier staat; daar zijn de
> commitgeschiedenis en de suite voor.
```

- [ ] **Step 3: Draai de Python-poorten**

```bash
uv run --no-sync pytest -q
bash scripts/gates.sh sync ruff ruff-format mypy shellcheck django-deploy-check pre-commit
bash scripts/gates.sh pytest perf
bash scripts/gates.sh bandit semgrep
bash scripts/gates.sh pip-audit sbom gitleaks
```

Beoordeel elke poort op de exitcode en nooit op een grep over de uitvoer. Voor `gitleaks` staat hier met opzet geen uitsluiting: taak 11 gebruikt `TEST_PASSWORD` uit `tests/helpers/accounts.py` in plaats van het wachtwoord zelf op te schrijven, dus geen bestand in deze reeks draagt het fixture-wachtwoord letterlijk, en een scanneruitzondering zou geen oplossing zijn voor een letterlijke waarde die dit project een commit eerder juist centraliseerde. Komt hier toch een melding, dan is dat een echte vondst. Let verder op:

- **dekking**: de drempel staat op 98,00 met `precision = 2`. Ligt het resultaat erboven, verhoog de drempel dan naar het gemeten getal op twee decimalen. Omlaag mag nooit.
- **`semgrep`**: leest `frontend/src`, dus ook `accounts.ts` en de vier bestanden onder `_account/`. Een bevinding op `ampeer-no-url-from-user-input` of `ampeer-no-reading-the-clock` is een echte bevinding en geen regel om te onderdrukken.
- **mypy**: `--strict` over `backend` en `tests`, inclusief de nieuwe helper en de nieuwe live checks.
- Een poort die hier NOT RUN meldt is geen geslaagde poort. Noteer welke, want dat is precies wat dat script over zichzelf zegt.

- [ ] **Step 4: Draai de frontend-poorten**

```bash
bash scripts/gates.sh frontend-install frontend-lint frontend-typecheck frontend-format frontend-test frontend-build pnpm-audit e2e
```

Verwacht: acht keer pass. De vier dekkingsdrempels van Vitest (96 / 93 / 96 / 97) horen na dit deelproject hoger te liggen dan ervoor; zijn ze gestegen, verhoog ze dan naar het gemeten getal, naar beneden afgerond op een heel procent. Omlaag mag nooit.

Is `e2e` NOT RUN omdat er geen browser staat, draai dan eerst `cd frontend && pnpm exec playwright install --with-deps chromium`. Een overgeslagen `e2e` is hier geen optie: negen van de controles in dit plan draaien alleen daar.

- [ ] **Step 5: Commit**

```bash
git add docs/superpowers/plans/2026-09-05-accounts-frontend.md
git commit
```

Boodschap: `docs(plans): the frontend accounts plan is delivered`.

De pull request gaat naar `dev` en daarna naar `main`, met alle vereiste checks groen. Nooit direct op `main`. Dit plan opent hem niet: het commit en verder niets.

---

## Zelfcontrole na het schrijven

### Dekking van de spec, hoofdstuk voor hoofdstuk

| Spec | Eis | Taak |
|---|---|---|
| 1 | één route, tweede client, de ene backendwijziging, taalgrens en toegankelijkheid als poort | 2, 4, 7, 6, 8, 10 |
| 2 | statisch, cookie-blind, `me/` als enige waarheid; niets gepost voor de eerste `me/` | 5, 7 |
| 2.1 | precies één wissel, in de laadfunctie, en een tweede 401 is het einde | 5 (Vitest, geteld op verzoeken), 10 (Playwright, idem) |
| 2.2 | `SameSite=Strict` werkt hier; niets aan `dev.py` veranderen | 11 (leest de attributen van de draad) |
| 3 | één route, ingang in de voettekst, niet in `SITEMAP_ROUTES`, `<h1>` en alinea in de export | 9, 7, 10 (de no-JS-controle) |
| 4 | `credentials: "include"`, CSRF-header, geen retry, vormcontrole per antwoord | 4 |
| 4.1 | één `ApiError`, `readErrorBody` gedupliceerd met een vergelijkende test | 4 |
| 4.2 | de negen aanroepen met hun vorm; export één keer als tekst | 4 |
| 5 / 5.1 | `GET consent-texts/`, publiek, `auth-read`, exacte JSON, dpia van acht naar negen | 2 |
| 5.2 | `text_version` op beide serializers, 400, `WITHDRAWN`-uitzondering, `consent_text_stale` | 2 |
| 6 | drie weergaven, toestand uit `me/` | 7 |
| 6.1 | inlogvelden, schakelaar, de eerlijke zin over wachtwoordherstel, de drie fouten letterlijk | 6, 5 |
| 6.2 | twee vakjes, uit, optioneel, tekst uit de API, niets versturen zonder de teksten, versie uit hetzelfde antwoord | 6 |
| 6.3 | e-mailadres, twee rijen met de asymmetrie, export als bestand, uitloggen, verwijderen met wachtwoord | 8 |
| 6.4 | na de 204 geen `me/` en geen `refresh/` | 8 (geteld), 10 (geteld) |
| 6.5 | netwerkfout toont de inlogweergave met een melding en wisselt niets | 5, 7, 9 (`privacy.spec.ts`), 10 |
| 7 | taalgrens, elke nieuwe zin in `ui-strings.txt`, teksten niet in `src/**` | 5, 6, 7, 8, 9 (regeneratie) en 3 (`test_no_consent_text_lives_in_the_frontend`) |
| 8 | bestaande tokens, twee kleine componenten, rustig, axe, `role="alert"`, `aria-expanded`, focus, toetsenbord | 6, 8, 10 |
| 9.1 | laag 1, Vitest over `accounts.ts` | 4 |
| 9.2 | laag 2, Vitest en Testing Library | 5, 6, 7, 8 |
| 9.3 | laag 3, Playwright met `page.route` | 10 |
| 9.4 | laag 4, de Python-contractlaag inclusief het geparametriseerde padpaar | 3, 4 |
| 9.5 | laag 5, de stack-smoke, opt-in, met de uitvoer in de commit | 11 |
| 10 | wat er niet in v1 zit | geen taak raakt de kop, `api.ts`, de vragenstroom of de adviespagina aan |
| 11 | de bestandenlijst | elk bestand daaruit staat in precies één Files-blok |
| 12 | definition of done | taak 13 draait de poorten die de laatste vier punten afdwingen |

Twee gaten die deze doorloop opleverde en die zijn gerepareerd in plaats van genoteerd. Het eerste: hoofdstuk 11 noemt `frontend/tests/account/*` maar niet dat de accountweergave in `AccountPage.tsx` woont, wat taak 7 en taak 8 in hetzelfde bestand laat schrijven; dat staat nu in de volgorde en in de bezitstabel in plaats van dat het bij de uitvoering zou blijken. Het tweede: hoofdstuk 9.4 vraagt om een vergelijking tussen `Consent.KINDS` en wat de frontend kent, en die kon niet in taak 3 staan omdat `accounts.ts` daar nog niet bestaat; hij staat nu in taak 4 stap 7, waar hij groen kan afsluiten.

### Plaatshouders

Doorzocht op `TBD`, `vergelijkbaar met taak`, `similar to task`, `naar behoefte`, `appropriate` en `...`. De enige `...` die overblijft staat in taak 4 stap 7, in de vorm `...(the existing docstring stays, with this paragraph added)...`, en die is een instructie over een bestaande docstring en geen weggelaten code. Geen enkele stap zegt "doe hetzelfde als hierboven".

### Namen die over taakgrenzen heen moeten kloppen

Gecontroleerd op elke plek waar ze voorkomen: `CONSENT_KINDS`, `ConsentKind`, `ConsentAction`, `ConsentTexts`, `Me`, `ConsentResult`, `RegisterInput`, `SignInInput`, `ConsentInput`, `getConsentTexts`, `register`, `login`, `refresh`, `getMe`, `postConsent`, `exportAccount`, `logout`, `deleteAccount`, `AccountState`, `LOADING`, `signedOut`, `loadSession`, `describeAuthError`, `fieldMessages`, `CONSENT_LABELS`, `ConsentCheckbox`, `ConsentRow`, `SignInForm`, `RegisterForm`, `AccountPage`, `AccountView`, `downloadJson`, `EXPORT_FILENAME`, `consent_text_stale`, `CONSENT_TEXT_VERSION`, `auth-consent-texts`, `ConsentTextsView`, `build_consent_texts_payload`, `SMOKE_BASE_URL_ENV`, `needs_stack`, `_Session`, `_shape`, `_api_prefix`, `_api_routes`, `ACCOUNTS_URLS`, `ACCOUNTS_TS`. Vier dingen die tijdens die doorloop zijn rechtgetrokken: `getMe` heette in een eerdere opzet `me()`, de propnaam op `SignInForm` is overal `onSignedIn` en niet `onSignIn` (die naam is de andere kant op, op `RegisterForm`), `downloadJson` neemt één argument omdat de bestandsnaam een constante in dezelfde module is, en `signedOut` is een functie en geen constante omdat er altijd een melding of `null` bij hoort.

### Kan elke rode-proef echt vuren

Per taak nagelopen, met de vraag of de tijdelijke bewerking de genoemde test daadwerkelijk raakt en of de test daarna weer groen kan worden. Taak 1: de statusregel weghalen maakt de strenge lezing van toepassing en die vindt twintig ontbrekende bestanden; de tweede tak wordt in taak 13 stap 1 uit zichzelf rood. Taak 2: de scope weghalen raakt de resolvercontrole, de `GRANTED`-tak weghalen raakt de twee `WITHDRAWN`-tests, de versievergelijking weghalen raakt de stale-test. Taak 3: de proef gebruikt een tijdelijk nieuw bestand omdat deze taak geen frontend-bronbestand bezit, en het hernoemen van een sleutel in de fixture raakt de vormvergelijking. Taak 4: `credentials` weghalen raakt negen geparametriseerde gevallen, de CSRF-spread zeven, het pad verminken de padcontrole, de soortenlijst inkorten de derde kopie. Taak 5: `length > 0` verruimen raakt de assertie op de Engelse standaardboodschap, en een tweede wissel raakt de telling die met "request 4 was not planned for" faalt. Taak 6: `required`, de tekstbron en de versiebron zijn drie afzonderlijke bewerkingen die elk precies één test raken. Taak 7: de twee takken van de schakeling. Taak 8: vier bewerkingen die elk een van de vier tellingen of vergelijkingen raken. Taak 9: de mock weghalen verandert wat er gemeten wordt, en dat is expliciet als bevinding en niet als groen resultaat geformuleerd. Taak 10: de lus, de bestandsnaam en de focus. Taak 11: de decorator weghalen maakt de poort om de poort rood. Taak 12: een pad in `decisions.md` verminken maakt `tests/test_decisions.py` rood.

Twee proeven die eerst in dit plan stonden en die zijn geschrapt omdat ze niet konden vuren. De eerste: taak 1 had een tweede proef die `test_every_test_file_named_in_a_comment_exists` rood moest maken, en dat kan niet, want elk Python-testbestand dat dit plan noemt bestaat al; dat staat nu als reden in taak 1 in plaats van als stap. De tweede: taak 9 had een proef die `privacy.spec.ts` rood moest maken door de melding uit de uitgelogde weergave te halen, en die spec gaat over verzoeken naar derden en blijft dan groen; die stap zegt dat nu met zoveel woorden en wijst naar de twee plekken waar die toestand wel wordt vastgehouden.

### Zijn de afhankelijkheden eerlijk over gedeelde bestanden

`frontend/tests/ui-strings.txt` wordt door taak 5, 6, 7, 8 en 9 geschreven, en die vijf staan in die volgorde achter elkaar. `AccountPage.tsx` en `AccountPage.test.tsx` door taak 7 en 8, in die volgorde. `tests/test_frontend_contract.py` door taak 3 en 4, in die volgorde. `tests/test_accounts_api.py` door taak 2 en 3, in die volgorde. Geen enkel bestand wordt door twee taken geschreven die niet in een `Hangt af van`-keten aan elkaar vastzitten. Taak 11 hangt inhoudelijk alleen van taak 2 af en dat staat er zo; hij draait als elfde omdat de serie serieel is en niet omdat er een bestand gedeeld wordt.

### De markering

De regel `**Status:** in progress` staat op regel 5, op kolom 0, en komt in die vorm precies één keer in dit document voor. Het voorbeeld ervan in taak 13 staat vier spaties ingesprongen, precies zoals het commentaar in `tests/test_plans.py` voorschrijft, zodat het geen tweede treffer is voor `_STATUS` en de replace-all in taak 13 het niet meeschrijft.

Er staat wel een tweede statusregel op kolom 0 in dit document: de `**Status:** delivered` in het codeblok van taak 13, die laat zien wat er straks komt te staan. Dat is dezelfde vorm die het vorige plan gebruikt en het is geen valstrik, om twee redenen die allebei nagelopen zijn. `_STATUS.search` geeft alleen de eerste treffer terug en die staat op regel 5. En de replace-all in taak 13 zoekt naar `in progress`, wat in dat voorbeeld niet staat. Na de omzetting draagt dit bestand twee keer `**Status:** delivered` op kolom 0, waarvan de eerste de echte is en de tweede het voorbeeld, en de strenge lezing geldt dan zoals hij hoort.
