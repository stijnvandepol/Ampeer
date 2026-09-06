# Wachtwoordherstel en e-mailbevestiging: implementatieplan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Status:** in progress

**Goal:** Wie zijn wachtwoord kwijt is vraagt op `/account/` een herstellink aan, ontvangt binnen een minuut een mail van `noreply@ampeer.nl`, kiest via die link een nieuw wachtwoord en logt daarmee in; wie een account aanmaakt ontvangt een bevestigingsmail, en na een klik op die link draagt `me/` het tijdstip van bevestiging dat fase 2 straks eist. Geen enkel verzoek van een bezoeker raakt daarbij het netwerk.

**Architecture:** Eén tabel `OneTimeToken` voor beide stromen, met alleen de sha256 van het token; één veld `email_verified_at` op `User`; vier POST-routes op `_AuthAPIView`, waarmee het er dertien worden. De mail verlaat het systeem via een outbox-tabel zonder adres en zonder token, geleegd door een management command op een systemd-timer dat het token pas bij het versturen aanmaakt, en één module `accounts/mailer.py` die `https://api.resend.com/emails` bereikt via `requests` en op de allowlist van `tests/test_boundaries.py` staat. De link draagt zijn token in het fragment van de URL, dat nooit de browser verlaat; `/account/` leest het één keer, wist het uit de adresbalk en kiest zijn weergave op wat `me/` en de API zeggen.

**Tech Stack:** Django 5.2 + DRF, `requests`, systemd op de host, Docker Compose voor de lokale stack; Next 16, React 19, TypeScript 5.9 strict, Tailwind 4, Vitest, Playwright, pnpm.

**Spec:** docs/superpowers/specs/2026-09-06-accounts-recovery-design.md

## Global Constraints

- Nederlands is wat een gebruiker leest; Engels is code, identifiers, comments, docstrings, testnamen en commitboodschappen. Elke zin die de API zegt staat in `backend/accounts/nl.py`; elke zin die de pagina zegt staat in `frontend/src/**` en daarmee in `frontend/tests/ui-strings.txt`, dat `e2e/language.spec.ts` byte voor byte in beide richtingen vergelijkt.
- Geen em-dash (U+2014), nergens: niet in gebruikersgerichte tekst, niet in `docs/`, niet in dit plan.
- Geld is `Decimal`, energie is float. Deze cyclus raakt geen van beide; een taak die een bedrag of een kWh zou aanraken stopt en meldt dat.
- `frontend/src/lib/api.ts` wordt niet gewijzigd. Geen taak noemt dat bestand in zijn Files-blok.
- Geen retry, op geen enkele status. De ene tokenwissel bij het laden van `/account/` staat in `_account/session.ts` en nergens anders; de tweede `me/` na een geslaagde bevestiging is een nieuwe vraag na een verandering en geen herhaling.
- Geen adviestekst en geen toestemmingstekst in de frontend. De twee labels verhuizen in deze cyclus naar de API en mogen daarna nergens in `frontend/src/**` staan.
- Geen kolom in `OneTimeToken`, `OutboundMail` of `AuditEvent` draagt een adres, een ruw token of een digest van een token dat nog bruikbaar is als credential. Het ruwe token bestaat alleen in het geheugen van het command en in de mail.
- `backend/accounts/mailer.py` is de enige module onder `backend/` die `requests` importeert; zijn bestemming is één literal op `api.resend.com`; `django.core.mail` mag nergens geïmporteerd worden.
- Elke route onder `/api/auth/` heeft een `throttle_scope` met een tarief; `tests/test_backend_settings.py` loopt de resolver af. De nieuwe scope is `auth-reset` op `10/hour`.
- De Python-dekkingsdrempel is 99,05 met `precision = 2`; de vier Vitest-drempels zijn 97 / 94 / 96 / 98. Ze mogen omhoog en nooit omlaag, en de meting die telt is die van de runner: meet lokaal met `data/nedu-profiles-2025.csv` opzij gezet.
- De jobnamen `quality`, `test`, `dependencies`, `sast` en `secrets` zijn een interface met de rulesets. Geen taak hernoemt er een; `scripts/setup_rulesets.sh` blijft onaangeraakt.
- Beoordeel elke poort op de exitcode, nooit op een grep over de uitvoer van een tool.
- Elk test- en poortcommando draait op de voorgrond, nooit met een achtergrondoptie en nooit door een pipe naar `head` of `tail`.
- De smoke-client stuurt op elk niet-GET-verzoek `Origin: https://127.0.0.1`, want nginx zet `X-Forwarded-Proto https` op elk verzoek en Django eist dan een Origin voordat hij naar het token kijkt (beslissing 41).
- Werk op `feat/accounts-recovery`. Nooit direct op `main`.
- Voor elke nieuwe controle geldt: toon aan dat hij rood kán worden, met het transcript erbij. Elke taak zegt per controle hoe.
- Python-code in dit document staat in `text`-fences, ook complete bestanden: de `ruff-format` pre-commit hook herschrijft `python`-fences in markdown en heeft in de vorige cyclus een `urlpatterns`-fragment tot een tuple gevouwen.

---

## Het werkmodel

1. **Het plan draait serieel**, taak 1 tot en met 14, in deze volgorde en nooit twee tegelijk. superpowers:subagent-driven-development is hier de uitvoeringsautoriteit en zegt met zoveel woorden "Never dispatch multiple implementation subagents in parallel (conflicts)". Drie taken schrijven in `docs/dpia.md`, drie in `tests/test_accounts_recovery.py`, twee in `backend/accounts/views.py` en twee in `.github/workflows/deploy.yml`; twee daarvan naast elkaar botsen gegarandeerd.
2. **Een taak bezit paden exclusief zolang hij draait.** Twee taken die in hetzelfde bestand schrijven kunnen nooit tegelijk. De tabel hieronder zegt per taak welke paden dat zijn.
3. **Uitvoerende agents committen, en niets daarbuiten.** Elke taak commit op `feat/accounts-recovery`, met alleen de bestanden gestaged die zijn eigen Files-blok noemt, en met de boodschap die de taak voorschrijft. Nooit `push`, nooit `rebase`, nooit `checkout`, nooit `amend`, nooit een andere branch aanraken. En nooit `git checkout --`, `git restore`, `git stash` of `git reset`: een tijdelijke bewerking voor een rode-proef wordt met de hand teruggezet, want die commando's gooien ook het werk weg dat er nog niet in zit.
4. **Elk test- en poortcommando draait op de voorgrond.** Nooit een achtergrondoptie, nooit een pipe naar `tail` of `head`: de exitcode die je leest hoort van het gereedschap zelf te komen en niet van het laatste programma in een pijp.
5. **Poorten draaien na de taken**, niet erin, behalve de gerichte commando's die een taak zelf voorschrijft.
6. **Een taak die niet verder kan zonder een bestand aan te raken dat hij niet bezit, stopt en meldt dat.** Hij reikt niet over de lijn heen.
7. **De Docker-stack wordt door twee taken gestart en door dezelfde twee afgebroken**, taak 12 en taak 14, altijd met `infra/compose.test.yml` in het commando en nooit met `down -v` zonder die override. De container `ampeer-devtest` op poort 5433 is de database van de suite en geen onderdeel van de stack; geen taak stopt hem.

### Volgorde

| Taak | Hangt af van |
|---|---|
| 1. Het plan en zijn markering | niets |
| 2. De modellen, de migratie en de vier auditsoorten | 1 |
| 3. `accounts/recovery.py` | 2 |
| 4. `nl.py`, de labels in `consent-texts/`, de fixture | 3 |
| 5. De vier routes, de serializers, de scope, `me/` | 4 |
| 6. `mailer.py`, de drie transporten, de grenstest, de omgeving | 5 |
| 7. Het command, de opruiming, de units, de deploy-job | 6 |
| 8. Frontend laag 1: `accounts.ts` | 7 |
| 9. Frontend laag 2: het fragment, `messages.ts`, de twee formulieren | 8 |
| 10. Frontend integratie: `AccountPage.tsx` en wat eromheen verandert | 9 |
| 11. `e2e/account.spec.ts` | 10 |
| 12. De stack-smoke tegen de echte stack | 11 |
| 13. De documenten | 12 |
| 14. De status omzetten en de poorten draaien | 13 |

### Bestandsbezit

| Taak | Bezit exclusief |
|---|---|
| 1 | `docs/superpowers/plans/2026-09-06-accounts-recovery.md` |
| 2 | `backend/accounts/models.py`, `backend/accounts/migrations/0004_recovery.py`, `backend/advice/models.py`, `tests/test_accounts_models.py`, `tests/test_dpia.py`, `docs/dpia.md` |
| 3 | `backend/accounts/recovery.py`, `tests/test_accounts_recovery.py` |
| 4 | `backend/accounts/nl.py`, `backend/accounts/views.py`, `tests/helpers/consent_texts_fixture.py`, `frontend/tests/fixtures/consent-texts.json`, `tests/test_frontend_contract.py`, `tests/test_accounts_api.py` |
| 5 | `backend/accounts/views.py`, `backend/accounts/urls.py`, `backend/accounts/serializers.py`, `backend/ampeer/settings/base.py`, `frontend/tests/fixtures/me-response.json`, `tests/test_accounts_recovery.py`, `tests/test_accounts_api.py` |
| 6 | `backend/accounts/mailer.py`, `backend/ampeer/settings/base.py`, `backend/ampeer/settings/dev.py`, `backend/ampeer/settings/prod.py`, `tests/test_accounts_mail.py`, `tests/test_boundaries.py`, `tests/test_infra.py`, `tests/test_deploy_workflow.py`, `tests/test_backend_settings.py`, `scripts/preflight_env.sh`, `infra/docker-compose.yml`, `infra/.env.example`, `.github/workflows/deploy.yml` |
| 7 | `backend/accounts/management/commands/send_outbound_mail.py`, `backend/accounts/management/commands/purge_expired_sessions.py`, `tests/test_accounts_mail.py`, `tests/test_dpia.py`, `docs/dpia.md`, `infra/systemd/ampeer-mail.service`, `infra/systemd/ampeer-mail.timer`, `infra/README.md`, `.github/workflows/deploy.yml`, `tests/test_stack_smoke.py` |
| 8 | `frontend/src/lib/accounts.ts`, `frontend/tests/lib/accounts.test.ts` |
| 9 | `frontend/src/app/_account/fragment.ts`, `frontend/src/app/_account/messages.ts`, `frontend/src/app/_account/ResetRequestForm.tsx`, `frontend/src/app/_account/ResetConfirmForm.tsx`, `frontend/tests/account/fragment.test.ts`, `frontend/tests/account/messages.test.ts`, `frontend/tests/account/ResetRequestForm.test.tsx`, `frontend/tests/account/ResetConfirmForm.test.tsx`, `frontend/tests/ui-strings.txt` |
| 10 | `frontend/src/app/_account/AccountPage.tsx`, `frontend/src/app/_account/SignInForm.tsx`, `frontend/src/app/_account/ConsentRow.tsx`, `frontend/src/app/_account/RegisterForm.tsx`, `frontend/tests/account/AccountPage.test.tsx`, `frontend/tests/account/ConsentRow.test.tsx`, `frontend/tests/account/RegisterForm.test.tsx`, `frontend/tests/account/SignInForm.test.tsx`, `frontend/tests/ui-strings.txt`, `tests/test_frontend_contract.py` |
| 11 | `frontend/e2e/account.spec.ts` |
| 12 | `tests/test_stack_smoke.py`, `infra/compose.test.yml` |
| 13 | `docs/decisions.md`, `docs/dpia.md`, `docs/superpowers/specs/2026-09-04-accounts-auth-design.md`, `docs/superpowers/specs/2026-09-05-accounts-frontend-design.md` |
| 14 | `docs/superpowers/plans/2026-09-06-accounts-recovery.md`, `pyproject.toml`, `frontend/vitest.config.ts` |

Gedeelde bestanden en de keten die ze veilig houdt: `views.py` door 4 en 5; `tests/test_accounts_api.py` door 4 en 5; `tests/test_accounts_recovery.py` door 3 en 5; `settings/base.py` door 5 en 6; `tests/test_accounts_mail.py` door 6 en 7; `tests/test_dpia.py` en `docs/dpia.md` door 2, 7 en 13; `.github/workflows/deploy.yml` door 6 en 7; `tests/test_stack_smoke.py` door 7 en 12; `tests/test_frontend_contract.py` door 4 en 10; `ui-strings.txt` door 9 en 10. Elk paar staat in die volgorde achter elkaar in de serie.

---

## Elf dingen die dit plan vastlegt en die de spec impliciet liet

**`me-response.json` verandert in taak 5 en niet in taak 8.** `test_the_me_fixture_has_the_shape_the_view_answers` in `tests/test_accounts_api.py` legt de fixture langs `_shape` naast het echte antwoord van `me/`. Zodra taak 5 `email_verified_at` aan `me/` toevoegt, is die test rood totdat de fixture het veld ook draagt. De fixture is dus een backend-bestand in de zin van die test, en taak 8 leest hem alleen.

**De wachtwoordvalidatie bij herstel deelt één vertaling met registratie.** `RegisterSerializer.validate_password` zet Django's `password_too_short` om naar `NL["password_too_short"]`, en die omzetting mag niet twee keer bestaan. Taak 5 tilt hem naar een modulefunctie `password_error_messages(error) -> list[str]` in `serializers.py`, die de serializer en `ResetConfirmView` allebei aanroepen. `recovery.confirm_password_reset` kent de gebruiker pas na het slot op het token, dus de validatie gebeurt daar, en een afkeuring komt terug als `PasswordRejected` met Django's `ValidationError` erin; de view vertaalt. Zo valideert `recovery.py` met de gebruiker erbij, zoals de spec eist, en blijft de Nederlandse zin op één plek.

**`enqueue` zegt of hij iets schreef, en alleen dan komt er een auditregel.** Spec 8.1 eist "twee verzoeken, één outbox-rij, één `PASSWORD_RESET_REQUESTED`". Dat kan alleen als de auditregel aan de ontdubbeling hangt: `recovery.enqueue(user, kind) -> bool` geeft `False` als er al een onverzonden rij ligt, en `request_password_reset` logt alleen bij `True`.

**Een geblokkeerd account krijgt geen mail.** `User.is_active` bestaat en `ModelBackend` weigert er een inlog op; `request_password_reset` zoekt daarom op `is_active=True`. Het antwoord blijft 202, de spec zegt dat al.

**De gelijktijdigheidstest is sequentieel plus een lezing van het slot.** Onder pytest-django loopt elke test in één transactie, en twee threads zien elkaars rijen niet zonder `transaction=True` en een echte race op Postgres, wat een proef oplevert die soms slaagt. Taak 3 bewijst daarom twee dingen apart: dat een tweede `confirm_password_reset` op hetzelfde token `TokenInvalid` krijgt en het wachtwoord één keer is gezet, en, via een AST-lezing van `recovery.py`, dat de rij met `select_for_update()` wordt opgehaald binnen `transaction.atomic()`. De semantiek van dat slot is die van Postgres en niet iets wat deze suite opnieuw hoeft te meten.

**Er komt geen `.gitkeep` in `infra/fixtures/mail/`.** `.gitignore` negeert `infra/fixtures/` in zijn geheel, dus een bestand daaronder is niet te committen. De map wordt aangemaakt door `main()` in `tests/test_stack_smoke.py`, dat de andere twee fixtures ook al schrijft, met `chmod 0o777` als beste poging voor een Linux-host waar de container als uid 10001 moet kunnen schrijven. Op Docker Desktop is die chmod overbodig en onschadelijk.

**`AMPEER_MAIL_FILE_DIR` is een vijfde naam, en hij hoort niet in de env-file.** `prod.py` leest hem met een standaardwaarde `/srv/mail`, want de map is een eigenschap van de container en niet van de host. `infra/compose.test.yml` mount `./fixtures/mail` op dat pad als literal, zonder interpolatie, zodat `test_the_environment_fixture_names_every_variable_the_stack_reads` er niets van hoeft te weten. De env-fixture, `.env.example` en de preflight kennen de vier andere namen.

**De twee hashes in `deploy.yml` bewegen in taak 6.** `test_the_deploy_pins_the_checksum_of_the_preflight_it_runs` en het bijbehorende `COMPOSE_SHA256` vergelijken de sha256 van `scripts/preflight_env.sh` en `infra/docker-compose.yml` met een literal in de workflow. Taak 6 wijzigt beide bestanden en herrekent beide hashes in dezelfde commit; taak 7 raakt de workflow daarna alleen voor de `--check`-stap.

**Als de toestemmingsteksten niet laden, heeft de accountweergave ook geen labels.** Ze komen uit hetzelfde antwoord. `ConsentRow` krijgt `label: string | null`; bij `null` staat er geen labelalinea en draagt de beschrijving van de knop alleen de uitlegzin die er al was. Twee rijen lezen dan gelijk voor een schermlezer. Dat is dezelfde vorm van achteruitgang die spec 6.3 van het frontend-ontwerp al aanvaardt voor de tekst zelf, en hij is bereikbaar in precies één toestand: de API is weg terwijl de pagina open staat.

**De lengte van het token wordt over de grens heen vastgezet.** `secrets.token_urlsafe(32)` geeft 43 tekens, en `readRecoveryFragment` accepteert alleen een fragment van precies die vorm, zodat een aangepast of afgekapt fragment `null` leest in plaats van een verzoek te worden. Taak 10 zet in `tests/test_frontend_contract.py` de `43` uit `fragment.ts` naast `len(secrets.token_urlsafe(TOKEN_BYTES))` uit `recovery.py`, zodat een wijziging aan een van beide kanten de andere rood maakt.

**De DPIA verandert in drie taken en niet in een.** `test_the_audit_log_records_exactly_what_the_document_says_it_does` bindt de lijst soorten aan hoofdstuk 2, dus de vier soorten en hun zin komen in taak 2, samen met de constanten. `test_the_document_names_everything_the_audit_line_carries` bindt elk sleutelwoord aan een zin, dus `provider_id` komt in taak 7, samen met het command dat hem schrijft. Al het andere, hoofdstuk 5, 6, 7 en 10, is proza zonder test erop en komt in taak 13.

---

### Taak 1: Het plan en zijn markering

**Files:**
- Create: `docs/superpowers/plans/2026-09-06-accounts-recovery.md`

**Interfaces:**
- Consumes: `tests/test_plans.py`, dat elk plan in `docs/superpowers/plans/` leest.
- Produces: de regel `**Status:** in progress` op regel 5, die taak 14 omzet.

De markering doet twee dingen tegelijk. Zolang hij erop staat, leest `test_every_file_a_finished_plan_names_exists` dit plan niet streng: de twintig bestanden die het noemt en die nog niet bestaan zijn dan geen fout. En `test_a_plan_marked_in_progress_is_actually_unfinished` wordt uit zichzelf rood zodra elk genoemd bestand bestaat, wat taak 12 doet met de twee nieuwe testbestanden en de twee units. Dat is de zelfvervallende tripwire: taak 14 moet de markering omzetten, en kan dat niet vergeten.

- [ ] **Step 1: Commit dit document**

Het staat al op de branch als deze taak begint; controleer dat de regel op regel 5 precies `**Status:** in progress` is, op kolom 0, en dat hij in die vorm precies één keer op kolom 0 in dit document voorkomt:

```bash
sed -n '5p' docs/superpowers/plans/2026-09-06-accounts-recovery.md
grep -c '^\*\*Status:\*\* in progress' docs/superpowers/plans/2026-09-06-accounts-recovery.md
```

Verwacht: de regel, en `1`.

- [ ] **Step 2: Draai de plancontrole**

```bash
uv run --no-sync pytest tests/test_plans.py -q
```

Verwacht: groen. `test_a_plan_marked_in_progress_is_actually_unfinished[2026-09-06-accounts-recovery.md]` is groen omdat er bestanden ontbreken, en `test_every_file_a_finished_plan_names_exists` slaat dit plan over.

- [ ] **Step 3: Toon aan dat de markering iets doet**

Verander regel 5 tijdelijk in `**Status:** delivered` en draai opnieuw:

```bash
uv run --no-sync pytest tests/test_plans.py -q
```

Verwacht: rood op `test_every_file_a_finished_plan_names_exists[2026-09-06-accounts-recovery.md]`, met een lijst van de bestanden die dit plan noemt en die nog niet bestaan, waaronder `backend/accounts/recovery.py` en `frontend/src/app/_account/fragment.ts`. Zet regel 5 met de hand terug op `**Status:** in progress` en draai een derde keer: groen. Plak beide uitvoeren in het rapport.

- [ ] **Step 4: Commit**

Alleen als de eerste stap iets veranderde; anders is dit plan al gecommit door de controller en is er niets te doen. Boodschap, indien nodig: `docs(plans): the accounts recovery plan, marked unfinished`.

---

### Taak 2: De modellen, de migratie en de vier auditsoorten

**Hangt af van:** taak 1.

**Files:**
- Modify: `backend/accounts/models.py`
- Create: `backend/accounts/migrations/0004_recovery.py` (via `makemigrations`)
- Modify: `backend/advice/models.py`
- Create: `tests/test_accounts_models.py`
- Modify: `tests/test_dpia.py`, `docs/dpia.md`

**Interfaces:**
- Consumes: `User`, `token_digest`, `AuditEvent` zoals ze zijn.
- Produces: `User.email_verified_at: DateTimeField(null=True)`; `OneTimeToken` met `PASSWORD_RESET`, `EMAIL_VERIFY`, `KINDS`, `LIFETIMES`, de velden uit spec 2.1 en de property `is_usable`; `OutboundMail` met de velden uit spec 4.2; `AuditEvent.PASSWORD_RESET_REQUESTED`, `PASSWORD_RESET_COMPLETED`, `EMAIL_VERIFIED`, `MAIL_SENT`.

- [ ] **Step 1: Schrijf de falende tests**

`tests/test_accounts_models.py`, compleet:

```text
"""The two recovery tables and the one new column, before any route exists.

Asserted on the model and on the schema rather than through a request, because
the properties below decide what a route may say later: a token that reads
usable after it was spent is a token that opens something twice.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.core.management import call_command
from django.utils import timezone
from helpers.accounts import TEST_PASSWORD

from accounts.models import OneTimeToken, OutboundMail, User
from advice.models import AuditEvent, token_digest


@pytest.fixture
def _account() -> User:
    return User.objects.create_user(email="iemand@voorbeeld.nl", password=TEST_PASSWORD)


@pytest.mark.django_db
def test_a_new_account_has_no_verified_address(_account: User) -> None:
    """Null means never confirmed, which is true of every account that exists
    before this cycle and of every account at the moment it is made."""
    assert _account.email_verified_at is None


@pytest.mark.django_db
def test_a_token_is_usable_until_spent_superseded_or_expired(_account: User) -> None:
    now = timezone.now()
    row = OneTimeToken.objects.create(
        user=_account,
        kind=OneTimeToken.PASSWORD_RESET,
        token_sha256=token_digest("een-ruw-token"),
        issued_at=now,
        expires_at=now + timedelta(hours=1),
    )
    assert row.is_usable
    row.spent_at = now
    assert not row.is_usable
    row.spent_at = None
    row.superseded_at = now
    assert not row.is_usable
    row.superseded_at = None
    row.expires_at = now - timedelta(seconds=1)
    assert not row.is_usable


def test_the_two_lifetimes_are_one_hour_and_seven_days() -> None:
    """Spec 2.1. A reset link is a password; a confirmation link is a fact
    about an address that does not change. Read off the model so a later edit
    of either number shows up here and not only in a mail nobody rereads."""
    assert OneTimeToken.LIFETIMES[OneTimeToken.PASSWORD_RESET] == timedelta(hours=1)
    assert OneTimeToken.LIFETIMES[OneTimeToken.EMAIL_VERIFY] == timedelta(days=7)
    assert set(OneTimeToken.LIFETIMES) == OneTimeToken.KINDS


@pytest.mark.django_db
def test_an_outbox_row_starts_unsent_and_due_now(_account: User) -> None:
    before = timezone.now()
    row = OutboundMail.objects.create(
        user=_account, kind=OneTimeToken.EMAIL_VERIFY, next_attempt_at=before
    )
    assert row.attempts == 0
    assert row.failed_at is None
    assert row.last_status is None
    assert row.created_at >= before


@pytest.mark.django_db
def test_deleting_the_account_takes_its_tokens_and_its_outbox_rows(_account: User) -> None:
    """A mail to an address that no longer belongs to an account must not
    leave, and a token for a user who is gone must not be findable."""
    now = timezone.now()
    OneTimeToken.objects.create(
        user=_account,
        kind=OneTimeToken.EMAIL_VERIFY,
        token_sha256=token_digest("nog-een-token"),
        issued_at=now,
        expires_at=now + timedelta(days=7),
    )
    OutboundMail.objects.create(user=_account, kind=OneTimeToken.EMAIL_VERIFY, next_attempt_at=now)
    _account.delete()
    assert OneTimeToken.objects.count() == 0
    assert OutboundMail.objects.count() == 0


def test_the_audit_log_knows_the_four_new_handlings() -> None:
    """Every entry on AuditEvent is a handling that exists, and these four
    arrive with this cycle. tests/test_dpia.py binds the same four to
    docs/dpia.md chapter 2; this pins the constants' own spelling."""
    for name in (
        "PASSWORD_RESET_REQUESTED",
        "PASSWORD_RESET_COMPLETED",
        "EMAIL_VERIFIED",
        "MAIL_SENT",
    ):
        assert getattr(AuditEvent, name) == name


@pytest.mark.django_db
def test_the_migrations_describe_the_models_exactly() -> None:
    """`makemigrations --check` exits non-zero when a model has drifted from
    its migrations. Run here rather than remembered, because a model edit
    without a migration passes every other test in this suite and fails on
    the first deploy."""
    call_command("makemigrations", "accounts", "--check", "--dry-run", verbosity=0)
```

- [ ] **Step 2: Draai ze en zie ze falen**

```bash
POSTGRES_HOST=127.0.0.1 POSTGRES_PORT=5433 POSTGRES_DB=ampeer POSTGRES_USER=ampeer POSTGRES_PASSWORD=devtest uv run --no-sync pytest tests/test_accounts_models.py -q
```

Verwacht: `ImportError` op `OneTimeToken`, want de klasse bestaat nog niet. Plak de eerste regel van de fout.

- [ ] **Step 3: Het veld en de twee modellen**

In `backend/accounts/models.py`: voeg aan de imports toe

```text
from datetime import timedelta
```

Voeg in `User`, direct onder `date_joined`, toe:

```text
    #: When the address was confirmed as this person's, by a confirmation
    #: link or by a completed password reset. A timestamp and not a flag,
    #: because "when" is the question a privacy document asks and a flag
    #: cannot answer it. Null means never, which is true of every account
    #: made before this column existed. Nothing in phase 1 reads it; phase 2
    #: requires it before a meter is linked, and that is the only place it
    #: blocks anything.
    email_verified_at = models.DateTimeField(null=True, blank=True)
```

Voeg onderaan het bestand, na `RefreshSession`, toe:

```text
class OneTimeToken(models.Model):
    """One link that works once, without the link.

    The same shape as `RefreshSession` above, for a second vocabulary: the
    row holds the sha256 of the token and never the token, so a copy of this
    table hands nobody a working link. `token_digest` is the same unsalted
    sha256 the advice token and the refresh session use, with the same
    argument: the input is 256 bits from `secrets.token_urlsafe`, so there
    is no dictionary to run and no salt that adds anything.

    Why not `django.contrib.auth.tokens.PasswordResetTokenGenerator`, which
    decision 31 pointed at: it hashes `last_login` into the token, so a
    confirmation link would die the moment the new account signs in, and it
    has no notion of "spent", so a reset link would stay valid until the
    password changed. `spent_at` answers that in one column.
    """

    PASSWORD_RESET = "PASSWORD_RESET"
    EMAIL_VERIFY = "EMAIL_VERIFY"
    KINDS: ClassVar[frozenset[str]] = frozenset({PASSWORD_RESET, EMAIL_VERIFY})

    #: One hour for a link that sets a password, seven days for a link that
    #: confirms a fact about an address. Counted from `issued_at`, which is
    #: the moment of sending and not the moment of asking.
    LIFETIMES: ClassVar[dict[str, timedelta]] = {
        PASSWORD_RESET: timedelta(hours=1),
        EMAIL_VERIFY: timedelta(days=7),
    }

    user = models.ForeignKey(
        "accounts.User", on_delete=models.CASCADE, related_name="one_time_tokens"
    )
    kind = models.CharField(max_length=16, db_index=True)
    token_sha256 = models.CharField(max_length=64, unique=True, db_index=True)
    issued_at = models.DateTimeField()
    expires_at = models.DateTimeField(db_index=True)
    spent_at = models.DateTimeField(null=True, blank=True)
    #: Set on every older unspent token of the same kind when a new one is
    #: minted, so a person has at most one usable link per kind at a time.
    superseded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering: ClassVar[list[str]] = ["-issued_at"]

    @property
    def is_usable(self) -> bool:
        """The one question the three routes that read a token ask."""
        return (
            self.spent_at is None
            and self.superseded_at is None
            and self.expires_at > timezone.now()
        )


class OutboundMail(models.Model):
    """One message waiting to leave, described by what it is and not by what it says.

    No address (it is on `User`, read at the moment of sending), no subject,
    no body and no token: the token does not exist yet when this row is
    written, because it is minted by the command that sends the mail, so the
    only two places a raw token ever is are that command's memory and the
    mail itself. `tests/test_dpia.py` keeps asserting that no table has an
    address column, and this table keeps that true.

    CASCADE, so an account deleted before its mail left takes the row with
    it: nothing goes out to an address that no longer belongs to an account.
    """

    user = models.ForeignKey(
        "accounts.User", on_delete=models.CASCADE, related_name="outbound_mails"
    )
    kind = models.CharField(max_length=16, db_index=True)
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    attempts = models.PositiveSmallIntegerField(default=0)
    #: From when the command may pick this row up again. Now on creation,
    #: later after a failed attempt.
    next_attempt_at = models.DateTimeField(db_index=True)
    #: The HTTP status of the last attempt, 0 for no answer at all.
    last_status = models.PositiveSmallIntegerField(null=True, blank=True)
    #: When the command gave up. A row with this set is never retried and is
    #: removed seven days later by `purge_expired_sessions`.
    failed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering: ClassVar[list[str]] = ["id"]
```

- [ ] **Step 4: De vier constanten**

In `backend/advice/models.py`, in `AuditEvent`, direct onder `ACCOUNT_DELETED = "ACCOUNT_DELETED"`:

```text
    #: The four that arrived with password reset and address confirmation.
    #: A reset request is logged only for an address that belongs to an
    #: account, with `user_id` and nothing else; for an unknown address there
    #: is nothing to point at and the log stays silent, because a line about
    #: it would have to carry the address to mean anything. `MAIL_SENT`
    #: carries the kind and the id the mail provider returned: that id is not
    #: a personal datum and is the only handle by which one delivery can be
    #: found at the processor.
    PASSWORD_RESET_REQUESTED = "PASSWORD_RESET_REQUESTED"
    PASSWORD_RESET_COMPLETED = "PASSWORD_RESET_COMPLETED"
    EMAIL_VERIFIED = "EMAIL_VERIFIED"
    MAIL_SENT = "MAIL_SENT"
```

- [ ] **Step 5: De migratie**

```bash
POSTGRES_HOST=127.0.0.1 POSTGRES_PORT=5433 POSTGRES_DB=ampeer POSTGRES_USER=ampeer POSTGRES_PASSWORD=devtest uv run --no-sync python backend/manage.py makemigrations accounts --name recovery
```

Verwacht: `backend/accounts/migrations/0004_recovery.py` met drie operaties: `AddField` voor `email_verified_at` op `user`, `CreateModel` voor `OneTimeToken`, `CreateModel` voor `OutboundMail`. Open het bestand en controleer dat het niets anders bevat; een vierde operatie betekent dat een bestaand model per ongeluk is veranderd. Draai daarna de formatter erover, want `makemigrations` schrijft geen ruff-conforme code:

```bash
uv run --no-sync ruff format backend/accounts/migrations/0004_recovery.py
uv run --no-sync ruff check backend/accounts/migrations/0004_recovery.py
```

