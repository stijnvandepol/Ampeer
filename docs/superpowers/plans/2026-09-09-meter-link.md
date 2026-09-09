# De meterkoppeling: implementatieplan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Status:** delivered

> **Status op 2026-09-09: opgeleverd.** Elk bestand dat dit plan noemt staat
> in de boom. `tests/test_plans.py` controleert dat voor alle plannen in
> `docs/superpowers/plans/`, en het wordt rood op de dag dat een van hen niet
> meer klopt. Wat die test niet kan zeggen is of elke stap is uitgevoerd zoals
> hij hier staat; daar zijn de commitgeschiedenis en de suite voor.
>
> Vier dingen liepen anders dan hier staat, en ze staan hier omdat een plan
> dat zijn eigen afwijkingen verzwijgt de volgende lezer misleidt. Het veld
> heet `push_path` en niet `push_url`. De testbestanden van de frontend staan
> in `frontend/tests/account/` en niet in `frontend/tests/app/`. Drie van de
> rode proeven die hier voorgeschreven staan bleken groen te blijven en zijn
> door de uitvoerders vervangen door mutaties die wel bijten; dat staat per
> geval in het commentaar van de test zelf. En de duwroute geeft de datum als
> woorden terug in plaats van de pagina hem te laten opmaken, omdat
> `.semgrep/frontend.yml` het frontend verbiedt de klok te lezen.

**Goal:** Een huishouden met een bevestigd e-mailadres en toestemming `METER_LINK` koppelt zijn slimme meter, krijgt eenmalig een sleutel, duwt daarmee kwartierstanden naar `POST /api/meter/readings/`, ziet op `/account/` wanneer er voor het laatst iets binnenkwam, en ontkoppelt met een druk op de knop waarna de metingen weg zijn. Kwartieren ouder dan negentig dagen worden uurtotalen. Het advies blijft synthetisch: de motorkoppeling is Fase 3 en zit hier niet in.

**Architecture:** Vier tabellen erbij onder `backend/accounts/`, geen nieuwe app: `MeterLink` naast `RefreshSession` en `OneTimeToken` met dezelfde vorm (afdruk in de kolom, sleutel nergens), en `QuarterReading` en `HourAggregate` eronder aan `MeterLink` met CASCADE. Drie sessieroutes onder `/api/auth/` en een vierde route buiten de sessie met een eigen authenticatieklasse die op de afdruk zoekt. De opruiming is een management command met een systemd-timer, in dezelfde vorm als `purge_expired_sessions` en `send_outbound_mail`. Op de frontend een servercomponent-loos blok in `frontend/src/app/_account/`, naast `ConsentRow`, dat drie toestanden kent.

**Tech Stack:** Django 5.2 + DRF, Python 3.12; Next 16, React 19, TypeScript 5.9 strict, Tailwind 4, Vitest, Playwright, pnpm; pytest + pytest-cov met branch coverage.

**Spec:** docs/superpowers/specs/2026-09-09-meter-link-design.md

## Global Constraints

- Nederlands is wat een gebruiker leest; Engels is code, identifiers, comments, docstrings, testnamen en commitboodschappen.
- Geen em-dash (U+2014), nergens.
- Geld is `Decimal`, energie is float. Kilowattuur is dus `float`, ook in de modellen en in de serializer.
- Alle tijdstempels in UTC opslaan.
- `backend/accounts/mailer.py` blijft de enige module onder `backend/` die `requests` importeert. `OUTBOUND_MODULES` in `tests/test_boundaries.py` blijft de vaste lijst van drie. Deze cyclus haalt niets op: meterdata komt binnen via push.
- Ingest-tokens gehasht opslaan, nooit in plaintext. De sleutel bestaat alleen in het geheugen van het verzoek dat hem maakt en in het antwoord daarop.
- Elk queryset filtert op `request.user` of op de koppeling die bij de aangeboden sleutel hoort, nooit alleen op pk.
- Elke route heeft een throttle-scope met een rate; `tests/test_backend_settings.py` loopt de resolver af en wordt rood zonder.
- De dekkingsvloer `fail_under = 98.73` met `precision = 2` mag omhoog en nooit omlaag. De vier Vitest-drempels ook niet.
- De jobnamen `quality`, `test`, `dependencies`, `sast` en `secrets` blijven zoals ze zijn.
- Beoordeel elke poort op de exitcode, nooit op een grep over de uitvoer van een tool.
- Elk test- en poortcommando draait op de voorgrond, nooit met een achtergrondoptie en nooit door een pipe naar `head` of `tail`.
- Werk op `feat/meter-link`. Nooit direct op `main`, nooit op `dev`.
- Voor elke nieuwe controle geldt: toon aan dat hij rood kan worden, en zet de tijdelijke bewerking daarna met de hand terug. Nooit `git checkout --`, `git restore`, `git stash` of `git reset`.
- Python-code in dit document staat in `text`-fences: de `ruff-format` pre-commit hook herschrijft `python`-fences in markdown.

---

## Het werkmodel

Dit plan draait in **drie sporen die elkaars bestanden niet aanraken**, en binnen een spoor strikt serieel. Dat wijkt af van de gebruikelijke serie van een enkel spoor, en de reden staat hieronder bij "Waarom drie sporen".