- [ ] **Step 6: De DPIA en de test die haar bindt**

`tests/test_dpia.py`, in `test_the_audit_log_records_exactly_what_the_document_says_it_does`: vervang de docstring-kop "Nine event types today" door "Thirteen event types today" en voeg aan de lijst in de assertie, na `"ACCOUNT_DELETED",`, toe:

```text
        "PASSWORD_RESET_REQUESTED",
        "PASSWORD_RESET_COMPLETED",
        "EMAIL_VERIFIED",
        "MAIL_SENT",
```

`docs/dpia.md`, hoofdstuk 2, de alinea die begint met "`AuditEvent` is append-only en kent sinds fase 1 negen soorten gebeurtenissen": vervang "negen soorten gebeurtenissen in plaats van een" door "dertien soorten gebeurtenissen in plaats van een", en voeg na "en dat een account is verwijderd (`ACCOUNT_DELETED`)" toe, voor de punt:

```text
, en sinds het derde deel van fase 1 ook dat om wachtwoordherstel is gevraagd
voor een adres dat bij een account hoort (`PASSWORD_RESET_REQUESTED`), dat een
herstel is voltooid (`PASSWORD_RESET_COMPLETED`), dat een e-mailadres is
bevestigd (`EMAIL_VERIFIED`) en dat een bericht bij de mailverwerker is
afgeleverd (`MAIL_SENT`)
```

Vervang in dezelfde alinea "De acht andere dragen geen vaste vorm" door "De twaalf andere dragen geen vaste vorm". Voeg aan het eind van die alinea, na "in een tabel zonder bewaartermijn.", één zin toe:

```text
Een herstelverzoek voor een adres dat bij geen account hoort, wordt niet
gelogd: een regel daarover zou het adres zelf moeten dragen om iets te
betekenen.
```

- [ ] **Step 7: Groen**

```bash
POSTGRES_HOST=127.0.0.1 POSTGRES_PORT=5433 POSTGRES_DB=ampeer POSTGRES_USER=ampeer POSTGRES_PASSWORD=devtest uv run --no-sync pytest tests/test_accounts_models.py tests/test_dpia.py tests/test_accounts_privacy.py -q
```

Verwacht: alles groen, inclusief `test_no_table_has_a_column_for_an_address`, dat nu drie modellen in `accounts/models.py` meer leest.

- [ ] **Step 8: Toon aan dat de DPIA-binding rood kan worden**

Haal `"MAIL_SENT",` tijdelijk uit de lijst in `tests/test_dpia.py` en draai:

```bash
uv run --no-sync pytest tests/test_dpia.py::test_the_audit_log_records_exactly_what_the_document_says_it_does -q
```

Verwacht: rood, met de dertien soorten in de melding tegenover de twaalf in de lijst. Zet de regel met de hand terug. Haal daarna `and self.superseded_at is None` tijdelijk uit `is_usable` en draai `tests/test_accounts_models.py::test_a_token_is_usable_until_spent_superseded_or_expired`: rood op de tweede `assert not row.is_usable`. Zet terug. Plak beide.

- [ ] **Step 9: mypy en ruff**

```bash
uv run --no-sync mypy --strict backend tests
uv run --no-sync ruff check . && uv run --no-sync ruff format --check .
```

- [ ] **Step 10: Commit**

```bash
git add backend/accounts/models.py backend/accounts/migrations/0004_recovery.py backend/advice/models.py tests/test_accounts_models.py tests/test_dpia.py docs/dpia.md
git commit
```

Boodschap: `feat(accounts): a one-time token table, an outbox, and when an address was confirmed`.

---

### Taak 3: `accounts/recovery.py`

**Hangt af van:** taak 2.

**Files:**
- Create: `backend/accounts/recovery.py`
- Create: `tests/test_accounts_recovery.py`

**Interfaces:**
- Consumes: `OneTimeToken`, `OutboundMail`, `User`, `_normalize_email` uit `accounts.models`; `tokens.revoke_all`; `token_digest` en `AuditEvent` uit `advice.models`; Django's `validate_password`.
- Produces, en dit zijn de handtekeningen die taak 5 en taak 7 gebruiken:
  - `TOKEN_BYTES: Final = 32`
  - `class TokenInvalid(Exception)`: één klasse voor verlopen, gebruikt, vervangen en onbekend
  - `class PasswordRejected(Exception)` met attribuut `error: DjangoValidationError`
  - `mint(user: User, kind: str) -> str`: geeft het ruwe token terug, schrijft de digest, vervangt oudere ongebruikte tokens van dezelfde soort
  - `enqueue(user: User, kind: str) -> bool`: één onverzonden rij per gebruiker per soort
  - `request_password_reset(email: str) -> None`
  - `confirm_password_reset(raw_token: str, password: str) -> User`
  - `request_email_verification(user: User) -> None`
  - `confirm_email_verification(raw_token: str) -> User`

De module staat naast `service.py` en niet erin, om de reden die spec 3.6 geeft: `_audit_context_keys` in `tests/test_dpia.py` eist dat `service.py` precies één `record()`-aanroep bevat.

- [ ] **Step 1: Schrijf de falende tests**

`tests/test_accounts_recovery.py`, compleet; taak 5 voegt er de routetests aan toe:

```text
"""The four recovery handlings, as functions, before a route touches them.

Every assertion here is about a property a route may later rely on: one use
per token, the same refusal for every bad token, a password that is validated
before anything is spent, and tables that never hold a raw token.
"""

from __future__ import annotations

import ast
import secrets
from datetime import timedelta
from pathlib import Path

import pytest
from django.utils import timezone
from helpers.accounts import OTHER_PASSWORD, TEST_PASSWORD

from accounts import recovery, tokens
from accounts.models import OneTimeToken, OutboundMail, RefreshSession, User
from advice.models import AuditEvent, token_digest

REPO_ROOT = Path(__file__).resolve().parent.parent
RECOVERY = REPO_ROOT / "backend" / "accounts" / "recovery.py"


@pytest.fixture
def _account() -> User:
    return User.objects.create_user(email="iemand@voorbeeld.nl", password=TEST_PASSWORD)


@pytest.mark.django_db
def test_minting_writes_a_digest_and_returns_the_token_once(_account: User) -> None:
    raw = recovery.mint(_account, OneTimeToken.PASSWORD_RESET)
    assert len(raw) == len(secrets.token_urlsafe(recovery.TOKEN_BYTES))
    row = OneTimeToken.objects.get(user=_account)
    assert row.token_sha256 == token_digest(raw)
    assert row.is_usable
    assert row.expires_at - row.issued_at == OneTimeToken.LIFETIMES[OneTimeToken.PASSWORD_RESET]


@pytest.mark.django_db
def test_a_new_token_supersedes_the_older_unspent_one_of_the_same_kind(_account: User) -> None:
    """Spec 2.3: at most one usable link per person per kind."""
    first = recovery.mint(_account, OneTimeToken.PASSWORD_RESET)
    recovery.mint(_account, OneTimeToken.EMAIL_VERIFY)
    second = recovery.mint(_account, OneTimeToken.PASSWORD_RESET)
    rows = {row.token_sha256: row for row in OneTimeToken.objects.filter(user=_account)}
    assert rows[token_digest(first)].superseded_at is not None
    assert rows[token_digest(second)].is_usable
    verify = OneTimeToken.objects.get(user=_account, kind=OneTimeToken.EMAIL_VERIFY)
    assert verify.is_usable, "a reset token must not supersede a verification token"


@pytest.mark.django_db
def test_minting_an_unknown_kind_is_refused(_account: User) -> None:
    with pytest.raises(ValueError, match="kind"):
        recovery.mint(_account, "SOMETHING_ELSE")


@pytest.mark.django_db
def test_a_reset_request_for_a_known_address_enqueues_exactly_once(_account: User) -> None:
    recovery.request_password_reset("IEMAND@voorbeeld.nl")
    recovery.request_password_reset("iemand@voorbeeld.nl")
    assert OutboundMail.objects.filter(user=_account, kind=OneTimeToken.PASSWORD_RESET).count() == 1
    assert AuditEvent.objects.filter(event_type=AuditEvent.PASSWORD_RESET_REQUESTED).count() == 1
    line = AuditEvent.objects.get(event_type=AuditEvent.PASSWORD_RESET_REQUESTED)
    assert line.context == {"user_id": _account.pk}


@pytest.mark.django_db
def test_a_reset_request_for_an_unknown_or_inactive_address_writes_nothing(_account: User) -> None:
    """No row and no audit line: a line about an unknown address would have
    to carry the address to mean anything."""
    recovery.request_password_reset("niemand@voorbeeld.nl")
    _account.is_active = False
    _account.save(update_fields=["is_active"])
    recovery.request_password_reset("iemand@voorbeeld.nl")
    assert OutboundMail.objects.count() == 0
    assert AuditEvent.objects.count() == 0


@pytest.mark.django_db
def test_a_reset_token_can_be_used_exactly_once(_account: User) -> None:
    """The second use reads a row with `spent_at` filled and is refused; the
    password is set once. The lock that makes this hold under a real race is
    read off the source in the test below, because two threads inside one
    pytest-django transaction cannot see each other's rows at all."""
    tokens.issue(_account)
    raw = recovery.mint(_account, OneTimeToken.PASSWORD_RESET)
    recovery.confirm_password_reset(raw, OTHER_PASSWORD)
    with pytest.raises(recovery.TokenInvalid):
        recovery.confirm_password_reset(raw, TEST_PASSWORD)
    _account.refresh_from_db()
    assert _account.check_password(OTHER_PASSWORD)
    assert not _account.check_password(TEST_PASSWORD)


def test_the_token_row_is_locked_before_it_is_read() -> None:
    """`select_for_update()` inside `transaction.atomic()`, read off recovery.py
    the way tests/test_dpia.py reads the views, so the lock cannot be dropped
    in a refactor that keeps every behavioural test green."""
    tree = ast.parse(RECOVERY.read_text(encoding="utf-8"))
    locked = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute) and node.attr == "select_for_update"
    ]
    assert locked, "recovery.py no longer locks the token row before reading it"
    atomic = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.With)
        and any(
            isinstance(item.context_expr, ast.Call)
            and ast.unparse(item.context_expr.func) == "transaction.atomic"
            for item in node.items
        )
    ]
    assert len(atomic) >= 2, "confirm_password_reset and confirm_email_verification each hold a transaction"


@pytest.mark.django_db
def test_expired_spent_superseded_and_unknown_tokens_all_raise_the_same_class(
    _account: User,
) -> None:
    now = timezone.now()
    spent = recovery.mint(_account, OneTimeToken.PASSWORD_RESET)
    recovery.confirm_password_reset(spent, OTHER_PASSWORD)
    superseded = recovery.mint(_account, OneTimeToken.PASSWORD_RESET)
    recovery.mint(_account, OneTimeToken.PASSWORD_RESET)
    expired = recovery.mint(_account, OneTimeToken.EMAIL_VERIFY)
    OneTimeToken.objects.filter(token_sha256=token_digest(expired)).update(
        expires_at=now - timedelta(seconds=1)
    )
    for raw in (spent, superseded, "dit-token-bestaat-niet"):
        with pytest.raises(recovery.TokenInvalid):
            recovery.confirm_password_reset(raw, TEST_PASSWORD)
    with pytest.raises(recovery.TokenInvalid):
        recovery.confirm_email_verification(expired)
    with pytest.raises(recovery.TokenInvalid):
        # A verification token offered to the reset route: the kind is part
        # of the lookup, so a link for one purpose cannot serve the other.
        recovery.confirm_password_reset(recovery.mint(_account, OneTimeToken.EMAIL_VERIFY), OTHER_PASSWORD)


@pytest.mark.django_db
def test_a_completed_reset_revokes_every_session_and_verifies_the_address(_account: User) -> None:
    tokens.issue(_account)
    tokens.issue(_account)
    raw = recovery.mint(_account, OneTimeToken.PASSWORD_RESET)
    before = timezone.now()
    user = recovery.confirm_password_reset(raw, OTHER_PASSWORD)
    assert user.pk == _account.pk
    assert not RefreshSession.objects.filter(user=_account, revoked_at__isnull=True).exists()
    _account.refresh_from_db()
    assert _account.email_verified_at is not None
    assert _account.email_verified_at >= before
    kinds = list(AuditEvent.objects.order_by("id").values_list("event_type", flat=True))
    assert kinds == [AuditEvent.PASSWORD_RESET_COMPLETED, AuditEvent.EMAIL_VERIFIED]


@pytest.mark.django_db
def test_a_reset_on_an_already_verified_address_does_not_verify_it_again(_account: User) -> None:
    first = recovery.mint(_account, OneTimeToken.EMAIL_VERIFY)
    recovery.confirm_email_verification(first)
    _account.refresh_from_db()
    stamped = _account.email_verified_at
    raw = recovery.mint(_account, OneTimeToken.PASSWORD_RESET)
    recovery.confirm_password_reset(raw, OTHER_PASSWORD)
    _account.refresh_from_db()
    assert _account.email_verified_at == stamped
    assert AuditEvent.objects.filter(event_type=AuditEvent.EMAIL_VERIFIED).count() == 1


@pytest.mark.django_db
def test_the_password_validators_apply_on_a_reset_and_spend_nothing(_account: User) -> None:
    """A rejected password leaves the token usable: the household reads the
    message and tries again with the same link."""
    raw = recovery.mint(_account, OneTimeToken.PASSWORD_RESET)
    with pytest.raises(recovery.PasswordRejected) as caught:
        recovery.confirm_password_reset(raw, "kort")
    assert any(error.code == "password_too_short" for error in caught.value.error.error_list)
    row = OneTimeToken.objects.get(token_sha256=token_digest(raw))
    assert row.is_usable
    _account.refresh_from_db()
    assert _account.check_password(TEST_PASSWORD)
    assert AuditEvent.objects.count() == 0


@pytest.mark.django_db
def test_a_verification_confirms_once_and_writes_one_line(_account: User) -> None:
    raw = recovery.mint(_account, OneTimeToken.EMAIL_VERIFY)
    recovery.confirm_email_verification(raw)
    with pytest.raises(recovery.TokenInvalid):
        recovery.confirm_email_verification(raw)
    _account.refresh_from_db()
    assert _account.email_verified_at is not None
    assert AuditEvent.objects.filter(event_type=AuditEvent.EMAIL_VERIFIED).count() == 1


@pytest.mark.django_db
def test_requesting_a_verification_dedupes_and_stops_once_verified(_account: User) -> None:
    recovery.request_email_verification(_account)
    recovery.request_email_verification(_account)
    assert OutboundMail.objects.filter(kind=OneTimeToken.EMAIL_VERIFY).count() == 1
    OutboundMail.objects.all().delete()
    _account.email_verified_at = timezone.now()
    _account.save(update_fields=["email_verified_at"])
    recovery.request_email_verification(_account)
    assert OutboundMail.objects.count() == 0


@pytest.mark.django_db
def test_no_column_anywhere_holds_a_raw_token(_account: User) -> None:
    """Value based, like test_no_session_row_carries_anything_that_opens_a_session:
    the raw token is searched for in every text column of the three tables."""
    recovery.request_password_reset(_account.email)
    raw = recovery.mint(_account, OneTimeToken.PASSWORD_RESET)
    values: list[str] = []
    for row in OneTimeToken.objects.all():
        values.extend([row.kind, row.token_sha256])
    for mail in OutboundMail.objects.all():
        values.append(mail.kind)
    for line in AuditEvent.objects.all():
        values.append(line.event_type)
        values.extend(str(item) for pair in line.context.items() for item in pair)
    assert values, "nothing was read, so nothing was checked"
    assert all(raw not in value for value in values)
    assert all(token_digest(raw) != value or value == token_digest(raw) for value in values)
```

De laatste assertie zegt met opzet niets tegen de digest: die hoort er te staan, en het is het ruwe token dat nergens mag staan.

- [ ] **Step 2: Zie ze falen**

```bash
POSTGRES_HOST=127.0.0.1 POSTGRES_PORT=5433 POSTGRES_DB=ampeer POSTGRES_USER=ampeer POSTGRES_PASSWORD=devtest uv run --no-sync pytest tests/test_accounts_recovery.py -q
```

Verwacht: `ImportError` op `accounts.recovery`. Plak de eerste regel.

- [ ] **Step 3: De module**

`backend/accounts/recovery.py`, compleet:

```text
"""Password reset and address confirmation, as four handlings and a mint.

Beside service.py and not inside it: tests/test_dpia.py reads service.py on
the assumption that it writes exactly one audit line, and says so in its own
assertion message. This module writes four kinds of line and keeps that
assumption true by living next door; the walk over every file under
backend/accounts/ still reads its keywords.

The raw token is returned by `mint` and never stored. It exists in the memory
of the command that sends the mail and in the mail itself, and the digest in
`OneTimeToken` is the only thing this table can hand anybody.
"""

from __future__ import annotations

import secrets
from typing import Final

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.utils import timezone

from accounts import tokens
from accounts.models import OneTimeToken, OutboundMail, User, _normalize_email
from advice.models import AuditEvent, token_digest

#: 32 bytes, 256 bits, 43 url-safe characters: twice the advice token, because
#: an advice token opens an advice that expires in ninety days and this one
#: sets a password. frontend/src/app/_account/fragment.ts accepts exactly
#: that length, and tests/test_frontend_contract.py holds the two together.
TOKEN_BYTES: Final = 32


class TokenInvalid(Exception):
    """Expired, spent, superseded, or never issued. One class on purpose: the
    difference between the four is only interesting to somebody trying tokens."""


class PasswordRejected(Exception):
    """Django's validators refused the new password. Carries their error so the
    view can translate it the way RegisterSerializer does, in one place."""

    def __init__(self, error: DjangoValidationError) -> None:
        super().__init__("the new password was refused by a validator")
        self.error = error


def mint(user: User, kind: str) -> str:
    """A fresh token of one kind, and the digest written down.

    Every older unspent token of the same kind for this user is superseded in
    the same statement, so there is at most one usable link per person per
    kind. Called by the command that sends the mail and by nothing else, so
    `issued_at` is the moment of sending.
    """
    if kind not in OneTimeToken.KINDS:
        raise ValueError(f"unknown token kind: {kind}")
    now = timezone.now()
    OneTimeToken.objects.filter(
        user=user, kind=kind, spent_at__isnull=True, superseded_at__isnull=True
    ).update(superseded_at=now)
    raw = secrets.token_urlsafe(TOKEN_BYTES)
    OneTimeToken.objects.create(
        user=user,
        kind=kind,
        token_sha256=token_digest(raw),
        issued_at=now,
        expires_at=now + OneTimeToken.LIFETIMES[kind],
    )
    return raw


def enqueue(user: User, kind: str) -> bool:
    """One unsent row per user per kind. Returns whether a row was written."""
    if OutboundMail.objects.filter(user=user, kind=kind, failed_at__isnull=True).exists():
        return False
    OutboundMail.objects.create(user=user, kind=kind, next_attempt_at=timezone.now())
    return True


def request_password_reset(email: str) -> None:
    """Never says anything about the address, and never touches the network.

    Lowered the way `_normalize_email` lowers on every write, because the row
    is stored lowered and a lookup in other capitals would miss it. A blocked
    account (`is_active` False) gets no mail: a reset would not let it in.
    """
    user = User.objects.filter(email=_normalize_email(email), is_active=True).first()
    if user is None:
        return
    if enqueue(user, OneTimeToken.PASSWORD_RESET):
        AuditEvent.record(AuditEvent.PASSWORD_RESET_REQUESTED, user_id=user.pk)


def _lock(raw_token: str, kind: str) -> OneTimeToken:
    """The row for this token, locked, and usable. Inside the caller's atomic block.

    The lock is `select_for_update` on the one row, the same shape as
    `tokens.rotate`: two confirmations with the same token queue on it, the
    second reads `spent_at` filled and is refused. There is no `revoke_all`
    branch here, unlike a reused refresh token: a reused reset link is a
    refused link, not evidence that somebody else holds the session.
    """
    row = (
        OneTimeToken.objects.select_for_update()
        .filter(token_sha256=token_digest(raw_token), kind=kind)
        .first()
    )
    if row is None or not row.is_usable:
        raise TokenInvalid(kind)
    return row


def _spend(row: OneTimeToken) -> None:
    row.spent_at = timezone.now()
    row.save(update_fields=["spent_at"])


def confirm_password_reset(raw_token: str, password: str) -> User:
    """Token first, then the password, then everything at once or nothing.

    The validators run with the user, because `UserAttributeSimilarityValidator`
    compares against the address, and they run before anything is written: a
    rejected password leaves the token usable and the transaction untouched.
    Then, still under the lock: the password, every session revoked so
    nothing that started under the old password survives, the address
    confirmed if it was not, the token spent, and the audit line.
    """
    with transaction.atomic():
        row = _lock(raw_token, OneTimeToken.PASSWORD_RESET)
        user = row.user
        try:
            validate_password(password, user)
        except DjangoValidationError as error:
            raise PasswordRejected(error) from error
        user.set_password(password)
        verified_now = user.email_verified_at is None
        if verified_now:
            user.email_verified_at = timezone.now()
        user.save(update_fields=["password", "email_verified_at"])
        tokens.revoke_all(user)
        _spend(row)
        AuditEvent.record(AuditEvent.PASSWORD_RESET_COMPLETED, user_id=user.pk)
        if verified_now:
            AuditEvent.record(AuditEvent.EMAIL_VERIFIED, user_id=user.pk)
    return user


def request_email_verification(user: User) -> None:
    """One mail, unless the address is already confirmed or one is waiting."""
    if user.email_verified_at is not None:
        return
    enqueue(user, OneTimeToken.EMAIL_VERIFY)


def confirm_email_verification(raw_token: str) -> User:
    with transaction.atomic():
        row = _lock(raw_token, OneTimeToken.EMAIL_VERIFY)
        user = row.user
        if user.email_verified_at is None:
            user.email_verified_at = timezone.now()
            user.save(update_fields=["email_verified_at"])
        _spend(row)
        AuditEvent.record(AuditEvent.EMAIL_VERIFIED, user_id=user.pk)
    return user
```

- [ ] **Step 4: Groen**

```bash
POSTGRES_HOST=127.0.0.1 POSTGRES_PORT=5433 POSTGRES_DB=ampeer POSTGRES_USER=ampeer POSTGRES_PASSWORD=devtest uv run --no-sync pytest tests/test_accounts_recovery.py tests/test_dpia.py -q
```

Verwacht: alles groen. `test_the_document_names_everything_the_audit_line_carries` blijft groen omdat deze module alleen `user_id` als sleutelwoord schrijft, dat de DPIA al noemt.

- [ ] **Step 5: Toon aan dat drie controles rood kunnen worden**

Drie tijdelijke bewerkingen in `recovery.py`, elk apart, elk met de hand teruggezet, elk met het transcript in het rapport:

1. Haal `.update(superseded_at=now)` weg door de filterregel in `mint` te vervangen door `pass` (laat de `raw =`-regel staan): `test_a_new_token_supersedes_the_older_unspent_one_of_the_same_kind` wordt rood op `superseded_at is not None`.
2. Verplaats `validate_password(password, user)` tot ná `_spend(row)`: `test_the_password_validators_apply_on_a_reset_and_spend_nothing` wordt rood op `row.is_usable`.
3. Vervang `.select_for_update()` door niets: `test_the_token_row_is_locked_before_it_is_read` wordt rood met "no longer locks the token row".

- [ ] **Step 6: mypy en ruff**

```bash
uv run --no-sync mypy --strict backend tests
uv run --no-sync ruff check . && uv run --no-sync ruff format --check .
```

- [ ] **Step 7: Commit**

```bash
git add backend/accounts/recovery.py tests/test_accounts_recovery.py
git commit
```

Boodschap: `feat(accounts): mint, spend and refuse one-time tokens, and say nothing about an address`.

---

### Taak 4: `nl.py`, de labels in `consent-texts/`, de fixture

**Hangt af van:** taak 3.

**Files:**
- Modify: `backend/accounts/nl.py`, `backend/accounts/views.py` (alleen `ConsentTextsView`), `tests/helpers/consent_texts_fixture.py`, `frontend/tests/fixtures/consent-texts.json` (gegenereerd), `tests/test_frontend_contract.py`, `tests/test_accounts_api.py`

**Interfaces:**
- Consumes: `NL`, `CONSENT_TEXT_VERSION`, `Consent.KINDS`.
- Produces: `NL["token_invalid"]`, `NL["CONSENT_LABEL_METER_LINK"]`, `NL["CONSENT_LABEL_LEAD_GENERATION"]`, `NL["MAIL_RESET_SUBJECT"]`, `NL["MAIL_RESET_BODY"]`, `NL["MAIL_VERIFY_SUBJECT"]`, `NL["MAIL_VERIFY_BODY"]` (de twee bodies met `%(link)s`); `GET /api/auth/consent-texts/` met een derde sleutel `labels`; de fixture met dezelfde sleutel.

- [ ] **Step 1: De falende tests**

In `tests/test_accounts_api.py`, na `test_the_me_fixture_has_the_shape_the_view_answers`:

```text
@pytest.mark.django_db
def test_the_consent_texts_carry_their_labels_under_the_same_version(client: Any) -> None:
    """Decision 38 closed: the label a row is shown under travels with the
    sentence it heads, under one version, so a label edit is caught the way
    a text edit already is."""
    response = client.get("/api/auth/consent-texts/")
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"text_version", "texts", "labels"}
    assert sorted(body["labels"]) == sorted(Consent.KINDS)
    assert body["labels"]["METER_LINK"] == NL["CONSENT_LABEL_METER_LINK"]
    assert body["labels"]["LEAD_GENERATION"] == NL["CONSENT_LABEL_LEAD_GENERATION"]
    for label in body["labels"].values():
        assert label and len(label) < 60, "a label is a heading, not a sentence"
```

In `tests/test_frontend_contract.py`, in `test_the_fixture_keys_are_the_consent_kinds`, na de bestaande lus:

```text
    assert sorted(payload["labels"]) == sorted(Consent.KINDS)
    for kind, label in payload["labels"].items():
        assert label.strip(), f"{kind} carries an empty label"
```

- [ ] **Step 2: Zie ze falen**

```bash
POSTGRES_HOST=127.0.0.1 POSTGRES_PORT=5433 POSTGRES_DB=ampeer POSTGRES_USER=ampeer POSTGRES_PASSWORD=devtest uv run --no-sync pytest tests/test_accounts_api.py::test_the_consent_texts_carry_their_labels_under_the_same_version tests/test_frontend_contract.py::test_the_fixture_keys_are_the_consent_kinds -q
```

Verwacht: twee keer rood, de eerste op `set(body) == {...}` en de tweede op `KeyError: 'labels'`.

- [ ] **Step 3: `nl.py`**

Vervang de docstring-alinea die begint met "The consent texts are a third category" door:

```text
The consent texts are a third category, and deliberately so: those are
sentences to a household, so they do use "u". They also carry a version,
because article 7(1) of the GDPR asks to be able to demonstrate what was
agreed to, and a reworded text with no version makes that impossible to
answer afterwards. The two `CONSENT_LABEL_` entries belong to this category
too since 2026-09-06: a label is the heading a row is shown under, it is read
together with its text, and decision 38 records the rule for editing one: a
label may narrow what it says only as far as the text still covers, and it
may never claim less than the row records. Both are under the same version
as the texts, so a label edit bumps it exactly as a text edit does.

A fourth category is the mail. `MAIL_RESET_SUBJECT`, `MAIL_RESET_BODY`,
`MAIL_VERIFY_SUBJECT` and `MAIL_VERIFY_BODY` are letters to a household, so
they address the reader with "u", and they carry no version because nothing
is recorded against them. Plain text with one placeholder, `%(link)s`, that
the sending command fills in. Written without accents on "een uur" and "een
keer", the way the first category writes them, because a mail client shows
plain text as it arrives.
```

Vervang het commentaar boven `CONSENT_TEXT_VERSION` door:

```text
#: Bumped whenever any CONSENT_ text or CONSENT_LABEL_ entry below is
#: reworded, never otherwise. The value is stored on every Consent row, so a
#: bump changes what new rows claim and leaves the old ones pointing at what
#: they actually agreed to. A label counts because label and text are read
#: together and recorded together; see decision 38 in docs/decisions.md.
```

Voeg in `NL` toe, na `"consent_action_unknown"`:

```text
    "token_invalid": "deze link is verlopen of al gebruikt; vraag een nieuwe aan",
```

en na `"CONSENT_LEAD_GENERATION"`:

```text
    "CONSENT_LABEL_METER_LINK": "Kwartiergegevens van uw slimme meter",
    "CONSENT_LABEL_LEAD_GENERATION": "Doorgeven aan een installateur",
    "MAIL_RESET_SUBJECT": "Uw wachtwoord bij Ampeer herstellen",
    "MAIL_RESET_BODY": (
        "U heeft gevraagd om een nieuw wachtwoord voor uw account bij Ampeer.\n"
        "\n"
        "Open deze link om een nieuw wachtwoord te kiezen. De link werkt een uur en kan een keer\n"
        "gebruikt worden:\n"
        "\n"
        "%(link)s\n"
        "\n"
        "Heeft u dit niet gevraagd, dan hoeft u niets te doen. Uw wachtwoord blijft zoals het was.\n"
        "\n"
        "Op dit bericht kunt u niet antwoorden.\n"
    ),
    "MAIL_VERIFY_SUBJECT": "Bevestig uw e-mailadres bij Ampeer",
    "MAIL_VERIFY_BODY": (
        "Met dit e-mailadres is een account bij Ampeer aangemaakt.\n"
        "\n"
        "Open deze link om te bevestigen dat dit adres van u is. De link werkt zeven dagen:\n"
        "\n"
        "%(link)s\n"
        "\n"
        "Heeft u geen account aangemaakt, dan heeft iemand anders uw adres ingevuld. U hoeft niets te\n"
        "doen: zonder bevestiging kan dat account geen slimme meter koppelen.\n"
        "\n"
        "Op dit bericht kunt u niet antwoorden.\n"
    ),
```

Werk de opsomming in de eerste docstring-alinea bij: `token_invalid` hoort bij de eerste categorie, dus voeg het toe aan de zin die met `email_taken` begint, tussen `consent_text_stale` en `throttled`.

- [ ] **Step 4: De view en de generator**

`backend/accounts/views.py`, `ConsentTextsView.get`, het antwoord wordt:

```text
        return Response(
            {
                "text_version": CONSENT_TEXT_VERSION,
                "texts": {kind: NL[f"CONSENT_{kind}"] for kind in sorted(Consent.KINDS)},
                "labels": {kind: NL[f"CONSENT_LABEL_{kind}"] for kind in sorted(Consent.KINDS)},
            }
        )
```

En de docstring van die view: vervang "The keys are `sorted(Consent.KINDS)` and the values are `NL["CONSENT_" + kind]`, literally" door "The keys are `sorted(Consent.KINDS)` under both `texts` and `labels`, and the values are `NL["CONSENT_" + kind]` and `NL["CONSENT_LABEL_" + kind]`, literally".

`tests/helpers/consent_texts_fixture.py`, `build_consent_texts_payload`, het teruggegeven object krijgt dezelfde derde sleutel:

```text
        "labels": {kind: NL[f"CONSENT_LABEL_{kind}"] for kind in sorted(Consent.KINDS)},
```

Genereer de fixture opnieuw:

```bash
uv run --no-sync python tests/helpers/consent_texts_fixture.py
git diff --stat frontend/tests/fixtures/consent-texts.json
```

Verwacht: het bestand groeit met vijf regels en verandert nergens anders.

- [ ] **Step 5: Groen, en de hele accounts-suite**

```bash
POSTGRES_HOST=127.0.0.1 POSTGRES_PORT=5433 POSTGRES_DB=ampeer POSTGRES_USER=ampeer POSTGRES_PASSWORD=devtest uv run --no-sync pytest tests/test_accounts_api.py tests/test_frontend_contract.py tests/test_advise.py -q
```

Verwacht: groen, inclusief `test_the_consent_texts_fixture_is_byte_for_byte_what_the_generator_writes` en `test_no_dutch_text_lives_outside_the_text_module`. De Vitest-suite is hier nog niet aan de beurt: `isConsentTexts` in `accounts.ts` laat een derde sleutel met opzet staan, dus de frontend blijft groen op de nieuwe fixture tot taak 8 hem gaat eisen.

- [ ] **Step 6: Toon aan dat de fixture-pin rood kan worden**

Verander in `frontend/tests/fixtures/consent-texts.json` één letter van een label en draai `tests/test_frontend_contract.py::test_the_consent_texts_fixture_is_byte_for_byte_what_the_generator_writes`: rood. Genereer opnieuw met het commando uit stap 4 en controleer met `git diff` dat het bestand weer is wat het was. Plak.

- [ ] **Step 7: mypy en ruff, dan commit**

```bash
uv run --no-sync mypy --strict backend tests
uv run --no-sync ruff check . && uv run --no-sync ruff format --check .
git add backend/accounts/nl.py backend/accounts/views.py tests/helpers/consent_texts_fixture.py frontend/tests/fixtures/consent-texts.json tests/test_frontend_contract.py tests/test_accounts_api.py
git commit
```

Boodschap: `feat(accounts): the consent labels travel with the texts, and the four mails have their words`.

---

### Taak 5: De vier routes, de serializers, de scope, `me/`

**Hangt af van:** taak 4.

**Files:**
- Modify: `backend/accounts/views.py`, `backend/accounts/urls.py`, `backend/accounts/serializers.py`, `backend/ampeer/settings/base.py`, `frontend/tests/fixtures/me-response.json`, `tests/test_accounts_recovery.py`, `tests/test_accounts_api.py`

**Interfaces:**
- Consumes: alles uit `recovery.py`; `NL["token_invalid"]`; `enforce_csrf`; `_AuthAPIView`.
- Produces: `POST /api/auth/reset/request/` (`auth-reset-request`), `POST /api/auth/reset/confirm/` (`auth-reset-confirm`), `POST /api/auth/verify/request/` (`auth-verify-request`), `POST /api/auth/verify/confirm/` (`auth-verify-confirm`); `me/` met `email_verified_at`; scope `auth-reset` op `10/hour`; `password_error_messages(error: DjangoValidationError) -> list[str]` in `serializers.py`; `ResetRequestSerializer`, `TokenSerializer`, `ResetConfirmSerializer`.

- [ ] **Step 1: De falende tests**

Voeg aan `tests/test_accounts_recovery.py` toe, onder de bestaande tests:

```text
# ---------------------------------------------------------------------------
# The four routes
# ---------------------------------------------------------------------------


class _CsrfHeader(TypedDict):
    HTTP_X_CSRFTOKEN: str


def _csrf(client: Any) -> _CsrfHeader:
    client.get("/api/auth/me/")
    return {"HTTP_X_CSRFTOKEN": client.cookies["csrftoken"].value}


def _register(client: Any, email: str = "iemand@voorbeeld.nl") -> _CsrfHeader:
    headers = _csrf(client)
    response = client.post(
        "/api/auth/register/",
        {
            "email": email,
            "password": TEST_PASSWORD,
            "consent_meter_link": False,
            "consent_lead_generation": False,
            "text_version": CONSENT_TEXT_VERSION,
        },
        content_type="application/json",
        **headers,
    )
    assert response.status_code == 201, response.content
    return headers


@pytest.mark.django_db
def test_a_reset_request_answers_the_same_for_a_known_and_an_unknown_address(
    client: Any,
) -> None:
    """Byte-identical, and nothing logged for the unknown one. Red-proof: make
    ResetRequestView answer 404 when recovery finds no user."""
    _register(client)
    client.post("/api/auth/logout/", content_type="application/json", **_csrf(client))
    lines_before = AuditEvent.objects.count()
    headers = _csrf(client)
    known = client.post(
        "/api/auth/reset/request/",
        {"email": "iemand@voorbeeld.nl"},
        content_type="application/json",
        **headers,
    )
    unknown = client.post(
        "/api/auth/reset/request/",
        {"email": "niemand@voorbeeld.nl"},
        content_type="application/json",
        **headers,
    )
    assert known.status_code == 202 == unknown.status_code
    assert known.content == unknown.content == b"{}"
    assert OutboundMail.objects.filter(kind=OneTimeToken.PASSWORD_RESET).count() == 1
    assert AuditEvent.objects.count() == lines_before + 1


@pytest.mark.django_db
def test_a_reset_request_without_a_valid_address_is_a_400_under_email(client: Any) -> None:
    headers = _csrf(client)
    response = client.post(
        "/api/auth/reset/request/",
        {"email": "geen adres"},
        content_type="application/json",
        **headers,
    )
    assert response.status_code == 400
    assert response.json() == {"email": [NL["email_invalid"]]}


@pytest.mark.django_db
def test_a_reset_confirm_sets_the_password_without_a_session(client: Any) -> None:
    _register(client)
    user = User.objects.get(email="iemand@voorbeeld.nl")
    raw = recovery.mint(user, OneTimeToken.PASSWORD_RESET)
    client.cookies.clear()
    headers = _csrf(client)
    response = client.post(
        "/api/auth/reset/confirm/",
        {"token": raw, "password": OTHER_PASSWORD},
        content_type="application/json",
        **headers,
    )
    assert response.status_code == 204, response.content
    assert "ampeer_access" not in response.cookies
    assert "ampeer_refresh" not in response.cookies
    old = client.post(
        "/api/auth/login/",
        {"email": "iemand@voorbeeld.nl", "password": TEST_PASSWORD},
        content_type="application/json",
        **headers,
    )
    assert old.status_code == 401
    new = client.post(
        "/api/auth/login/",
        {"email": "iemand@voorbeeld.nl", "password": OTHER_PASSWORD},
        content_type="application/json",
        **headers,
    )
    assert new.status_code == 200, new.content


@pytest.mark.django_db
@pytest.mark.parametrize("token", ["dit-bestaat-niet", ""])
def test_a_bad_token_is_one_sentence_under_token(client: Any, token: str) -> None:
    headers = _csrf(client)
    response = client.post(
        "/api/auth/reset/confirm/",
        {"token": token, "password": OTHER_PASSWORD},
        content_type="application/json",
        **headers,
    )
    assert response.status_code == 400
    assert response.json() == {"token": [NL["token_invalid"]]}


@pytest.mark.django_db
def test_a_rejected_password_on_reset_reads_like_registration(client: Any) -> None:
    _register(client)
    user = User.objects.get(email="iemand@voorbeeld.nl")
    raw = recovery.mint(user, OneTimeToken.PASSWORD_RESET)
    headers = _csrf(client)
    response = client.post(
        "/api/auth/reset/confirm/",
        {"token": raw, "password": "kort"},
        content_type="application/json",
        **headers,
    )
    assert response.status_code == 400
    assert response.json()["password"][0] == NL["password_too_short"] % {"min_length": 12}
    assert OneTimeToken.objects.get(token_sha256=token_digest(raw)).is_usable


@pytest.mark.django_db
def test_a_verification_confirm_answers_204_and_me_carries_the_timestamp(client: Any) -> None:
    headers = _register(client)
    user = User.objects.get(email="iemand@voorbeeld.nl")
    raw = recovery.mint(user, OneTimeToken.EMAIL_VERIFY)
    before = client.get("/api/auth/me/").json()
    assert before["email_verified_at"] is None
    response = client.post(
        "/api/auth/verify/confirm/", {"token": raw}, content_type="application/json", **headers
    )
    assert response.status_code == 204
    after = client.get("/api/auth/me/").json()
    assert isinstance(after["email_verified_at"], str)
    again = client.post(
        "/api/auth/verify/confirm/", {"token": raw}, content_type="application/json", **headers
    )
    assert again.status_code == 400
    assert again.json() == {"token": [NL["token_invalid"]]}


@pytest.mark.django_db
def test_registration_enqueues_a_verification_mail(client: Any) -> None:
    _register(client)
    user = User.objects.get(email="iemand@voorbeeld.nl")
    assert OutboundMail.objects.filter(user=user, kind=OneTimeToken.EMAIL_VERIFY).count() == 1


@pytest.mark.django_db
def test_resending_a_verification_requires_a_session_and_dedupes(client: Any) -> None:
    stranger = client.post("/api/auth/verify/request/", content_type="application/json", **_csrf(client))
    assert stranger.status_code == 401
    headers = _register(client)
    first = client.post("/api/auth/verify/request/", content_type="application/json", **headers)
    second = client.post("/api/auth/verify/request/", content_type="application/json", **headers)
    assert first.status_code == 202 == second.status_code
    assert first.content == b"{}"
    assert OutboundMail.objects.filter(kind=OneTimeToken.EMAIL_VERIFY).count() == 1


@pytest.mark.django_db
def test_the_public_recovery_routes_refuse_a_post_without_the_csrf_header(client: Any) -> None:
    from rest_framework.test import APIClient

    strict = APIClient(enforce_csrf_checks=True)
    strict.get("/api/auth/me/")
    for path, body in (
        ("/api/auth/reset/request/", {"email": "iemand@voorbeeld.nl"}),
        ("/api/auth/reset/confirm/", {"token": "x", "password": OTHER_PASSWORD}),
        ("/api/auth/verify/confirm/", {"token": "x"}),
    ):
        response = strict.post(path, body, format="json")
        assert response.status_code == 403, (path, response.content)


@pytest.mark.django_db
def test_the_thirteen_routes_each_carry_a_scope_with_a_rate() -> None:
    """Spec 3.5, beside tests/test_backend_settings.py's resolver walk: the
    four new views name `auth-reset` or `auth-write`, and nginx's ceiling
    still clears the summed per-visitor rate by fifty times."""
    from django.conf import settings

    from accounts import urls, views

    assert len(urls.urlpatterns) == 13
    rates = settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]
    assert rates["auth-reset"] == "10/hour"
    assert views.ResetRequestView.throttle_scope == "auth-reset"
    assert views.ResetConfirmView.throttle_scope == "auth-reset"
    assert views.VerifyConfirmView.throttle_scope == "auth-reset"
    assert views.VerifyRequestView.throttle_scope == "auth-write"
    per_hour = sum(int(rate.split("/")[0]) for rate in rates.values())
    assert per_hour == 490
    assert 10.0 >= 50 * (per_hour / 3600)
```

Twee imports horen bovenaan het bestand bij de andere, niet halverwege, anders is het een `E402` voor ruff: voeg `from typing import Any, TypedDict` toe bij de standaardbibliotheek en `from accounts.nl import CONSENT_TEXT_VERSION, NL` bij de `accounts`-imports. `OTHER_PASSWORD` bestaat in `tests/helpers/accounts.py` sinds de backend-cyclus; het is het tweede vaste wachtwoord van de suite.

- [ ] **Step 2: Zie ze falen**

```bash
POSTGRES_HOST=127.0.0.1 POSTGRES_PORT=5433 POSTGRES_DB=ampeer POSTGRES_USER=ampeer POSTGRES_PASSWORD=devtest uv run --no-sync pytest tests/test_accounts_recovery.py -q
```

Verwacht: de routetests rood op 404 (de paden bestaan niet), `test_the_thirteen_routes_each_carry_a_scope_with_a_rate` rood op `len(urls.urlpatterns) == 13`, en `test_a_verification_confirm_answers_204_and_me_carries_the_timestamp` rood op `KeyError: 'email_verified_at'`.

- [ ] **Step 3: De serializers**

In `backend/accounts/serializers.py`: voeg boven `class LoginSerializer` toe:

```text
def password_error_messages(error: DjangoValidationError) -> list[str]:
    """Django's validator messages, with the one that its Dutch catalogue
    cannot translate corrected by hand.

    Lifted out of `RegisterSerializer.validate_password` so the reset route
    translates a refusal with the same words as registration: two copies of
    this mapping would be two places the sentence can drift. The reason the
    mapping exists at all is in that method's docstring.
    """
    messages: list[str] = []
    for sub_error in error.error_list:
        if sub_error.code == "password_too_short" and sub_error.params:
            messages.append(NL["password_too_short"] % sub_error.params)
        else:
            messages.extend(sub_error.messages)
    return messages
```

Vervang in `RegisterSerializer.validate_password` het `except`-blok door:

```text
        except DjangoValidationError as error:
            raise serializers.ValidationError(password_error_messages(error)) from error
```

De docstring van die methode blijft staan; voeg er één zin aan toe: "The mapping itself lives in `password_error_messages` above, because `ResetConfirmView` needs the same words."

Voeg onderaan het bestand toe:

```text
class ResetRequestSerializer(serializers.Serializer[dict[str, Any]]):
    """One field, and the view answers the same whatever it is."""

    email = serializers.EmailField(error_messages={"invalid": NL["email_invalid"]})


class TokenSerializer(serializers.Serializer[dict[str, Any]]):
    """The token off a link. A missing or empty one reads as an invalid one:
    the difference between "you sent nothing" and "you sent something old" is
    a difference only somebody probing the route would learn from."""

    token = serializers.CharField(
        trim_whitespace=False,
        error_messages={
            "required": NL["token_invalid"],
            "blank": NL["token_invalid"],
            "null": NL["token_invalid"],
        },
    )


class ResetConfirmSerializer(TokenSerializer):
    #: Not validated here: the validators need the user, and the user is
    #: only known once the token has been looked up under its lock. See
    #: recovery.confirm_password_reset.
    password = serializers.CharField(
        write_only=True, trim_whitespace=False, error_messages={"required": NL["password_required"]}
    )
```

- [ ] **Step 4: De views**

In `backend/accounts/views.py`: vervang de eerste regel van de moduledocstring, "The account routes. Nine of them, and only `get` and `post` among them.", door "The account routes. Thirteen of them, and only `get` and `post` among them." Werk de imports bij:

```text
from rest_framework.exceptions import (
    AuthenticationFailed,
    NotAuthenticated,
    PermissionDenied,
    Throttled,
    ValidationError,
)

from accounts import cookies, recovery, service, tokens
from accounts.serializers import (
    ConsentSerializer,
    LoginSerializer,
    RegisterSerializer,
    ResetConfirmSerializer,
    ResetRequestSerializer,
    TokenSerializer,
    password_error_messages,
)
```

In `RegisterView.post`, direct na `AuditEvent.record(AuditEvent.ACCOUNT_CREATED, user_id=user.pk)`:

```text
        # One mail per new account, within the minute: an outbox row, no
        # network here. Spec 3.4.
        recovery.request_email_verification(user)
```

In `MeView.get`, het antwoord krijgt een derde sleutel:

```text
                "email_verified_at": (
                    None
                    if self.user.email_verified_at is None
                    else self.user.email_verified_at.isoformat()
                ),
```

Voeg na `DeleteView` toe:

```text
class ResetRequestView(_AuthAPIView):
    """Ask for a reset link, and learn nothing from the answer.

    202 with an empty object for every well-formed address, known or not,
    active or not: a 202 and a 404 would be an address book that can be read
    at ten requests an hour. No mail leaves in this request and no token is
    minted; a known address costs one INSERT more than an unknown one, which
    is under the noise of a database round trip.
    """

    authentication_classes: Sequence[type[BaseAuthentication]] = ()
    permission_classes: Sequence[type[BasePermission]] = (AllowAny,)
    throttle_scope = "auth-reset"

    def post(self, request: Request) -> Response:
        enforce_csrf(request)
        serializer = ResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        recovery.request_password_reset(serializer.validated_data["email"])
        return Response({}, status=status.HTTP_202_ACCEPTED)


class ResetConfirmView(_AuthAPIView):
    """Set a new password with a link, and do not sign in.

    Token first, then the password: a bad token is one sentence under
    `token` for expired, spent, superseded and unknown alike, and a rejected
    password is the same list of sentences registration gives. 204 without
    cookies on purpose: `login/` stays the only place a session starts and
    `LOGIN_SUCCEEDED` is written, so the DPIA's sentence that every sign-in
    is a line stays true. Axes plays no part here, since nothing goes
    through `authenticate()`; the token's 256 bits and `auth-reset` do.
    """

    authentication_classes: Sequence[type[BaseAuthentication]] = ()
    permission_classes: Sequence[type[BasePermission]] = (AllowAny,)
    throttle_scope = "auth-reset"

    def post(self, request: Request) -> Response:
        enforce_csrf(request)
        serializer = ResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            recovery.confirm_password_reset(
                serializer.validated_data["token"], serializer.validated_data["password"]
            )
        except recovery.TokenInvalid as error:
            raise ValidationError({"token": [NL["token_invalid"]]}) from error
        except recovery.PasswordRejected as rejected:
            raise ValidationError(
                {"password": password_error_messages(rejected.error)}
            ) from rejected
        return Response(status=status.HTTP_204_NO_CONTENT)


class VerifyRequestView(_AuthAPIView):
    """Send the confirmation mail again. The one recovery route that needs a
    session, and therefore the one that needs no body. 202 whether or not a
    mail is written: an address already confirmed answers the same, because
    `me/` already says so and a 400 would be a second way to read it."""

    throttle_scope = "auth-write"

    def post(self, request: Request) -> Response:
        recovery.request_email_verification(self.user)
        return Response({}, status=status.HTTP_202_ACCEPTED)


class VerifyConfirmView(_AuthAPIView):
    """Confirm an address with a link. Public, because the link is opened on
    whatever device the mail was read on, and a 401 would send a household
    to a sign-in form to prove what the link already proves."""

    authentication_classes: Sequence[type[BaseAuthentication]] = ()
    permission_classes: Sequence[type[BasePermission]] = (AllowAny,)
    throttle_scope = "auth-reset"

    def post(self, request: Request) -> Response:
        enforce_csrf(request)
        serializer = TokenSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            recovery.confirm_email_verification(serializer.validated_data["token"])
        except recovery.TokenInvalid as error:
            raise ValidationError({"token": [NL["token_invalid"]]}) from error
        return Response(status=status.HTTP_204_NO_CONTENT)
```

- [ ] **Step 5: De paden en de scope**

`backend/accounts/urls.py`: voeg de vier views aan de import toe en de vier paden na `delete/`:

```text
    path("reset/request/", ResetRequestView.as_view(), name="auth-reset-request"),
    path("reset/confirm/", ResetConfirmView.as_view(), name="auth-reset-confirm"),
    path("verify/request/", VerifyRequestView.as_view(), name="auth-verify-request"),
    path("verify/confirm/", VerifyConfirmView.as_view(), name="auth-verify-confirm"),
```

`backend/ampeer/settings/base.py`, in `DEFAULT_THROTTLE_RATES`, na `"auth-export"`:

```text
        # A reset link tried at most as often as a password: the same ten as
        # auth-login, for reset/request/, reset/confirm/ and verify/confirm/.
        # Decision 33's sum moves from 480 to 490 an hour, which 10 r/s still
        # clears 73 times; tests/test_nginx_config.py re-runs that arithmetic.
        "auth-reset": "10/hour",
```

- [ ] **Step 6: De fixture**

`frontend/tests/fixtures/me-response.json` wordt:

```json
{
  "email": "iemand@voorbeeld.nl",
  "consents": {
    "LEAD_GENERATION": false,
    "METER_LINK": true
  },
  "email_verified_at": null
}
```

Met een afsluitende regeleinde en zonder BOM; `test_the_me_fixture_has_the_shape_the_view_answers` vergelijkt de vorm en niet de bytes, dus alleen de sleutels tellen.

- [ ] **Step 7: Groen**

```bash
POSTGRES_HOST=127.0.0.1 POSTGRES_PORT=5433 POSTGRES_DB=ampeer POSTGRES_USER=ampeer POSTGRES_PASSWORD=devtest uv run --no-sync pytest tests/test_accounts_recovery.py tests/test_accounts_api.py tests/test_backend_settings.py tests/test_nginx_config.py tests/test_frontend_contract.py tests/test_dpia.py -q
```

Verwacht: alles groen. `test_every_public_route_is_rate_limited` ziet dertien routes met een scope; `test_something_ahead_of_django_limits_the_rate` rekent 490 na; `test_the_api_answers_only_the_verbs_the_document_describes` ziet alleen `post` bij de vier nieuwe views; `test_every_path_the_frontend_calls_is_one_the_backend_serves[accounts]` blijft groen omdat `accounts.ts` nog negen paden noemt en die alle negen bestaan.

- [ ] **Step 8: Toon aan dat de enumeratietest rood kan worden**

Laat `ResetRequestView.post` tijdelijk `Response({}, status=404)` antwoorden als `User.objects.filter(email=...).exists()` vals is (drie regels voor de aanroep van `recovery`), en draai `test_a_reset_request_answers_the_same_for_a_known_and_an_unknown_address`: rood op `202 == 404`. Zet terug. Haal daarna `recovery.request_email_verification(user)` tijdelijk uit `RegisterView.post`: `test_registration_enqueues_a_verification_mail` rood. Zet terug. Plak beide.

- [ ] **Step 9: mypy en ruff, dan commit**

```bash
uv run --no-sync mypy --strict backend tests
uv run --no-sync ruff check . && uv run --no-sync ruff format --check .
git add backend/accounts/views.py backend/accounts/urls.py backend/accounts/serializers.py backend/ampeer/settings/base.py frontend/tests/fixtures/me-response.json tests/test_accounts_recovery.py tests/test_accounts_api.py
git commit
```

Boodschap: `feat(accounts): four routes to reset a password and confirm an address, and me/ says when`.

---

### Taak 6: `mailer.py`, de drie transporten, de grenstest, de omgeving

**Hangt af van:** taak 5.

**Files:**
- Create: `backend/accounts/mailer.py`, `tests/test_accounts_mail.py`
- Modify: `backend/ampeer/settings/base.py`, `backend/ampeer/settings/dev.py`, `backend/ampeer/settings/prod.py`, `tests/test_boundaries.py`, `tests/test_infra.py`, `tests/test_deploy_workflow.py`, `tests/test_backend_settings.py`, `scripts/preflight_env.sh`, `infra/docker-compose.yml`, `infra/.env.example`, `.github/workflows/deploy.yml`

**Interfaces:**
- Consumes: `requests` (al in `uv.lock`); `settings`.
- Produces: `mailer.RESEND_ENDPOINT`, `mailer.TIMEOUT_SECONDS`, `mailer.Message(to, subject, text, idempotency_key)`, `mailer.TransportError(status)`, `mailer.Transport` (protocol met `send(message) -> str`), `mailer.ResendTransport`, `mailer.FileTransport`, `mailer.MemoryTransport` met `sent: list[Message]`, `mailer.transport() -> Transport`; de settings `AMPEER_MAIL_TRANSPORT`, `AMPEER_MAIL_FROM`, `AMPEER_SITE_ORIGIN`, `AMPEER_MAIL_FILE_DIR`, `RESEND_API_KEY`; de vier namen in `.env.example`, compose, de preflight en `REQUIRED_ENV`.

- [ ] **Step 1: De falende tests voor de module**

`tests/test_accounts_mail.py`, compleet; taak 7 voegt er de commandtests aan toe:

```text
"""The one module that reaches api.resend.com, and the two that do not.

`requests.post` is patched at the call, never the network: what is asserted
is the exact request the transport builds, which is the whole of what a
reviewer can check about an outbound call without a key.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest import mock

import pytest
import requests
from django.test import override_settings

from accounts import mailer

MESSAGE = mailer.Message(
    to="iemand@voorbeeld.nl",
    subject="Onderwerp",
    text="Tekst met een link.\n",
    idempotency_key="outbox-7",
)


def _answer(status: int, body: dict[str, Any] | None = None) -> mock.Mock:
    response = mock.Mock()
    response.status_code = status
    response.json.return_value = {} if body is None else body
    return response


def test_the_mailer_posts_one_literal_url_with_the_bearer_the_key_and_the_timeout() -> None:
    transport = mailer.ResendTransport(api_key="sleutel", sender="noreply@ampeer.nl")
    with mock.patch.object(requests, "post", return_value=_answer(200, {"id": "abc"})) as post:
        provider_id = transport.send(MESSAGE)
    assert provider_id == "abc"
    post.assert_called_once()
    args, kwargs = post.call_args
    assert args == (mailer.RESEND_ENDPOINT,)
    assert mailer.RESEND_ENDPOINT == "https://api.resend.com/emails"
    assert kwargs["timeout"] == mailer.TIMEOUT_SECONDS == 10
    assert kwargs["headers"] == {
        "Authorization": "Bearer sleutel",
        "Idempotency-Key": "outbox-7",
    }
    assert kwargs["json"] == {
        "from": "noreply@ampeer.nl",
        "to": ["iemand@voorbeeld.nl"],
        "subject": "Onderwerp",
        "text": "Tekst met een link.\n",
    }


@pytest.mark.parametrize("status", [429, 500, 401])
def test_a_refused_answer_is_a_transport_error_carrying_the_status(status: int) -> None:
    transport = mailer.ResendTransport(api_key="sleutel", sender="noreply@ampeer.nl")
    with (
        mock.patch.object(requests, "post", return_value=_answer(status)),
        pytest.raises(mailer.TransportError) as caught,
    ):
        transport.send(MESSAGE)
    assert caught.value.status == status


def test_no_answer_at_all_is_a_transport_error_with_status_zero() -> None:
    transport = mailer.ResendTransport(api_key="sleutel", sender="noreply@ampeer.nl")
    with (
        mock.patch.object(requests, "post", side_effect=requests.ConnectionError("down")),
        pytest.raises(mailer.TransportError) as caught,
    ):
        transport.send(MESSAGE)
    assert caught.value.status == 0


def test_a_success_without_an_id_is_refused_rather_than_logged_as_sent() -> None:
    """Resend answers `{"id": ...}` on 200. A 200 without it is not a delivery
    this command can point at afterwards, so it is not a delivery."""
    transport = mailer.ResendTransport(api_key="sleutel", sender="noreply@ampeer.nl")
    with (
        mock.patch.object(requests, "post", return_value=_answer(200, {})),
        pytest.raises(mailer.TransportError) as caught,
    ):
        transport.send(MESSAGE)
    assert caught.value.status == 200


def test_the_file_transport_writes_one_readable_file_per_message(tmp_path: Path) -> None:
    transport = mailer.FileTransport(tmp_path / "mail")
    provider_id = transport.send(MESSAGE)
    assert provider_id == "file-outbox-7"
    written = (tmp_path / "mail" / "outbox-7.txt").read_text(encoding="utf-8")
    assert written == "To: iemand@voorbeeld.nl\nSubject: Onderwerp\n\nTekst met een link.\n"


def test_the_memory_transport_keeps_what_it_was_handed() -> None:
    transport = mailer.MemoryTransport()
    assert transport.send(MESSAGE) == "memory-outbox-7"
    assert transport.sent == [MESSAGE]


@pytest.mark.parametrize(
    ("name", "expected"),
    [("resend", mailer.ResendTransport), ("file", mailer.FileTransport), ("memory", mailer.MemoryTransport)],
)
def test_the_setting_chooses_the_transport(name: str, expected: type[object]) -> None:
    with override_settings(
        AMPEER_MAIL_TRANSPORT=name, RESEND_API_KEY="sleutel", AMPEER_MAIL_FILE_DIR="/tmp/mail"
    ):
        assert isinstance(mailer.transport(), expected)


def test_an_unknown_transport_name_is_refused() -> None:
    with override_settings(AMPEER_MAIL_TRANSPORT="smtp"), pytest.raises(RuntimeError, match="smtp"):
        mailer.transport()


def test_the_test_suite_runs_on_the_memory_transport() -> None:
    """The suite never reaches the network, and this is the line that says so."""
    from django.conf import settings

    assert settings.AMPEER_MAIL_TRANSPORT == "memory"


def test_prod_settings_refuse_the_memory_transport(monkeypatch: pytest.MonkeyPatch) -> None:
    """A container on the memory transport would report every mail as sent
    and deliver none. prod.py refuses to import under it."""
    import importlib
    import sys

    for name in (
        "DJANGO_SECRET_KEY",
        "DJANGO_ALLOWED_HOSTS",
        "DJANGO_CORS_ALLOWED_ORIGINS",
        "AMPEER_NEDU_PROFILE_PATH",
        "POSTGRES_DB",
        "POSTGRES_USER",
        "POSTGRES_PASSWORD",
        "POSTGRES_HOST",
        "AMPEER_MAIL_FROM",
        "AMPEER_SITE_ORIGIN",
    ):
        monkeypatch.setenv(name, "set")
    monkeypatch.setenv("DJANGO_NUM_PROXIES", "2")
    monkeypatch.setenv("AMPEER_MAIL_TRANSPORT", "memory")
    sys.modules.pop("ampeer.settings.prod", None)
    with pytest.raises(RuntimeError, match="memory"):
        importlib.import_module("ampeer.settings.prod")
    sys.modules.pop("ampeer.settings.prod", None)


def test_prod_settings_require_the_key_only_on_resend(monkeypatch: pytest.MonkeyPatch) -> None:
    import importlib
    import sys

    for name in (
        "DJANGO_SECRET_KEY",
        "DJANGO_ALLOWED_HOSTS",
        "DJANGO_CORS_ALLOWED_ORIGINS",
        "AMPEER_NEDU_PROFILE_PATH",
        "POSTGRES_DB",
        "POSTGRES_USER",
        "POSTGRES_PASSWORD",
        "POSTGRES_HOST",
        "AMPEER_MAIL_FROM",
        "AMPEER_SITE_ORIGIN",
    ):
        monkeypatch.setenv(name, "set")
    monkeypatch.setenv("DJANGO_NUM_PROXIES", "2")
    monkeypatch.delenv("RESEND_API_KEY", raising=False)
    monkeypatch.setenv("AMPEER_MAIL_TRANSPORT", "resend")
    sys.modules.pop("ampeer.settings.prod", None)
    with pytest.raises(RuntimeError, match="RESEND_API_KEY"):
        importlib.import_module("ampeer.settings.prod")
    monkeypatch.setenv("AMPEER_MAIL_TRANSPORT", "file")
    sys.modules.pop("ampeer.settings.prod", None)
    module = importlib.import_module("ampeer.settings.prod")
    assert module.AMPEER_MAIL_TRANSPORT == "file"
    assert module.AMPEER_MAIL_FILE_DIR == "/srv/mail"
    sys.modules.pop("ampeer.settings.prod", None)
```

`tests/test_backend_settings.py` heeft al een test die `prod.py` onder een nagebootste omgeving importeert; lees die eerst en gebruik dezelfde opzet als hij iets anders doet dan `importlib` en `sys.modules.pop`, zodat twee tests hetzelfde bestand niet op twee manieren laden.

- [ ] **Step 2: Zie ze falen**

```bash
POSTGRES_HOST=127.0.0.1 POSTGRES_PORT=5433 POSTGRES_DB=ampeer POSTGRES_USER=ampeer POSTGRES_PASSWORD=devtest uv run --no-sync pytest tests/test_accounts_mail.py -q
```

Verwacht: `ImportError` op `accounts.mailer`.

- [ ] **Step 3: De module**

`backend/accounts/mailer.py`, compleet:

```text
"""The one module under backend/ that reaches outside this machine, and where.

Resend is one endpoint with four fields, so it is spoken to with `requests`
and not with its SDK: the SDK would open connections from a package
tests/test_boundaries.py never reads. The destination is a literal on the
line where a reviewer sees it, the client is the one that test allows, and
the same test now holds this file to the rule pvgis.py has always been held
to, that a URL is named and never assembled.

Three transports, one interface. `resend` is production, `file` is the local
stack and a developer machine, `memory` is the test suite. prod.py refuses
`memory`, and scripts/preflight_env.sh refuses anything but `resend` on a
host, so the two that deliver nothing can never be the one a household's
mail depends on.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Final, Protocol

import requests
from django.conf import settings

#: The destination, on the allowlist in tests/test_boundaries.py.
RESEND_ENDPOINT: Final = "https://api.resend.com/emails"
#: Seconds. The command runs every minute; a send that takes longer than
#: this is a send that is retried, not waited for.
TIMEOUT_SECONDS: Final = 10


@dataclass(frozen=True)
class Message:
    """One mail, fully composed. Never stored: it exists between the command
    building it and the transport accepting it."""

    to: str
    subject: str
    text: str
    #: `outbox-<id>`. Resend keeps it 24 hours, so a retry after a timeout is
    #: not a second mail. The outbox id is never reused.
    idempotency_key: str


class TransportError(Exception):
    """The transport did not accept the message. `status` is the HTTP status
    it answered, 0 when it answered nothing at all."""

    def __init__(self, status: int) -> None:
        super().__init__(f"the mail transport answered {status}")
        self.status = status


class Transport(Protocol):
    def send(self, message: Message) -> str:
        """Deliver, and return the provider's id for it. Raise TransportError otherwise."""


class ResendTransport:
    def __init__(self, api_key: str, sender: str) -> None:
        self._api_key = api_key
        self._sender = sender

    def send(self, message: Message) -> str:
        try:
            response = requests.post(
                RESEND_ENDPOINT,
                json={
                    "from": self._sender,
                    "to": [message.to],
                    "subject": message.subject,
                    "text": message.text,
                },
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Idempotency-Key": message.idempotency_key,
                },
                timeout=TIMEOUT_SECONDS,
            )
        except requests.RequestException as error:
            raise TransportError(0) from error
        if response.status_code != 200:
            raise TransportError(response.status_code)
        body = response.json()
        provider_id = body.get("id") if isinstance(body, dict) else None
        if not isinstance(provider_id, str) or not provider_id:
            # A 200 that names no delivery is not a delivery this command
            # can point at in MAIL_SENT, so it is not one.
            raise TransportError(response.status_code)
        return provider_id


class FileTransport:
    """One text file per message, for the local stack and a developer machine.

    tests/test_stack_smoke.py reads the link out of that file, which is how
    the live checks close the loop without a key and without Resend.
    """

    def __init__(self, directory: Path) -> None:
        self._directory = directory

    def send(self, message: Message) -> str:
        self._directory.mkdir(parents=True, exist_ok=True)
        path = self._directory / f"{message.idempotency_key}.txt"
        path.write_text(
            f"To: {message.to}\nSubject: {message.subject}\n\n{message.text}",
            encoding="utf-8",
        )
        return f"file-{message.idempotency_key}"


class MemoryTransport:
    """The test suite's. Keeps every message so a test can read it back."""

    def __init__(self) -> None:
        self.sent: list[Message] = []

    def send(self, message: Message) -> str:
        self.sent.append(message)
        return f"memory-{message.idempotency_key}"


#: One instance for the whole process, so a test that reads `mailer.MEMORY.sent`
#: sees what the command handed to `mailer.transport()`.
MEMORY = MemoryTransport()


def transport() -> Transport:
    """The transport `AMPEER_MAIL_TRANSPORT` names. Anything else is a refusal,
    not a fallback: a fallback here would be the silent failure prod.py exists
    to prevent."""
    name = settings.AMPEER_MAIL_TRANSPORT
    if name == "resend":
        return ResendTransport(settings.RESEND_API_KEY, settings.AMPEER_MAIL_FROM)
    if name == "file":
        return FileTransport(Path(settings.AMPEER_MAIL_FILE_DIR))
    if name == "memory":
        return MEMORY
    raise RuntimeError(f"AMPEER_MAIL_TRANSPORT is {name!r}; it must be resend, file or memory")
```

- [ ] **Step 4: De instellingen**

`backend/ampeer/settings/base.py`, onder `AMPEER_ADVICE_TTL_DAYS`:

```text
#: How a mail leaves, and from whom. Base is the test suite's answer: the
#: memory transport delivers nothing and the suite never touches the network.
#: dev.py writes files; prod.py reads all of these from the environment and
#: refuses `memory`. See accounts/mailer.py.
AMPEER_MAIL_TRANSPORT = "memory"
AMPEER_MAIL_FROM = "noreply@ampeer.test.invalid"
#: Where the links in a mail point. The page reads the token off the fragment
#: of this origin's /account/ route, so it has to be the origin a household
#: sees and not the API's.
AMPEER_SITE_ORIGIN = "http://127.0.0.1:3000"
#: The file transport's directory. A property of the process, not of the
#: host, so it is not in the env file: prod.py fixes it to /srv/mail and
#: infra/compose.test.yml mounts the fixture directory there.
AMPEER_MAIL_FILE_DIR = str(BASE_DIR.parent / "data" / "mail")
#: Empty everywhere but production. Never a default with a value.
RESEND_API_KEY = ""
```

`backend/ampeer/settings/dev.py`, onderaan:

```text
# A developer reads the mail as a file under data/mail/, which .gitignore
# already keeps out of the tree along with the rest of data/.
AMPEER_MAIL_TRANSPORT = "file"
```

`backend/ampeer/settings/prod.py`, onder `AMPEER_NEDU_PROFILE_PATH = _required(...)`:

```text
# How the mail leaves. `resend` on a host; `file` only for the local stack,
# which runs under these settings so the live checks read a real deployment
# and not a rehearsal of one. `memory` is refused: a container on it would
# report every mail as sent and deliver none. scripts/preflight_env.sh
# refuses `file` on a host for the same reason, before a container starts.
AMPEER_MAIL_TRANSPORT = _required("AMPEER_MAIL_TRANSPORT")
if AMPEER_MAIL_TRANSPORT not in {"resend", "file"}:
    raise RuntimeError(
        f"AMPEER_MAIL_TRANSPORT is {AMPEER_MAIL_TRANSPORT!r}; a deployment sends through "
        "resend or, on the local stack only, writes files"
    )
AMPEER_MAIL_FROM = _required("AMPEER_MAIL_FROM")
AMPEER_SITE_ORIGIN = _required("AMPEER_SITE_ORIGIN")
RESEND_API_KEY = _required("RESEND_API_KEY") if AMPEER_MAIL_TRANSPORT == "resend" else ""
AMPEER_MAIL_FILE_DIR = "/srv/mail"
```

- [ ] **Step 5: De grenstest**

`tests/test_boundaries.py`, vier wijzigingen:

1. `_imported_module_names` levert ook de gepunte naam. Vervang de functie door:

```text
def _imported_module_names(path: pathlib.Path) -> set[str]:
    """Both the top-level name and the full dotted name of every import.

    The full name is what lets `django.core.mail` be forbidden below: until
    2026-09-06 only the first segment was kept, so Django's own mail API,
    which imports smtplib inside .venv where this scan never walks, was
    invisible to a rule written to be categorical.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name)
                names.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names.add(node.module)
            names.add(node.module.split(".")[0])
            # `from django.core import mail` names the same module.
            names.update(f"{node.module}.{alias.name}" for alias in node.names)
    return names
```

2. `NETWORK_CLIENTS` krijgt `"django.core.mail",` erbij, met erboven het commentaar:

```text
#: Django's own mail API, by its dotted name: `from django.core.mail import
#: send_mail` opens an SMTP connection from inside .venv, where this scan
#: never walks. This project sends through accounts/mailer.py and nothing
#: else, so the framework's own channel is forbidden outright.
```

3. `OUTBOUND_MODULES` krijgt een derde regel, en het commentaar erboven wordt herschreven. Vervang de twee commentaarblokken boven `OUTBOUND_MODULES` (vanaf "The only module allowed to reach outside" tot en met "is Stijn's line to move, not mine.") door:

```text
#: Every module allowed to open an outbound connection, and where each may go.
#:
#: Three. pvgis.py is reached by a web request; ingest_profiles.py is a build
#: time command somebody runs by hand; mailer.py runs under a systemd timer
#: and reaches the mail provider, which is the only destination a household's
#: data ever travels to from this machine. The allowlist is one constant in
#: one module rather than a settings entry, because a configuration layer
#: that exactly one caller reads is a layer that hides where the value comes
#: from. CLAUDE.md names these same destinations since 2026-09-06; before
#: that it named three sources of which one was never reached, and the gap
#: is recorded as answered in docs/decisions.md.
```

en de mapping:

```text
OUTBOUND_MODULES: dict[str, frozenset[str]] = {
    "ampeer_sim/production/pvgis.py": frozenset({"re.jrc.ec.europa.eu"}),
    "tools/ingest_profiles.py": frozenset({"energiedatawijzer.nl"}),
    "backend/accounts/mailer.py": frozenset({"api.resend.com"}),
}
```

4. `STRICT_DESTINATION_MODULE` wordt een tuple en de test parametriseert erover. Vervang de constante en haar commentaar door:

```text
#: The modules whose destination must be a bare constant at the call site.
#:
#: Two, and both are reached from a process nobody watches: pvgis.py by a web
#: request, mailer.py by a timer. ingest_profiles.py hands its URL down
#: through two functions before requests sees it, which the check below
#: cannot follow, so that file is held to a different and separately stated
#: argument.
STRICT_DESTINATION_MODULES = ("ampeer_sim/production/pvgis.py", "backend/accounts/mailer.py")
```

en de kop van de test:

```text
@pytest.mark.parametrize("module", STRICT_DESTINATION_MODULES)
def test_the_module_that_speaks_http_never_assembles_its_url(module: str) -> None:
```

met `import pytest` bij de imports en de regel `module = STRICT_DESTINATION_MODULE` uit het lichaam verwijderd. De docstring blijft; voeg één zin toe: "Since 2026-09-06 the same three checks run over accounts/mailer.py."

- [ ] **Step 6: De omgeving**

`infra/.env.example`, na `POSTGRES_HOST=` en voor de regel over `AMPEER_VERSION`:

```text
# How the mail leaves. `resend` on a host; scripts/preflight_env.sh refuses
# anything else here, because `file` writes every mail to disk and delivers
# none. The other two are the sender a household sees and the origin the
# links in a mail point at, for example noreply@ampeer.nl and
# https://ampeer.nl.
AMPEER_MAIL_TRANSPORT=
RESEND_API_KEY=
AMPEER_MAIL_FROM=
AMPEER_SITE_ORIGIN=
```

Vervang in de kop van dat bestand "the first nine" door "the first thirteen".

`infra/docker-compose.yml`, in `services.api.environment`, na `POSTGRES_HOST`:

```text
      AMPEER_MAIL_TRANSPORT: ${AMPEER_MAIL_TRANSPORT}
      RESEND_API_KEY: ${RESEND_API_KEY}
      AMPEER_MAIL_FROM: ${AMPEER_MAIL_FROM}
      AMPEER_SITE_ORIGIN: ${AMPEER_SITE_ORIGIN}
```

`tests/test_infra.py`, `REQUIRED_ENV`: de vier namen erbij, na `"POSTGRES_HOST",`, in deze volgorde: `"AMPEER_MAIL_TRANSPORT"`, `"RESEND_API_KEY"`, `"AMPEER_MAIL_FROM"`, `"AMPEER_SITE_ORIGIN"`. Vervang in het commentaar erboven niets; de tuple zegt zelf wat hij is. `test_the_stack_has_the_four_services_it_needs` blijft waar, want er komt geen service bij.

`scripts/preflight_env.sh`: vervang in de kop "prod.py requires nine variables" door "prod.py requires thirteen variables", en "The nine names" door "The thirteen names"; voeg aan `REQUIRED=(...)` na `POSTGRES_HOST` toe:

```text
  AMPEER_MAIL_TRANSPORT
  RESEND_API_KEY
  AMPEER_MAIL_FROM
  AMPEER_SITE_ORIGIN
```

en voeg na het `DJANGO_NUM_PROXIES`-blok, voor het `AMPEER_NEDU_PROFILE_PATH`-blok, toe:

```text
# AMPEER_MAIL_TRANSPORT decides whether a household ever receives a mail.
# prod.py accepts `file` as well as `resend`, because the local stack runs
# under prod settings and its live checks read the mail out of a file. On a
# host `file` is the quietest outage there is: every reset mail is written
# to disk inside a container and nobody is told. So a host is held to
# `resend` here, before any container starts, and the local stack's env
# fixture is the only file in the repository that ever says `file`.
TRANSPORT="${VALUES[AMPEER_MAIL_TRANSPORT]}"
case "${TRANSPORT}" in
  resend) ;;
  *)
    fail "AMPEER_MAIL_TRANSPORT is not 'resend'."
    fail "prod.py would start and write every mail to a file inside the container,"
    fail "and no household would receive one. Set it to resend on a host."
    exit 1
    ;;
esac
```

Vervang de laatste regel `echo "preflight: ${#REQUIRED[@]} variables set, profile readable at the host path"` niet: hij telt de array en zegt nu dertien.

`tests/test_deploy_workflow.py`: in `_complete`, na `values["DJANGO_NUM_PROXIES"] = "2"`, voeg toe `values["AMPEER_MAIL_TRANSPORT"] = "resend"`, met het commentaar erboven uitgebreid met één zin: "AMPEER_MAIL_TRANSPORT has to be `resend`, because the preflight refuses every other value on a host." Voeg in `TestThePreflight` toe:

```text
    @pytest.mark.parametrize("value", ["file", "memory", "smtp"])
    def test_the_host_preflight_refuses_any_transport_but_resend(
        self, tmp_path: Path, value: str
    ) -> None:
        """prod.py accepts `file` for the local stack's sake; a host must not
        be able to say it. Red-proof: drop the case block from the script."""
        values = _complete(_profile(tmp_path))
        values["AMPEER_MAIL_TRANSPORT"] = value
        result = _preflight(_write_env(tmp_path, values))
        assert result.returncode != 0, f"{value!r} passed the preflight"
        assert "AMPEER_MAIL_TRANSPORT" in result.stdout + result.stderr
```

Werk in dat bestand de namen bij die "nine" zeggen: `test_it_is_quiet_and_exits_zero_when_all_nine_are_set` wordt `..._when_all_thirteen_are_set` en `test_it_catches_each_of_the_nine_on_its_own` wordt `..._each_of_the_thirteen_on_its_own`; de docstrings die "nine" zeggen zeggen "thirteen".

`tests/test_backend_settings.py`: er is een test die de negen namen van `prod.py` telt of noemt; lees het bestand op "nine" en "_required" en werk elke telling bij tot dertien, met de vier namen erbij waar een lijst staat.

`.github/workflows/deploy.yml`: herreken beide hashes en zet ze op de bestaande regels:

```bash
sha256sum scripts/preflight_env.sh infra/docker-compose.yml
```

`PREFLIGHT_SHA256` wordt de eerste, `COMPOSE_SHA256` de tweede. Lees het commentaar boven beide regels: het zegt al dat de host een stale kopie weigert, en dat is precies wat de eigenaar na deze cyclus te doen krijgt (hoofdstuk 9 van de spec: `preflight_env.sh` en `docker-compose.yml` opnieuw naar `/srv/ampeer/` kopiëren).

- [ ] **Step 7: Groen**

```bash
POSTGRES_HOST=127.0.0.1 POSTGRES_PORT=5433 POSTGRES_DB=ampeer POSTGRES_USER=ampeer POSTGRES_PASSWORD=devtest uv run --no-sync pytest tests/test_accounts_mail.py tests/test_boundaries.py tests/test_infra.py tests/test_deploy_workflow.py tests/test_backend_settings.py tests/test_stack_smoke.py -q
```

Verwacht: alles groen. Let op `test_the_environment_fixture_names_every_variable_the_stack_reads` in `test_stack_smoke.py`: die leest compose en de env-fixture, en compose interpoleert nu vier namen die de fixture nog niet kent. Die test is rood tot taak 12 de fixture aanvult, en dat is de bedoeling: hij bewijst dat de koppeling werkt. Meld hem als de enige rode in het rapport, met de vier namen in zijn melding, en verander niets aan `tests/test_stack_smoke.py` (taak 7 en 12 bezitten dat bestand).

- [ ] **Step 8: Toon aan dat de grenstest het gat ziet**

Maak tijdelijk `backend/accounts/_probe.py` met één regel, `from django.core.mail import send_mail`, en draai:

```bash
uv run --no-sync pytest tests/test_boundaries.py::test_only_these_modules_can_reach_outside_this_machine -q
```

Verwacht: rood, met `backend/accounts/_probe.py: ['django.core.mail']` in de melding. Verwijder het bestand. Draai daarna hetzelfde met een tijdelijke `import smtplib` in `mailer.py`: rood, want `mailer.py` mag alleen `requests`. Zet terug. Vervang daarna tijdelijk `requests.post(RESEND_ENDPOINT, ...)` door `requests.post("https://api.resend.com/emails", ...)` en draai `test_the_module_that_speaks_http_never_assembles_its_url[backend/accounts/mailer.py]`: rood op "not a module level constant". Zet terug. Haal ten slotte het `case`-blok uit de preflight en draai `tests/test_deploy_workflow.py -k refuses_any_transport`: drie keer rood. Zet terug. Plak alle vier.

- [ ] **Step 9: mypy, ruff, shellcheck, dan commit**

```bash
uv run --no-sync mypy --strict backend tests
uv run --no-sync ruff check . && uv run --no-sync ruff format --check .
bash scripts/gates.sh shellcheck
git add backend/accounts/mailer.py tests/test_accounts_mail.py backend/ampeer/settings/base.py backend/ampeer/settings/dev.py backend/ampeer/settings/prod.py tests/test_boundaries.py tests/test_infra.py tests/test_deploy_workflow.py tests/test_backend_settings.py scripts/preflight_env.sh infra/docker-compose.yml infra/.env.example .github/workflows/deploy.yml
git commit
```

Boodschap: `feat(accounts): one module reaches Resend, three transports, and the boundary test sees Django's mail API`.

---

### Taak 7: Het command, de opruiming, de units, de deploy-job

**Hangt af van:** taak 6.

**Files:**
- Create: `backend/accounts/management/commands/send_outbound_mail.py`, `infra/systemd/ampeer-mail.service`, `infra/systemd/ampeer-mail.timer`
- Modify: `backend/accounts/management/commands/purge_expired_sessions.py`, `tests/test_accounts_mail.py`, `tests/test_dpia.py`, `docs/dpia.md`, `infra/README.md`, `.github/workflows/deploy.yml`, `tests/test_stack_smoke.py`

**Interfaces:**
- Consumes: `recovery.mint`, `mailer.transport`, `mailer.Message`, `mailer.TransportError`, `NL["MAIL_*"]`, `settings.AMPEER_SITE_ORIGIN`, `OutboundMail`, `AuditEvent.MAIL_SENT`.
- Produces: `python backend/manage.py send_outbound_mail [--check]`; de constanten `BACKOFF`, `GIVE_UP_AFTER`, `OVERDUE_AFTER` in het command; `purge_expired_sessions` ruimt drie tabellen op; de twee units; de deploy-stap; `AUDIT_CONTEXT_PHRASES["provider_id"]`.

- [ ] **Step 1: De falende tests**

Voeg aan `tests/test_accounts_mail.py` toe:

```text
# ---------------------------------------------------------------------------
# The command that empties the outbox
# ---------------------------------------------------------------------------


def _run(*args: str) -> str:
    out = io.StringIO()
    call_command("send_outbound_mail", *args, stdout=out)
    return out.getvalue()


class _Failing:
    """A transport that answers one status, for every message."""

    def __init__(self, status: int) -> None:
        self.status = status
        self.attempts = 0

    def send(self, message: mailer.Message) -> str:
        self.attempts += 1
        raise mailer.TransportError(self.status)


@pytest.fixture
def _account() -> User:
    return User.objects.create_user(email="iemand@voorbeeld.nl", password=TEST_PASSWORD)


@pytest.fixture(autouse=True)
def _empty_memory() -> None:
    mailer.MEMORY.sent.clear()


@pytest.mark.django_db
def test_the_command_mints_sends_deletes_and_logs(_account: User) -> None:
    recovery.request_password_reset(_account.email)
    before = timezone.now()
    output = _run()
    assert "sent 1" in output
    assert OutboundMail.objects.count() == 0
    [message] = mailer.MEMORY.sent
    assert message.to == _account.email
    assert message.subject == NL["MAIL_RESET_SUBJECT"]
    link = re.search(r"http://127\.0\.0\.1:3000/account/#herstel=([A-Za-z0-9_-]{43})", message.text)
    assert link, message.text
    row = OneTimeToken.objects.get(user=_account, kind=OneTimeToken.PASSWORD_RESET)
    assert row.token_sha256 == token_digest(link.group(1))
    assert row.issued_at >= before
    line = AuditEvent.objects.get(event_type=AuditEvent.MAIL_SENT)
    assert line.context["user_id"] == _account.pk
    assert line.context["kind"] == OneTimeToken.PASSWORD_RESET
    assert line.context["provider_id"].startswith("memory-outbox-")
    assert set(line.context) == {"user_id", "kind", "provider_id"}


@pytest.mark.django_db
def test_a_verification_mail_carries_the_other_link(_account: User) -> None:
    recovery.request_email_verification(_account)
    _run()
    [message] = mailer.MEMORY.sent
    assert message.subject == NL["MAIL_VERIFY_SUBJECT"]
    assert re.search(r"/account/#verificatie=[A-Za-z0-9_-]{43}", message.text)
    assert "%(link)s" not in message.text


@pytest.mark.django_db
def test_a_transport_failure_leaves_no_token_behind(_account: User, monkeypatch: pytest.MonkeyPatch) -> None:
    """Spec 4.4: the mint and the send share a transaction, so a mail that
    never left leaves no digest of a token nobody received."""
    monkeypatch.setattr(mailer, "transport", lambda: _Failing(503))
    recovery.request_password_reset(_account.email)
    before = timezone.now()
    output = _run()
    assert "deferred 1" in output
    assert OneTimeToken.objects.count() == 0
    row = OutboundMail.objects.get()
    assert row.attempts == 1
    assert row.last_status == 503
    assert row.failed_at is None
    assert timedelta(seconds=55) <= row.next_attempt_at - before <= timedelta(seconds=65)
    assert AuditEvent.objects.filter(event_type=AuditEvent.MAIL_SENT).count() == 0


@pytest.mark.django_db
def test_the_backoff_is_one_five_fifteen_sixty_and_then_failed(
    _account: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Driven by moving the row's own clock rather than the wall clock: each
    round sets `next_attempt_at` into the past and `created_at` further back,
    which is what a row looks like after that much waiting."""
    monkeypatch.setattr(mailer, "transport", lambda: _Failing(0))
    recovery.request_email_verification(_account)
    row = OutboundMail.objects.get()
    expected = [1, 5, 15, 60, 60]
    for minutes in expected:
        OutboundMail.objects.filter(pk=row.pk).update(next_attempt_at=timezone.now())
        before = timezone.now()
        _run()
        row.refresh_from_db()
        assert row.failed_at is None
        waited = row.next_attempt_at - before
        assert timedelta(minutes=minutes) - timedelta(seconds=5) <= waited <= timedelta(minutes=minutes) + timedelta(seconds=5), (minutes, waited)
    OutboundMail.objects.filter(pk=row.pk).update(
        next_attempt_at=timezone.now(), created_at=timezone.now() - timedelta(hours=25)
    )
    _run()
    row.refresh_from_db()
    assert row.failed_at is not None
    assert row.attempts == 6


@pytest.mark.django_db
def test_a_four_hundred_other_than_429_fails_at_once(_account: User, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mailer, "transport", lambda: _Failing(401))
    recovery.request_password_reset(_account.email)
    _run()
    row = OutboundMail.objects.get()
    assert row.failed_at is not None
    assert row.last_status == 401
    assert row.attempts == 1


@pytest.mark.django_db
def test_a_429_is_retried_like_a_network_fault(_account: User, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mailer, "transport", lambda: _Failing(429))
    recovery.request_password_reset(_account.email)
    _run()
    row = OutboundMail.objects.get()
    assert row.failed_at is None
    assert row.attempts == 1


@pytest.mark.django_db
def test_a_failed_row_is_never_picked_up_again(_account: User, monkeypatch: pytest.MonkeyPatch) -> None:
    transport = _Failing(401)
    monkeypatch.setattr(mailer, "transport", lambda: transport)
    recovery.request_password_reset(_account.email)
    _run()
    _run()
    assert transport.attempts == 1


@pytest.mark.django_db
def test_the_command_exits_nonzero_when_something_is_overdue(
    _account: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The half that notices. `--check` sends nothing and asks one question:
    is anything unsent older than fifteen minutes?"""
    monkeypatch.setattr(mailer, "transport", lambda: _Failing(0))
    recovery.request_password_reset(_account.email)
    _run("--check")
    OutboundMail.objects.update(created_at=timezone.now() - timedelta(minutes=16))
    with pytest.raises(CommandError, match="waiting"):
        _run("--check")
    assert mailer.MEMORY.sent == []
    with pytest.raises(CommandError, match="waiting"):
        _run()


@pytest.mark.django_db
def test_two_overlapping_runs_never_send_one_row_twice(_account: User) -> None:
    """`FOR UPDATE SKIP LOCKED`, read off the source like the lock in
    recovery.py: the behavioural half is that a row locked by another run is
    skipped, which two processes on Postgres provide and one test process
    cannot stage."""
    source = COMMAND.read_text(encoding="utf-8")
    assert "select_for_update(skip_locked=True)" in source


@pytest.mark.django_db
def test_the_purge_removes_expired_tokens_and_old_failures(_account: User) -> None:
    now = timezone.now()
    live = recovery.mint(_account, OneTimeToken.EMAIL_VERIFY)
    dead = recovery.mint(_account, OneTimeToken.PASSWORD_RESET)
    OneTimeToken.objects.filter(token_sha256=token_digest(dead)).update(
        expires_at=now - timedelta(seconds=1)
    )
    OutboundMail.objects.create(
        user=_account, kind=OneTimeToken.EMAIL_VERIFY, next_attempt_at=now, failed_at=now - timedelta(days=8)
    )
    OutboundMail.objects.create(
        user=_account, kind=OneTimeToken.PASSWORD_RESET, next_attempt_at=now, failed_at=now - timedelta(days=6)
    )
    out = io.StringIO()
    call_command("purge_expired_sessions", stdout=out)
    assert "1 expired one-time tokens" in out.getvalue()
    assert "1 failed mails" in out.getvalue()
    assert OneTimeToken.objects.get().token_sha256 == token_digest(live)
    assert OutboundMail.objects.count() == 1
```

Met bovenaan het bestand de imports erbij: `import io`, `import re`, `from datetime import timedelta`, `from django.core.management import CommandError, call_command`, `from django.utils import timezone`, `from helpers.accounts import TEST_PASSWORD`, `from accounts import recovery`, `from accounts.models import OneTimeToken, OutboundMail, User`, `from accounts.nl import NL`, `from advice.models import AuditEvent, token_digest`, en de constante `COMMAND = Path(__file__).resolve().parent.parent / "backend" / "accounts" / "management" / "commands" / "send_outbound_mail.py"`.

- [ ] **Step 2: Zie ze falen**

```bash
POSTGRES_HOST=127.0.0.1 POSTGRES_PORT=5433 POSTGRES_DB=ampeer POSTGRES_USER=ampeer POSTGRES_PASSWORD=devtest uv run --no-sync pytest tests/test_accounts_mail.py -q
```

Verwacht: `CommandError: Unknown command: 'send_outbound_mail'` op elke commandtest, en de purge-test rood op de ontbrekende tekst in de uitvoer.

- [ ] **Step 3: Het command**

`backend/accounts/management/commands/send_outbound_mail.py`, compleet:

```text
"""Send what is waiting in the outbox, minting each token at the moment of sending.

Called every minute by infra/systemd/ampeer-mail.timer, and not by Celery,
for the reason the two purge commands give: a small amount of work on a
schedule needs a timer and not a queue. This is the only process in this
repository that opens a connection to the mail provider, and it never runs
inside a request.

The order inside one row is exact. The token is minted before the send,
because it has to be in the mail, and the mint and the send share one
savepoint: a transport error leaves that savepoint with an exception, which
rolls the mint back, so no digest of a token nobody received survives. The
outbox row is then updated in the enclosing transaction with the attempt and
the wait. Two writes, in that order, and the first commits only if the
transport took the message.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any, Final

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from accounts import mailer, recovery
from accounts.models import OneTimeToken, OutboundMail
from accounts.nl import NL
from advice.models import AuditEvent

#: After the first, second, third and every later failed attempt.
BACKOFF: Final = (
    timedelta(minutes=1),
    timedelta(minutes=5),
    timedelta(minutes=15),
    timedelta(minutes=60),
)
#: A row older than this is marked failed on its next failure rather than
#: deferred again. A reset link a day late is a link somebody stopped waiting for.
GIVE_UP_AFTER: Final = timedelta(hours=24)
#: `--check` exits non-zero when an unsent row is older than this. The timer
#: runs every minute; a quarter of an hour is fifteen missed runs.
OVERDUE_AFTER: Final = timedelta(minutes=15)

_SUBJECT: Final = {
    OneTimeToken.PASSWORD_RESET: "MAIL_RESET_SUBJECT",
    OneTimeToken.EMAIL_VERIFY: "MAIL_VERIFY_SUBJECT",
}
_BODY: Final = {
    OneTimeToken.PASSWORD_RESET: "MAIL_RESET_BODY",
    OneTimeToken.EMAIL_VERIFY: "MAIL_VERIFY_BODY",
}
#: The word after `#` in the link. frontend/src/app/_account/fragment.ts reads
#: exactly these two.
_FRAGMENT: Final = {
    OneTimeToken.PASSWORD_RESET: "herstel",
    OneTimeToken.EMAIL_VERIFY: "verificatie",
}


def _compose(row: OutboundMail, raw_token: str) -> mailer.Message:
    link = f"{settings.AMPEER_SITE_ORIGIN}/account/#{_FRAGMENT[row.kind]}={raw_token}"
    return mailer.Message(
        to=row.user.email,
        subject=NL[_SUBJECT[row.kind]],
        text=NL[_BODY[row.kind]] % {"link": link},
        idempotency_key=f"outbox-{row.pk}",
    )


def _retryable(status: int) -> bool:
    """A network fault, a timeout, a 429 or a 5xx is worth another attempt. A
    wrong key or an address the provider refuses is not."""
    return status == 0 or status == 429 or status >= 500


class Command(BaseCommand):
    help = "Send what is waiting in the outbox; with --check only report what is overdue."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            "--check",
            action="store_true",
            help="Send nothing; exit non-zero if an unsent mail is older than fifteen minutes.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        if not options["check"]:
            sent, deferred = self._deliver()
            self.stdout.write(f"sent {sent} messages, deferred {deferred}")
        overdue = OutboundMail.objects.filter(
            failed_at__isnull=True, created_at__lte=timezone.now() - OVERDUE_AFTER
        ).count()
        if overdue:
            raise CommandError(
                f"{overdue} mails have been waiting longer than {OVERDUE_AFTER}; "
                "the timer has stopped or the transport refuses everything"
            )

    def _deliver(self) -> tuple[int, int]:
        sender = mailer.transport()
        sent = deferred = 0
        while True:
            with transaction.atomic():
                row = (
                    OutboundMail.objects.select_for_update(skip_locked=True)
                    .filter(failed_at__isnull=True, next_attempt_at__lte=timezone.now())
                    .order_by("id")
                    .first()
                )
                if row is None:
                    return sent, deferred
                try:
                    with transaction.atomic():
                        raw = recovery.mint(row.user, row.kind)
                        provider_id = sender.send(_compose(row, raw))
                except mailer.TransportError as error:
                    self._defer(row, error.status)
                    deferred += 1
                    continue
                AuditEvent.record(
                    AuditEvent.MAIL_SENT,
                    user_id=row.user_id,
                    kind=row.kind,
                    provider_id=provider_id,
                )
                row.delete()
                sent += 1

    def _defer(self, row: OutboundMail, status: int) -> None:
        now = timezone.now()
        row.attempts += 1
        row.last_status = status
        if not _retryable(status) or now - row.created_at >= GIVE_UP_AFTER:
            row.failed_at = now
        else:
            row.next_attempt_at = now + BACKOFF[min(row.attempts, len(BACKOFF)) - 1]
        row.save(update_fields=["attempts", "last_status", "failed_at", "next_attempt_at"])