1. **Een taak bezit zijn paden exclusief.** De tabel per spoor zegt welke. Twee sporen delen geen enkel pad; waar ze elkaar raken is dat via een test die pas groen wordt als beide zijn geland, en dat is per geval hieronder benoemd.
2. **Uitvoerende agents committen, en niets daarbuiten.** Elke taak commit op `feat/meter-link`, met alleen de bestanden gestaged die zijn eigen Files-blok noemt. Nooit `push`, `rebase`, `checkout`, `amend`, `merge` of een andere branch.
3. **Poorten draaien na de sporen**, door de controller, niet in de taken. Wat een taak zelf draait staat in zijn Verify-blok en is altijd een gericht commando.
4. **Een taak die niet verder kan zonder een bestand aan te raken dat hij niet bezit, stopt en meldt dat.**
5. **Geen commit draagt een test die de taak zelf rood weet**, behalve de drie kruisverbanden die hieronder met naam en toenaam staan.

### Waarom drie sporen

De backend, de frontend en de documenten delen in deze cyclus geen enkel bestand. De frontend schrijft tegen de routevorm die de spec vastlegt en niet tegen de draaiende backend; de documenten beschrijven de constanten die het backendspoor schrijft. Serieel draaien zou drie keer dezelfde wachttijd kosten voor werk dat niets van elkaar nodig heeft. Wat het kost als dit fout is: een tussentoestand waarin de boom niet groen is. Dat is aanvaard, en de controller draait de poorten pas als alle drie de sporen klaar zijn.

### De drie kruisverbanden, vooraf benoemd

| Test | Rood vanaf | Groen na |
|---|---|---|
| `tests/test_dpia.py::test_the_audit_log_records_exactly_what_the_document_says_it_does` | A1 (twee soorten erbij) | C1 (hoofdstuk 2 noemt ze) |
| `tests/test_frontend_contract.py` (paden in `accounts.ts` naast `urls.py`) | B1 (vier paden erbij) | A2 en A3 (de routes bestaan) |
| `tests/test_dpia.py` retentietabel | A4 (een tabel met een bewaartermijn erbij) | C1 |

Geen andere test hoort tijdens de rit rood te staan. Wordt er een vierde gevonden, dan meldt de taak dat en gaat niet raden.

---

## Spoor A: de backend

| Taak | Hangt af van |
|---|---|
| A1. De modellen, de migratie, de logsoorten, de zinnen | niets |
| A2. De duwroute | A1 |
| A3. De drie sessieroutes, het intrekken, de export | A2 |
| A4. De opruiming en de timer | A1 |

A4 hangt alleen van A1 af en kan naast A2 draaien, maar deelt met A3 geen bestand alleen als A3 `settings/base.py` niet aanraakt en A4 wel. Om dat simpel te houden draait spoor A gewoon A1, A2, A3, A4 achter elkaar.

### Taak A1: De modellen, de migratie, de logsoorten en de zinnen

**Files:**
- Modify: `backend/accounts/models.py`, `backend/advice/models.py`, `backend/accounts/nl.py`, `tests/test_dpia.py`
- Create: `backend/accounts/migrations/0005_meter_link.py` (de naam die `makemigrations` kiest kan afwijken; hernoem hem dan hier mee)
- Test: `tests/test_meter_models.py`

**Wat:**

Drie modellen aan het eind van `backend/accounts/models.py`, in deze volgorde en met een docstring in dezelfde toon als de modellen erboven: die zegt waarom het model is zoals het is, niet wat de velden heten.

```text
class MeterLink(models.Model):
    user = FK("accounts.User", on_delete=CASCADE, related_name="meter_links")
    token_sha256 = CharField(max_length=64, unique=True, db_index=True)
    created_at = DateTimeField(default=timezone.now, editable=False)
    revoked_at = DateTimeField(null=True, blank=True)
    last_seen_at = DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    @property
    def is_active(self) -> bool:
        return self.revoked_at is None


class QuarterReading(models.Model):
    link = FK("accounts.MeterLink", on_delete=CASCADE, related_name="quarter_readings")
    measured_at = DateTimeField(db_index=True)
    consumption_kwh = FloatField()
    feed_in_kwh = FloatField()

    class Meta:
        constraints = [UniqueConstraint(fields=["link", "measured_at"],
                                        name="accounts_quarterreading_link_moment_unique")]
        ordering = ["measured_at"]


class HourAggregate(models.Model):
    link = FK("accounts.MeterLink", on_delete=CASCADE, related_name="hour_aggregates")
    hour_start = DateTimeField(db_index=True)
    consumption_kwh = FloatField()
    feed_in_kwh = FloatField()
    quarters = PositiveSmallIntegerField()

    class Meta:
        constraints = [UniqueConstraint(fields=["link", "hour_start"],
                                        name="accounts_houraggregate_link_hour_unique")]
        ordering = ["hour_start"]
```

Geen EAN, geen meternummer, geen adres: de spec zegt in hoofdstuk 3 waarom, en de docstring van `MeterLink` zegt het ook, want dat is precies het soort veld dat een latere lezer er goedbedoeld bij zet.

Op `MeterLink` een classmethod:

```text
@classmethod
def active_for(cls, user: "User") -> "MeterLink | None":
    return cls.objects.filter(user=user, revoked_at__isnull=True).first()
```

`ordering` zorgt dat dat de nieuwste is, en de regel "een actieve koppeling per account" maakt het bovendien de enige.

In `backend/advice/models.py`, in `AuditEvent`, direct na `MAIL_SENT`:

```text
    METER_LINKED = "METER_LINKED"
    METER_UNLINKED = "METER_UNLINKED"
```

En in `tests/test_dpia.py` de assertielijst uitbreiden met diezelfde twee, aan het eind, plus de docstring van die test van "Thirteen event types today" naar vijftien. **Die test blijft rood tot taak C1 hoofdstuk 2 van `docs/dpia.md` heeft bijgewerkt**; dat is kruisverband 1 en is verwacht.

In `backend/accounts/nl.py` vier sleutels erbij, in de stijl van wat er staat, met "u", zonder em-dash, en zonder iemand aan te spreken op wat hij fout deed:

- `meter_token_invalid`: dat de aangeboden sleutel niet bij een actieve koppeling hoort.
- `meter_not_allowed`: dat koppelen een bevestigd e-mailadres en toestemming vraagt.
- `meter_reading_invalid`: dat een meting op een heel kwartier moet staan en niet negatief kan zijn.
- `meter_batch_too_large`: dat er ten hoogste honderd metingen per bericht meekunnen.

**Verify:**

`tests/test_meter_models.py` bewijst, met `pytest.mark.django_db`:

1. Een tweede `QuarterReading` met dezelfde `(link, measured_at)` valt om op `IntegrityError`. Rood-proef: verwijder de `UniqueConstraint`, draai, zie hem groen worden, zet terug. Dit gaat in een migratie zitten, dus de proef draait tegen de constraint in het model plus een `makemigrations --check`; als dat te omslachtig is, is de proef dat de test faalt wanneer de constraint uit `Meta` wordt gehaald en de migratie mee wordt gegenereerd, in een tijdelijke tak van het werk die met de hand wordt teruggezet.
2. Hetzelfde voor `HourAggregate` op `(link, hour_start)`.
3. `is_active` is `True` voor een verse koppeling en `False` zodra `revoked_at` staat. Rood-proef: laat `is_active` `True` teruggeven ongeacht `revoked_at`.
4. `active_for` geeft `None` voor een gebruiker zonder koppeling, de koppeling voor een gebruiker met een actieve, en `None` zodra die is ingetrokken. Rood-proef: haal `revoked_at__isnull=True` uit de filter.
5. Het verwijderen van een `User` verwijdert de koppeling, de kwartieren en de uren. Geteld met `.count()` op alle drie voor en na. Rood-proef: zet `on_delete` op `SET_NULL` met `null=True` op `QuarterReading.link` en zie de telling niet meer op nul komen.

Draai: `uv run pytest tests/test_meter_models.py -q` en `uv run python backend/manage.py makemigrations --check --dry-run --settings=ampeer.settings.test` (die tweede moet exit 0 geven, dus de migratie hoort erbij te zitten).

**Commit:** `feat(accounts): add the meter link and its two measurement tables`

---

### Taak A2: De duwroute

**Files:**
- Create: `backend/accounts/meter.py`
- Modify: `backend/accounts/serializers.py`, `backend/accounts/views.py`, `backend/ampeer/urls.py`, `backend/ampeer/settings/base.py`
- Test: `tests/test_meter_ingest.py`

**Wat:**

`backend/accounts/meter.py`:

```text
class MeterTokenAuthentication(BaseAuthentication):
    """The push route's whole notion of who is calling.

    No cookie and no CSRF: the caller is a device without a browser and the
    route changes nothing about a session. The header carries the key, this
    class carries its digest to the database, and the raw key is never
    written anywhere.
    """

    keyword = "Meter"

    def authenticate(self, request): ...
    def authenticate_header(self, request) -> str: ...
```

Ontbrekende header: `None` teruggeven, zodat DRF met een 401 antwoordt via de permissieklasse. Een header met het juiste woord maar een onbekende, ingetrokken of misvormde sleutel: `AuthenticationFailed(NL["meter_token_invalid"])`. De afdruk komt van `token_digest` uit `backend/advice/models.py`, dezelfde functie die `RefreshSession` en `OneTimeToken` gebruiken. `authenticate` geeft `(link.user, link)` terug, zodat `request.auth` de koppeling is en de view niet nog eens hoeft te zoeken.

De serializer, in `backend/accounts/serializers.py`:

```text
MAX_READINGS_PER_REQUEST = 100
```

Een `ReadingSerializer` met `measured_at` (`DateTimeField`), `consumption_kwh` en `feed_in_kwh` (`FloatField(min_value=0)`), en een `validate_measured_at` die weigert wat niet op een heel kwartier staat: minuut in `{0, 15, 30, 45}` en seconde en microseconde nul, na omzetting naar UTC. Een `ReadingBatchSerializer` met `readings = ReadingSerializer(many=True)` en een `validate_readings` die weigert boven `MAX_READINGS_PER_REQUEST` met `NL["meter_batch_too_large"]` en onder één met `NL["meter_reading_invalid"]`. Een lege lijst is een fout: een bericht zonder inhoud is een vergissing aan de andere kant en stilzwijgend 202 antwoorden verbergt hem.

De opslag, ook in `meter.py`:

```text
def store_readings(link: MeterLink, rows: list[dict[str, Any]]) -> tuple[int, int]:
    """Write what is new, count what was already there, in one transaction."""
```

`bulk_create(..., ignore_conflicts=True)` binnen `transaction.atomic()`, gevolgd door het zetten van `last_seen_at` op `timezone.now()` op dezelfde koppeling. Het aantal opgeslagen wordt gemeten door voor en na te tellen op de betrokken tijdstippen, niet door de terugkeerwaarde van `bulk_create`, want die is per database anders. Dubbele tijdstippen binnen hetzelfde bericht tellen als een: ontdubbel op `measured_at` voordat je schrijft, en tel het verschil bij de overgeslagen.