```

Let op de `while True` met `return` binnen het `with`: de transactie sluit netjes bij een `return`, en elke ronde verwijdert of verschuift de rij die hij las, dus de lus eindigt.

- [ ] **Step 4: De opruiming**

`backend/accounts/management/commands/purge_expired_sessions.py`: vervang de docstring-alinea die begint met "Rows are removed on `expires_at`" door:

```text
Rows are removed on `expires_at` and not on `rotated_at`. A rotated row is the
evidence that a token was spent, and that evidence is what makes reuse
detectable; dropping it early would turn a stolen token into an unknown one.
The same holds for `OneTimeToken.spent_at`, so those rows go on `expires_at`
too. Failed outbox rows go seven days after `failed_at`: long enough to be
read when somebody asks why a mail never came, and no longer.
```

en `handle` door:

```text
    def handle(self, *args: Any, **options: Any) -> None:
        now = timezone.now()
        sessions, _ = RefreshSession.objects.filter(expires_at__lte=now).delete()
        tokens, _ = OneTimeToken.objects.filter(expires_at__lte=now).delete()
        mails, _ = OutboundMail.objects.filter(failed_at__lte=now - timedelta(days=7)).delete()
        self.stdout.write(
            f"removed {sessions} expired refresh sessions, {tokens} expired one-time tokens, "
            f"{mails} failed mails"
        )
```

met `from datetime import timedelta` en `from accounts.models import OneTimeToken, OutboundMail, RefreshSession` bij de imports.

- [ ] **Step 5: De DPIA-binding voor `provider_id`**

`tests/test_dpia.py`, `AUDIT_CONTEXT_PHRASES`, na `"reused": "`reused`",`:

```text
    "provider_id": "`provider_id`",
```

`docs/dpia.md`, hoofdstuk 2, de alinea over het auditlogboek, na de zin over `reused` ("...zou een koppeling suggereren die er niet is."), voeg toe:

```text
Een regel over een verzonden mail draagt naast `user_id` en `kind` een
`provider_id`: het bericht-id dat de mailverwerker teruggeeft. Dat id is geen
persoonsgegeven en het is wel het enige waarmee een verzending bij die
verwerker teruggevonden kan worden.
```

- [ ] **Step 6: De units, de README en de deploy-stap**

`infra/systemd/ampeer-mail.service`:

```text
# THIS FILE IS INSTALLED BY HAND. NOTHING IN THIS REPOSITORY INSTALLS IT.
#
# Who:   Stijn, on the Ampeer LXC, as root. No workflow, no deploy job and no
#        test may copy, enable or start this unit, and none of them does.
# Where: /etc/systemd/system/ampeer-mail.service, together with
#        /etc/systemd/system/ampeer-mail.timer.
# How:   cp infra/systemd/ampeer-mail.* /etc/systemd/system/
#        systemctl daemon-reload
#        systemctl enable --now ampeer-mail.timer
# Check: systemctl list-timers ampeer-mail.timer
#
# Spelled out for the same reason ampeer-purge.service spells it out: a file
# that looks automatic and is not is worse than one that says so. If nobody
# runs the three commands above, no reset mail and no confirmation mail ever
# leaves, and the only observable behaviour is a household waiting for a mail
# that does not come. `send_outbound_mail --check` is the half that notices:
# the deploy job runs it after migrate and goes red when a mail has waited
# longer than fifteen minutes.

[Unit]
Description=Send the mails waiting in Ampeer's outbox
Requires=docker.service
After=docker.service
ConditionPathExists=/srv/ampeer/docker-compose.yml

[Service]
Type=oneshot
WorkingDirectory=/srv/ampeer
# The same shape as the purge unit, for the same reasons: --env-file because
# compose gives none of its variables a default, --entrypoint python because
# the image's entrypoint execs gunicorn, backend/manage.py because the image's
# working directory is /app.
ExecStart=/usr/bin/docker compose --env-file /srv/ampeer/.env -f /srv/ampeer/docker-compose.yml run --rm --entrypoint python api backend/manage.py send_outbound_mail
# The command prints two counts and nothing else. No address and no token
# reaches the journal, which outlives the rows it describes.
```

`infra/systemd/ampeer-mail.timer`:

```text
# Installed by hand, see ampeer-mail.service.

[Unit]
Description=Run Ampeer's outbox every minute

[Timer]
# Every minute, on the minute. A mail a household is waiting for should not
# wait for a cron granularity chosen for a daily purge.
OnCalendar=*-*-* *:*:00
AccuracySec=10s
# No Persistent=true: a missed minute needs no catch-up run, because the
# next run sends whatever is waiting. The purge timer is different, and says
# why it is.
Unit=ampeer-mail.service

[Install]
WantedBy=timers.target
```

`infra/README.md`, sectie 1: voeg aan de tabel "prod.py refuses to start without these nine" (maak er "these thirteen" van) vier rijen toe:

```text
| `AMPEER_MAIL_TRANSPORT` | `resend` on a host. The preflight refuses every other value here: `file` writes each mail to a file inside the container and delivers none |
| `RESEND_API_KEY` | The Resend key with send permission for the domain below. A credential, like the tunnel token |
| `AMPEER_MAIL_FROM` | The sender a household sees, `noreply@ampeer.nl`, on a domain verified at Resend with the SPF and DKIM records it hands out |
| `AMPEER_SITE_ORIGIN` | Where the links in a mail point, `https://ampeer.nl`. The page reads the token off the fragment of that origin's `/account/` route |
```

Sectie 3 krijgt een tweede kop en blok, na het bestaande "Verify"-blok van de purge-timer en voor "What notices when the purge stops":

```text
### The outbox timer is installed the same way

`infra/systemd/ampeer-mail.service` and `infra/systemd/ampeer-mail.timer`
send the password reset and address confirmation mails, every minute.
**Nothing in this repository installs, enables or starts them either.**

```sh
cp infra/systemd/ampeer-mail.* /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now ampeer-mail.timer
```

**Verify:**

```sh
systemctl list-timers ampeer-mail.timer       # NEXT must be within a minute
docker compose --env-file /srv/ampeer/.env -f /srv/ampeer/docker-compose.yml run --rm --entrypoint python api backend/manage.py send_outbound_mail --check
```

The second command exits non-zero as soon as an unsent mail is older than
fifteen minutes, and the deploy job runs it after `migrate` for the same
reason it runs the purge check there. It does not notice a timer that was
never enabled until the first mail is fifteen minutes late, which for a
household is already too late; only `list-timers` answers that question, and
it is written down here rather than papered over.
```

`.github/workflows/deploy.yml`: na de stap "Confirm expired advice is still being deleted" een tweede stap in dezelfde vorm:

```text
      # The same question for the outbox: a mail waiting longer than fifteen
      # minutes means the timer has stopped or the provider refuses
      # everything, and either is a deploy worth stopping on. After migrate,
      # for the reason the step above gives.
      - name: Confirm the outbox is being emptied
        run: >-
          docker compose -f "$STACK/docker-compose.yml" --env-file "$STACK/.env"
          run --rm --entrypoint python api backend/manage.py send_outbound_mail --check
```

`tests/test_stack_smoke.py`: voeg naast `test_the_deploy_checks_that_retention_is_still_running` toe:

```text
def test_the_deploy_checks_that_the_outbox_is_being_emptied() -> None:
    """The same shape as the retention check, for the mails a household is
    waiting on. Neither notices a timer that was never enabled."""
    workflow = DEPLOY_WORKFLOW.read_text(encoding="utf-8")
    assert "send_outbound_mail --check" in workflow


def test_the_mail_unit_runs_the_command_every_minute() -> None:
    service = (INFRA / "systemd" / "ampeer-mail.service").read_text(encoding="utf-8")
    timer = (INFRA / "systemd" / "ampeer-mail.timer").read_text(encoding="utf-8")
    assert "backend/manage.py send_outbound_mail" in service
    assert "--entrypoint python" in service
    assert "OnCalendar=*-*-* *:*:00" in timer
    assert "Persistent=true" not in timer
    assert "INSTALLED BY HAND" in service[:400]
```

- [ ] **Step 7: Groen**

```bash
POSTGRES_HOST=127.0.0.1 POSTGRES_PORT=5433 POSTGRES_DB=ampeer POSTGRES_USER=ampeer POSTGRES_PASSWORD=devtest uv run --no-sync pytest tests/test_accounts_mail.py tests/test_dpia.py tests/test_stack_smoke.py tests/test_deploy_workflow.py tests/test_accounts_privacy.py -q
```

Verwacht: alles groen behalve `test_the_environment_fixture_names_every_variable_the_stack_reads`, dat rood blijft tot taak 12 (zie taak 6 stap 7). `test_the_document_names_everything_the_audit_line_carries` ziet nu `provider_id` in het command en in de DPIA. `test_no_audit_line_the_account_layer_writes_carries_an_address` blijft groen omdat `MAIL_SENT` het adres niet draagt.

- [ ] **Step 8: Toon aan dat drie controles rood kunnen worden**

1. Haal in `_deliver` de binnenste `with transaction.atomic():` weg (laat de twee regels erin staan, één niveau minder ingesprongen): `test_a_transport_failure_leaves_no_token_behind` wordt rood op `OneTimeToken.objects.count() == 0`, want de mint overleeft de mislukte verzending. Zet terug.
2. Vervang `_retryable(status)` tijdelijk door `True`: `test_a_four_hundred_other_than_429_fails_at_once` rood. Zet terug.
3. Haal `"provider_id": "`provider_id`",` tijdelijk uit `AUDIT_CONTEXT_PHRASES`: `test_the_document_names_everything_the_audit_line_carries` rood met `provider_id` in de melding. Zet terug.

Plak alle drie.

- [ ] **Step 9: mypy, ruff, dan commit**

```bash
uv run --no-sync mypy --strict backend tests
uv run --no-sync ruff check . && uv run --no-sync ruff format --check .
git add backend/accounts/management/commands/send_outbound_mail.py backend/accounts/management/commands/purge_expired_sessions.py tests/test_accounts_mail.py tests/test_dpia.py docs/dpia.md infra/systemd/ampeer-mail.service infra/systemd/ampeer-mail.timer infra/README.md .github/workflows/deploy.yml tests/test_stack_smoke.py
git commit
```

Boodschap: `feat(accounts): the outbox is emptied every minute, and the token is minted as the mail leaves`.

---

### Taak 8: Frontend laag 1: `accounts.ts`

**Hangt af van:** taak 7 (en inhoudelijk van taak 5: de vier paden moeten bestaan voordat `test_every_path_the_frontend_calls_is_one_the_backend_serves[accounts]` ze mag zien).

**Files:**
- Modify: `frontend/src/lib/accounts.ts`, `frontend/tests/lib/accounts.test.ts`

**Interfaces:**
- Consumes: de vier routes uit taak 5; `me-response.json` met `email_verified_at`; `consent-texts.json` met `labels`.
- Produces: `Me.email_verified_at: string | null`; `ConsentTexts.labels: Readonly<Record<ConsentKind, string>>`; `requestPasswordReset({ email })`, `confirmPasswordReset({ token, password })`, `requestEmailVerification()`, `confirmEmailVerification({ token })`, alle vier `Promise<void>`; `isMe` en `isConsentTexts` eisen de nieuwe sleutels.

- [ ] **Step 1: De falende tests**

In `frontend/tests/lib/accounts.test.ts`: voeg de vier functies aan de import toe en vier regels aan `CALLS`, na `delete`:

```ts
  {
    name: "reset-request",
    status: 202,
    body: {},
    method: "POST",
    run: () => requestPasswordReset({ email: "iemand@voorbeeld.nl" }),
  },
  {
    name: "reset-confirm",
    status: 204,
    body: null,
    method: "POST",
    run: () =>
      confirmPasswordReset({
        token: "a".repeat(43),
        password: "een-ander-wachtwoord",
      }),
  },
  {
    name: "verify-request",
    status: 202,
    body: {},
    method: "POST",
    run: requestEmailVerification,
  },
  {
    name: "verify-confirm",
    status: 204,
    body: null,
    method: "POST",
    run: () => confirmEmailVerification({ token: "a".repeat(43) }),
  },
```

Werk het commentaar boven `CALLS` bij van "The nine calls" naar "The thirteen calls". Voeg onderaan het bestand toe:

```ts
describe("the two shape guards that grew a key", () => {
  it("refuses a me/ that does not say whether the address is confirmed", async () => {
    const { email_verified_at: _dropped, ...withoutIt } = me;
    stub(200, withoutIt);
    await expect(getMe()).rejects.toBeInstanceOf(ApiError);
  });

  it("accepts a me/ whose address is confirmed at a time", async () => {
    stub(200, { ...me, email_verified_at: "2026-09-06T10:00:00+00:00" });
    const answer = await getMe();
    expect(answer.email_verified_at).toBe("2026-09-06T10:00:00+00:00");
  });

  it("refuses consent texts without the labels, and labels without a kind", async () => {
    const { labels: _dropped, ...withoutLabels } = consentTexts;
    stub(200, withoutLabels);
    await expect(getConsentTexts()).rejects.toBeInstanceOf(ApiError);
    stub(200, {
      ...consentTexts,
      labels: { METER_LINK: consentTexts.labels.METER_LINK },
    });
    await expect(getConsentTexts()).rejects.toBeInstanceOf(ApiError);
  });

  it("sends the four recovery bodies exactly as the API reads them", async () => {
    const fetchMock = stub(202, {});
    await requestPasswordReset({ email: "iemand@voorbeeld.nl" });
    await confirmPasswordReset({ token: "t".repeat(43), password: "pw" });
    await confirmEmailVerification({ token: "v".repeat(43) });
    const bodies = fetchMock.mock.calls.map((call) =>
      JSON.parse(String((call[1] as RequestInit).body)),
    );
    expect(bodies).toEqual([
      { email: "iemand@voorbeeld.nl" },
      { token: "t".repeat(43), password: "pw" },
      { token: "v".repeat(43) },
    ]);
    const paths = fetchMock.mock.calls.map((call) => new URL(String(call[0])).pathname);
    expect(paths).toEqual([
      "/api/auth/reset/request/",
      "/api/auth/reset/confirm/",
      "/api/auth/verify/confirm/",
    ]);
  });
});
```

De bestaande tests op `credentials: "include"`, de CSRF-header en "één fetch per aanroep op elke status" lopen over `CALLS` en dekken de vier nieuwe aanroepen daarmee zonder een regel extra.

- [ ] **Step 2: Zie ze falen**

```bash
cd frontend && pnpm vitest run tests/lib/accounts.test.ts
```

Verwacht: rood op de import (`requestPasswordReset` bestaat niet) en op de twee vormcontroles, die de oude vorm nog accepteren.

- [ ] **Step 3: `accounts.ts`**

In de moduledocstring: "Every answer is checked for shape" blijft; werk de tellingen bij waar het bestand "nine" zegt. `Me` en `ConsentTexts` worden:

```ts
export interface ConsentTexts {
  readonly text_version: string;
  readonly texts: Readonly<Record<ConsentKind, string>>;
  /**
   * The heading each consent is shown under, from the same answer and under
   * the same version as the sentence it heads. Decision 38: a label edit is
   * caught the way a text edit is, and no label lives in this tree.
   */
  readonly labels: Readonly<Record<ConsentKind, string>>;
}

export interface Me {
  readonly email: string;
  readonly consents: Readonly<Record<ConsentKind, boolean>>;
  /** ISO 8601, or null for an address nobody has confirmed yet. */
  readonly email_verified_at: string | null;
}
```

Voeg toe na `ConsentInput`:

```ts
export interface ResetRequestInput {
  readonly email: string;
}

export interface ResetConfirmInput {
  /** Off the fragment of the link in the mail. Never typed, never shown. */
  readonly token: string;
  readonly password: string;
}

export interface VerifyConfirmInput {
  readonly token: string;
}
```

`isConsentTexts` wordt:

```ts
/** Both kinds present under `texts` and under `labels`, none empty. A further key is left alone. */
function isConsentTexts(value: unknown): value is ConsentTexts {
  if (!isObject(value)) return false;
  const version = value["text_version"];
  if (!isString(version) || version.length === 0) return false;
  const texts = value["texts"];
  const labels = value["labels"];
  if (!isObject(texts) || !isObject(labels)) return false;
  return CONSENT_KINDS.every((kind) => {
    const sentence = texts[kind];
    const label = labels[kind];
    return (
      isString(sentence) &&
      sentence.length > 0 &&
      isString(label) &&
      label.length > 0
    );
  });
}
```

`isMe` wordt:

```ts
function isMe(value: unknown): value is Me {
  if (!isObject(value) || !isString(value["email"])) return false;
  const consents = value["consents"];
  if (!isObject(consents)) return false;
  if (!("email_verified_at" in value)) return false;
  const verified = value["email_verified_at"];
  if (verified !== null && !isString(verified)) return false;
  return CONSENT_KINDS.every((kind) => typeof consents[kind] === "boolean");
}
```

Voeg onderaan toe:

```ts
/**
 * The four recovery calls. All four answer with an empty body (202 with `{}`,
 * or 204), so there is no shape to check and nothing to return: a success is
 * the absence of an `ApiError`, and a failure carries the API's own Dutch
 * sentence, under `token` or `password` or as `detail`, like every other call
 * in this file.
 */
export async function requestPasswordReset(
  input: ResetRequestInput,
): Promise<void> {
  await call("/api/auth/reset/request/", { method: "POST", body: input });
}

export async function confirmPasswordReset(
  input: ResetConfirmInput,
): Promise<void> {
  await call("/api/auth/reset/confirm/", { method: "POST", body: input });
}

export async function requestEmailVerification(): Promise<void> {
  await call("/api/auth/verify/request/", { method: "POST" });
}

export async function confirmEmailVerification(
  input: VerifyConfirmInput,
): Promise<void> {
  await call("/api/auth/verify/confirm/", { method: "POST", body: input });
}
```

- [ ] **Step 4: Groen, en de contractlaag**

```bash
cd frontend && pnpm vitest run tests/lib/accounts.test.ts && pnpm typecheck && pnpm lint && cd ..
POSTGRES_HOST=127.0.0.1 POSTGRES_PORT=5433 POSTGRES_DB=ampeer POSTGRES_USER=ampeer POSTGRES_PASSWORD=devtest uv run --no-sync pytest tests/test_frontend_contract.py -q
```

Verwacht: groen. `test_every_path_the_frontend_calls_is_one_the_backend_serves[accounts]` ziet dertien paden en vindt ze alle dertien in `urls.py`. `pnpm typecheck` is hier al rood op `ConsentRow.tsx`, `RegisterForm.tsx` en `AccountPage.tsx` als `Me` en `ConsentTexts` strenger zijn geworden dan hun gebruikers: controleer dat elke typefout in een bestand van taak 9 of 10 zit en meld ze bij naam in het rapport; ze zijn de reden dat die taken bestaan. Is er een typefout in een bestand dat geen enkele taak bezit, stop dan en meld dat.

- [ ] **Step 5: Toon aan dat de padcontrole rood kan worden**

Verander in `accounts.ts` tijdelijk `"/api/auth/reset/request/"` in `"/api/auth/reset/requests/"` en draai de contracttest: rood, met het pad in de melding. Zet terug. Plak.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/lib/accounts.ts frontend/tests/lib/accounts.test.ts
git commit
```

Boodschap: `feat(frontend): four recovery calls, and the two shapes that grew a key`.

---

### Taak 9: Frontend laag 2: het fragment, `messages.ts`, de twee formulieren

**Hangt af van:** taak 8.

**Files:**
- Create: `frontend/src/app/_account/fragment.ts`, `frontend/src/app/_account/ResetRequestForm.tsx`, `frontend/src/app/_account/ResetConfirmForm.tsx`, `frontend/tests/account/fragment.test.ts`, `frontend/tests/account/ResetRequestForm.test.tsx`, `frontend/tests/account/ResetConfirmForm.test.tsx`
- Modify: `frontend/src/app/_account/messages.ts`, `frontend/tests/account/messages.test.ts`, `frontend/tests/ui-strings.txt`

**Interfaces:**
- Consumes: `requestPasswordReset`, `confirmPasswordReset` uit `accounts.ts`; `describeAuthError`, `fieldErrors`.
- Produces: `readRecoveryFragment(): RecoveryFragment | null` met `RecoveryFragment = { kind: "reset" | "verify"; token: string }`; `AccountField` met `"token"`; `ResetRequestForm({ onBack })`; `ResetConfirmForm({ token, onReset, onRequestNew })`.

- [ ] **Step 1: De falende tests**

`frontend/tests/account/fragment.test.ts`:

```ts
import { afterEach, describe, expect, it } from "vitest";
import { readRecoveryFragment } from "@/app/_account/fragment";

const TOKEN = "A".repeat(43);

afterEach(() => {
  window.history.replaceState(null, "", "/account/");
});

describe("the token in the fragment", () => {
  it("reads a reset link and clears the fragment from the address bar", () => {
    window.history.replaceState(null, "", `/account/#herstel=${TOKEN}`);
    expect(readRecoveryFragment()).toEqual({ kind: "reset", token: TOKEN });
    expect(window.location.hash).toBe("");
    expect(window.location.pathname).toBe("/account/");
  });

  it("reads a verification link", () => {
    window.history.replaceState(null, "", `/account/#verificatie=${TOKEN}`);
    expect(readRecoveryFragment()).toEqual({ kind: "verify", token: TOKEN });
    expect(window.location.hash).toBe("");
  });

  it("reads nothing on a second call, because the first one cleared it", () => {
    window.history.replaceState(null, "", `/account/#herstel=${TOKEN}`);
    readRecoveryFragment();
    expect(readRecoveryFragment()).toBeNull();
  });

  it.each([
    "",
    "#",
    "#herstel=",
    `#herstel=${"A".repeat(42)}`,
    `#herstel=${"A".repeat(44)}`,
    `#herstel=${"A".repeat(42)}!`,
    `#reset=${TOKEN}`,
    `#herstel=${TOKEN}&x=1`,
    "#organisatie",
  ])("reads nothing from %j and leaves it alone", (hash) => {
    window.history.replaceState(null, "", `/account/${hash}`);
    expect(readRecoveryFragment()).toBeNull();
    expect(window.location.hash).toBe(hash === "#" ? "" : hash);
  });

  it("keeps the query string when it clears the fragment", () => {
    window.history.replaceState(null, "", `/account/?ronde=2#herstel=${TOKEN}`);
    readRecoveryFragment();
    expect(window.location.search).toBe("?ronde=2");
    expect(window.location.hash).toBe("");
  });
});
```

`frontend/tests/account/messages.test.ts`, één test erbij aan het eind:

```ts
  it("keeps a token error beside the field it belongs to", () => {
    const error = new ApiError(
      400,
      { token: ["deze link is verlopen of al gebruikt; vraag een nieuwe aan"] },
      "",
    );
    expect(fieldErrors(error)).toEqual({
      token: ["deze link is verlopen of al gebruikt; vraag een nieuwe aan"],
    });
  });
```

De import bovenaan dat bestand wordt `import { describeAuthError, fieldErrors } from "@/app/_account/messages";`.

`frontend/tests/account/ResetRequestForm.test.tsx`:

```tsx
import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ResetRequestForm } from "@/app/_account/ResetRequestForm";

afterEach(() => vi.unstubAllGlobals());