De view in `backend/accounts/views.py`, een `APIView` en niet `_AuthAPIView` (die is voor de sessieroutes en zet een CSRF-cookie, wat hier zinloos is):

```text
class MeterReadingsView(_NoStoreAPIView):
    authentication_classes = (MeterTokenAuthentication,)
    permission_classes = (IsAuthenticated,)
    throttle_scope = "meter-ingest"

    def post(self, request): ...
```

Antwoordt 202 met `{"stored": n, "skipped": m}`.

De route in `backend/ampeer/urls.py`: `path("api/meter/readings/", MeterReadingsView.as_view(), name="meter-readings")`. Kijk hoe `/api/auth/` daar is gemonteerd en volg dezelfde vorm; als dat via een `include` van een app-urls gaat, doe dat dan ook, in `backend/accounts/urls.py`, en pas dan hoort dat bestand ook in dit Files-blok.

De scope in `backend/ampeer/settings/base.py`, met een comment dat de som uitrekent:

```text
        # A device pushing every quarter makes four requests an hour. This
        # allows a buffered day plus repeats after an outage. Decision 33's
        # sum moves from 490 to 610 an hour, which 10 r/s clears 59 times
        # over; tests/test_nginx_config.py re-runs that arithmetic.
        "meter-ingest": "120/hour",
```

**Verify:**

`tests/test_meter_ingest.py`, met `pytest.mark.django_db` en de bestaande API-testvorm uit `tests/test_accounts_api.py`:

1. Geen header: 401. Rood-proef: zet `permission_classes` op `AllowAny`.
2. Een sleutel die niet bestaat: 401, met de Nederlandse zin uit `nl.py` in de body. Rood-proef: laat `authenticate` `None` teruggeven in plaats van te falen, en zie de zin verdwijnen.
3. Een ingetrokken koppeling: 401. Rood-proef: haal `revoked_at__isnull=True` uit de zoekopdracht.
4. Een geldige sleutel met twee metingen: 202, `stored` is 2, de rijen staan er, en `last_seen_at` is gezet. Rood-proef: laat `store_readings` niets schrijven.
5. Hetzelfde bericht nog een keer: 202, `stored` is 0 en `skipped` is 2, en er staan nog steeds twee rijen. Rood-proef: haal `ignore_conflicts=True` weg en zie een `IntegrityError` in plaats van een 202.
6. Honderdeen metingen: 400 met `NL["meter_batch_too_large"]`. Rood-proef: verhoog `MAX_READINGS_PER_REQUEST`.
7. Een leeg `readings`: 400.
8. `measured_at` op 10:07: 400 met `NL["meter_reading_invalid"]`. Rood-proef: haal `validate_measured_at` weg.
9. Een negatieve `consumption_kwh`: 400. Rood-proef: haal `min_value=0` weg.
10. Een sleutel van een ander huishouden schrijft niet in de koppeling van dit huishouden: maak twee accounts, duw met de sleutel van de een, en tel de rijen onder de ander. Rood-proef: laat `store_readings` op `MeterLink.objects.first()` schrijven.
11. Het antwoord draagt `Cache-Control: private, no-store`. Rood-proef: erf van `APIView` in plaats van `_NoStoreAPIView`.

Draai: `uv run pytest tests/test_meter_ingest.py tests/test_nginx_config.py tests/test_backend_settings.py -q`.

**Commit:** `feat(accounts): accept pushed quarter readings on a hashed meter key`

---

### Taak A3: De drie sessieroutes, het intrekken en de export

**Files:**
- Modify: `backend/accounts/service.py`, `backend/accounts/views.py`, `backend/accounts/urls.py`, `tests/test_accounts_privacy.py`
- Test: `tests/test_meter_link_api.py`

**Wat:**

In `backend/accounts/service.py` drie functies, met dezelfde vorm als wat er staat (een docstring die de beslissing draagt, en `AuditEvent.record` op de plek waar de handeling af is):

```text
def may_link_meter(user: User) -> bool:
    """A confirmed address and a granted METER_LINK consent, both."""


def link_meter(user: User) -> tuple[MeterLink, str]:
    """Mint one key, keep only its digest, revoke whatever came before.

    Returns the row and the raw key. The key is returned and never stored,
    which is why this is the only function that has both in the same scope.
    """


def unlink_meter(user: User) -> bool:
    """Revoke and erase, in one transaction. False when there was nothing."""
```

`link_meter` draait binnen `transaction.atomic()`: eerst `MeterLink.objects.filter(user=user, revoked_at__isnull=True).update(revoked_at=now)`, dan de nieuwe rij, dan `AuditEvent.record(AuditEvent.METER_LINKED, user_id=user.pk)`. De sleutel is `secrets.token_urlsafe(32)`. Het intrekken van de vorige koppeling verwijdert ook diens metingen: `unlink_meter` en dit pad delen daarom één private helper, zodat er niet twee plekken zijn die moeten onthouden dat er ook data weg moet.

`unlink_meter` draait ook binnen `transaction.atomic()`: `QuarterReading.objects.filter(link=link).delete()`, `HourAggregate.objects.filter(link=link).delete()`, `revoked_at` zetten, en `AuditEvent.record(AuditEvent.METER_UNLINKED, user_id=user.pk)`.

In dezelfde module: waar een `METER_LINK`-toestemming wordt ingetrokken, roept die code `unlink_meter(user)` aan. Zoek waar `Consent.record(..., WITHDRAWN)` gebeurt (dat is `ConsentView` in `views.py` of een servicefunctie ernaast) en hang het daar op, in dezelfde transactie. Een toestemming intrekken die de data laat staan is precies de fout die de spec in hoofdstuk 6 uitsluit.

`export_account` krijgt er een sleutel `meter` bij: `null` zonder actieve koppeling, en anders een object met `created_at`, `last_seen_at`, `hours` (elk uur met `hour_start`, `consumption_kwh`, `feed_in_kwh`, `quarters`) en `quarters` (elk kwartier met `measured_at`, `consumption_kwh`, `feed_in_kwh`). De sleutel zelf staat er niet in, en de docstring zegt waarom: Ampeer kent hem niet.

Drie views in `backend/accounts/views.py`, alle drie op `_AuthAPIView`:

- `MeterStatusView`, `throttle_scope = "auth-read"`, `get` antwoordt `{"may_link": bool, "linked": bool, "created_at": str | null, "last_seen_at": str | null}`.
- `MeterLinkView`, `throttle_scope = "auth-write"`, `post` weigert met `PermissionDenied(NL["meter_not_allowed"])` als `may_link_meter` vals is, en antwoordt anders 201 met `{"token": ..., "push_url": ..., "created_at": ...}`. `push_url` komt uit een instelling en wordt niet in de view samengesteld uit iets wat de aanroeper stuurde.
- `MeterUnlinkView`, `throttle_scope = "auth-write"`, `post` antwoordt 204, ook wanneer er niets te ontkoppelen was: het resultaat is hetzelfde en een verschil zou alleen zeggen of er een koppeling was.

De drie routes in `backend/accounts/urls.py`: `meter/`, `meter/link/`, `meter/unlink/`.

`push_url`: zet in `backend/ampeer/settings/base.py` geen nieuwe instelling als `AMPEER_PUBLIC_API_BASE` of iets dergelijks al bestaat; zoek dat eerst uit. Bestaat er niets, dan is de eenvoudigste eerlijke oplossing het pad zelf teruggeven (`"/api/meter/readings/"`) en de frontend het absolute adres laten tonen op basis van zijn eigen `NEXT_PUBLIC_API_BASE`, die hij al kent. Kies dat, en zeg in de docstring waarom: de backend weet niet onder welk publiek adres hij hangt, en gokken zou een fout adres in een apparaat zetten dat niemand meer nakijkt.

**Verify:**

`tests/test_meter_link_api.py`:

1. Zonder sessie: 401 op alle drie. Rood-proef: `permission_classes = (AllowAny,)` op één ervan.
2. Zonder bevestigd adres: `may_link` is vals, en `link/` geeft 403 met `NL["meter_not_allowed"]`. Rood-proef: haal de `email_verified_at`-controle uit `may_link_meter`.
3. Zonder toestemming: hetzelfde. Rood-proef: haal de `Consent.current`-controle eruit.
4. Met beide: `link/` geeft 201, de sleutel is 43 tekens, hij staat nergens in `MeterLink.objects.values_list("token_sha256", flat=True)`, en met die sleutel lukt een duw op de ingest-route. Rood-proef: sla de sleutel op in een kolom en zie de assertie omvallen.
5. Twee keer `link/`: de eerste sleutel werkt niet meer op de ingest-route, en `MeterLink.objects.filter(revoked_at__isnull=True).count()` is 1. Rood-proef: haal de `update(revoked_at=...)` weg.
6. `unlink/` na een duw: 204, de kwartieren zijn nul, de uren zijn nul, `status` zegt `linked: false`. Rood-proef: laat `unlink_meter` alleen `revoked_at` zetten.
7. `unlink/` zonder koppeling: 204, en er wordt geen `METER_UNLINKED` weggeschreven. Rood-proef: schrijf de logregel onvoorwaardelijk.
8. Het intrekken van `METER_LINK` via `consent/` verwijdert de metingen en trekt de koppeling in. Rood-proef: haal de aanroep van `unlink_meter` uit dat pad.
9. `link/` en `unlink/` schrijven elk één logregel van de juiste soort, met `user_id` en niets anders erin. Rood-proef: voeg een extra sleutel aan de context toe en zie `tests/test_dpia.py` erover vallen (die tweede helft hoeft niet in deze test, maar de assertie op de contextsleutels wel).
10. De koppeling van een ander huishouden is onzichtbaar: account B ziet `linked: false` terwijl A gekoppeld is. Rood-proef: filter in `active_for` niet op `user`.
11. `export/` draagt `meter` met de uren en de kwartieren, en nergens de sleutel. Rood-proef: haal de sleutel uit `export_account` en zie de assertie op aanwezigheid omvallen; en voeg de afdruk toe en zie de assertie op afwezigheid omvallen.

In `tests/test_accounts_privacy.py` erbij: het verwijderen van een account laat nul `MeterLink`, nul `QuarterReading` en nul `HourAggregate` achter. Volg de vorm van de telling die daar al staat.

Draai: `uv run pytest tests/test_meter_link_api.py tests/test_accounts_privacy.py tests/test_meter_ingest.py -q`.

**Commit:** `feat(accounts): link and unlink a meter, and export what it pushed`

---

### Taak A4: De opruiming en de timer