function stub(status: number, body: unknown) {
  const fetchMock = vi.fn<typeof fetch>(
    async () =>
      new Response(status === 204 ? null : JSON.stringify(body), {
        status,
        headers: { "content-type": "application/json" },
      }),
  );
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

const SENT =
  "Als dit adres bij ons bekend is, staat er binnen enkele minuten een e-mail voor u klaar. De link daarin werkt een uur.";

describe("asking for a reset link", () => {
  it("posts the address and then says the same sentence whatever the address was", async () => {
    const fetchMock = stub(202, {});
    render(<ResetRequestForm onBack={vi.fn()} />);
    await userEvent.type(screen.getByLabelText("E-mailadres"), "iemand@voorbeeld.nl");
    await userEvent.click(screen.getByRole("button", { name: "Stuur een herstellink" }));
    expect(await screen.findByRole("status")).toHaveTextContent(SENT);
    expect(screen.queryByLabelText("E-mailadres")).not.toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(JSON.parse(String((fetchMock.mock.calls[0]?.[1] as RequestInit).body))).toEqual({
      email: "iemand@voorbeeld.nl",
    });
  });

  it("shows a 400 beside the address field and keeps the form", async () => {
    stub(400, { email: ["geen geldig e-mailadres"] });
    render(<ResetRequestForm onBack={vi.fn()} />);
    await userEvent.type(screen.getByLabelText("E-mailadres"), "geen adres");
    await userEvent.click(screen.getByRole("button", { name: "Stuur een herstellink" }));
    const field = screen.getByLabelText("E-mailadres");
    expect(await screen.findByRole("alert")).toHaveTextContent("geen geldig e-mailadres");
    expect(field).toHaveAccessibleDescription("geen geldig e-mailadres");
    expect(field).toHaveAttribute("aria-invalid", "true");
  });

  it("shows a 429 as the API wrote it, and never English", async () => {
    stub(429, {
      detail: "te veel verzoeken achter elkaar; probeer het over 900 seconden opnieuw",
    });
    render(<ResetRequestForm onBack={vi.fn()} />);
    await userEvent.type(screen.getByLabelText("E-mailadres"), "iemand@voorbeeld.nl");
    await userEvent.click(screen.getByRole("button", { name: "Stuur een herstellink" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "te veel verzoeken achter elkaar; probeer het over 900 seconden opnieuw",
    );
    expect(document.body.textContent).not.toContain("API returned");
  });

  it("goes back to signing in on the one button that says so", async () => {
    const onBack = vi.fn();
    render(<ResetRequestForm onBack={onBack} />);
    await userEvent.click(screen.getByRole("button", { name: "Terug naar inloggen" }));
    expect(onBack).toHaveBeenCalledTimes(1);
  });

  it("names its own heading, so the group around it can point at it", () => {
    render(<ResetRequestForm onBack={vi.fn()} />);
    expect(screen.getByRole("heading", { name: "Wachtwoord herstellen" })).toHaveAttribute(
      "id",
      "wachtwoord-herstellen",
    );
  });
});
```

`frontend/tests/account/ResetConfirmForm.test.tsx`:

```tsx
import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ResetConfirmForm } from "@/app/_account/ResetConfirmForm";

afterEach(() => vi.unstubAllGlobals());

const TOKEN = "T".repeat(43);

function stub(status: number, body: unknown) {
  const fetchMock = vi.fn<typeof fetch>(
    async () =>
      new Response(status === 204 ? null : JSON.stringify(body), {
        status,
        headers: { "content-type": "application/json" },
      }),
  );
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

describe("choosing a new password with a link", () => {
  it("posts the token and the password, and reports back on a 204", async () => {
    const fetchMock = stub(204, null);
    const onReset = vi.fn();
    render(<ResetConfirmForm token={TOKEN} onReset={onReset} onRequestNew={vi.fn()} />);
    await userEvent.type(screen.getByLabelText("Nieuw wachtwoord"), "een-ander-wachtwoord");
    await userEvent.click(screen.getByRole("button", { name: "Wachtwoord opslaan" }));
    await vi.waitFor(() => expect(onReset).toHaveBeenCalledTimes(1));
    expect(JSON.parse(String((fetchMock.mock.calls[0]?.[1] as RequestInit).body))).toEqual({
      token: TOKEN,
      password: "een-ander-wachtwoord",
    });
    expect(document.body.textContent).not.toContain(TOKEN);
  });

  it("hangs a token error on the password field and offers a new link", async () => {
    stub(400, { token: ["deze link is verlopen of al gebruikt; vraag een nieuwe aan"] });
    const onRequestNew = vi.fn();
    render(<ResetConfirmForm token={TOKEN} onReset={vi.fn()} onRequestNew={onRequestNew} />);
    await userEvent.type(screen.getByLabelText("Nieuw wachtwoord"), "een-ander-wachtwoord");
    await userEvent.click(screen.getByRole("button", { name: "Wachtwoord opslaan" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "deze link is verlopen of al gebruikt; vraag een nieuwe aan",
    );
    expect(screen.getByLabelText("Nieuw wachtwoord")).toHaveAccessibleDescription(
      "deze link is verlopen of al gebruikt; vraag een nieuwe aan",
    );
    await userEvent.click(screen.getByRole("button", { name: "Wachtwoord vergeten?" }));
    expect(onRequestNew).toHaveBeenCalledTimes(1);
  });

  it("hangs a password error on the password field, like registration does", async () => {
    stub(400, { password: ["wachtwoord moet minimaal 12 tekens bevatten"] });
    render(<ResetConfirmForm token={TOKEN} onReset={vi.fn()} onRequestNew={vi.fn()} />);
    await userEvent.type(screen.getByLabelText("Nieuw wachtwoord"), "kort");
    await userEvent.click(screen.getByRole("button", { name: "Wachtwoord opslaan" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "wachtwoord moet minimaal 12 tekens bevatten",
    );
    expect(screen.queryByRole("button", { name: "Wachtwoord vergeten?" })).not.toBeInTheDocument();
  });

  it("never renders the token anywhere in the document", () => {
    render(<ResetConfirmForm token={TOKEN} onReset={vi.fn()} onRequestNew={vi.fn()} />);
    expect(document.body.innerHTML).not.toContain(TOKEN);
  });
});
```

- [ ] **Step 2: Zie ze falen**

```bash
cd frontend && pnpm vitest run tests/account/fragment.test.ts tests/account/messages.test.ts tests/account/ResetRequestForm.test.tsx tests/account/ResetConfirmForm.test.tsx
```

Verwacht: rood op drie ontbrekende modules en op `fieldErrors` dat `token` laat vallen.

- [ ] **Step 3: `fragment.ts`**

```ts
/**
 * The token off the link in a mail, read once and then gone.
 *
 * A fragment never leaves the browser: nginx does not see it, so the access
 * log does not, Cloudflare does not, and a Referer does not carry it. That is
 * why the link is `/account/#herstel=<token>` rather than a path of its own,
 * and why none of what `/advies/<token>/` needed (a location, a serve.json
 * rule, a log redaction) exists for this.
 *
 * `replaceState` clears it in the same call, so the token does not linger in
 * the history, a tab title or a shared URL. The page keeps the token in its
 * own state and nowhere in the DOM.
 *
 * Exactly 43 url-safe characters, which is `secrets.token_urlsafe(32)` on the
 * Python side; tests/test_frontend_contract.py holds the two numbers
 * together. Anything else reads as no fragment at all, and is left alone.
 */
export type RecoveryFragment = {
  readonly kind: "reset" | "verify";
  readonly token: string;
};

const PATTERN = /^#(herstel|verificatie)=([A-Za-z0-9_-]{43})$/;

export function readRecoveryFragment(): RecoveryFragment | null {
  const match = PATTERN.exec(window.location.hash);
  if (match === null) return null;
  window.history.replaceState(
    window.history.state,
    "",
    window.location.pathname + window.location.search,
  );
  return {
    kind: match[1] === "herstel" ? "reset" : "verify",
    token: match[2] ?? "",
  };
}
```

- [ ] **Step 4: `messages.ts`**

`AccountField` wordt `"email" | "password" | "text_version" | "token"`, `ACCOUNT_FIELDS` krijgt `"token"` erbij, en de docstring erboven zegt "The four fields" met één zin extra: "`token` has no input of its own; `ResetConfirmForm` hangs its sentence on the password field, because that is the only field on that form and the sentence is about the link the form was opened with."

- [ ] **Step 5: `ResetRequestForm.tsx`**

```tsx
"use client";

import { useId, useState } from "react";
import { requestPasswordReset } from "@/lib/accounts";
import { describeAuthError, fieldErrors } from "./messages";

/**
 * Shown once, after the 202, in place of the field. The same sentence for
 * every address, known or not, because the API says nothing either: a page
 * that revealed which addresses have an account would be an address book.
 * A module constant for the reason `DELETION_CONFIRMATION` in
 * `AccountPage.tsx` is one: the extractor behind `e2e/language.spec.ts`
 * walks variable initialisers and JSX text, not a call argument.
 */
const SENT =
  "Als dit adres bij ons bekend is, staat er binnen enkele minuten een e-mail voor u klaar. De link daarin werkt een uur.";

/**
 * Asking for a reset link: one field, one button, one sentence afterwards.
 *
 * Reached from the sign-in form's "Wachtwoord vergeten?" button, which stands
 * where the sentence saying there was no reset used to stand.
 */
export function ResetRequestForm({ onBack }: { readonly onBack: () => void }) {
  const emailId = useId();
  const emailErrorId = `${emailId}-error`;
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const [sent, setSent] = useState(false);
  const [failure, setFailure] = useState<string | null>(null);
  const [fields, setFields] = useState<ReturnType<typeof fieldErrors>>({});

  async function submit(): Promise<void> {
    setBusy(true);
    setFailure(null);
    setFields({});
    try {
      await requestPasswordReset({ email });
      setSent(true);
    } catch (error) {
      const perField = fieldErrors(error);
      setFields(perField);
      setFailure(
        Object.keys(perField).length > 0 ? null : describeAuthError(error),
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <section aria-labelledby="wachtwoord-herstellen" className="flex flex-col gap-6">
      <h2 id="wachtwoord-herstellen" className="text-2xl">
        Wachtwoord herstellen
      </h2>
      {sent ? (
        <p role="status" className="max-w-[60ch]">
          {SENT}
        </p>
      ) : (
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
              aria-invalid={fields.email !== undefined}
              aria-describedby={
                fields.email !== undefined ? emailErrorId : undefined
              }
              onChange={(event) => setEmail(event.target.value)}
            />
            {fields.email !== undefined && (
              <p id={emailErrorId} role="alert" className="text-sm text-danger">
                {fields.email.join(" ")}
              </p>
            )}
          </div>
          <p>
            <button type="submit" className="button-accent" disabled={busy}>
              Stuur een herstellink
            </button>
          </p>
          {busy && (
            <p role="status" aria-live="polite" className="sr-only">
              Bezig.
            </p>
          )}
        </form>
      )}
      {failure !== null && (
        <p role="alert" className="text-danger">
          {failure}
        </p>
      )}
      <p>
        <button type="button" className="button-quiet" onClick={onBack}>
          Terug naar inloggen
        </button>
      </p>
    </section>
  );
}
```

- [ ] **Step 6: `ResetConfirmForm.tsx`**

```tsx
"use client";

import { useId, useState } from "react";
import { confirmPasswordReset } from "@/lib/accounts";
import { describeAuthError, fieldErrors } from "./messages";

/**
 * A new password, with the token that arrived in the fragment.
 *
 * The token is a prop and lives in the page's state; it is never rendered,
 * not in a hidden input and not in an attribute. A 400 under `token` is the
 * API's one sentence for expired, spent, superseded and unknown, hung on the
 * password field because it is the only field here, with the one button that
 * still helps: asking for a new link. A 400 under `password` is the same
 * list of sentences registration gives.
 *
 * After the 204 the page switches to signing in with a notice; nothing here
 * signs anybody in, because `login/` is the only place a session starts.
 */
export function ResetConfirmForm({
  token,
  onReset,
  onRequestNew,
}: {
  readonly token: string;
  readonly onReset: () => void;
  readonly onRequestNew: () => void;
}) {
  const passwordId = useId();
  const passwordErrorId = `${passwordId}-error`;
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [failure, setFailure] = useState<string | null>(null);
  const [fields, setFields] = useState<ReturnType<typeof fieldErrors>>({});

  const fieldMessage = fields.token ?? fields.password;

  async function submit(): Promise<void> {
    setBusy(true);
    setFailure(null);
    setFields({});
    try {
      await confirmPasswordReset({ token, password });
      onReset();
    } catch (error) {
      const perField = fieldErrors(error);
      setFields(perField);
      setFailure(
        Object.keys(perField).length > 0 ? null : describeAuthError(error),
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <section aria-labelledby="nieuw-wachtwoord" className="flex flex-col gap-6">
      <h2 id="nieuw-wachtwoord" className="text-2xl">
        Nieuw wachtwoord
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
          <label htmlFor={passwordId}>Nieuw wachtwoord</label>
          <input
            id={passwordId}
            type="password"
            autoComplete="new-password"
            value={password}
            aria-invalid={fieldMessage !== undefined}
            aria-describedby={
              fieldMessage !== undefined ? passwordErrorId : undefined
            }
            onChange={(event) => setPassword(event.target.value)}
          />
          {fieldMessage !== undefined && (
            <p id={passwordErrorId} role="alert" className="text-sm text-danger">
              {fieldMessage.join(" ")}
            </p>
          )}
        </div>
        <p>
          <button type="submit" className="button-accent" disabled={busy}>
            Wachtwoord opslaan
          </button>
        </p>
        {busy && (
          <p role="status" aria-live="polite" className="sr-only">
            Bezig.
          </p>
        )}
      </form>
      {failure !== null && (
        <p role="alert" className="text-danger">
          {failure}
        </p>
      )}
      {fields.token !== undefined && (
        <p>
          <button type="button" className="button-quiet" onClick={onRequestNew}>
            Wachtwoord vergeten?
          </button>
        </p>
      )}
    </section>
  );
}
```

- [ ] **Step 7: Groen, en de strings**

```bash
cd frontend && pnpm vitest run tests/account && pnpm typecheck && pnpm lint && pnpm format:check
```

Verwacht: de vier nieuwe testbestanden groen; `typecheck` mogelijk nog rood op de bestanden van taak 10 (zie taak 8 stap 4), en nergens anders. Regenereer daarna de strings en lees de diff:

```bash
cd frontend && pnpm build && UPDATE_UI_STRINGS=1 pnpm e2e language; git diff frontend/tests/ui-strings.txt
```

Verwacht in de diff, en niets anders: de nieuwe regels `Als dit adres bij ons bekend is, staat er binnen enkele minuten een e-mail voor u klaar. De link daarin werkt een uur.`, `Nieuw wachtwoord`, `Stuur een herstellink`, `Terug naar inloggen`, `Wachtwoord herstellen`, `Wachtwoord opslaan`, `Wachtwoord vergeten?`, `nieuw-wachtwoord`, `wachtwoord-herstellen`. Een regel die daar niet bij hoort is een string die per ongeluk in een component terecht is gekomen. Draai daarna `pnpm e2e language` zonder de variabele: groen.

- [ ] **Step 8: Toon aan dat twee controles rood kunnen worden**

Verander in `fragment.ts` tijdelijk `{43}` in `{40,}`: `fragment.test.ts` wordt rood op het geval met 44 tekens. Zet terug. Haal daarna in `ResetConfirmForm.tsx` `fields.token ??` uit `fieldMessage`: de test "hangs a token error on the password field" wordt rood op `toHaveAccessibleDescription`. Zet terug. Plak beide.

- [ ] **Step 9: Commit**

```bash
git add frontend/src/app/_account/fragment.ts frontend/src/app/_account/messages.ts frontend/src/app/_account/ResetRequestForm.tsx frontend/src/app/_account/ResetConfirmForm.tsx frontend/tests/account/fragment.test.ts frontend/tests/account/messages.test.ts frontend/tests/account/ResetRequestForm.test.tsx frontend/tests/account/ResetConfirmForm.test.tsx frontend/tests/ui-strings.txt
git commit
```

Boodschap: `feat(frontend): the token off the fragment, and the two forms that use it`.

---

### Taak 10: Frontend integratie: `AccountPage.tsx` en wat eromheen verandert

**Hangt af van:** taak 9.

**Files:**
- Modify: `frontend/src/app/_account/AccountPage.tsx`, `frontend/src/app/_account/SignInForm.tsx`, `frontend/src/app/_account/ConsentRow.tsx`, `frontend/src/app/_account/RegisterForm.tsx`, `frontend/tests/account/AccountPage.test.tsx`, `frontend/tests/account/ConsentRow.test.tsx`, `frontend/tests/account/RegisterForm.test.tsx`, `frontend/tests/account/SignInForm.test.tsx`, `frontend/tests/ui-strings.txt`, `tests/test_frontend_contract.py`

**Interfaces:**
- Consumes: `readRecoveryFragment`, `ResetRequestForm`, `ResetConfirmForm`, `confirmEmailVerification`, `requestEmailVerification`, `getMe`, `ConsentTexts.labels`, `Me.email_verified_at`.
- Produces: `SignedOutView` met `reset_request` en `reset_confirm`; `SignInForm({ onSignedIn, onRegister, onForgot })`; `ConsentCheckbox` en `ConsentRow` met `label` als prop en zonder `CONSENT_LABELS`; `AccountView` met de statusregel, de herstuurknop en de staande mededeling.

- [ ] **Step 1: De falende tests**

`frontend/tests/account/AccountPage.test.tsx`, een nieuw `describe` aan het eind:

```tsx
describe("a link with a token in its fragment", () => {
  const TOKEN = "F".repeat(43);

  afterEach(() => {
    window.history.replaceState(null, "", "/account/");
  });

  it("opens the new-password form on a reset fragment when nobody is signed in", async () => {
    window.history.replaceState(null, "", `/account/#herstel=${TOKEN}`);
    const { seen } = stub([
      { status: 401, body: { detail: "u bent niet ingelogd" } },
      { status: 200 },
      { status: 401, body: { detail: "u bent niet ingelogd" } },
    ]);
    render(<AccountPage />);
    expect(
      await screen.findByRole("heading", { name: "Nieuw wachtwoord" }),
    ).toBeInTheDocument();
    expect(window.location.hash).toBe("");
    expect(document.body.innerHTML).not.toContain(TOKEN);
    expect(seen.filter((url) => url.endsWith("/reset/confirm/"))).toHaveLength(0);
    expect(document.activeElement).toBe(document.body);
  });

  it("ignores a reset fragment when somebody is signed in", async () => {
    window.history.replaceState(null, "", `/account/#herstel=${TOKEN}`);
    stub([
      { status: 200, body: me },
      { status: 200, body: consentTexts },
    ]);
    render(<AccountPage />);
    expect(await screen.findByText(me.email)).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Nieuw wachtwoord" })).not.toBeInTheDocument();
  });

  it("returns to signing in with a notice after the password was saved", async () => {
    const userEvent = (await import("@testing-library/user-event")).default;
    window.history.replaceState(null, "", `/account/#herstel=${TOKEN}`);
    const { seen } = stub([
      { status: 401, body: { detail: "u bent niet ingelogd" } },
      { status: 200 },
      { status: 401, body: { detail: "u bent niet ingelogd" } },
      { status: 204 },
    ]);
    render(<AccountPage />);
    await userEvent.type(
      await screen.findByLabelText("Nieuw wachtwoord"),
      "een-ander-wachtwoord",
    );
    await userEvent.click(screen.getByRole("button", { name: "Wachtwoord opslaan" }));
    expect(await screen.findByRole("status")).toHaveTextContent(
      "Uw wachtwoord is gewijzigd. Log in met uw nieuwe wachtwoord.",
    );
    expect(screen.getByRole("heading", { name: "Inloggen" })).toBeInTheDocument();
    expect(seen.at(-1)).toContain("/api/auth/reset/confirm/");
    expect(seen.filter((url) => url.endsWith("/me/"))).toHaveLength(2);
  });

  it("confirms an address only after the first me/, and asks me/ again when signed in", async () => {
    window.history.replaceState(null, "", `/account/#verificatie=${TOKEN}`);
    const { seen } = stub([
      { status: 200, body: me },
      { status: 200, body: consentTexts },
      { status: 204 },
      { status: 200, body: { ...me, email_verified_at: "2026-09-06T10:00:00+00:00" } },
    ]);
    render(<AccountPage />);
    expect(await screen.findByText("Uw e-mailadres is bevestigd.")).toBeInTheDocument();
    const paths = seen.map((url) => new URL(url).pathname);
    expect(paths.indexOf("/api/auth/verify/confirm/")).toBeGreaterThan(
      paths.indexOf("/api/auth/me/"),
    );
    expect(paths.filter((path) => path === "/api/auth/me/")).toHaveLength(2);
    expect(await screen.findByText("E-mailadres bevestigd")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Verstuur de bevestigingsmail opnieuw" })).not.toBeInTheDocument();
  });

  it("confirms an address for a visitor who is not signed in, and shows the sign-in form", async () => {
    window.history.replaceState(null, "", `/account/#verificatie=${TOKEN}`);
    const { seen } = stub([
      { status: 401, body: { detail: "u bent niet ingelogd" } },
      { status: 200 },
      { status: 401, body: { detail: "u bent niet ingelogd" } },
      { status: 204 },
    ]);
    render(<AccountPage />);
    expect(await screen.findByText("Uw e-mailadres is bevestigd.")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Inloggen" })).toBeInTheDocument();
    expect(seen.filter((url) => url.endsWith("/me/"))).toHaveLength(2);
  });

  it("shows the API's sentence when the confirmation link is stale", async () => {
    window.history.replaceState(null, "", `/account/#verificatie=${TOKEN}`);
    stub([
      { status: 401, body: { detail: "u bent niet ingelogd" } },
      { status: 200 },
      { status: 401, body: { detail: "u bent niet ingelogd" } },
      { status: 400, body: { token: ["deze link is verlopen of al gebruikt; vraag een nieuwe aan"] } },
    ]);
    render(<AccountPage />);
    expect(await screen.findByRole("status")).toHaveTextContent(
      "deze link is verlopen of al gebruikt; vraag een nieuwe aan",
    );
  });
});

describe("the address line in the account view", () => {
  it("says the address is not yet confirmed, offers to resend, and says why it matters", async () => {
    const userEvent = (await import("@testing-library/user-event")).default;
    const { seen } = stub([
      { status: 200, body: me },
      { status: 200, body: consentTexts },
      { status: 202, body: {} },
    ]);
    render(<AccountPage />);
    expect(await screen.findByText("E-mailadres nog niet bevestigd")).toBeInTheDocument();
    expect(
      screen.getByText("Voor het koppelen van een slimme meter is een bevestigd e-mailadres nodig."),
    ).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Verstuur de bevestigingsmail opnieuw" }));
    expect(await screen.findByText("De bevestigingsmail is onderweg.")).toBeInTheDocument();
    expect(seen.at(-1)).toContain("/api/auth/verify/request/");
  });

  it("says the address is confirmed and offers nothing when it is", async () => {
    stub([
      { status: 200, body: { ...me, email_verified_at: "2026-09-06T10:00:00+00:00" } },
      { status: 200, body: consentTexts },
    ]);
    render(<AccountPage />);
    expect(await screen.findByText("E-mailadres bevestigd")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Verstuur de bevestigingsmail opnieuw" })).not.toBeInTheDocument();
    expect(document.body.textContent).not.toContain("2026-09-06");
  });

  it("says a mail is on its way right after registering", async () => {
    const userEvent = (await import("@testing-library/user-event")).default;
    stub([
      { status: 401, body: { detail: "u bent niet ingelogd" } },
      { status: 200 },
      { status: 401, body: { detail: "u bent niet ingelogd" } },
      { status: 200, body: consentTexts },
      { status: 201 },
      { status: 200, body: me },
      { status: 200, body: consentTexts },
    ]);
    render(<AccountPage />);
    await userEvent.click(
      await screen.findByRole("button", { name: "Nog geen account? Account aanmaken" }),
    );
    await userEvent.type(await screen.findByLabelText("E-mailadres"), "iemand@voorbeeld.nl");
    await userEvent.type(screen.getByLabelText("Wachtwoord"), "een-heel-lang-wachtwoord");
    await userEvent.click(screen.getByRole("button", { name: "Account aanmaken" }));
    expect(
      await screen.findByText("Er is een e-mail onderweg om uw adres te bevestigen."),
    ).toBeInTheDocument();
  });

  it("reaches the request form from the sign-in form and back", async () => {
    const userEvent = (await import("@testing-library/user-event")).default;
    stub([
      { status: 401, body: { detail: "u bent niet ingelogd" } },
      { status: 200 },
      { status: 401, body: { detail: "u bent niet ingelogd" } },
    ]);
    render(<AccountPage />);
    await userEvent.click(await screen.findByRole("button", { name: "Wachtwoord vergeten?" }));
    expect(screen.getByRole("heading", { name: "Wachtwoord herstellen" })).toBeInTheDocument();
    expect(document.activeElement).not.toBe(document.body);
    await userEvent.click(screen.getByRole("button", { name: "Terug naar inloggen" }));
    expect(screen.getByRole("heading", { name: "Inloggen" })).toBeInTheDocument();
  });
});
```

`frontend/tests/account/ConsentRow.test.tsx`: vervang de import van `CONSENT_LABELS` door niets, geef elke `<ConsentRow ... />` en `<ConsentCheckbox ... />` in dat bestand een `label={consentTexts.labels.<KIND>}` prop, en voeg toe:

```tsx
  it("carries no label of its own: the heading is a prop from the API", async () => {
    const source = await import("@/app/_account/ConsentRow");
    expect("CONSENT_LABELS" in source).toBe(false);
  });

  it("describes the toggle by the label and the sentence it was handed", () => {
    render(
      <ConsentRow
        kind="METER_LINK"
        label={consentTexts.labels.METER_LINK}
        text={consentTexts.texts.METER_LINK}
        granted={false}
        busy={false}
        onToggle={vi.fn()}
      />,
    );
    expect(screen.getByRole("button", { name: "Toestemming geven" })).toHaveAccessibleDescription(
      `${consentTexts.labels.METER_LINK} ${consentTexts.texts.METER_LINK}`,
    );
  });

  it("stands without a label when the texts could not be fetched, and says why granting is blocked", () => {
    render(
      <ConsentRow
        kind="METER_LINK"
        label={null}
        text={null}
        granted={false}
        busy={false}
        onToggle={vi.fn()}
      />,
    );
    const button = screen.getByRole("button", { name: "Toestemming geven" });
    expect(button).toBeDisabled();
    expect(button).toHaveAccessibleDescription(
      "De toestemmingstekst kon niet worden opgehaald. Intrekken kan wel, aanzetten niet.",
    );
  });
```

Lees `ConsentRow.test.tsx` eerst in zijn geheel: een bestaande test die de beschrijving van de knop op `label + text` legt (uit de fixgolf van 2026-09-06) blijft staan en krijgt alleen de prop erbij.

`frontend/tests/account/RegisterForm.test.tsx` en `frontend/tests/account/SignInForm.test.tsx`: lees ze; elke assertie die `CONSENT_LABELS` importeert of een label als literal vergelijkt, leest het label voortaan uit `consentTexts.labels`. In `SignInForm.test.tsx` komt één test bij:

```tsx
  it("offers to reset a forgotten password, in place of the sentence that said it could not", () => {
    const onForgot = vi.fn();
    render(<SignInForm onSignedIn={vi.fn()} onRegister={vi.fn()} onForgot={onForgot} />);
    expect(screen.queryByText(/kunnen wij het niet herstellen/)).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Wachtwoord vergeten?" }));
    expect(onForgot).toHaveBeenCalledTimes(1);
  });
```

en elke bestaande `render(<SignInForm ... />)` in dat bestand krijgt `onForgot={vi.fn()}` erbij.

`tests/test_frontend_contract.py`, twee tests erbij aan het eind:

```text
def test_no_consent_label_lives_in_the_frontend() -> None:
    """Decision 38 closed: the labels travel with the texts, so a copy in the
    frontend would be the drift `text_version` cannot see."""
    import sys

    sys.path.insert(0, str(REPO_ROOT / "backend"))
    from accounts.nl import NL

    labels = {key: NL[key] for key in ("CONSENT_LABEL_METER_LINK", "CONSENT_LABEL_LEAD_GENERATION")}
    offenders = [
        f"{path.relative_to(REPO_ROOT).as_posix()} carries {key}"
        for path in sorted(FRONTEND_SOURCE.rglob("*.ts*"))
        for key, label in labels.items()
        if label in path.read_text(encoding="utf-8")
    ]
    assert not offenders, "a consent label lives in the frontend as well as in nl.py:\n  " + "\n  ".join(
        offenders
    )


def test_the_fragment_accepts_exactly_the_token_length_the_backend_mints() -> None:
    """43 in fragment.ts and TOKEN_BYTES in recovery.py are one number written
    on two sides of a language boundary. Held together here."""
    import secrets
    import sys

    sys.path.insert(0, str(REPO_ROOT / "backend"))
    from accounts.recovery import TOKEN_BYTES

    fragment = (FRONTEND_SOURCE / "app" / "_account" / "fragment.ts").read_text(encoding="utf-8")
    declared = re.search(r"\{(\d+)\}\)\$/", fragment)
    assert declared, "fragment.ts no longer pins a token length"
    assert int(declared.group(1)) == len(secrets.token_urlsafe(TOKEN_BYTES))
```

- [ ] **Step 2: Zie ze falen**

```bash
cd frontend && pnpm vitest run tests/account && cd ..
POSTGRES_HOST=127.0.0.1 POSTGRES_PORT=5433 POSTGRES_DB=ampeer POSTGRES_USER=ampeer POSTGRES_PASSWORD=devtest uv run --no-sync pytest tests/test_frontend_contract.py -q
```

Verwacht: de nieuwe Vitest-tests rood (geen "Wachtwoord vergeten?", geen `label`-prop, `CONSENT_LABELS` bestaat nog), `test_no_consent_label_lives_in_the_frontend` rood op `ConsentRow.tsx`, de lengtetest groen.

- [ ] **Step 3: `ConsentRow.tsx`**

Verwijder `CONSENT_LABELS` en zijn docstring. `ConsentCheckbox` krijgt `readonly label: string` als prop en rendert `{label}` waar `CONSENT_LABELS[kind]` stond. `ConsentRow` krijgt `readonly label: string | null` en wordt in zijn kop:

```tsx
  const labelId = `consent-label-${kind.toLowerCase()}`;
  const textId = `consent-text-${kind.toLowerCase()}`;
  const explanationId = `consent-unavailable-${kind.toLowerCase()}`;
  const describedBy = [
    label === null ? null : labelId,
    text === null ? null : textId,
    unavailable ? explanationId : null,
  ]
    .filter((value): value is string => value !== null)
    .join(" ");
```

en de labelalinea wordt voorwaardelijk:

```tsx
      {label !== null && (
        <p id={labelId} className="font-medium">
          {label}
        </p>
      )}
```

Voeg aan de docstring van `ConsentRow` één alinea toe: "The label is a prop since 2026-09-06 and comes from the same `consent-texts/` answer as the sentence, under the same version (decision 38). When that answer could not be fetched there is no label either, and the description carries only the explanation; two rows then read alike, which is the same degradation this row already accepts for the sentence, reachable only while the API is down with the page open."

- [ ] **Step 4: `RegisterForm.tsx` en `SignInForm.tsx`**

`RegisterForm.tsx`: `<ConsentCheckbox ... />` krijgt `label={texts.labels[kind]}`. `SignInForm.tsx`: de props krijgen `readonly onForgot: () => void`; de alinea met de zin over "geen wachtwoordherstel" wordt vervangen door:

```tsx
      <p>
        <button type="button" className="button-quiet" onClick={onForgot}>
          Wachtwoord vergeten?
        </button>
      </p>
```

en de docstring van `SignInForm` verliest "and the one honest sentence underneath it"; in plaats daarvan: "Signing in, and the way out for somebody who cannot: the reset request stands where a sentence saying there was no reset stood until 2026-09-06."

- [ ] **Step 5: `AccountPage.tsx`**

De wijzigingen, in volgorde door het bestand:

Imports: `confirmEmailVerification`, `getMe`, `requestEmailVerification` erbij uit `@/lib/accounts`; `ResetConfirmForm`, `ResetRequestForm` en `readRecoveryFragment` uit hun modules.

```tsx
/** Which of the four signed-out forms is showing. State, not an address. */
type SignedOutView = "sign_in" | "register" | "reset_request" | "reset_confirm";
```

Drie constanten naast `DELETION_CONFIRMATION`, met dezelfde reden in hun commentaar:

```tsx
const PASSWORD_CHANGED = "Uw wachtwoord is gewijzigd. Log in met uw nieuwe wachtwoord.";
const ADDRESS_CONFIRMED = "Uw e-mailadres is bevestigd.";
const CONFIRMATION_MAIL_UNDERWAY = "Er is een e-mail onderweg om uw adres te bevestigen.";
```

In `AccountPage`: twee states erbij,

```tsx
  // The token off a reset link, held here and rendered nowhere. Read once,
  // before `me/` is asked, so the fragment is gone from the address bar
  // whatever `me/` answers.
  const [resetToken, setResetToken] = useState<string | null>(null);
  // What a confirmation link led to: nothing yet, the sentence for success,
  // or the API's sentence for a stale link. Rendered in a `role="status"`
  // above whichever view `me/` decided on.
  const [verification, setVerification] = useState<string | null>(null);
  // Whether the account view was reached by registering just now, which is
  // the one moment "a mail is on its way" is true and worth saying.
  const [justRegistered, setJustRegistered] = useState(false);
```

Het mount-effect wordt:

```tsx
  useEffect(() => {
    let alive = true;
    // The fragment first, and `me/` after it. Order is the rule of chapter 2:
    // nothing is posted before the first `me/` has come back, so a
    // confirmation link waits for it, and a reset token only decides a view.
    const fragment = readRecoveryFragment();
    if (fragment?.kind === "reset") {
      setResetToken(fragment.token);
      setView("reset_confirm");
    }
    void loadSession().then(async (next) => {
      if (!alive) return;
      setState(next);
      if (fragment?.kind !== "verify") return;
      try {
        await confirmEmailVerification({ token: fragment.token });
        if (!alive) return;
        setVerification(ADDRESS_CONFIRMED);
        if (next.status === "signed_in") {
          // A second `me/` after a change, so the address line below says
          // what the server now says. Not a retry: the first answer was
          // right at the time and the question has changed since.
          const refreshed = await getMe();
          if (alive) setState({ status: "signed_in", me: refreshed });
        }
      } catch (error) {
        if (!alive) return;
        const perField = fieldErrors(error);
        setVerification(
          perField.token === undefined
            ? describeAuthError(error)
            : perField.token.join(" "),
        );
      }
    });
    return () => {
      alive = false;
    };
  }, []);
```

Het commentaar boven `let alive = true;` blijft staan zoals het is. `signedIn` krijgt een tweede functie ernaast:

```tsx
  function registered(who: Me): void {
    setJustRegistered(true);
    signedIn(who);
  }
```

De rendering: boven `state.notice` komt de bevestigingsregel, zowel in de uitgelogde tak als vóór `<AccountView>` (zet daarvoor de `signed_in`-tak in een fragment met de regel erboven):

```tsx
      {verification !== null && (
        <p role="status" className="max-w-[60ch]">
          {verification}
        </p>
      )}
```

`AccountView` krijgt twee props erbij, `justRegistered: boolean` en niets anders; de `signed_in`-tak wordt:

```tsx
  if (state.status === "signed_in") {
    return (
      <div className="flex flex-col gap-8">
        {verification !== null && (
          <p role="status" className="max-w-[60ch]">
            {verification}
          </p>
        )}
        <AccountView
          me={state.me}
          focusHeadingOnMount={visitorActed}
          justRegistered={justRegistered}
          onSignedOut={(line) => {
            setVisitorActed(true);
            setConfirmation(line);
            setView("sign_in");
            setJustRegistered(false);
            setState(signedOut(null));
          }}
        />
      </div>
    );
  }
```

De uitgelogde `role="group"` kiest zijn `aria-labelledby` uit vier waarden en rendert vier formulieren:

```tsx
const GROUP_HEADING: Readonly<Record<SignedOutView, string>> = {
  sign_in: "inloggen",
  register: "registreren",
  reset_request: "wachtwoord-herstellen",
  reset_confirm: "nieuw-wachtwoord",
};
```

als moduleconstante, en in de JSX `aria-labelledby={GROUP_HEADING[view]}` met:

```tsx
        {view === "sign_in" && (
          <SignInForm
            onSignedIn={signedIn}
            onRegister={() => switchView("register")}
            onForgot={() => switchView("reset_request")}
          />
        )}
        {view === "register" && (
          <RegisterForm
            onRegistered={registered}
            onSignIn={() => switchView("sign_in")}
          />
        )}
        {view === "reset_request" && (
          <ResetRequestForm onBack={() => switchView("sign_in")} />
        )}
        {view === "reset_confirm" && resetToken !== null && (
          <ResetConfirmForm
            token={resetToken}
            onReset={() => {
              setResetToken(null);
              setVisitorActed(true);
              setConfirmation(PASSWORD_CHANGED);
              setView("sign_in");
            }}
            onRequestNew={() => {
              setResetToken(null);
              switchView("reset_request");
            }}
          />
        )}
```

Een `reset_confirm` zonder token kan alleen ontstaan als `onRequestNew` net liep, en dan is de view al gewisseld; de `&&` op `resetToken` houdt de typecheck eerlijk en rendert dan niets tot de volgende render.

In `AccountView`: één state erbij, `const [mailNotice, setMailNotice] = useState<string | null>(justRegistered ? CONFIRMATION_MAIL_UNDERWAY : null);`, één handeling erbij naast `signOut`:

```tsx
  async function resendConfirmation(): Promise<void> {
    markBusy("verify");
    setFailure(null);
    try {
      await requestEmailVerification();
      setMailNotice("De bevestigingsmail is onderweg.");
    } catch (error) {
      setFailure(describeAuthError(error));
    } finally {
      clearBusy("verify");
    }
  }
```

met `"verify"` toegevoegd aan `AccountActionId`. De JSX direct onder `<p>{me.email}</p>`:

```tsx
      <div className="flex flex-col gap-2">
        <p className="text-sm">
          {me.email_verified_at === null
            ? "E-mailadres nog niet bevestigd"
            : "E-mailadres bevestigd"}
        </p>
        {me.email_verified_at === null && (
          <>
            <p className="max-w-[60ch] text-sm text-ink-muted">
              Voor het koppelen van een slimme meter is een bevestigd
              e-mailadres nodig.
            </p>
            <p>
              <button
                type="button"
                className="button-quiet"
                disabled={busy.size > 0}
                onClick={() => void resendConfirmation()}
              >
                Verstuur de bevestigingsmail opnieuw
              </button>
              {busy.has("verify") && (
                <span role="status" aria-live="polite" className="sr-only">
                  Bezig.
                </span>
              )}
            </p>
          </>
        )}
        {mailNotice !== null && <p role="status">{mailNotice}</p>}
      </div>
```

De twee `<ConsentRow>`-aanroepen krijgen `label={texts === null ? null : texts.labels[kind]}`. Geen datum op het scherm: `me.email_verified_at` wordt alleen op `null` vergeleken en nergens getoond, precies zoals spec 6.4 zegt.

- [ ] **Step 6: Groen, en de strings**

```bash
cd frontend && pnpm vitest run && pnpm typecheck && pnpm lint && pnpm format:check
cd frontend && pnpm build && UPDATE_UI_STRINGS=1 pnpm e2e language; git diff frontend/tests/ui-strings.txt
```

Verwacht in de diff: weg is de regel `Bent u uw wachtwoord kwijt, dan kunnen wij het niet herstellen. Er is nog geen wachtwoordherstel, en zonder uw wachtwoord komt u ook niet meer bij de knop waarmee u uw account verwijdert.` en de twee labelregels `Doorgeven aan een installateur` en `Kwartiergegevens van uw slimme meter`; erbij komen `De bevestigingsmail is onderweg.`, `E-mailadres bevestigd`, `E-mailadres nog niet bevestigd`, `Er is een e-mail onderweg om uw adres te bevestigen.`, `Uw e-mailadres is bevestigd.`, `Uw wachtwoord is gewijzigd. Log in met uw nieuwe wachtwoord.`, `Verstuur de bevestigingsmail opnieuw`, `Voor het koppelen van een slimme meter is een bevestigd e-mailadres nodig.` Verander daarna met de hand de kop van het bestand: de zin "(the no-password-reset sentence, the deletion sentence)" wordt "(the deletion sentence, the sentence that linking a meter needs a confirmed address)". Draai `pnpm e2e language` zonder de variabele: groen, en `pnpm vitest run` nog een keer: alle Vitest-drempels boven 97 / 94 / 96 / 98.

Daarna de contractlaag:

```bash
POSTGRES_HOST=127.0.0.1 POSTGRES_PORT=5433 POSTGRES_DB=ampeer POSTGRES_USER=ampeer POSTGRES_PASSWORD=devtest uv run --no-sync pytest tests/test_frontend_contract.py -q
```

Verwacht: groen, inclusief `test_no_consent_label_lives_in_the_frontend`.

- [ ] **Step 7: Toon aan dat drie controles rood kunnen worden**

1. Verplaats in het mount-effect `readRecoveryFragment()` tot ná `loadSession()` en post de bevestiging vóór `setState(next)`: de test "confirms an address only after the first me/" wordt rood op de volgorde van de paden. Zet terug.
2. Laat de `signed_in`-tak het fragment niet negeren door `setView("reset_confirm")` ook te laten tellen als `state.status === "signed_in"`, wat betekent: render tijdelijk `<ResetConfirmForm>` boven `<AccountView>` als `resetToken !== null`: "ignores a reset fragment when somebody is signed in" rood. Zet terug.
3. Zet tijdelijk `CONSENT_LABELS` als exportconstante terug in `ConsentRow.tsx` met de twee labels: `test_no_consent_label_lives_in_the_frontend` rood met het pad in de melding, en de Vitest-test "carries no label of its own" rood. Zet terug.

Plak alle drie.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/app/_account/AccountPage.tsx frontend/src/app/_account/SignInForm.tsx frontend/src/app/_account/ConsentRow.tsx frontend/src/app/_account/RegisterForm.tsx frontend/tests/account/AccountPage.test.tsx frontend/tests/account/ConsentRow.test.tsx frontend/tests/account/RegisterForm.test.tsx frontend/tests/account/SignInForm.test.tsx frontend/tests/ui-strings.txt tests/test_frontend_contract.py
git commit
```

Boodschap: `feat(frontend): two more views on /account/, a link that confirms, and the labels from the API`.

---

### Taak 11: `e2e/account.spec.ts`

**Hangt af van:** taak 10.

**Files:**
- Modify: `frontend/e2e/account.spec.ts`

**Interfaces:**
- Consumes: `serveAuth`, `UNAUTHENTICATED`, `preflight`, de fixtures, en de axe-opzet die het bestand al heeft (de drie `test.describe`-blokken die `page.emulateMedia({ colorScheme })` en `new AxeBuilder({ page }).withTags([...])` gebruiken).
- Produces: vier tests en twee axe-rondes.

`theme.spec.ts` en `privacy.spec.ts` veranderen niet: zonder fragment post de pagina niets nieuws, en hun bestaande 401-stubs op `me/` en `refresh/` dekken de pagina zoals hij nu is. Als een van beide toch rood wordt, is dat een bevinding over taak 10 en geen reden om hier een stub toe te voegen.

- [ ] **Step 1: De vier tests**

Voeg toe, in een nieuw `test.describe("a link with a token in its fragment", ...)`:

```ts
const TOKEN = "e".repeat(43);

test.describe("a link with a token in its fragment", () => {
  test("a reset link opens the new-password form, clears the fragment, and ends on sign-in with a notice", async ({
    page,
  }) => {
    let confirmBody: unknown = null;
    await page.route("**/api/auth/reset/confirm/", async (route) => {
      if (route.request().method() === "OPTIONS") {
        await preflight(route);
        return;
      }
      confirmBody = route.request().postDataJSON();
      await route.fulfill({ status: 204, headers: CORS });
    });
    const counts = await serveAuth(page, {
      "/api/auth/me/": UNAUTHENTICATED,
      "/api/auth/refresh/": { status: 200, body: null },
    });
    await page.goto(`/account/#herstel=${TOKEN}`);
    await expect(page.getByRole("heading", { name: "Nieuw wachtwoord" })).toBeVisible();
    expect(new URL(page.url()).hash).toBe("");
    await expect(page.locator("body")).not.toContainText(TOKEN);
    await page.getByLabel("Nieuw wachtwoord").fill("een-ander-wachtwoord");
    await page.getByRole("button", { name: "Wachtwoord opslaan" }).click();
    await expect(page.locator("main").getByRole("status")).toContainText(
      "Uw wachtwoord is gewijzigd. Log in met uw nieuwe wachtwoord.",
    );
    await expect(page.getByRole("heading", { name: "Inloggen" })).toBeVisible();
    expect(confirmBody).toEqual({ token: TOKEN, password: "een-ander-wachtwoord" });
    expect(counts["/api/auth/me/"]).toBe(2);
    await expect(page.locator("body")).not.toContainText("advice API returned");
    await expect(page.locator("body")).not.toContainText("auth API returned");
  });

  test("asking for a link says the same sentence for a known and an unknown address", async ({
    page,
  }) => {
    const bodies: unknown[] = [];
    await page.route("**/api/auth/reset/request/", async (route) => {
      if (route.request().method() === "OPTIONS") {
        await preflight(route);
        return;
      }
      bodies.push(route.request().postDataJSON());
      await route.fulfill({
        status: 202,
        contentType: "application/json",
        headers: CORS,
        body: "{}",
      });
    });
    await serveAuth(page, {
      "/api/auth/me/": UNAUTHENTICATED,
      "/api/auth/refresh/": { status: 200, body: null },
    });
    await page.goto("/account/");
    await page.getByRole("button", { name: "Wachtwoord vergeten?" }).click();
    await expect(page.getByRole("heading", { name: "Wachtwoord herstellen" })).toBeVisible();
    await page.getByLabel("E-mailadres").fill("iemand@voorbeeld.nl");
    await page.getByRole("button", { name: "Stuur een herstellink" }).click();
    const sentence =
      "Als dit adres bij ons bekend is, staat er binnen enkele minuten een e-mail voor u klaar. De link daarin werkt een uur.";
    await expect(page.locator("main").getByRole("status")).toContainText(sentence);
    await expect(page.getByLabel("E-mailadres")).toHaveCount(0);
    // The mock answers 202 for every address, exactly as the API does. What
    // this proves is that the page shows one sentence and no second one: a
    // page that said "bekend" or "onbekend" would have to get it from somewhere,
    // and there is nowhere.
    expect(bodies).toEqual([{ email: "iemand@voorbeeld.nl" }]);
    await page.getByRole("button", { name: "Terug naar inloggen" }).click();
    await expect(page.getByRole("heading", { name: "Inloggen" })).toBeVisible();
  });

  test("a confirmation link posts after the first me/ and says the address is confirmed", async ({
    page,
  }) => {
    const order: string[] = [];
    await page.route("**/api/auth/verify/confirm/", async (route) => {
      if (route.request().method() === "OPTIONS") {
        await preflight(route);
        return;
      }
      order.push("confirm");
      await route.fulfill({ status: 204, headers: CORS });
    });
    await page.route("**/api/auth/me/", async (route) => {
      if (route.request().method() === "OPTIONS") {
        await preflight(route);
        return;
      }
      order.push("me");
      await route.fulfill({
        status: 401,
        contentType: "application/json",
        headers: { ...CORS, "set-cookie": "csrftoken=een-e2e-token; Path=/; SameSite=Strict" },
        body: JSON.stringify({ detail: "u bent niet ingelogd" }),
      });
    });
    await page.route("**/api/auth/refresh/", async (route) => {
      if (route.request().method() === "OPTIONS") {
        await preflight(route);
        return;
      }
      await route.fulfill({ status: 200, headers: CORS, body: "" });
    });
    await page.goto(`/account/#verificatie=${TOKEN}`);
    await expect(page.locator("main").getByRole("status")).toContainText("Uw e-mailadres is bevestigd.");
    await expect(page.getByRole("heading", { name: "Inloggen" })).toBeVisible();
    expect(new URL(page.url()).hash).toBe("");
    expect(order.indexOf("confirm")).toBeGreaterThan(order.indexOf("me"));
    expect(order.filter((entry) => entry === "confirm")).toHaveLength(1);
  });

  test("a stale confirmation link shows the API's sentence and nothing English", async ({
    page,
  }) => {
    await page.route("**/api/auth/verify/confirm/", async (route) => {
      if (route.request().method() === "OPTIONS") {
        await preflight(route);
        return;
      }
      await route.fulfill({
        status: 400,
        contentType: "application/json",
        headers: CORS,
        body: JSON.stringify({ token: ["deze link is verlopen of al gebruikt; vraag een nieuwe aan"] }),
      });
    });
    await serveAuth(page, {
      "/api/auth/me/": UNAUTHENTICATED,
      "/api/auth/refresh/": { status: 200, body: null },
    });
    await page.goto(`/account/#verificatie=${TOKEN}`);
    await expect(page.locator("main").getByRole("status")).toContainText(
      "deze link is verlopen of al gebruikt; vraag een nieuwe aan",
    );
    await expect(page.locator("body")).not.toContainText("API returned");
  });
});
```

De aparte `page.route`-handlers voor de nieuwe paden staan boven `serveAuth`, zoals de bestaande tests dat doen voor een route die een body moet vangen: Playwright evalueert de laatst geregistreerde handler eerst, en `serveAuth` werpt op een pad dat niet gepland is.

- [ ] **Step 2: De twee axe-rondes**

Lees het bestaande `test.describe` dat axe over de drie weergaven draait in beide paletten, en voeg in dezelfde vorm twee gevallen toe: de aanvraagweergave (na de klik op "Wachtwoord vergeten?") en de nieuw-wachtwoordweergave (na `goto` met `#herstel=`), elk onder `light` en `dark`, met `.withTags(["wcag2a", "wcag2aa", "wcag22aa"])` en `expect(results.violations).toEqual([])`.

- [ ] **Step 3: Draaien**

```bash
cd frontend && pnpm build && pnpm exec playwright test e2e/account.spec.ts
```

Verwacht: alle tests in het bestand groen, 22 plus de zes van deze taak. Daarna het hele pakket:

```bash
cd frontend && pnpm e2e
```

Verwacht: alles groen; `theme.spec.ts` en `privacy.spec.ts` onveranderd groen.

- [ ] **Step 4: Toon aan dat twee controles rood kunnen worden**

1. Verander in `fragment.ts` tijdelijk `window.history.replaceState(...)` in een no-op (commentarieer de aanroep): de eerste test wordt rood op `hash).toBe("")`. Zet terug, bouw opnieuw.
2. Laat `AccountPage.tsx` tijdelijk `confirmEmailVerification` aanroepen vóór `loadSession()` (verplaats de aanroep naar vóór de `void loadSession()`-regel): de derde test wordt rood op `indexOf("confirm")).toBeGreaterThan(...)`. Zet terug, bouw opnieuw.

Plak beide, met de build ertussen: een e2e-test leest `out/`, niet `src/`.

- [ ] **Step 5: Commit**

```bash
git add frontend/e2e/account.spec.ts
git commit
```

Boodschap: `test(e2e): the reset round, the request round and the confirmation round in a browser`.

---

### Taak 12: De stack-smoke tegen de echte stack

**Hangt af van:** taak 11.

**Files:**
- Modify: `tests/test_stack_smoke.py`, `infra/compose.test.yml`

**Interfaces:**
- Consumes: `_Session`, `_fresh_email`, `_assert_session_cookie_attributes`, `needs_stack`, `env_fixture_lines`, `main`; de vier routes; het `file`-transport; het command.
- Produces: `MAIL_FIXTURE_DIR`, `_run_outbox()`, `_link_from_newest_mail(kind)`, `test_live_a_reset_link_closes_the_loop`, `test_live_a_verification_link_sets_the_timestamp`; de env-fixture met vier namen erbij; de mount in de override.

- [ ] **Step 1: De override en de fixture**

`infra/compose.test.yml`, in `services.api`, naast `volumes`:

```yaml
    environment:
      # The file transport, for the two live checks that read a mail back
      # out of infra/fixtures/mail/. prod.py accepts this value for exactly
      # this stack and scripts/preflight_env.sh refuses it on a host.
      AMPEER_MAIL_FILE_DIR: /srv/mail
    volumes:
      - ./fixtures/nedu-flat-2025.csv:/srv/profiles/nedu.csv:ro
      # Writable, because the container writes here. Created by
      # tests/test_stack_smoke.py's main(), world-writable there for a Linux
      # host where the container's uid 10001 is nobody the developer knows.
      - ./fixtures/mail:/srv/mail
```

Lees eerst hoe `volumes` daar nu staat (één regel met het profiel) en voeg de tweede regel toe onder dezelfde sleutel; compose voegt lijsten van een override toe aan die van het basisbestand behalve op hetzelfde doelpad, en `/srv/mail` komt in het basisbestand niet voor.

`tests/test_stack_smoke.py`: constante `MAIL_FIXTURE_DIR = FIXTURES / "mail"` naast `ENV_FIXTURE`; in `env_fixture_lines`, na `"POSTGRES_HOST=db",`:

```text
        # The file transport: the two recovery checks read the mail back out
        # of infra/fixtures/mail/, which the override mounts on /srv/mail.
        # The only file in the repository that ever says `file`; the
        # preflight refuses it on a host.
        "AMPEER_MAIL_TRANSPORT=file",
        # Unused under the file transport and interpolated by compose all the
        # same. Not beginning with `re_`, the prefix of a real Resend key, so
        # this line can never be mistaken for one.
        "RESEND_API_KEY=smoke-check-placeholder-not-a-secret",
        # The reserved suffix again: nothing can ever be delivered to it.
        "AMPEER_MAIL_FROM=noreply@ampeer.smoke.invalid",
        # Where the links in a mail point, which for this stack is the
        # published port. The check reads the token off that link's fragment.
        "AMPEER_SITE_ORIGIN=http://127.0.0.1:8080",
```

In `test_the_environment_fixture_holds_no_value_that_could_be_mistaken_for_real`: het tuple van prefixen wordt `("DJANGO_SECRET_KEY=", "POSTGRES_PASSWORD=", "RESEND_API_KEY=")`, en één assertie erbij in de lus:

```text
        if line.startswith("RESEND_API_KEY="):
            assert not line.split("=", 1)[1].startswith("re_"), line
```

In `main()`, vóór het schrijven van de env-fixture:

```text
    MAIL_FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    # The api container runs as uid 10001 and writes here through the bind
    # mount. On Docker Desktop any uid may; on a Linux host the directory
    # would belong to the developer, so it is opened up. Best effort: chmod is
    # a no-op on Windows and this directory holds nothing but test mail.
    MAIL_FIXTURE_DIR.chmod(0o777)
```

en één regel in de uitvoer: `print(f"prepared {MAIL_FIXTURE_DIR}")`.

- [ ] **Step 2: De twee live checks en hun hulpen**

Na `test_live_a_stale_version_is_refused_over_the_real_route`:

```text
#: The override's project name, so the command below runs in the stack the
#: live checks are talking to and not in a production one. Read from the file
#: rather than written here, for the reason test_the_override_runs_under_a_project_name_of_its_own gives.
def _run_outbox() -> None:
    """Run send_outbound_mail once, inside the api container of the local stack.

    The timer that does this on a host does not exist on a developer machine,
    so the check does what the timer would: one run, foreground, exit code
    read. `--entrypoint python` for the reason the systemd unit gives.
    """
    import subprocess

    docker = shutil.which("docker")
    assert docker, "the live checks need docker on PATH to run the outbox command"
    subprocess.run(
        [
            docker,
            "compose",
            "-f",
            COMPOSE.as_posix(),
            "-f",
            OVERRIDE.as_posix(),
            "--env-file",
            ENV_FIXTURE.as_posix(),
            "run",
            "--rm",
            "--entrypoint",
            "python",
            "api",
            "backend/manage.py",
            "send_outbound_mail",
        ],
        check=True,
        timeout=120,
    )


def _link_token_from_newest_mail(fragment: str) -> str:
    """The token off the newest file the file transport wrote, and the file removed.

    Removed, so a second run of this file reads its own mail and not the
    previous run's, and so no working link stays on disk after the check.
    """
    files = sorted(MAIL_FIXTURE_DIR.glob("outbox-*.txt"), key=lambda path: path.stat().st_mtime)
    assert files, f"no mail was written to {MAIL_FIXTURE_DIR}; did the transport run at all?"
    newest = files[-1]
    text = newest.read_text(encoding="utf-8")
    newest.unlink()
    match = re.search(rf"http://127\.0\.0\.1:8080/account/#{fragment}=([A-Za-z0-9_-]{{43}})", text)
    assert match, f"the mail carries no {fragment} link:\n{text}"
    return match.group(1)


@needs_stack
def test_live_a_reset_link_closes_the_loop() -> None:
    """The whole recovery flow over one real connection, with the mail read
    back out of a file: request, send, follow, set, sign in, and the address
    confirmed on the way. No layer above this can prove that the link in the
    mail is the link the API accepts.
    """
    from accounts.nl import CONSENT_TEXT_VERSION

    assert STACK is not None
    session = _Session(STACK)
    session.request("GET", "/api/auth/me/")
    email = _fresh_email()
    session.json(
        "POST",
        "/api/auth/register/",
        {
            "email": email,
            "password": TEST_PASSWORD,
            "consent_meter_link": False,
            "consent_lead_generation": False,
            "text_version": CONSENT_TEXT_VERSION,
        },
    )
    session.json("POST", "/api/auth/logout/")
    # Registration queued a confirmation mail; send it now so the reset mail
    # below is the newest file and so nothing is left waiting.
    _run_outbox()
    _link_token_from_newest_mail("verificatie")

    answer = session.json("POST", "/api/auth/reset/request/", {"email": email})
    assert answer == {}
    _run_outbox()
    token = _link_token_from_newest_mail("herstel")

    status, payload = session.request(
        "POST",
        "/api/auth/reset/confirm/",
        {"token": token, "password": OTHER_PASSWORD},
        {"X-CSRFToken": session.cookies["csrftoken"]},
    )
    assert status == 204, payload
    assert not any(header.startswith("ampeer_") for header in session.set_cookie), (
        f"a reset signed somebody in: {session.set_cookie}"
    )

    status, _ = session.request(
        "POST",
        "/api/auth/login/",
        {"email": email, "password": TEST_PASSWORD},
        {"X-CSRFToken": session.cookies["csrftoken"]},
    )
    assert status == 401, "the old password still works after a reset"
    session.json("POST", "/api/auth/login/", {"email": email, "password": OTHER_PASSWORD})
    _assert_session_cookie_attributes(session, "login/ after a reset")
    me = session.json("GET", "/api/auth/me/")
    assert me["email_verified_at"] is not None, "a completed reset did not confirm the address"

    status, payload = session.request(
        "POST",
        "/api/auth/reset/confirm/",
        {"token": token, "password": OTHER_PASSWORD},
        {"X-CSRFToken": session.cookies["csrftoken"]},
    )
    assert status == 400 and b"token" in payload, (status, payload)
    session.json("POST", "/api/auth/delete/", {"password": OTHER_PASSWORD})


@needs_stack
def test_live_a_verification_link_sets_the_timestamp() -> None:
    """The mail registration itself queued, followed on a session that is not
    signed in, and `me/` afterwards saying when."""
    from accounts.nl import CONSENT_TEXT_VERSION

    assert STACK is not None
    session = _Session(STACK)
    session.request("GET", "/api/auth/me/")
    email = _fresh_email()
    session.json(
        "POST",
        "/api/auth/register/",
        {
            "email": email,
            "password": TEST_PASSWORD,
            "consent_meter_link": False,
            "consent_lead_generation": False,
            "text_version": CONSENT_TEXT_VERSION,
        },
    )
    assert session.json("GET", "/api/auth/me/")["email_verified_at"] is None
    _run_outbox()
    token = _link_token_from_newest_mail("verificatie")

    stranger = _Session(STACK)
    stranger.request("GET", "/api/auth/me/")
    status, payload = stranger.request(
        "POST",
        "/api/auth/verify/confirm/",
        {"token": token},
        {"X-CSRFToken": stranger.cookies["csrftoken"]},
    )
    assert status == 204, payload

    assert session.json("GET", "/api/auth/me/")["email_verified_at"] is not None
    session.json("POST", "/api/auth/delete/", {"password": TEST_PASSWORD})
```

Met `import shutil` bij de imports en `OTHER_PASSWORD` erbij in de import uit `helpers.accounts`. `test_every_live_check_is_gated_on_the_same_variable` ziet de twee nieuwe functies vanzelf.

- [ ] **Step 3: Zonder stack**

```bash
uv run --no-sync pytest tests/test_stack_smoke.py -q -rs
```

Verwacht: zes `SKIPPED` met de reden die de variabele noemt, de rest groen, inclusief `test_the_environment_fixture_names_every_variable_the_stack_reads`, dat sinds taak 6 rood was en nu de vier namen vindt. Haal daarna `@needs_stack` tijdelijk van `test_live_a_verification_link_sets_the_timestamp` en draai `tests/test_stack_smoke.py::test_every_live_check_is_gated_on_the_same_variable`: rood met "is not gated on". Zet terug. Plak.

- [ ] **Step 4: Tegen de echte stack**

Zoals `infra/README.md` sectie 7 beschrijft, met de fixtures opnieuw geschreven omdat de env-fixture vier namen erbij heeft:

```bash
uv run --no-sync python tests/test_stack_smoke.py
cd frontend && NEXT_PUBLIC_API_BASE= pnpm build && cd ..
docker compose -f infra/docker-compose.yml -f infra/compose.test.yml --env-file infra/fixtures/env.smoke build
docker compose -f infra/docker-compose.yml -f infra/compose.test.yml --env-file infra/fixtures/env.smoke up -d
docker compose -f infra/docker-compose.yml -f infra/compose.test.yml --env-file infra/fixtures/env.smoke run --rm --entrypoint python api backend/manage.py migrate --noinput
AMPEER_SMOKE_BASE_URL=http://127.0.0.1:8080 uv run --no-sync pytest tests/test_stack_smoke.py -q -rs
```

Verwacht: zes `PASSED` op de live checks en geen skip. De registratie in de twee nieuwe checks en in de bestaande spendt samen vier van `auth-register`'s vijf per uur per beller; draai de live suite één keer, en bij een 429 een verse stack (`down -v`, `up -d`, `migrate`) en niet een hoger tarief. Controleer na afloop dat `infra/fixtures/mail/` leeg is: de hulp verwijdert elk bestand dat hij las. Breek af met:

```bash
docker compose -f infra/docker-compose.yml -f infra/compose.test.yml --env-file infra/fixtures/env.smoke down -v
```

Plak de volledige uitvoer van de live run in het commitbericht, met datum en adres, zoals de vier bestaande live checks dat in `6d84840` deden. Slaat er een over terwijl de variabele gezet is, dan is dat een bevinding.

- [ ] **Step 5: mypy en ruff, dan commit**

```bash
uv run --no-sync mypy --strict tests
uv run --no-sync ruff check . && uv run --no-sync ruff format --check .
git add tests/test_stack_smoke.py infra/compose.test.yml
git commit
```

Boodschap: `test(smoke): a reset link and a confirmation link, read out of the mail and followed over the real stack`, met de uitvoer uit stap 4 in het lichaam.

---

### Taak 13: De documenten

**Hangt af van:** taak 12.

**Files:**
- Modify: `docs/decisions.md`, `docs/dpia.md`, `docs/superpowers/specs/2026-09-04-accounts-auth-design.md`, `docs/superpowers/specs/2026-09-05-accounts-frontend-design.md`

**Interfaces:**
- Consumes: alles uit taak 2 tot en met 12.
- Produces: zeven entries in `docs/decisions.md` (Engels, het bestaande formaat), twee bijgewerkte punten onder "What was not decided here", de DPIA-hoofdstukken 2, 5, 6, 7 en 10, en de twee eerdere ontwerpen bijgewerkt waar ze door dit ontwerp zijn ingehaald.

`docs/decisions.md` is Engels; de DPIA en de specs zijn Nederlands. Geen em-dash in een van de vier.

- [ ] **Step 1: De zeven entries**

Onder "The decisions", na entry 41, de nummers 42 tot en met 48:

```text
### 42. A password can be reset, and the token is a row rather than a signature

**Decided:** `POST /api/auth/reset/request/` and `POST /api/auth/reset/confirm/`
exist, and the link they exchange is backed by a row in `OneTimeToken` that
holds the sha256 of the token, `issued_at`, `expires_at`, `spent_at` and
`superseded_at`. Decision 31 is reversed. Its "to reverse" clause named
`django.contrib.auth.tokens.PasswordResetTokenGenerator`; that is not what was
built, and this entry says why.

**Because:** the generator hashes `last_login` into the token, which for a
reset is a merit and for a confirmation link a fault: a new account is signed
in the moment it is made, and the confirmation mail arriving a minute later
would already be dead. It also has no notion of "spent": a reset link stays
valid until the password changes, and a confirmation link changes nothing it
hashes over, so it would stay valid for seven days. One column, `spent_at`,
answers both, and the shape already existed: `RefreshSession` is a table that
holds no credential and still says which token was used when. Two
vocabularies on one pattern read better than two patterns. The row is locked
with `select_for_update` before it is read, in the same ordering
`tokens.rotate` argues for, so two confirmations with one link queue on it
and the second is refused. A reset does not sign the household in: `login/`
remains the only place a session starts and `LOGIN_SUCCEEDED` is written.

**Lives in:** `OneTimeToken` in `backend/accounts/models.py`,
`backend/accounts/recovery.py`, `ResetRequestView` and `ResetConfirmView` in
`backend/accounts/views.py`.

**To reverse:** remove the two routes and the table. The cost is the one
chapter 10 of the auth design named as the weakest point of that design: a
household that forgets its password cannot reach `delete/` and has no
self-service way back in.

### 43. Mail leaves through an outbox and a timer, not through the request and not through Celery

**Decided:** a request that needs a mail writes one `OutboundMail` row
(user, kind, when) and returns. `send_outbound_mail`, a management command
under `infra/systemd/ampeer-mail.timer`, sends every minute what is waiting,
mints the token as it sends, deletes the row on success and writes
`MAIL_SENT`, and backs off 1, 5, 15 and 60 minutes on a network fault, a
timeout, a 429 or a 5xx before giving up after 24 hours. A 4xx other than 429
fails at once.

**Because:** sending inside the request makes a view wait on an external
service, turns a provider outage into a 500 or a silent fault, and lets the
answer time differ between a known and an unknown address, which is the one
thing `reset/request/` may not do. Celery brings Redis, a worker and a third
container for two mails a day, and every design in this repository has
refused it for that reason. The outbox is the shape that already exists: the
two purge commands run under systemd timers, and this is the third. The
consequence that matters most is that no request a visitor can reach ever
opens a connection, so CLAUDE.md's rule that the backend never calls out
except to a fixed list stays categorical on the request path. The mint and
the send share one savepoint, so a mail that never left leaves no digest of a
token nobody received.

**Lives in:** `OutboundMail` in `backend/accounts/models.py`,
`backend/accounts/management/commands/send_outbound_mail.py`,
`infra/systemd/ampeer-mail.service`, `infra/systemd/ampeer-mail.timer`.

**To reverse:** call the transport from the views and drop the command and the
units. The costs are the three above, and `test_a_reset_request_answers_the_same_for_a_known_and_an_unknown_address`
would then be measuring only the body and not the time.

### 44. Resend is reached from one module on the allowlist, and Django's mail API is forbidden by the boundary test

**Decided:** `backend/accounts/mailer.py` is the only module under `backend/`
that imports `requests`, its destination is the literal
`https://api.resend.com/emails`, and `tests/test_boundaries.py` holds it to
the same rule as `pvgis.py`: named, never assembled, handed to the call as a
module constant. `django.core.mail` joins the forbidden network clients by its
dotted name, and `_imported_module_names` keeps dotted names so that check can
see it. No Resend SDK, no SMTP.

**Because:** the context reading for this cycle found a hole in the boundary
test that had been there since the first day: only the first segment of an
import was kept, so `from django.core.mail import send_mail` counted as
`django` and the categorical rule against outbound connections did not see
outbound mail through Django's own API, whose SMTP client lives in `.venv/`
where the scan never walks. This design does not use that API and closes the
hole anyway, because a known gap left open is a decision. One endpoint with
four fields needs no SDK, and an SDK would open connections from a package
the test never reads.

**Lives in:** `backend/accounts/mailer.py`, `OUTBOUND_MODULES`,
`NETWORK_CLIENTS` and `STRICT_DESTINATION_MODULES` in `tests/test_boundaries.py`.

**To reverse:** the reverse of decision 2 applies: add or remove a module in
that constant, on purpose, and say why the backend now reaches one more
place.

### 45. The recovery link carries its token in the fragment

**Decided:** the link in a mail is `https://ampeer.nl/account/#herstel=<token>`
or `#verificatie=<token>`. `/account/` reads the fragment once at load,
removes it from the address bar with `history.replaceState`, keeps the token
in page state and renders it nowhere.

**Because:** a fragment never leaves the browser. nginx does not see it, so
neither the access log nor Cloudflare does, and a `Referer` does not carry
it. Everything `/advies/<token>/` needed, a `location` with `try_files`, a
`serve.json` rule, a log-redaction `map` and a sentence in the DPIA about
Cloudflare seeing a second secret path, does not exist for this link because
there is nothing to redact. The principle from chapter 2 of the frontend
design, that a view is state and not an address, holds: the fragment names no
view, it carries a token, and what the page does with it depends on what
`me/` and the API answer. Exactly 43 url-safe characters, which is
`secrets.token_urlsafe(32)`, and `tests/test_frontend_contract.py` holds the
two sides of that number together.

**Lives in:** `frontend/src/app/_account/fragment.ts`, `_FRAGMENT` in
`backend/accounts/management/commands/send_outbound_mail.py`.

**To reverse:** move the token into a path and bring back the four things
above for it.

### 46. Verification is a timestamp, set by a confirmation or a completed reset, and read by nothing before phase 2

**Decided:** `User.email_verified_at` is a nullable `DateTimeField`. A
confirmation link sets it; a completed password reset sets it if it was
empty. Nothing in phase 1 reads it, `me/` reports it, and phase 2 requires it
before a meter is linked. Registration is not blocked on it.

**Because:** a timestamp answers the question a privacy document asks, which
is "when", and a flag cannot. A reset confirms the address because whoever
opened a link out of that mailbox holds that address, which is exactly what
confirmation establishes. The owner chose, on 2026-09-06, a stamp that phase
2 requires and that blocks nothing before it, over a registration that is
unusable until a mail is clicked: the first experience of every household
would otherwise be waiting for a mail.

**Lives in:** `email_verified_at` on `User` in `backend/accounts/models.py`,
`confirm_password_reset` and `confirm_email_verification` in
`backend/accounts/recovery.py`.

**To reverse:** make `login/` refuse an account whose stamp is empty. That is
one condition in `LoginView`, and it changes what a household is told on its
first visit, which is not a change to make in passing.

### 47. The consent labels travel with the texts under one version

**Decided:** `GET /api/auth/consent-texts/` answers `labels` beside `texts`,
both keyed by kind, both under `text_version`, and the frontend carries no
label of its own. Decision 38 is closed.

**Because:** decision 38 recorded that a label edit was invisible to
`text_version` while a text edit was not, and scheduled a versioned field
for the next backend touch. This is that touch. A separate `label_version`
was weighed and refused: label and text are read together and recorded
together, so one version for the pair is the honest form, and the rule from
decision 38 (a label may narrow only as far as the text still covers, and
never claim less than the row records) now sits as a comment beside the
constant it governs. `test_no_consent_label_lives_in_the_frontend` is what
keeps the frontend from growing a copy.

**Lives in:** `CONSENT_LABEL_METER_LINK` and `CONSENT_LABEL_LEAD_GENERATION`
in `backend/accounts/nl.py`, `ConsentTextsView` in `backend/accounts/views.py`,
`ConsentTexts.labels` in `frontend/src/lib/accounts.ts`.

**To reverse:** put the labels back in `ConsentRow.tsx` and delete the
contract test. The cost is the drift decision 38 described.

### 48. A reset request answers the same way for every address, and logs nothing for an unknown one

**Decided:** `POST /api/auth/reset/request/` answers 202 with `{}` for every
well-formed address, known, unknown, active or blocked. For a known active
address it writes one outbox row and one `PASSWORD_RESET_REQUESTED` line
carrying `user_id`, once per pending mail. For anything else it writes
nothing at all.

**Because:** a 202 and a 404 would be an address book readable at ten
requests an hour. The answer time is the same for the same reason the outbox
exists: no mail leaves and no token is minted inside the request, so a known
address costs one INSERT more than an unknown one. An audit line for an
unknown address would have to carry the address to mean anything, and
chapter 2 of the DPIA forbids exactly that in a table with no retention.

**Lives in:** `request_password_reset` in `backend/accounts/recovery.py`,
`ResetRequestView` in `backend/accounts/views.py`.

**To reverse:** answer 404 for an unknown address. `test_a_reset_request_answers_the_same_for_a_known_and_an_unknown_address`
is the test that would then be measuring an address book.
```

- [ ] **Step 2: De twee punten onder "What was not decided here"**

Vervang het punt dat begint met "**Whether the allowlist in CLAUDE.md should name a fourth source.**" (tot en met "Editing that document is not mine.") door een beantwoord punt, in de vorm die het document zelf gebruikt voor een beantwoorde vraag:

```text
- **Whether the allowlist in CLAUDE.md should name a fourth source.** Answered
  on 2026-09-06 rather than dropped. The owner had the sentence rewritten to
  name the destinations the repository actually reaches, PVGIS,
  energiedatawijzer.nl for the hand-run NEDU ingest, and api.resend.com for
  transactional mail, with ENTSO-E and KNMI marked as foreseen and not yet
  reached, and it now points at `OUTBOUND_MODULES` in `tests/test_boundaries.py`
  as the list itself. The licence findings that were recorded here on
  2026-09-02 stand: the NEDU files carry no reuse condition of any kind and
  stay out of the tree, and PVGIS is free to use without restriction.
```

Voeg aan het eind van de lijst een nieuw punt toe:

```text
- **Whether an account whose address is never confirmed is ever removed.** An
  account made with somebody else's address, or with a typo, stays: whoever
  made it can delete it, whoever holds the address can reset the password
  through the link and then delete it, and nothing does it for them. An
  automatic removal after some number of days is a retention period on a
  `User` row, which is a DPIA decision and not one to take inside a plan.
  It becomes a live question only once there are accounts nobody confirms,
  and chapter 10 of the DPIA does not list it yet for that reason.
```

En de zin "Six sit outside that document." wordt "Seven sit outside that document."; tel na het schrijven de punten in die lijst en laat het woord kloppen.

- [ ] **Step 3: De controle op dat bestand**

```bash
uv run --no-sync pytest tests/test_decisions.py -q
```

Verwacht: groen. Verander daarna tijdelijk `backend/accounts/recovery.py` in entry 42 in `backend/accounts/recover.py` en draai opnieuw: rood met dat pad. Zet met de hand terug. Plak.

- [ ] **Step 4: De DPIA**

Hoofdstuk 2, de paragraaf "Wat er niet is": voeg na de zin over `last_login` toe:

```text
Sinds het derde deel van fase 1 staat er ook `email_verified_at` bij: het
tijdstip waarop het adres is bevestigd via een link uit een mail, of leeg als
dat nooit is gebeurd. Een tijdstip en geen vlag, omdat "wanneer" de vraag is
die dit document stelt. Twee tabellen kwamen erbij en geen van beide draagt
een adres: `OneTimeToken` houdt de sha256 van een herstel- of
bevestigingslink met de tijdstippen van uitgifte, verloop en gebruik, en
`OutboundMail` houdt alleen wie een mail moet krijgen, van welke soort en
sinds wanneer; het adres wordt op het moment van verzenden van het account
gelezen en het token bestaat dan nog niet. Een tokenrij verdwijnt bij
verloop (`spent_at` blijft tot dan staan, want een gebruikt token dat nog
bestaat is wat hergebruik zichtbaar maakt), een outbox-rij bij verzending en
zeven dagen na een mislukking.
```

Hoofdstuk 5: vervang "Verder wordt niets uitbesteed. Er draait geen andere dienst van derden mee in de stack en er gaat geen gegeven naar een advertentie- of analysepartij." door:

```text
**Resend, Inc. is sinds het derde deel van fase 1 de tweede verwerker.** Hij
verstuurt de mails voor wachtwoordherstel en adresbevestiging, en ziet per
bericht het e-mailadres, het feit dat bij dat adres een account bestaat of om
herstel is gevraagd, en de inhoud van de mail, waarvan de link een uur of zeven
dagen een werkende sleutel is. Hij bewaart een eigen verzendlog met adres,
onderwerp en inhoud, en dat log staat in de Verenigde Staten, ongeacht de
verzendregio: Resend zegt zelf dat de regio bepaalt waar een mail vandaan
wordt verstuurd en niet waar accountdata, metadata en logs staan. De doorgifte
rust op de Standard Contractual Clauses in zijn Data Processing Addendum en op
zijn certificering onder het EU-US Data Privacy Framework; die DPA is
voorgetekend bij elk account en te downloaden uit het dashboard. De
verzendregio is de EU-regio (Ierland), zodat de mail zelf niet via een
Amerikaans datacenter loopt. Wat Resend niet ziet: de reden voor een
herstelverzoek, een wachtwoord, een toestemming of een advies. Alleen het
command `send_outbound_mail` bereikt Resend, onder een timer; geen enkel
verzoek van een bezoeker doet dat.

Verder wordt niets uitbesteed. Er gaat geen gegeven naar een advertentie- of
analysepartij.
```

Hoofdstuk 6, na de alinea "**Voor de dienst: naar een vaste lijst.**": voeg toe:

```text
Sinds het derde deel van fase 1 staat `api.resend.com` op die lijst, als
bestemming van het command dat de outbox leegt. Alleen dat command bereikt
die host, elke minuut onder een timer, en geen verzoek van een bezoeker; de
lijst zelf staat als `OUTBOUND_MODULES` in `tests/test_boundaries.py` en die
test valt om zodra een tweede module dezelfde host aanraakt of Django's eigen
mail-API ergens wordt geïmporteerd.
```

Hoofdstuk 7: vervang "met negen routes die geen van alle meer dan `get` of `post` beantwoorden. De negende is publiek en levert geen persoonsgegeven terug: hij geeft de toestemmingsteksten en de versie ervan, voor iedereen hetzelfde." door:

```text
met dertien routes die geen van alle meer dan `get` of `post` beantwoorden.
Vier daarvan zijn publiek zonder een persoonsgegeven terug te geven: de
toestemmingsteksten met hun labels en versie, voor iedereen hetzelfde, en de
drie routes waarmee een herstellink wordt aangevraagd, een herstellink wordt
gebruikt en een bevestigingslink wordt gebruikt. De aanvraag antwoordt voor
elk adres hetzelfde en zegt dus niet of er een account bij hoort.
```

En vervang de alinea die begint met "Diezelfde vraag om het wachtwoord heeft een keerzijde" (tot en met "het aantal accounts klein is.") door:

```text
Diezelfde vraag om het wachtwoord had tot het derde deel van fase 1 een
keerzijde: er was geen route om een vergeten wachtwoord te herstellen, dus wie
het kwijt was bereikte `/api/auth/delete/` niet meer. Die route bestaat nu.
`POST /api/auth/reset/request/` zet een mail klaar naar het adres van het
account, `POST /api/auth/reset/confirm/` zet met de link uit die mail een nieuw
wachtwoord, trekt elke sessie in en bevestigt het adres, en daarna werkt
inloggen, en dus ook verwijderen, met het nieuwe wachtwoord. De link werkt een
uur en een keer. Wie zijn wachtwoord kwijt is heeft daarmee weer een
zelfbedieningsweg, en de zwakste plek van het auth-ontwerp is dicht. Wat er
nog niet kan: het adres zelf wijzigen; wie een ander adres wil, verwijdert zijn
account en maakt een nieuw.
```

Hoofdstuk 10: "Vier dingen kan dit document niet" wordt "Vijf dingen kan dit document niet", en na punt 4 komt:

```text
5. **Resend als verwerker.** Drie deelvragen. Of de voorgetekende DPA van
   Resend volstaat als de verwerkersovereenkomst die artikel 28 vraagt, of dat
   er iets naast moet. Of de verzendregio in het dashboard van Resend op de
   EU-regio staat, wat een instelling is die dit document veronderstelt en
   niet kan controleren. En of opslag van het verzendlog in de Verenigde
   Staten, onder SCC's en het Data Privacy Framework, aanvaardbaar is voor deze
   dienst, of dat een Europese aanbieder de volgende backend-aanraking wordt.
   Wat daarbij hoort en niet als zesde punt staat, omdat het dezelfde vraag is
   als punt 2: de grondslag voor het bevestigen van een adres is geen van de
   twee toestemmingen. Dit document zet hem voorlopig op noodzaak voor de
   dienst, want zonder bevestigd adres kan de dienst geen wachtwoord herstellen
   en straks geen meter koppelen.
```

En in de slotalinea van hoofdstuk 10: "geen vastgelegde verwerkersovereenkomst met Cloudflare" wordt "geen vastgelegde verwerkersovereenkomst met Cloudflare en geen beoordeelde met Resend", en na "hoofdstuk 5 beschrijft wat Cloudflare op elk verzoek te zien krijgt." komt "en wat Resend per mail te zien krijgt. Voor het register: Resend, Inc., voor het versturen van herstel- en bevestigingsmails, ziet e-mailadres en berichtinhoud, bewaart een verzendlog in de Verenigde Staten, grondslag voor doorgifte SCC's en DPF, overeenkomst de voorgetekende DPA. Voor de privacyverklaring: dat een account een adres heeft, dat er mails naar dat adres gaan voor herstel en bevestiging en nergens anders voor, en dat een derde partij die mails aflevert."

- [ ] **Step 5: De twee eerdere ontwerpen**

`docs/superpowers/specs/2026-09-04-accounts-auth-design.md`: hoofdstuk 5.1, de routetabel krijgt vier rijen erbij en "Negen routes" eronder wordt "Dertien routes", met een verwijzing naar `docs/superpowers/specs/2026-09-06-accounts-recovery-design.md`:

```text
| `POST /api/auth/reset/request/` | publiek | `auth-reset` | 202 met `{}`, voor elk adres hetzelfde |
| `POST /api/auth/reset/confirm/` | publiek | `auth-reset` | 204; het token en het nieuwe wachtwoord |
| `POST /api/auth/verify/request/` | ingelogd | `auth-write` | 202 met `{}`; de bevestigingsmail opnieuw |
| `POST /api/auth/verify/confirm/` | publiek | `auth-reset` | 204; het token |
```

Hoofdstuk 10 daar, "Wachtwoordherstel ontbreekt, en wat dat kost": voeg bovenaan het hoofdstuk één alinea toe: "Dit hoofdstuk beschrijft de toestand tot 2026-09-06. `docs/superpowers/specs/2026-09-06-accounts-recovery-design.md` keert het om: er is wachtwoordherstel en e-mailbevestiging, via een outbox en Resend, met een token als rij en niet als handtekening. De redenering hieronder blijft staan als de reden waarom het niet in het eerste deel zat." Hoofdstuk 11 daar: het punt over wachtwoordherstel in de lijst van wat niet in v1 zit krijgt "(omgekeerd op 2026-09-06, zie hoofdstuk 10)".

`docs/superpowers/specs/2026-09-05-accounts-frontend-design.md`: hoofdstuk 6.1, de alinea die begint met "En één eerlijke zin: er is geen wachtwoordherstel." wordt:

```text
Tot 2026-09-06 stond hier één eerlijke zin: er is geen wachtwoordherstel.
`docs/superpowers/specs/2026-09-06-accounts-recovery-design.md` verving die zin
door een knop, "Wachtwoord vergeten?", die naar de aanvraagweergave uit dat
ontwerp leidt. De regel eronder blijft: wat op het scherm staat is wat waar is.
```

Hoofdstuk 10 daar: de twee punten "Geen wachtwoordherstel-UI" en "Geen e-mailverificatie" krijgen elk "(omgekeerd op 2026-09-06, zie het herstelontwerp)" erachter. Hoofdstuk 11: de regel bij `_account/ConsentRow.tsx` verliest "met `CONSENT_LABELS`" als die er staat, en zegt dat de labels sinds 2026-09-06 uit `consent-texts/` komen.

- [ ] **Step 6: De documentcontroles**

```bash
uv run --no-sync pytest tests/test_plans.py tests/test_decisions.py tests/test_dpia.py tests/test_pipeline_contract.py -q
```

Verwacht: alles groen behalve `test_a_plan_marked_in_progress_is_actually_unfinished[2026-09-06-accounts-recovery.md]`, die nu rood is omdat elk bestand dat dit plan noemt bestaat. Dat is de zelfvervallende marker uit taak 1 die zijn werk doet, en taak 14 zet hem om. Is hij niet rood, dan noemt dit plan nog een bestand dat niet bestaat en dat is de vraag om te beantwoorden voordat u verder gaat. `test_the_chapter_of_open_decisions_states_how_many_there_are` telt vijf punten en leest "Vijf". Controleer daarna op em-dashes:

```bash
grep -c $'\xe2\x80\x94' docs/decisions.md docs/dpia.md docs/superpowers/specs/2026-09-04-accounts-auth-design.md docs/superpowers/specs/2026-09-05-accounts-frontend-design.md
```

Verwacht: vier keer `0`.

- [ ] **Step 7: Commit**

```bash
git add docs/decisions.md docs/dpia.md docs/superpowers/specs/2026-09-04-accounts-auth-design.md docs/superpowers/specs/2026-09-05-accounts-frontend-design.md
git commit
```

Boodschap: `docs(decisions): seven decisions behind the recovery flow, and the DPIA's second processor`.

---

### Taak 14: De status omzetten en de poorten draaien

**Hangt af van:** taak 13.

**Files:**
- Modify: `docs/superpowers/plans/2026-09-06-accounts-recovery.md`, `pyproject.toml`, `frontend/vitest.config.ts`

**Interfaces:**
- Consumes: de statusregel uit taak 1; de vloeren.
- Produces: niets. Twee commits, geen pull request.

- [ ] **Step 1: Zie de rode test**

```bash
uv run --no-sync pytest tests/test_plans.py -q
```

Verwacht: `2026-09-06-accounts-recovery.md is marked 'in progress' and every file it names is in the tree. The work is done`. Dit is het bewijs voor de tweede tak van het paar uit taak 1: die tak wordt rood zodra het werk af is, uit zichzelf.

- [ ] **Step 2: Meet zonder `data/`**

De meting die telt is die van de runner, die het ingelezen NEDU-bestand niet heeft. Zet het opzij, meet, en zet het terug in hetzelfde commando zodat het nooit weg blijft:

```bash
NEDU=data/nedu-profiles-2025.csv; if [ -f "$NEDU" ]; then mv "$NEDU" "$NEDU.aside"; fi; POSTGRES_HOST=127.0.0.1 POSTGRES_PORT=5433 POSTGRES_DB=ampeer POSTGRES_USER=ampeer POSTGRES_PASSWORD=devtest uv run --no-sync pytest -m "not perf" --cov -q; echo "pytest exit=$?"; if [ -f "$NEDU.aside" ]; then mv "$NEDU.aside" "$NEDU"; fi; ls "$NEDU"
cd frontend && pnpm test
```

Noteer de `TOTAL`-regel en de vier Vitest-percentages. Dit is een meting op de boom vóór de omzetting; hij verandert niet door stap 3.

- [ ] **Step 3: Zet de status om**

Vervang bovenin dit bestand de regel

    **Status:** in progress

(hierboven met vier spaties ingesprongen weergegeven en niet als codeblok op kolom 0: `_STATUS` in `tests/test_plans.py` is met `^` verankerd in MULTILINE, dus een voorbeeld op kolom 0 zou een tweede treffer zijn) door, met de datum van de dag waarop dit gebeurt:

```
**Status:** delivered

> **Status op <datum>: opgeleverd.** Elk bestand dat dit plan noemt staat in
> de boom, wat `tests/test_plans.py` voor alle negen plannen controleert en wat
> rood wordt op de dag dat een ervan niet meer klopt. Wat die test niet kan
> zeggen is of elke stap is uitgevoerd zoals hij hier staat; daar zijn de
> commitgeschiedenis en de suite voor.
```

Eén gerichte bewerking van regel 5, nooit een replace-all. Controleer: `grep -c '^\*\*Status:\*\* in progress' docs/superpowers/plans/2026-09-06-accounts-recovery.md` geeft `0`, en `uv run --no-sync pytest tests/test_plans.py -q` is groen.

- [ ] **Step 4: De vloeren**

`pyproject.toml`, `fail_under`: het gemeten `TOTAL`-percentage uit stap 2 op twee decimalen, min één honderdste als het gemeten getal de vloer exact zou raken (het commentaar erboven zegt waarom: pytest-cov print dan FAIL bij exit 0). Nooit lager dan 99,05. `frontend/vitest.config.ts`: elk van de vier drempels naar het gemeten percentage naar beneden afgerond op een heel procent, nooit lager dan 97 / 94 / 96 / 98. Rood-bewijs per verhoogde vloer: zet hem tijdelijk één honderdste (Python) of één punt (Vitest) boven de meting, draai, exit 1; zet terug op de gekozen waarde, draai, exit 0. Plak beide transcripten. Eerste commit:

```bash
git add pyproject.toml frontend/vitest.config.ts
git commit
```

Boodschap: `test(coverage): raise the floors to what the branch measures on the runner`, met de oude en nieuwe getallen en de meting in het lichaam. Is geen enkele vloer gestegen, dan is er niets te committen en zegt het rapport dat met de meting erbij.

- [ ] **Step 5: Draai de Python-poorten**

```bash
uv run --no-sync pytest -q
bash scripts/gates.sh sync ruff ruff-format mypy shellcheck django-deploy-check pre-commit
bash scripts/gates.sh pytest perf
bash scripts/gates.sh bandit semgrep
bash scripts/gates.sh pip-audit sbom gitleaks
```

Beoordeel elke poort op de exitcode en nooit op een grep over de uitvoer. Voor `gitleaks` staat hier met opzet geen uitsluiting: de placeholder voor `RESEND_API_KEY` in de env-fixture begint niet met `re_` en de fixture is git-ignored; komt hier toch een melding, dan is dat een echte vondst. Let verder op:

- **`django-deploy-check`**: `manage.py check --deploy` onder prod-instellingen leest nu vier variabelen meer; de poort zet ze zelf of meldt welke ontbreekt. Een NOT RUN hier is geen pass.
- **`semgrep`**: leest `frontend/src`, dus ook `fragment.ts`; `history.replaceState` en `window.location` zijn geen klok en geen URL uit invoer. Een bevinding op `ampeer-no-url-from-user-input` of `ampeer-no-reading-the-clock` is een echte bevinding.
- **`bandit`**: `subprocess` in `tests/test_stack_smoke.py` valt buiten zijn bereik (beslissing 7); `mailer.py` bevat geen `assert` en geen shell.
- Een poort die NOT RUN meldt is geen geslaagde poort. Noteer welke.

- [ ] **Step 6: Draai de frontend-poorten**

```bash
bash scripts/gates.sh frontend-install frontend-lint frontend-typecheck frontend-format frontend-test frontend-build pnpm-audit e2e
```

Verwacht: acht keer pass. Is `e2e` NOT RUN omdat er geen browser staat, draai dan eerst `cd frontend && pnpm exec playwright install --with-deps chromium`. Een overgeslagen `e2e` is hier geen optie: zes van de controles in dit plan draaien alleen daar.

- [ ] **Step 7: Commit**

```bash
git add docs/superpowers/plans/2026-09-06-accounts-recovery.md
git commit
```

Boodschap: `docs(plans): the accounts recovery plan is delivered`.

De pull request gaat naar `dev` en daarna naar `main`, met alle vereiste checks groen. Nooit direct op `main`. Dit plan opent hem niet: het commit en verder niets. Wat de eigenaar daarna op de host doet staat in hoofdstuk 9 van de spec: het domein bij Resend, de vier variabelen in `/srv/ampeer/.env`, `preflight_env.sh` en `docker-compose.yml` opnieuw kopiëren omdat hun hashes zijn bewogen, en de twee units installeren.

---

## Zelfcontrole na het schrijven

### Dekking van de spec, hoofdstuk voor hoofdstuk

| Spec | Eis | Taak |
|---|---|---|
| 1 | binnen scope: tabel, veld, vier routes, kanaal, twee weergaven, labels, documenten; buiten scope: HTML, `api.ts`, Celery, nieuw pad, inloggen na herstel | 2, 5, 7, 9, 10, 4, 13; geen taak raakt `api.ts`, geen taak maakt een pad of een worker |
| 2.1 | `OneTimeToken` met zeven velden, 43 tekens, `token_digest`, `is_usable` | 2, 3 |
| 2.2 | één keer, onder `select_for_update`, geen `revoke_all`-tak | 3 (sequentieel plus AST) |
| 2.3 | een nieuw token vervangt het vorige | 3 |
| 2.4 | niet de generator | 13 (beslissing 42) |
| 2.5 | `email_verified_at`, gezet door bevestiging en herstel, migratie | 2, 3 |
| 3.1 | vier POST-routes op `_AuthAPIView`, `enforce_csrf` op de publieke, dertien in totaal | 5 |
| 3.2 | 202 identiek, geen log voor onbekend, geen netwerk in het verzoek | 3, 5 |
| 3.3 | token dan wachtwoord, `token_invalid`, validators met gebruiker, `revoke_all`, 204 zonder cookies | 3, 5 |
| 3.4 | `verify/request/` ingelogd en gededupliceerd, registratie zet klaar, `verify/confirm/` publiek, `me/` met het veld | 3, 5 |
| 3.5 | `auth-reset` 10/uur, de som 490, 73 keer | 5 |
| 3.6 | `recovery.py` naast `service.py`, de zes exports | 3 |
| 3.7 | labels in `consent-texts/` onder `text_version`, fixture, contracttest | 4, 10 |
| 4.1 | outbox in plaats van request of Celery | 7, 13 (beslissing 43) |
| 4.2 | `OutboundMail` zonder adres, token, onderwerp of body; één onverzonden per soort | 2, 3 |
| 4.3 | het token ontstaat bij het versturen | 7 |
| 4.4 | claim met SKIP LOCKED, mint en send in één transactie, backoff, 24 uur, 4xx, `--check`, opruiming | 7 |
| 4.5 | `mailer.py`: literal, `requests`, timeout 10, Bearer, idempotentiesleutel, geen SDK | 6 |
| 4.6 | drie transporten, `prod.py` weigert `memory`, preflight weigert alles behalve `resend`, de vier variabelen, de placeholders | 6, 12 |
| 4.7 | de grenstest strenger: gepunte namen, `django.core.mail`, derde module, tuple van strikte modules | 6 |
| 4.8 | de units, de README, de deploy-stap | 7 |
| 5.1 | vier auditsoorten, `provider_id`, nooit adres of token, geen regel voor een geweigerde link | 2, 7, 3 |
| 5.2 | wat Resend ziet en bewaart | 13 |
| 5.3 | DPIA hoofdstuk 2, 5, 6, 7, 10 | 2, 7, 13 |
| 5.4 | de regels voor register en verklaring | 13 |
| 6.1 | fragment, `replaceState`, `readRecoveryFragment`, toestand geen adres | 9, 10 |
| 6.2 | twee weergaven, de knop, de zinnen na 202 en 204, `token` aan het wachtwoordveld, genegeerd bij 200 | 9, 10 |
| 6.3 | bevestiging na de eerste `me/`, tweede `me/` bij 200, de zin bij 400 | 10, 11 |
| 6.4 | de statusregel zonder datum, de herstuurknop, de staande mededeling, na registratie | 10 |
| 6.5 | vier aanroepen, `Me.email_verified_at`, `labels`, `token` in `AccountField`, dezelfde commit als de routes | 8, 9 |
| 6.6 | `ui-strings.txt`: de zin weg, de kop bijgewerkt, de nieuwe zinnen via regeneratie | 9, 10 |
| 6.7 | geen focus bij aankomst, `role="alert"` alleen voor formulieren, `describedby`, axe | 10, 11 |
| 7 | elke zin één thuis, geen Engels bereikbaar, de exacte zinnen | 4, 9, 10 |
| 8.1 | laag 1 | 2, 3, 5, 6, 7 |
| 8.2 | laag 2 | 8, 9, 10 |
| 8.3 | laag 3 | 11 |
| 8.4 | laag 4 | 4, 5, 8, 10 |
| 8.5 | laag 5 | 12 |
| 8.6 | de vloeren op de runner | 14 |
| 9 | deploy: wat de eigenaar doet, de deploy-job, `--no-interpolate` | 6, 7, 14 (de slotalinea) |
| 10 | wat niet in v1 zit | geen taak bouwt het; 13 noteert onbevestigde accounts |
| 11 | de bestandenlijst | elk bestand daaruit staat in precies één Files-blok, behalve de gedeelde die de bezitstabel noemt |
| 12 | definition of done | 12 en 14 draaien wat de punten afdwingt |
| 13 | de zeven beslissingen | 13 |

Twee dingen die deze doorloop opleverde en die zijn gerepareerd in plaats van genoteerd. Het eerste: hoofdstuk 11 noemt `infra/fixtures/mail/.gitkeep`, en dat bestand kan niet bestaan omdat `.gitignore` de hele map negeert; het plan laat `main()` de map maken en noemt het bestand nergens in een Files-blok, zodat `test_every_file_a_finished_plan_names_exists` er niet op valt. Het tweede: hoofdstuk 11 zet `me-response.json` bij de frontend, terwijl `test_the_me_fixture_has_the_shape_the_view_answers` hem rood maakt zodra `me/` verandert; de fixture staat daarom in taak 5.

### Plaatshouders

Doorzocht op `TBD`, `TODO`, `vergelijkbaar met taak`, `similar to task`, `naar behoefte`, `nader te bepalen`, `appropriate` en `...`. De drie `...` die overblijven staan in taak 3 stap 5 ("laat de `raw =`-regel staan"), in taak 5 stap 8 als beschrijving van een tijdelijke bewerking, en in taak 14 stap 3 als `<datum>`, dat de dag van uitvoering is en geen weggelaten waarde. Geen enkele stap zegt "doe hetzelfde als hierboven".

### Namen die over taakgrenzen heen moeten kloppen

Gecontroleerd op elke plek waar ze voorkomen: `OneTimeToken`, `OutboundMail`, `PASSWORD_RESET`, `EMAIL_VERIFY`, `KINDS`, `LIFETIMES`, `is_usable`, `email_verified_at`, `TOKEN_BYTES`, `TokenInvalid`, `PasswordRejected`, `mint`, `enqueue`, `request_password_reset`, `confirm_password_reset`, `request_email_verification`, `confirm_email_verification`, `password_error_messages`, `ResetRequestSerializer`, `TokenSerializer`, `ResetConfirmSerializer`, `ResetRequestView`, `ResetConfirmView`, `VerifyRequestView`, `VerifyConfirmView`, `auth-reset`, `token_invalid`, `CONSENT_LABEL_METER_LINK`, `CONSENT_LABEL_LEAD_GENERATION`, `MAIL_RESET_SUBJECT`, `MAIL_RESET_BODY`, `MAIL_VERIFY_SUBJECT`, `MAIL_VERIFY_BODY`, `RESEND_ENDPOINT`, `TIMEOUT_SECONDS`, `Message`, `TransportError`, `Transport`, `ResendTransport`, `FileTransport`, `MemoryTransport`, `MEMORY`, `transport`, `AMPEER_MAIL_TRANSPORT`, `AMPEER_MAIL_FROM`, `AMPEER_SITE_ORIGIN`, `AMPEER_MAIL_FILE_DIR`, `RESEND_API_KEY`, `BACKOFF`, `GIVE_UP_AFTER`, `OVERDUE_AFTER`, `PASSWORD_RESET_REQUESTED`, `PASSWORD_RESET_COMPLETED`, `EMAIL_VERIFIED`, `MAIL_SENT`, `provider_id`, `STRICT_DESTINATION_MODULES`, `requestPasswordReset`, `confirmPasswordReset`, `requestEmailVerification`, `confirmEmailVerification`, `ResetRequestInput`, `ResetConfirmInput`, `VerifyConfirmInput`, `readRecoveryFragment`, `RecoveryFragment`, `ResetRequestForm`, `ResetConfirmForm`, `onBack`, `onReset`, `onRequestNew`, `onForgot`, `SignedOutView`, `GROUP_HEADING`, `PASSWORD_CHANGED`, `ADDRESS_CONFIRMED`, `CONFIRMATION_MAIL_UNDERWAY`, `justRegistered`, `MAIL_FIXTURE_DIR`, `_run_outbox`, `_link_token_from_newest_mail`. Drie dingen die tijdens die doorloop zijn rechtgetrokken: `enqueue` geeft een `bool` terug omdat de auditregel eraan hangt; `_lock` en `_spend` zijn twee functies omdat de validators tussen die twee in moeten; en `STRICT_DESTINATION_MODULE` heet nu `STRICT_DESTINATION_MODULES` omdat het een tuple is.

### Kan elke rode-proef echt vuren

Per taak nagelopen. Taak 1: de markering weghalen laat de strenge lezing twintig ontbrekende bestanden vinden; de tweede tak wordt in taak 14 stap 1 uit zichzelf rood. Taak 2: een soort uit de DPIA-lijst halen raakt de gelijkheid; `superseded_at` uit `is_usable` halen raakt de tweede assertie van de waarheidstabel. Taak 3: de `update` weghalen raakt de supersede-test, de validatie verplaatsen raakt de "spend nothing"-test, het slot weghalen raakt de AST-test. Taak 4: één letter in de fixture raakt de byte-vergelijking. Taak 5: een 404 voor onbekend raakt de gelijkheid van twee antwoorden, de aanroep uit `RegisterView` halen raakt de outbox-telling. Taak 6: een tijdelijk bestand met `django.core.mail` raakt de gelijkheid over de hele mapping, `smtplib` in `mailer.py` ook, een URL-literal in de aanroep raakt de constante-controle, het `case`-blok uit de preflight raakt drie geparametriseerde gevallen. Taak 7: de binnenste transactie weghalen laat een digest achter, `_retryable` op `True` laat een 401 doorgaan, `provider_id` uit de tabel halen raakt de sleutelwoordvergelijking. Taak 8: één letter in een pad raakt de padcontrole. Taak 9: `{40,}` raakt het geval met 44 tekens, `fields.token ??` weghalen raakt de beschrijving van het veld. Taak 10: de volgorde van fragment en `me/` omdraaien raakt de padvolgorde, het fragment bij een 200 wel tonen raakt de negeertest, `CONSENT_LABELS` terugzetten raakt de contracttest. Taak 11: `replaceState` uitzetten raakt de hash-assertie, de bevestiging vóór `me/` posten raakt de volgorde. Taak 12: de decorator weghalen maakt de poort om de poort rood. Taak 13: een pad verminken maakt `tests/test_decisions.py` rood. Taak 14: een vloer boven de meting geeft exit 1.

Eén proef die in een eerdere opzet van dit plan stond en is geschrapt omdat hij niet kon vuren: een test met twee threads op één token onder `transaction=True`, die op Postgres soms slaagt en soms niet afhankelijk van welke thread het slot eerst neemt. Hij is vervangen door de sequentiële test plus de AST-lezing van het slot, en het plan zegt waarom in de lijst van elf dingen.

### Zijn de afhankelijkheden eerlijk over gedeelde bestanden

`backend/accounts/views.py` wordt door taak 4 en 5 geschreven, in die volgorde. `tests/test_accounts_recovery.py` door 3 en 5. `tests/test_accounts_api.py` door 4 en 5. `backend/ampeer/settings/base.py` door 5 en 6. `tests/test_accounts_mail.py` door 6 en 7. `tests/test_dpia.py` en `docs/dpia.md` door 2, 7 en 13. `.github/workflows/deploy.yml` door 6 en 7. `tests/test_stack_smoke.py` door 7 en 12. `tests/test_frontend_contract.py` door 4 en 10. `frontend/tests/ui-strings.txt` door 9 en 10. Geen enkel bestand wordt door twee taken geschreven die niet in een `Hangt af van`-keten aan elkaar vastzitten, en de keten is de serie zelf.

### De markering

De regel `**Status:** in progress` staat op regel 5, op kolom 0, en komt in die vorm precies één keer in dit document voor. Het voorbeeld ervan in taak 14 staat vier spaties ingesprongen, zoals het commentaar in `tests/test_plans.py` voorschrijft. Er staat wel een tweede statusregel op kolom 0: de `**Status:** delivered` in het codeblok van taak 14, die laat zien wat er komt te staan. `_STATUS.search` geeft alleen de eerste treffer terug en die staat op regel 5, en de omzetting in taak 14 is één gerichte bewerking van die ene regel en geen replace-all.