**Files:**
- Create: `backend/accounts/management/commands/purge_meter_readings.py`
- Create: `infra/systemd/ampeer-meter-purge.service`, `infra/systemd/ampeer-meter-purge.timer`
- Modify: het bestaande systemd-testbestand (zoek het met een grep op `ampeer-purge.timer`)
- Test: `tests/test_purge_meter_readings.py`

**Wat:**

Het commando, in de vorm van `send_outbound_mail.py` ernaast:

```text
RETENTION = timedelta(days=90)
```

`handle` neemt `--check` en `--max` (standaard 200, het aantal koppelingen dat het in een run behandelt). Zonder `--check`: per koppeling, binnen `transaction.atomic()`, de kwartieren ouder dan `now - RETENTION` optellen per uur (`hour_start` is `measured_at` afgekapt op het uur in UTC), die uren met `update_or_create` wegschrijven waarbij een bestaand uur wordt opgeteld en `quarters` meegroeit, en daarna precies die kwartieren verwijderen. Eén regel naar stdout met het aantal opgetelde kwartieren en het aantal geschreven uren.

`--check` schrijft niets en geeft exit 1 wanneer er kwartieren ouder dan `RETENTION` plus één dag zijn: dan draait de timer niet meer. De extra dag is de marge die de dagelijkse timer nodig heeft, en het commentaar zegt dat, want een `--check` die rood wordt op de dag dat alles goed gaat leert mensen hem te negeren.

Een uur met minder dan vier kwartieren wordt bewaard met `quarters` op wat er was. Niet weggooien: de spec zegt in hoofdstuk 5 waarom.

De timer, dagelijks, in dezelfde vorm als de bestaande. Geen catch-up-vlag, om dezelfde reden als de mailtimer; het commentaar daar zegt hoe dat geformuleerd moet worden zonder de letterlijke tekenreeks te noemen die de bijbehorende test verbiedt. Lees die test voordat je het commentaar schrijft.

**Verify:**

`tests/test_purge_meter_readings.py`, met een vaste klok (`freeze` bestaat hier niet; zet `measured_at` expliciet ver in het verleden):

1. Vier kwartieren van 95 dagen oud in hetzelfde uur worden één `HourAggregate` met de som en `quarters` op 4, en de vier kwartieren zijn weg. Rood-proef: laat het commando de kwartieren niet verwijderen.
2. Kwartieren van 89 dagen oud blijven staan en worden geen uur. Rood-proef: zet `RETENTION` op één dag.
3. Twee kwartieren in hetzelfde uur worden een uur met `quarters` op 2 en de som van die twee. Rood-proef: zet `quarters` hard op 4.
4. Een tweede run over hetzelfde uur telt niet dubbel: draai het commando twee keer en zie dezelfde som. Rood-proef: gebruik `create` in plaats van `update_or_create` en zie een `IntegrityError` of een dubbele rij.
5. De kwartieren van koppeling A raken die van B niet. Rood-proef: laat de optelling over alle koppelingen tegelijk gaan.
6. `--check` geeft exit 0 op een schone boom en exit 1 met oude kwartieren erin. Rood-proef: laat `--check` altijd 0 geven.
7. `--check` schrijft niets: tel de kwartieren voor en na. Rood-proef: laat `--check` toch opruimen.
8. Het commando schrijft geen `AuditEvent`. Rood-proef: schrijf er een en zie de telling omvallen.

Draai: `uv run pytest tests/test_purge_meter_readings.py -q` en de systemd-test.

**Commit:** `feat(accounts): fold quarter readings into hours after ninety days`

---

## Spoor B: de frontend

| Taak | Hangt af van |
|---|---|
| B1. `accounts.ts`: de drie aanroepen en hun vormcontroles | niets |
| B2. `MeterSection.tsx` en zijn drie toestanden | B1 |
| B3. De accountpagina, de zinnenlijst en de e2e-ronde | B2 |

Spoor B schrijft tegen de routevorm uit de spec en heeft de draaiende backend niet nodig. `tests/test_frontend_contract.py` wordt rood zodra B1 landt en groen zodra A3 landt; dat is kruisverband 2 en verwacht.

### Taak B1: `accounts.ts`

**Files:**
- Modify: `frontend/src/lib/accounts.ts`
- Test: `frontend/tests/lib/accounts.test.ts`

**Wat:**

Twee interfaces en drie functies, in de vorm en de toon van wat er staat. Elk antwoord dat een body heeft krijgt een vormcontrole, en die controle weigert liever dan te raden, want de pagina heeft geen error boundary boven zich.

```text
export interface MeterStatus {
  readonly may_link: boolean;
  readonly linked: boolean;
  readonly created_at: string | null;
  readonly last_seen_at: string | null;
}

export interface MeterKey {
  readonly token: string;
  readonly push_path: string;
  readonly created_at: string;
}

export async function getMeterStatus(): Promise<MeterStatus>;
export async function linkMeter(): Promise<MeterKey>;
export async function unlinkMeter(): Promise<void>;
```

`isMeterStatus` eist vier sleutels van het juiste type, met `created_at` en `last_seen_at` als string of `null`, en `"created_at" in value` net als `isMe` doet voor `email_verified_at`: een ontbrekende sleutel is niet hetzelfde als `null`, en de reden staat daar al opgeschreven. `isMeterKey` eist een niet-lege `token`, een `push_path` die met `/` begint, en een `created_at`. `unlinkMeter` antwoordt 204 en heeft dus geen body en geen controle.

Geen retry, in geen van de drie. De regel bovenaan het bestand geldt onverkort.

**Verify:**

In `frontend/tests/lib/accounts.test.ts`, in de vorm van de tabellen die er staan:

1. De drie roepen het juiste pad met de juiste methode aan.
2. `getMeterStatus` en `linkMeter` sturen de sessiecookies mee (`credentials: "include"`), en de twee POSTs sturen de CSRF-header mee terwijl de GET dat niet doet. Rood-proef: haal `credentials` uit `call` en zie het omvallen.
3. Een antwoord zonder `may_link` gooit een `ApiError` met een lege boodschap. Rood-proef: laat `isMeterStatus` altijd `true` geven.
4. Een antwoord waarin `created_at` ontbreekt in plaats van `null` te zijn, wordt geweigerd. Rood-proef: vervang de `in`-controle door een `!== undefined`-vergelijking en zie de test groen worden, en zet terug.
5. Een 403 met een Nederlandse `detail` komt als die zin terug in `ApiError`. Rood-proef: laat `readErrorBody` `detail` laten vallen.

Draai: `pnpm vitest run tests/lib/accounts.test.ts`.

**Commit:** `feat(frontend): add the three meter calls to the account client`

---

### Taak B2: `MeterSection.tsx`

**Files:**
- Create: `frontend/src/app/_account/MeterSection.tsx`
- Test: `frontend/tests/account/MeterSection.test.tsx`

**Wat:**

Een clientcomponent naast `ConsentRow.tsx`, met dezelfde vorm: hij krijgt zijn gegevens en zijn handelingen als props en doet zelf geen netwerkaanroep. De pagina eromheen roept aan; deze component toont.

```text
interface MeterSectionProps {
  readonly status: MeterStatus | null;
  readonly issuedKey: MeterKey | null;
  readonly apiBase: string;
  readonly busy: boolean;
  readonly onLink: () => void;
  readonly onUnlink: () => void;
}
```

Drie toestanden, precies zoals hoofdstuk 8 van de spec ze beschrijft. De kop is `<h3>` onder de `<h2 id="uw-gegevens">` van de pagina, met een eigen `id` en `aria-labelledby` op de sectie, net als de rest van die pagina doet.

Bij `issuedKey`: de sleutel in een `<code>`, het volledige duwadres als `apiBase + push_path`, en de zin dat de sleutel hierna niet meer te zien is. Geen kopieerknop die iets naar het klembord schrijft zonder dat te zeggen; als er een komt, zegt hij het.

De ontkoppelknop vraagt eerst om bevestiging, in de vorm die de verwijderknop op dezelfde pagina al gebruikt. Lees die eerst en volg hem, in plaats van een tweede patroon te bedenken.

Een bezige knop is `disabled` en heeft een `role="status"`-melding ernaast, net als elders op die pagina. Niet `aria-busy`: het commentaar bij de exportknop legt uit waarom niet.

**Verify:**

`frontend/tests/account/MeterSection.test.tsx`, met Testing Library, en let op de valkuil die deze repository al twee keer heeft geraakt: een kop en een veld met dezelfde naam laten `getByLabelText` op meer dan één element vallen. Gebruik `getByRole("button", { name })` en `getByRole("heading", { name })`.

1. `may_link` vals: de knop staat er niet, en de zin over wat er ontbreekt staat er wel. Rood-proef: toon de knop onvoorwaardelijk.
2. `may_link` waar en niet gekoppeld: de knop staat er, en `onLink` wordt precies één keer aangeroepen bij een klik. Rood-proef: roep hem twee keer aan.
3. `issuedKey` gezet: de sleutel staat op het scherm en het volledige adres ook. Rood-proef: laat `push_path` weg uit de samenstelling.
4. Gekoppeld met `last_seen_at` op `null`: de zin dat er nog niets binnenkwam. Rood-proef: toon altijd een datum.
5. Gekoppeld met een `last_seen_at`: die datum, in `Europe/Amsterdam` getoond. Zoek eerst of dit project daar al een helper voor heeft en gebruik die; is die er niet, dan `toLocaleString("nl-NL", { timeZone: "Europe/Amsterdam" })`. Rood-proef: toon de UTC-string.
6. `onUnlink` wordt pas aangeroepen na de bevestiging. Rood-proef: roep hem meteen aan.
7. `busy`: beide knoppen `disabled`. Rood-proef: haal `disabled` weg.

Draai: `pnpm vitest run tests/app/MeterSection.test.tsx`.

**Commit:** `feat(frontend): show the meter link in its three states`

---

### Taak B3: De accountpagina, de zinnenlijst en de e2e-ronde

**Files:**
- Modify: `frontend/src/app/_account/AccountPage.tsx`, `frontend/tests/ui-strings.txt`, `frontend/e2e/account.spec.ts`
- Test: `frontend/tests/account/AccountPage.test.tsx`

**Wat:**

`AccountPage` laadt de status na `me/`, in dezelfde `useEffect` die de toestemmingsteksten laadt of in een tweede ernaast, en houdt `issuedKey` in state. `onLink` roept `linkMeter` aan, zet `issuedKey`, en herlaadt de status. `onUnlink` roept `unlinkMeter` aan, wist `issuedKey` en herlaadt. Beide gaan door dezelfde `markBusy`/`clearBusy` en dezelfde `describeAuthError` als de rest van die pagina; er komt geen tweede foutafhandeling naast.

Het blok komt onder de toestemmingen en boven de exportknop, want het hoort bij wat er met gegevens gebeurt en niet bij het beheer van het account.

`ui-strings.txt` wordt geregenereerd met `UPDATE_UI_STRINGS=1 pnpm e2e language`, en de diff wordt gelezen: elke toegevoegde regel is een zin die deze cyclus heeft geschreven of een element-id-kop. Staat er iets anders in, dan is dat een vondst en geen ruis.

In `frontend/e2e/account.spec.ts` een ronde met gemockte API: koppelen, de sleutel zien, ontkoppelen. Let op de registratievolgorde van de routes: Playwright matcht in omgekeerde volgorde van registratie, dus de brede handler wordt eerst geregistreerd en de smalle daarna. Dat staat er al een keer fout gegaan in de geschiedenis van dit bestand.

**Verify:**

1. De vitest-ronde: koppelen toont de sleutel, ontkoppelen laat hem verdwijnen, een 403 op `link/` toont de Nederlandse zin uit het antwoord en niet de Engelse standaard van `ApiError`. Rood-proef voor die laatste: laat de pagina `error.message` tonen in plaats van via `describeAuthError` te gaan, met een lege boodschap, en zie de assertie omvallen.
2. De e2e-ronde draait groen, inclusief axe op de nieuwe toestand.
3. `pnpm e2e language` is groen zonder `UPDATE_UI_STRINGS`.

Draai: `pnpm vitest run tests/app/AccountPage.test.tsx tests/app/MeterSection.test.tsx` en `pnpm e2e account language`.

**Commit:** `feat(frontend): wire the meter section into the account page`

---

## Spoor C: de documenten

### Taak C1: DPIA, register, beslissingen

**Files:**
- Modify: `docs/dpia.md`, `docs/verwerkersregister.md`, `docs/decisions.md`, `CLAUDE.md`

**Wat:**

`docs/dpia.md`:

- Hoofdstuk 2: de twee nieuwe logsoorten `METER_LINKED` en `METER_UNLINKED` benoemen, in dezelfde vorm als de dertien die er staan. `tests/test_dpia.py` vergelijkt de lijst in de code met dit hoofdstuk; taak A1 heeft de code al veranderd, dus dit hoofdstuk maakt die test weer groen.
- Hoofdstuk 2: de drie nieuwe tabellen, en dat `MeterLink` de sleutel niet bevat maar zijn afdruk, in dezelfde woorden als waarin `RefreshSession` en `OneTimeToken` daar al staan.
- De retentietabel: ruwe kwartieren negentig dagen, uurtotalen tot het account of de koppeling weg is.
- Hoofdstuk over de rechten: de export draagt de metingen; ontkoppelen en het intrekken van de toestemming verwijderen ze allebei.
- Hoofdstuk 10: het beantwoorde punt over de rechtsgrond eruit. De numerieke test in `tests/test_dpia.py` telt de open punten, dus tel mee.

`docs/verwerkersregister.md`: een verwerking erbij voor de meterdata, met de categorie, de bewaartermijn en de grondslag (toestemming), gebonden aan de code op dezelfde manier als de rest. Kijk in `tests/test_verwerkersregister.py` wat daar aan gebonden is en of er iets bij hoort; voegt deze taak een bewering toe die aan een constante te binden is, dan hoort die test in dit Files-blok en dan bind je hem.

`docs/decisions.md`: de zeven beslissingen uit hoofdstuk 13 van de spec, in de vorm en de nummering die daar loopt. Elke beslissing zegt wat het kost als hij fout is.

`CLAUDE.md`: de stackregel zegt "PostgreSQL 16 + TimescaleDB (hypertables voor tijdreeksen)" en de repository draait plain `postgres:16-alpine`. Dat is nu een zin die niet klopt over de enige tijdreeks die bestaat. Verander hem in wat waar is, met de reden erbij in één zin: een gewone tabel met een index op `(link, measured_at)`, en TimescaleDB als optie voor wanneer dat gemeten te weinig blijkt. Verander niets anders in dat bestand.

**Verify:**

`uv run pytest tests/test_dpia.py tests/test_verwerkersregister.py tests/test_docs.py -q` (zoek uit hoe die laatste heet; er is een test die `docs/decisions.md` en de plannen leest). Deze taak schrijft zelf geen nieuwe test en heeft dus geen rode proef, met één uitzondering: bindt hij een bewering aan een constante, dan wel.

**Commit:** `docs: describe the meter link, its retention and what it logs`

---

## Na de drie sporen: de controller

- [ ] `uv run pytest -q` in zijn geheel, zonder `data/nedu-profiles-2025.csv`, en de dekking opnieuw meten. De vloer gaat omhoog naar wat gemeten wordt min één honderdste, met het commentaar in `pyproject.toml` uitgebreid in dezelfde vorm als de metingen die er staan. `MINIMUM_COVERAGE_FLOOR` in `tests/test_pipeline_contract.py` volgt.
- [ ] `pnpm vitest run` en `pnpm e2e` in hun geheel.
- [ ] `scripts/gates.sh`, elke groep, beoordeeld op de exitcode.
- [ ] Een live ronde tegen de echte stack: registreren, bevestigen, toestemming geven, koppelen, duwen met `curl`, terugzien op de pagina, exporteren, ontkoppelen, en zien dat het weg is.
- [ ] Dit plan op `delivered`, met de notitie in dezelfde vorm als de eerdere plannen.
- [ ] Push en PR naar `dev`.
