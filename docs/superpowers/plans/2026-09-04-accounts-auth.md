# Accounts en authenticatie: implementatieplan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Status:** in progress

**Goal:** Een huishouden kan een account aanmaken bij de start van een meterkoppeling, inloggen, zijn twee toestemmingen geven en intrekken, zijn gegevens exporteren en zijn account verwijderen, zonder dat de anonieme rekenmachine iets van dat alles merkt.

**Architecture:** Een nieuwe Django-app `backend/accounts/` naast `backend/advice/`, met een eigen gebruikersmodel op `AbstractBaseUser`. Authenticatie is een JWT in httpOnly `SameSite=Strict` cookies, uitgegeven door `djangorestframework-simplejwt` maar bijgehouden in een eigen `RefreshSession` die alleen een digest bewaart. De adviesendpoints blijven anoniem: `DEFAULT_AUTHENTICATION_CLASSES` blijft leeg en de authenticatieklasse wordt per view gezet.

**Tech Stack:** Django 5.2 LTS, Django REST Framework 3.18, `djangorestframework-simplejwt`, `django-axes`, `argon2-cffi`, PostgreSQL 16 via psycopg 3, pytest-django, uv.

**Spec:** `docs/superpowers/specs/2026-09-04-accounts-auth-design.md`

## Global Constraints

- Wachtwoorden worden gehasht met Argon2**id**. Niet Argon2 als familie: het `type`-attribuut van de hasher moet `argon2.low_level.Type.ID` zijn en daar staat een test op.
- JWT in httpOnly `SameSite=Strict` cookies, met rotatie van het refresh-token. Geen token in een `Authorization`-header, in geen enkele richting.
- `django-axes` staat aan zodra er iets is om op in te loggen, met `axes.backends.AxesStandaloneBackend` als **eerste** entry van `AUTHENTICATION_BACKENDS`.
- Rate limiting op alle publieke endpoints. Een view zonder `throttle_scope` wordt door DRF zonder enige limiet beantwoord, dus elke nieuwe route noemt een scope die een tarief heeft.
- Object-level permissions: elk queryset filtert op `request.user`, nooit alleen op `pk`.
- Er staat nergens een bruikbaar credential in de database. Geen refresh-token, geen `jti`, geen ingest-token. Alleen digests.
- Er staat nergens een IP-adres of een e-mailadres in een tabel, in een cachesleutel of in een auditregel.
- Geld is `Decimal`, energie is `float`. Bedragen gaan als string over de lijn. De export geeft opgeslagen JSON ongewijzigd door en bouwt niets opnieuw op.
- Alle tijdstempels in UTC opslaan, in Europe/Amsterdam tonen.
- Type hints verplicht in Python. `mypy --strict` blijft schoon over `backend`.
- Code is Engels, applicatie is Nederlands. Nederlandse tekst hoort nooit hardcoded in de logica: alles wat een gebruiker leest staat in `backend/accounts/nl.py`, gekoppeld aan een Engelse id.
- Geen em-dashes in gebruikersgerichte teksten, en niet in de documenten in `docs/`.
- Elke nieuwe afhankelijkheid gaat via `uv add`, en `uv.lock` wordt meegecommit.
- De dekkingsdrempel is 98,00 met `precision = 2`. Hij mag omhoog en nooit omlaag. Beoordeel een poort op de exitcode, nooit op het getoonde percentage.
- De jobnamen `quality`, `test`, `dependencies`, `sast` en `secrets` zijn een interface met de rulesets. Hernoem er nooit een zonder `scripts/setup_rulesets.sh` in dezelfde commit mee te wijzigen.
- Werk op `feat/accounts-auth`. Nooit direct op `main`.
- Voor elke nieuwe controle geldt: toon aan dat hij rood kán worden. Een groene uitkomst is pas bewijs als het instrument aantoonbaar werkt. Elke taak hieronder zegt per test hoe je dat doet.

---

## De blokkade die dit plan als eerste opruimt

`tests/test_plans.py` parametriseert over `PLANS_DIR.glob("*.md")` en eist dat elk pad dat een plan op een `- Create:`, `- Modify:` of `- Test:`-regel noemt, in de boom staat. Dat leest de **werkmap** en niet git, dus dit bestand hier neerzetten maakt de suite rood voordat er ook maar iets gecommit is. Er is vandaag geen statusmechanisme, geen skip en geen uitzondering voor lopend werk: de blokquote "Status on 2026-08-22: delivered" bovenaan `2026-08-21-advice-api.md` is proza die geen enkele test leest.

Er zijn vier uitwegen en drie ervan deugen niet.

Het plan pas aan het eind schrijven maakt het onbruikbaar voor de agents die het moeten uitvoeren. De paden zonder backticks schrijven omzeilt de scanner en daarmee de hele controle. In taak 1 alvast lege bestanden aanmaken zet elf lege modules in de boom, verpest de TDD-volgorde en levert een dekkingsmeting over bestanden die niets doen.

**Gekozen: `tests/test_plans.py` krijgt in taak 1 een statusmechanisme**, en dat is meteen de eerste taak omdat er code voor nodig is. De vorm is bewust zo dat de ontsnappingsroute niet open kan blijven staan:

| Status | Alle genoemde bestanden bestaan | Sommige ontbreken |
|---|---|---|
| `in progress` | **rood**: het werk is klaar, zet de status om | groen |
| iets anders, of geen statusregel | groen | **rood**: dit is de bestaande controle |

Er is dus geen enkele combinatie die groen is omdat de vraag niet van toepassing zou zijn. Een status die niet letterlijk `in progress` is, inclusief een typefout en een ontbrekende regel, valt terug op de strengste lezing. En een plan dat `in progress` blijft zeggen nadat het werk geland is, wordt rood met de instructie om de regel om te zetten. Taak 13 zet hem om, en die taak kan niet vergeten worden omdat de suite hem afdwingt.

---

## Het meerdere-agents-werkmodel

Vijf regels, overgenomen uit de drie plannen die hiervoor liepen:

1. **Een taak bezit paden exclusief.** Geen twee taken schrijven ooit in hetzelfde bestand zonder dat de een op de ander gewacht heeft.
2. **Uitvoerende agents committen, en niets daarbuiten.** Elke taak commit op `feat/accounts-auth` en nergens anders, met alleen de bestanden gestaged die de Files-blok van diezelfde taak noemt, en met de boodschap die de taak al voorschrijft. Nooit `push`, nooit `rebase`, nooit `checkout`, nooit een andere branch aanraken.
3. **Elke taak draait zijn eigen verificatiecommando** en rapporteert de uitvoer.
4. **Poorten draaien na de taken**, niet erin.
5. **Een taak die niet verder kan zonder een bestand aan te raken dat hij niet bezit, stopt en meldt dat.** Hij reikt niet over de lijn heen.

### Volgorde

Het plan draait **serieel**, taak 1 tot en met 13, in deze volgorde en nooit twee tegelijk. Twee redenen, allebei op zichzelf genoeg. Ten eerste is superpowers:subagent-driven-development hier de uitvoeringsautoriteit voor deze run en zegt met zoveel woorden "Never dispatch multiple implementation subagents in parallel (conflicts)". Ten tweede draaien taken 4, 5 en 7 alle drie pytest tegen dezelfde Postgres, en pytest-django maakt en sloopt daarbij één `test_ampeer` per run: een band naast elkaar corrumpeert zijn eigen metingen. De kolom hieronder is dus geen keuzemenu, het is de volgorde.

| Taak | Hangt af van |
|---|---|
| 1. Statusmechanisme in `test_plans.py` | niets |
| 2. Meting 1: telt de cache elke ophoging | niets |
| 3. Afhankelijkheden, instellingen, `accounts`-app, `User` | 2 |
| 4. Meting 2: sluit axes echt buiten | 3 |
| 5. `Consent` en `nl.py` | 3 |
| 6. `RefreshSession` en het opruimen | 5 |
| 7. `StoredAdvice.owner` en de auditwoordenschat | 3 |
| 8. `cookies.py`, `tokens.py`, `authentication.py` | 6 |
| 9. `_AuthAPIView`, registreren, inloggen, verversen, uitloggen | 5, 7, 8 |
| 10. `me/` en `consent/` | 7, 9 |
| 11. `export/` en `delete/` | 7, 10 |
| 12. De documenten en de verbrede controles | 11 |
| 13. Status omzetten en de poorten draaien | 12 |

Taken 9, 10 en 11 schrijven alle drie in `backend/accounts/views.py` en `backend/accounts/urls.py`. Taak 5 en 6 schrijven allebei in `backend/accounts/models.py`. De serie hierboven is precies wat dat zonder botsing houdt.

### Bestandsbezit

| Taak | Bezit exclusief |
|---|---|
| 1 | `tests/test_plans.py`, `docs/superpowers/plans/2026-09-04-accounts-auth.md` |
| 2 | `tests/test_accounts_lockout_store.py` |
| 3 | `pyproject.toml`, `uv.lock`, `backend/ampeer/settings/**`, `backend/accounts/__init__.py`, `backend/accounts/apps.py`, `backend/accounts/models.py`, `backend/accounts/lockout.py`, `backend/accounts/migrations/0001_initial.py`, `tests/test_backend_settings.py`, `tests/test_accounts_models.py` |
| 4 | `tests/test_accounts_lockout.py` |
| 5 | `backend/accounts/models.py`, `backend/accounts/migrations/0002_consent.py`, `backend/accounts/nl.py`, `tests/test_accounts_consent.py` |
| 6 | `backend/accounts/models.py`, `backend/accounts/migrations/0003_refreshsession.py`, `backend/accounts/management/commands/purge_expired_sessions.py`, `tests/test_accounts_models.py`, `infra/systemd/ampeer-purge.service` |
| 7 | `backend/advice/models.py`, `backend/advice/migrations/0005_storedadvice_owner.py`, `tests/test_advice_api.py`, `tests/test_dpia.py`, `docs/dpia.md` |
| 8 | `backend/accounts/cookies.py`, `backend/accounts/tokens.py`, `backend/accounts/authentication.py`, `tests/test_accounts_auth.py` |
| 9 | `backend/accounts/views.py`, `backend/accounts/urls.py`, `backend/accounts/serializers.py`, `backend/ampeer/urls.py`, `tests/test_accounts_api.py` |
| 10 | `backend/accounts/views.py`, `backend/accounts/urls.py`, `backend/accounts/serializers.py`, `tests/test_accounts_api.py` |
| 11 | `backend/accounts/views.py`, `backend/accounts/urls.py`, `backend/accounts/service.py`, `tests/test_accounts_deletion.py` |
| 12 | `docs/dpia.md`, `docs/decisions.md`, `tests/test_dpia.py`, `tests/test_accounts_privacy.py`, `backend/advice/views.py` |
| 13 | `docs/superpowers/plans/2026-09-04-accounts-auth.md` |

---

## Vier dingen die dit plan vastlegt en die de spec impliciet liet

**De axes-callables staan in `backend/accounts/lockout.py`**, een bestand dat niet in de tabel van hoofdstuk 2 van de spec staat. Ze moeten bestaan voordat de instellingen die ze bij naam noemen geladen kunnen worden, en ze horen bij geen van de bestanden die er wel staan: het zijn geen modellen en geen views. Taak 12 vult de rij aan in de spec, zodat de twee documenten niet uiteenlopen.

**Onbekende velden in een request body worden genegeerd en niet geweigerd.** De adviesserializers weigeren ze, en dat is daar de moeite waard omdat het formulier negen velden heeft die precies moeten kloppen. Hier bouwt de view de `User` expliciet uit drie benoemde waarden op, dus een onbekend veld kan niets bereiken en het weigeren ervan zou alleen een tweede boodschap in `nl.py` opleveren. Als dat later toch gewenst is, is het één mixin en het is geen aanname die iets anders blokkeert.

**`AMPEER_COOKIE_SECURE` is geen omgevingsvariabele.** `prod.py` zet hem hard op `True` en `dev.py` op `False`, zoals `SESSION_COOKIE_SECURE` daar vandaag al gaat. Daarmee hoeft `REQUIRED_ENV` in `tests/test_backend_settings.py` niet mee te groeien en hoeft de stap "Django deployment checklist" in `.github/workflows/ci.yml` niet aangepast te worden. Dat is bewust: die twee lijsten zijn een tweede kopie van elkaar en elke naam die er niet bij hoeft, hoort er niet bij.

**De verdubbelde `_csrf`-helper in taak 9 en taak 11, en het drievoudig herhaalde anonieme-view-voorspel in taak 9, blijven zo staan.** Een gedeelde conftest-helper zou `tests/test_accounts_api.py` en `tests/test_accounts_deletion.py` aan elkaar koppelen, en dat is precies de koppeling die dit plan elders bewust vermijdt tussen bestanden die het apart wil kunnen laten falen. Dit is een bewuste keuze en geen vergeten opruiming: als een latere reviewer de duplicatie heropent, is dit de reden om ernaartoe te wijzen in plaats van hem te verhelpen.

---

## Fase 0: de poorten en de metingen

### Taak 1: Een plan mag onaf zijn, en mag daar niet over liegen

**Hangt af van:** niets.

**Files:**
- Modify: `tests/test_plans.py`, `tests/test_pipeline_contract.py`
- Create: `docs/superpowers/plans/2026-09-04-accounts-auth.md`

**Interfaces:**
- Consumes: niets.
- Produces: de statusregel `**Status:** in progress` als afgesproken markering; helper `_is_in_progress(plan: Path) -> bool` in `tests/test_plans.py`; helpers `_plan_that_speaks_for(path: Path) -> Path` en `_is_in_progress(path: Path) -> bool` in `tests/test_pipeline_contract.py`, dezelfde markering lezend.

Deze taak raakt twee bestaande poorten en niet een. Gemeten op 2026-09-04, voordat dit plan zelf iets aanraakte: `uv run --no-sync pytest -q` faalt op precies twee tests, allebei veroorzaakt door de twee documenten die vandaag zijn toegevoegd (dit plan en zijn spec) en door niets in de bestaande code. De eerste is `tests/test_plans.py::test_every_file_a_plan_names_exists[2026-09-04-accounts-auth.md]`, hierboven al beschreven. De tweede is `tests/test_pipeline_contract.py::test_every_test_file_named_in_a_comment_exists`, die deze taak in dezelfde beweging repareert: zonder dat zou elke agent die dit plan uitvoert een rode poort erven die niets met zijn eigen werk te maken heeft.

- [ ] **Step 1: Zie de rode test die dit plan zelf veroorzaakt**

Dit plandocument staat al in `docs/superpowers/plans/`. Draai:

```bash
uv run --no-sync pytest tests/test_plans.py -q
```

Verwacht: `test_every_file_a_plan_names_exists[2026-09-04-accounts-auth.md]` faalt met een lijst die begint bij `backend/accounts/apps.py`. Dat is geen storing en het is de reden dat deze taak bestaat. Noteer de lijst; hij moet na stap 4 leeg lijken te zijn zonder dat er één bestand is aangemaakt.

- [ ] **Step 2: Schrijf de test die de nieuwe regel aan beide kanten vastpint**

Voeg onderaan `tests/test_plans.py` toe:

```python
def test_the_status_rule_reads_only_the_exact_marker(tmp_path: Path) -> None:
    """Both branches of the rule, run rather than reasoned about.

    An escape hatch that is entered by accident is worse than no escape hatch,
    so everything that is not the exact marker falls back to the strict reading:
    a misspelling, a status of another word, the prose blockquote the older
    plans carry, and no status line at all.
    """
    cases = [
        ("**Status:** in progress\n", True),
        ("**Status:** delivered\n", False),
        ("**Status:** in-progress\n", False),
        ("**Status:**in progress\n", True),
        ("> **Status on 2026-08-22: delivered.**\n", False),
        ("no status line here at all\n", False),
    ]
    for text, expected in cases:
        plan = tmp_path / "plan.md"
        plan.write_text(text, encoding="utf-8")
        assert _is_in_progress(plan) is expected, f"the rule read {text!r} as {not expected}"
```

- [ ] **Step 3: Draai hem en zie hem falen op de ontbrekende helper**

```bash
uv run --no-sync pytest tests/test_plans.py::test_the_status_rule_reads_only_the_exact_marker -q
```

Verwacht: `NameError: name '_is_in_progress' is not defined`.

- [ ] **Step 4: Voeg het mechanisme toe**

Voeg bij de andere patronen bovenin `tests/test_plans.py`, direct onder `_SPEC`:

```python
#: A plan that says exactly this may name files that are not in the tree yet.
#:
#: Everything else gets the strict reading, including a plan with no status line
#: and a plan whose status is misspelled. Fail closed: an exemption that can be
#: entered by a typo is not an exemption, it is a hole. The pair of tests below
#: is what keeps the marker from being left on: while it is set, a plan whose
#: files all exist fails and says to take it off.
#:
#: `_STATUS` is anchored with `^`, so it matches at the start of any line, not
#: only the one at the top of the file. Taak 13 hieronder shows the marker text
#: as an example inside its own instructions, and if that example sat at column
#: 0 in a fenced code block it would be a second match `_is_in_progress` could
#: find. `.search` only reports the first, so today it would stay silent, but
#: a replace-all across the file (which taak 13 performs) would rewrite the
#: example along with the real marker. That is why the example in taak 13 is
#: shown four-space indented rather than as a column-0 code sample: indentation
#: keeps it from being a candidate for either the regex or the replace-all.
IN_PROGRESS = "in progress"

_STATUS = re.compile(r"^\*\*Status:\*\*\s*(.+?)\s*$", re.MULTILINE)


def _is_in_progress(plan: Path) -> bool:
    match = _STATUS.search(plan.read_text(encoding="utf-8"))
    return match is not None and match.group(1).strip() == IN_PROGRESS
```

Vervang `test_every_file_a_plan_names_exists` door dit paar. De docstring van de eerste blijft staan zoals hij is, met de laatste alinea eraan toegevoegd:

```python
@pytest.mark.parametrize("plan", PLANS, ids=lambda plan: plan.name)
def test_every_file_a_finished_plan_names_exists(plan: Path) -> None:
    """Measured on 2026-08-22: six plans make 172 references to 150 distinct
    names and every one of them is in the tree, so all six are delivered.

    The twenty-two named twice are files one plan creates and another modifies,
    which is the seam between two plans and where a rename does the most damage.

    A plan marked in progress is not checked here and is not unchecked either:
    the test below holds it to the opposite claim, that something it names is
    still missing. Between the two there is no plan and no state that is green
    because the question did not apply.
    """
    if _is_in_progress(plan):
        return
    missing = sorted({names[0] for names in _named_paths(plan) if not _exists(names)})
    assert not missing, (
        f"{plan.name} names files that are not in the tree:\n"
        + "\n".join(f"  {path}" for path in missing)
        + "\nEither the work is not done, or something was renamed and the plan "
        "still points at where it used to be."
    )


@pytest.mark.parametrize("plan", PLANS, ids=lambda plan: plan.name)
def test_a_plan_marked_in_progress_is_actually_unfinished(plan: Path) -> None:
    """The marker cannot be left on, because finishing the work turns it red.

    Two ways an in-progress plan can be lying. It can be finished, in which case
    the status is stale and the strict check above is not running over a plan
    that should be under it. Or it can name nothing that exists at all, which is
    what a plan pointing at a directory that moved looks like, and the marker
    would hide that for as long as it stayed on.
    """
    if not _is_in_progress(plan):
        return
    names = _named_paths(plan)
    assert names, f"{plan.name} is marked '{IN_PROGRESS}' and names no files at all"
    distinct = {entry[0] for entry in names}
    missing = {entry[0] for entry in names if not _exists(entry)}
    assert missing, (
        f"{plan.name} is marked '{IN_PROGRESS}' and every file it names is in the tree. "
        f"The work is done: change the status line to something other than '{IN_PROGRESS}', "
        "which puts the plan back under the strict check."
    )
    assert missing != distinct, (
        f"{plan.name} names {len(distinct)} files and not one of them exists. That is not "
        "an unfinished plan, that is a plan pointing at somewhere else entirely."
    )
```

Verhoog in `test_the_scan_actually_reads_the_plans` de ondergrens van zes naar zeven:

```python
    assert len(PLANS) >= 7, f"only found {[plan.name for plan in PLANS]} under {PLANS_DIR}"
```

- [ ] **Step 5: Draai alles en zie het groen worden**

```bash
uv run --no-sync pytest tests/test_plans.py -q
```

Verwacht: alle tests slagen. `test_every_file_a_finished_plan_names_exists[2026-09-04-accounts-auth.md]` valt door de vroege `return` heen en `test_a_plan_marked_in_progress_is_actually_unfinished` vindt de ontbrekende bestanden die stap 1 opsomde.

- [ ] **Step 6: Toon aan dat beide nieuwe takken rood kunnen worden**

Twee keer een tijdelijke bewerking, allebei terugdraaien. Dit is de enige stap die niets oplevert behalve zekerheid, en zonder deze stap is stap 5 een groene uitslag van een instrument waarvan niemand weet of het aanstaat.

```bash
# Tak 1: een afgerond plan dat nog in progress zegt.
sed -i 's/^\*\*Status:\*\* in progress$/**Status:** in progress/' /dev/null  # geen wijziging, plaatshouder
uv run --no-sync pytest "tests/test_plans.py::test_a_plan_marked_in_progress_is_actually_unfinished[2026-08-21-advice-api.md]" -q
```

Die laatste slaat over omdat dat plan geen marker draagt. Zet er tijdelijk `**Status:** in progress` in, direct onder de blokquote, draai opnieuw, en verwacht: `every file it names is in the tree. The work is done`. Haal de regel weg.

```bash
# Tak 2: dit plan zegt niets meer over zijn status.
```
Haal in dit bestand tijdelijk de regel `**Status:** in progress` weg en draai `uv run --no-sync pytest tests/test_plans.py -q`. Verwacht: `test_every_file_a_finished_plan_names_exists[2026-09-04-accounts-auth.md]` faalt met dezelfde lijst als in stap 1. Zet de regel terug.

- [ ] **Step 7: Zie de rode test die de tweede valstrik veroorzaakt**

```bash
uv run --no-sync pytest tests/test_pipeline_contract.py::test_every_test_file_named_in_a_comment_exists -q
```

Verwacht: rood, met een lijst van namen als `tests/test_accounts_api.py`, elk genoemd in `docs/superpowers/plans/2026-09-04-accounts-auth.md`, in `docs/superpowers/specs/2026-09-04-accounts-auth-design.md` en, als de SDD-werkmap van deze run nog op schijf staat, in `.superpowers/sdd/2026-09-04-accounts-auth/progress.md`. Het precieze aantal namen schuift mee met wat dit plan op dat moment noemt en is niet de bewering; de bewering is dat de lijst niet leeg is. Dat laatste pad is git-genegeerd (`.superpowers/sdd/.gitignore` bevat een kale `*`) maar `_files_that_can_carry_a_reference` loopt met `os.walk` over de werkmap en raadpleegt git voor niets, dus de map wordt toch gelezen.

- [ ] **Step 8: Schrijf de tests die de twee reparaties vastpinnen**

Twee dingen moeten waar zijn, en geen van beide mag aangenomen worden. Voeg toe aan `tests/test_pipeline_contract.py`, na `_files_that_can_carry_a_reference`:

```python
def test_a_directory_named_dot_superpowers_is_never_walked(tmp_path: Path) -> None:
    """The SDD scratch workspace, which git never sees and os.walk always does.

    `_NOT_OURS`'s own docstring calls itself "directories whose contents are
    not this repository's own source", and a git-ignored agent workspace is
    exactly that. Built on a throwaway tree rather than the real repository,
    so this does not depend on a run happening to be mid-flight when it runs.
    """
    # Built from two halves at runtime rather than written out whole: a whole
    # "tests/test_..._anywhere.py" literal in this plan's own source would be
    # a reference this very check would flag once the plan is no longer
    # exempt, which is the trap ruling 6 already names for the status marker.
    nonexistent = "tests/test_does_not" + "_exist_anywhere.py"
    (tmp_path / ".superpowers" / "sdd").mkdir(parents=True)
    carrier = tmp_path / ".superpowers" / "sdd" / "progress.md"
    carrier.write_text(f"{nonexistent}\n", encoding="utf-8")
    (tmp_path / "real.md").write_text("tests/test_pipeline_contract.py\n", encoding="utf-8")

    found = {path.name for path in _files_that_can_carry_a_reference(tmp_path)}
    assert "progress.md" not in found, ".superpowers is walked and should be pruned"
    assert "real.md" in found, "the walk was pruned so hard it lost a file that is ours"


def test_a_spec_is_exempt_only_when_its_own_plan_is_in_progress(tmp_path: Path) -> None:
    """The pairing, run rather than reasoned about.

    A spec never says "in progress" in its own status line: every spec in
    docs/superpowers/specs/ opens with "Status: vastgesteld, klaar voor
    implementatieplan", delivered or not, so a spec's exemption cannot come
    from its own text. It has to come from the plan it was written for, and
    this proves it both ways: exempt while that plan is in progress, not
    exempt the moment the plan says anything else, and not exempt at all when
    there is no such plan on disk.
    """
    plans = tmp_path / "docs" / "superpowers" / "plans"
    specs = tmp_path / "docs" / "superpowers" / "specs"
    plans.mkdir(parents=True)
    specs.mkdir(parents=True)
    plan = plans / "2026-09-04-accounts-auth.md"
    spec = specs / "2026-09-04-accounts-auth-design.md"
    spec.write_text("Status: vastgesteld, klaar voor implementatieplan\n", encoding="utf-8")

    plan.write_text("**Status:** in progress\n", encoding="utf-8")
    assert _is_in_progress(spec) is True

    plan.write_text("**Status:** delivered\n", encoding="utf-8")
    assert _is_in_progress(spec) is False

    orphan = specs / "2026-09-04-nothing-design.md"
    orphan.write_text("Status: vastgesteld, klaar voor implementatieplan\n", encoding="utf-8")
    assert _is_in_progress(orphan) is False
```

- [ ] **Step 9: Draai ze en zie ze falen op de ontbrekende helpers**

```bash
uv run --no-sync pytest tests/test_pipeline_contract.py::test_a_directory_named_dot_superpowers_is_never_walked tests/test_pipeline_contract.py::test_a_spec_is_exempt_only_when_its_own_plan_is_in_progress -q
```

Verwacht: `TypeError: _files_that_can_carry_a_reference() takes 0 positional arguments but 1 was given` voor de eerste (hij bestaat al, maar zonder argument), en `NameError: name '_is_in_progress' is not defined` voor de tweede.

- [ ] **Step 10: Voeg het mechanisme toe**

Geef `_files_that_can_carry_a_reference` een optionele wortel, zodat de test hierboven hem op een tijdelijke boom kan draaien in plaats van op deze repository:

```python
def _files_that_can_carry_a_reference(root: Path = REPO_ROOT) -> list[Path]:
    """Every file of ours that could name a test, pruned during the walk.

    Pruned rather than filtered afterwards: rglob descends into .venv and
    node_modules first and discards them second, which cost fourteen seconds
    against a suite that runs in forty. A test slow enough to be noticed is a
    test somebody eventually runs with -k.

    `root` defaults to this repository and exists so a test can point this at
    a throwaway tree instead, the same reason tests/test_plans.py takes
    `tmp_path` rather than writing into `PLANS_DIR`.
    """
    suffixes = {".py", ".sh", ".yml", ".yaml", ".ts", ".tsx", ".md", ".toml", ".conf"}
    skip = {name.strip("/") for name in _NOT_OURS}
    found: list[Path] = []
    for directory, subdirectories, filenames in os.walk(root):
        subdirectories[:] = [name for name in subdirectories if name not in skip]
        for filename in filenames:
            path = Path(directory) / filename
            if path.suffix in suffixes:
                found.append(path)
    return found
```

Voeg `/.superpowers/` toe aan `_NOT_OURS`:

```python
_NOT_OURS = (
    "/.venv/",
    "/node_modules/",
    "/.git/",
    "/out/",
    "/data/",
    "/.next/",
    "/htmlcov/",
    "/.superpowers/",
)
```

Voeg de marker- en koppelingslogica toe, direct boven `test_every_test_file_named_in_a_comment_exists`:

```python
#: The same fail-closed marker tests/test_plans.py uses, read independently
#: here so this file's own defence does not depend on that module's
#: internals. A plan without the exact marker (a typo, another word, no
#: status line at all) falls back to the strict reading, same as there.
_PLAN_STATUS = re.compile(r"^\*\*Status:\*\*\s*(.+?)\s*$", re.MULTILINE)

#: docs/superpowers/specs/{name}-design.md pairs with docs/superpowers/plans/{name}.md:
#: the same date-prefixed name, differing only by this suffix.
_SPEC_SUFFIX = "-design.md"


def _plan_that_speaks_for(path: Path) -> Path:
    """Which file's status marker this path's references are exempt under.

    A plan under docs/superpowers/plans/ speaks for itself. A spec under
    docs/superpowers/specs/ speaks for the plan it was written for: specs
    carry no completion status of their own, so a spec's exemption has to
    come from the plan. Anything else speaks for itself too, which
    `_is_in_progress` then reads as "not a plan, no marker, not exempt".
    """
    posix = path.as_posix()
    if "docs/superpowers/specs/" in posix and path.name.endswith(_SPEC_SUFFIX):
        plan_name = path.name[: -len(_SPEC_SUFFIX)] + ".md"
        return path.parents[1] / "plans" / plan_name
    return path


def _is_in_progress(path: Path) -> bool:
    plan = _plan_that_speaks_for(path)
    if not plan.is_file():
        return False
    match = _PLAN_STATUS.search(plan.read_text(encoding="utf-8"))
    return match is not None and match.group(1).strip() == "in progress"
```

Werk `test_every_test_file_named_in_a_comment_exists` bij zodat hij de uitzondering toepast:

```python
def test_every_test_file_named_in_a_comment_exists() -> None:
    """This repository explains itself by naming the test that holds each rule.
    ...(bestaande docstring blijft staan)...

    A plan still being built, and the spec it was written from, may name a test
    that does not exist yet. tests/test_plans.py already holds the plan itself
    to the opposite promise elsewhere, that something it names is still
    missing, so a second red here would say nothing a reader could not already
    tell from that test. The exemption is read fresh from the plan's own
    status line on every run, not assumed, so a finished plan (and its spec)
    falls straight back under the strict reading below.
    """
    missing: dict[str, set[str]] = {}
    for path in _files_that_can_carry_a_reference():
        if _is_in_progress(path):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:  # pragma: no cover - binary with a text suffix
            continue
        for reference in set(_TEST_REFERENCE.findall(text)):
            if not (REPO_ROOT / reference).is_file():
                missing.setdefault(reference, set()).add(path.relative_to(REPO_ROOT).as_posix())
    assert not missing, "comments name test files that do not exist:\n" + "\n".join(
        f"  {reference} named in {sorted(where)}" for reference, where in sorted(missing.items())
    )
```

- [ ] **Step 11: Draai alles en zie het groen worden**

```bash
uv run --no-sync pytest tests/test_pipeline_contract.py -q
```

Verwacht: alles groen, inclusief de twee nieuwe tests uit stap 8 en `test_every_test_file_named_in_a_comment_exists` zelf, ondanks dat het plan en de spec nog steeds testbestanden noemen die niet bestaan.

- [ ] **Step 12: Toon aan dat beide reparaties rood kunnen worden**

Zet `/.superpowers/` tijdelijk weer uit `_NOT_OURS`, draai `uv run --no-sync pytest tests/test_pipeline_contract.py::test_a_directory_named_dot_superpowers_is_never_walked -q` en verwacht een falende eerste assertie. Zet hem terug.

Zet daarna in dit plandocument tijdelijk de regel `**Status:** in progress` om in iets anders, en draai:

```bash
uv run --no-sync pytest tests/test_pipeline_contract.py::test_every_test_file_named_in_a_comment_exists -q
```

Verwacht: rood, met dezelfde lijst als in stap 7, plan en spec allebei weer als bron. Dat de spec hier opnieuw meedoet is het bewijs dat `_plan_that_speaks_for` de spec aan het plan koppelt en niet toevallig meegroen was: haar eigen statusregel is nooit veranderd. Zet de regel terug.

- [ ] **Step 13: Commit**

```bash
git add tests/test_plans.py tests/test_pipeline_contract.py docs/superpowers/plans/2026-09-04-accounts-auth.md
git commit
```

Boodschap: `test(plans): a plan may be unfinished, and may not lie about it`.

---

### Taak 2: Meting 1, telt de cache elke ophoging

**Hangt af van:** niets.

Hoofdstuk 9.6 van de spec zet deze meting vooraan omdat de uitkomst het ontwerp eronder raakt. `AXES_HANDLER = "axes.handlers.cache.AxesCacheHandler"` bestaat om te voorkomen dat er een tabel met een `ip_address`-kolom ontstaat, en die keuze is alleen verdedigbaar als de teller in die cache een lockout kan dragen. In productie is die cache `DatabaseCache` in Postgres.

Wat gemeten moet worden is niet "is het atomair", want dat is het aantoonbaar niet: Django's `DatabaseCache` implementeert `incr` niet zelf, dus `BaseCache.incr` geldt en dat is een lezing gevolgd door een schrijving. Wat gemeten moet worden is of het verlies onder gelijktijdigheid de lockout **uitstelt** of **uitschakelt**, want alleen het tweede is een ontwerpfout.

**Files:**
- Create: `tests/test_accounts_lockout_store.py`

**Interfaces:**
- Consumes: `backend/advice/migrations/0002_cache_table.py` (de tabel `ampeer_cache` bestaat al in de testdatabase).
- Produces: het gemeten verliespercentage, dat taak 12 in `docs/decisions.md` vastlegt; de constante `CONCURRENT_WRITERS: int` en `WRITES_PER_WORKER: int` in dit testbestand.

- [ ] **Step 1: Schrijf de test die de exacte helft vastlegt**

Maak `tests/test_accounts_lockout_store.py`:

```python
"""Can the cache in production carry a lockout counter.

`AXES_HANDLER` is set to the cache handler so that no table with an
`ip_address` column ever exists, which is chapter 3.2 of the design. In
production that cache is `DatabaseCache` in Postgres, and Django does not
implement `incr` for it: `BaseCache.incr` reads and then writes, so two workers
that raise the same counter at the same moment lose one of the two.

That is measured here rather than assumed, and the question is deliberately not
"is it atomic". It is not. The question is whether the loss delays a lockout or
removes it, because only the second is a design fault. A counter that reaches
five after seven attempts instead of five still locks the account; a counter
that never reaches five does not.
"""

from __future__ import annotations

import threading

import pytest
from django.core.cache import caches
from django.db import connections
from django.test import override_settings

from ampeer.settings import base

#: Far past anything a real attacker gets through the rate limit in front of
#: this, and the point is to be far past it: if the property holds under an
#: absurd amount of contention it holds under a realistic amount.
CONCURRENT_WRITERS = 8
WRITES_PER_WORKER = 25

#: `AXES_FAILURE_LIMIT` in the settings. Written here as its own name rather
#: than imported, because this test has to keep meaning something if the
#: setting is raised, and the assertion below is about crossing a threshold
#: that a lockout uses, not about this particular number.
LOCKOUT_THRESHOLD = 5

DATABASE_CACHE = {
    "lockout": {
        "BACKEND": "django.core.cache.backends.db.DatabaseCache",
        # Not the literal "ampeer_cache" a second time. base.py:114-117 warns
        # that two literals which must agree are one literal that eventually
        # will not, about this exact string and the migration that creates
        # the table it names.
        "LOCATION": base.AMPEER_CACHE_TABLE,
    }
}


def _bump(alias: str, key: str, times: int) -> None:
    """One worker's share of the increments, the way the cache handler does it."""
    cache = caches[alias]
    for _ in range(times):
        cache.set(key, (cache.get(key) or 0) + 1, 3600)
    for connection in connections.all():
        connection.close()


@pytest.mark.django_db(transaction=True)
@override_settings(CACHES=DATABASE_CACHE)
def test_the_database_cache_counts_a_sequential_run_exactly() -> None:
    """The half that has to be exact, and would make everything else moot."""
    caches["lockout"].delete("sequential")
    _bump("lockout", "sequential", CONCURRENT_WRITERS * WRITES_PER_WORKER)
    assert caches["lockout"].get("sequential") == CONCURRENT_WRITERS * WRITES_PER_WORKER
```

- [ ] **Step 2: Draai hem**

```bash
uv run --no-sync pytest tests/test_accounts_lockout_store.py -q
```

Verwacht: groen. Zo niet, dan is `DatabaseCache` onbruikbaar voor elke teller, ook voor de bestaande snelheidslimiet, en dan stopt deze taak en meldt dat als een bevinding over `prod.py` en niet over dit ontwerp.

- [ ] **Step 3: Voeg de gelijktijdige meting toe**

```python
@pytest.mark.django_db(transaction=True)
@override_settings(CACHES=DATABASE_CACHE)
def test_a_lockout_threshold_is_still_crossed_under_contention() -> None:
    """What the design actually needs, and it is not exactness.

    The measured shortfall goes in docs/decisions.md rather than in an
    assertion, because it is a property of the machine and the moment. What is
    asserted is the pair of bounds that decide whether the cache handler is
    usable at all: the counter never overshoots, so nobody is locked out early,
    and it clears the threshold a lockout fires at, so nobody is not locked out.
    """
    total = CONCURRENT_WRITERS * WRITES_PER_WORKER
    caches["lockout"].delete("contended")
    workers = [
        threading.Thread(target=_bump, args=("lockout", "contended", WRITES_PER_WORKER))
        for _ in range(CONCURRENT_WRITERS)
    ]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join()

    counted = caches["lockout"].get("contended")
    assert counted is not None, "the counter is gone entirely, which is not a race but a loss"
    assert counted <= total, (
        f"the counter reached {counted} out of {total} writes, which is more than were made. "
        "An overcounting lockout locks people out of their own accounts."
    )
    assert counted >= LOCKOUT_THRESHOLD, (
        f"{total} concurrent failed attempts moved the counter to {counted}, which is below "
        f"the {LOCKOUT_THRESHOLD} a lockout fires at. The cache handler cannot carry this "
        "counter and design chapter 3.2 has to be reopened."
    )
    print(
        f"\nMEASUREMENT 1: {counted} of {total} increments survived "
        f"{CONCURRENT_WRITERS} concurrent writers"
    )
```

- [ ] **Step 4: Draai en noteer het getal**

```bash
uv run --no-sync pytest tests/test_accounts_lockout_store.py -q -s
```

Verwacht: groen, met een regel `MEASUREMENT 1: <n> of 200 increments survived 8 concurrent writers`. **Noteer dat getal en de datum.** Taak 12 schrijft het in `docs/decisions.md`. Wordt de derde assertie rood, dan stopt dit plan hier en gaat hoofdstuk 3.2 van de spec terug naar de gebruiker.

- [ ] **Step 5: Toon aan dat de controle rood kan worden**

Zet `LOCKOUT_THRESHOLD` tijdelijk op `total + 1` en draai opnieuw. Verwacht: `which is below the 201 a lockout fires at`. Zet hem terug op 5. Zonder deze stap zegt stap 4 alleen dat er iets gedraaid heeft.

- [ ] **Step 6: Commit**

Boodschap: `test(accounts): measure whether a shared cache can carry a lockout counter`.

---

## Fase 1: de app en de instellingen

### Taak 3: Afhankelijkheden, instellingen, de `accounts`-app en `User`

**Hangt af van:** taak 2 (de uitkomst bevestigt `AXES_HANDLER`).

Deze taak is groot en kan niet gesplitst worden. `django.contrib.auth` in `INSTALLED_APPS` zonder een `AUTH_USER_MODEL` dat ergens naar wijst, start niet; een `AUTH_USER_MODEL` zonder app en model bestaat niet; en `tests/test_backend_settings.py::test_authentication_never_arrives_without_its_defences` wordt rood zodra die app erin staat, tenzij axes, de backendvolgorde en Argon2 in dezelfde commit zitten. Dat is precies wat die valstrik moet afdwingen, dus hij wordt gehoorzaamd en niet omzeild.

**Files:**
- Modify: `pyproject.toml`, `uv.lock`
- Create: `backend/accounts/__init__.py`, `backend/accounts/apps.py`, `backend/accounts/models.py`, `backend/accounts/lockout.py`, `backend/accounts/migrations/__init__.py`, `backend/accounts/migrations/0001_initial.py`
- Modify: `backend/ampeer/settings/base.py`, `backend/ampeer/settings/dev.py`, `backend/ampeer/settings/prod.py`
- Test: `tests/test_accounts_models.py`, `tests/test_backend_settings.py`

**Interfaces:**
- Consumes: `advice.throttling.HashedIdentScopedRateThrottle` (bestaat), met `get_ident(request: Request) -> str`.
- Produces:
  - `accounts.models.User`, met `email: str`, `is_active: bool`, `date_joined: datetime`, `USERNAME_FIELD = "email"`
  - `accounts.models.UserManager.create_user(email: str, password: str) -> User`
  - `accounts.lockout.client_ip(request: HttpRequest) -> str`
  - `accounts.lockout.username(request: HttpRequest, credentials: dict[str, object] | None) -> str`
  - instellingen `AMPEER_ACCESS_COOKIE: str`, `AMPEER_REFRESH_COOKIE: str`, `AMPEER_ACCESS_COOKIE_PATH: str`, `AMPEER_REFRESH_COOKIE_PATH: str`, `AMPEER_COOKIE_SECURE: bool`
  - throttlescopes `auth-register`, `auth-login`, `auth-refresh`, `auth-read`, `auth-write`, `auth-export`

- [ ] **Step 1: Voeg de drie pakketten toe**

```bash
uv add --group backend "djangorestframework-simplejwt>=5.5" "django-axes>=8.0" "argon2-cffi>=25.1"
uv sync --locked --group dev --group backend
```

Controleer daarna dat `uv.lock` is gewijzigd en meegecommit wordt. Controleer ook dat de API-image bouwt met `argon2-cffi` erin: dat pakket draagt een C-extensie en levert manylinux-wheels, dus er hoort niets te veranderen aan `infra/api.Dockerfile`. Bouwt het niet, dan is dat een bevinding en geen wijziging die deze taak mag maken.

- [ ] **Step 2: Schrijf de falende test voor het gebruikersmodel**

Maak `tests/test_accounts_models.py`:

```python
"""What an account is, and what it deliberately is not."""

from __future__ import annotations

import pytest
from django.db.utils import IntegrityError

from accounts.models import User


@pytest.mark.django_db
def test_an_email_address_is_stored_in_lower_case() -> None:
    """`BaseUserManager.normalize_email` lowers only the domain.

    With the local part left as typed, `A@voorbeeld.nl` and `a@voorbeeld.nl` are
    two accounts and, in accounts/lockout.py, two lockout keys, so five failed
    attempts against one address count as five against two. That halves the
    brute force defence without anybody seeing it happen.
    """
    user = User.objects.create_user(email="Iemand@Voorbeeld.NL", password="een-lang-wachtwoord")
    assert user.email == "iemand@voorbeeld.nl"


@pytest.mark.django_db
def test_the_same_address_in_other_capitals_is_not_a_second_account() -> None:
    User.objects.create_user(email="iemand@voorbeeld.nl", password="een-lang-wachtwoord")
    with pytest.raises(IntegrityError):
        User.objects.create_user(email="IEMAND@VOORBEELD.NL", password="een-ander-wachtwoord")


@pytest.mark.django_db
def test_the_password_is_never_stored_as_typed() -> None:
    user = User.objects.create_user(email="iemand@voorbeeld.nl", password="een-lang-wachtwoord")
    assert "een-lang-wachtwoord" not in user.password
    assert user.password.startswith("argon2$argon2id$"), (
        f"the stored hash begins {user.password[:24]!r}, which is not Argon2id"
    )
    assert user.check_password("een-lang-wachtwoord")


@pytest.mark.django_db
def test_the_string_form_of_a_user_never_carries_the_address() -> None:
    """A model's `__str__` ends up in exception text and in shell output, and
    `RedactedFormatter` in the settings drops messages precisely because nobody
    can predict which ones carry a secret. Not putting it there is cheaper."""
    user = User.objects.create_user(email="iemand@voorbeeld.nl", password="een-lang-wachtwoord")
    assert "voorbeeld" not in str(user)


def test_creating_a_user_without_an_email_address_is_refused() -> None:
    """The branch `create_user` takes before it ever reaches the database.

    Django's own `createsuperuser` management command calls `create_user` with
    whatever `USERNAME_FIELD` resolves to, and on a model with no username that
    is nothing unless this raises first. No `@pytest.mark.django_db`: the point
    is that this never gets as far as a query.
    """
    with pytest.raises(ValueError, match="email"):
        User.objects.create_user(email="", password="een-lang-wachtwoord")


def test_an_account_carries_no_name_and_no_username() -> None:
    """Django's default User forces three columns this product never fills, and
    two of them are called a name in a document that says there is no name."""
    fields = {field.name for field in User._meta.get_fields()}
    assert not fields & {"username", "first_name", "last_name"}, (
        f"the user model grew {sorted(fields & {'username', 'first_name', 'last_name'})}"
    )
```

- [ ] **Step 3: Draai en zie hem falen**

```bash
uv run --no-sync pytest tests/test_accounts_models.py -q
```

Verwacht: `ModuleNotFoundError: No module named 'accounts'`.

- [ ] **Step 4: Maak de app en het model**

`backend/accounts/__init__.py`: leeg.

`backend/accounts/apps.py`:

```python
from __future__ import annotations

from django.apps import AppConfig


class AccountsConfig(AppConfig):
    name = "accounts"
    verbose_name = "Accounts"
```

`backend/accounts/migrations/__init__.py`: leeg.

`backend/accounts/models.py`:

```python
"""The account, and nothing that is not needed to be one.

`backend/advice/models.py` opens by saying that none of its tables holds a
personal detail, and docs/dpia.md chapter 2 leans on that sentence. This file
is where that stops being true, which is exactly why it is a separate file: one
promise per module stays checkable, where a longer exception would not.
"""

from __future__ import annotations

from typing import Any, ClassVar, Self

from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.db import models
from django.utils import timezone


class UserManager(BaseUserManager["User"]):
    """The only way an account is made, so normalisation cannot be skipped."""

    def create_user(self, email: str, password: str) -> User:
        if not email:
            raise ValueError("an account needs an email address")
        user = self.model(email=self.normalize_email(email).strip().lower())
        user.set_password(password)
        user.save(using=self._db)
        return user


class User(AbstractBaseUser):
    """One household's identity, and the whole of it.

    No username, no first name, no last name and no postcode. The postcode stays
    where it belongs, in `StoredAdvice.inputs`, on four digits, refused rather
    than truncated. `PermissionsMixin` is absent on purpose: there is no admin
    and there are no roles, so its two join tables would hold nothing.
    """

    email = models.EmailField(unique=True, db_index=True)
    is_active = models.BooleanField(default=True)
    #: Not `auto_now_add`, for the same reason `StoredAdvice.created_at` is not.
    date_joined = models.DateTimeField(default=timezone.now, editable=False)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS: ClassVar[list[str]] = []

    objects = UserManager()

    def __str__(self) -> str:
        """Deliberately not the address. A `__str__` reaches exception text and
        shell output, and neither is a place this project writes an address."""
        return f"user {self.pk}"
```

`backend/accounts/lockout.py`:

```python
"""Who axes is counting, without writing down who that is.

django-axes counts failed attempts per caller and per account name, and by
default it writes both into `AccessAttempt` rows with an `ip_address` column.
The handler in the settings keeps those tables from existing at all; these two
callables keep the values that end up in the cache key from being an address or
an email address either. Removing the tables and leaving the addresses in the
keys would have taken away the address book and left the addresses.

The caller identity is not computed here, it is asked of the throttle that
already answers that question. Two definitions of "the same visitor" that must
agree are one definition that eventually will not, and this one also inherits
`NUM_PROXIES`, which is the setting that decides whether the answer means
anything at all.
"""

from __future__ import annotations

from django.http import HttpRequest
from django.utils.crypto import salted_hmac
from rest_framework.request import Request

from advice.throttling import HashedIdentScopedRateThrottle

#: A namespace for `username`'s digest only, so it can never collide with
#: another use of SECRET_KEY. `client_ip` below does not use it: it reuses
#: `HashedIdentScopedRateThrottle`'s own digest instead of salting a second
#: one, which is a deliberate deviation from an earlier reading of spec 9.3
#: that had both callables salt with this constant. Task 12 corrects that
#: chapter to say so instead of leaving the deviation unlabelled.
KEY_SALT = "ampeer.accounts.lockout"

#: 128 bits of the digest, hex, like advice/throttling.py.
DIGEST_CHARS = 32

_THROTTLE = HashedIdentScopedRateThrottle()


def client_ip(request: HttpRequest) -> str:
    """What axes counts a caller as: the digest the rate limit already uses.

    Deliberately not `axes.helpers.get_client_ip_address`. That function reads
    `AXES_CLIENT_IP_CALLABLE` and calls it, so calling it from here would
    recurse until the stack ran out.
    """
    return _THROTTLE.get_ident(Request(request))


def username(request: HttpRequest, credentials: dict[str, object] | None) -> str:
    """What axes counts an account as, without holding the address.

    Lowered before hashing, and that is load bearing rather than tidy: the
    address is stored lowered, so a login attempt in other capitals has to
    produce the same digest or five attempts against one account count as five
    against two.
    """
    raw = ""
    if credentials:
        value = credentials.get("username", credentials.get("email", ""))
        if isinstance(value, str):
            raw = value.strip().lower()
    return salted_hmac(KEY_SALT, raw, algorithm="sha256").hexdigest()[:DIGEST_CHARS]
```

- [ ] **Step 5: Zet de instellingen om, en let op de volgorde**

In `backend/ampeer/settings/base.py`, vervang de `INSTALLED_APPS`-lijst op regel 21 en het commentaarblok op regel 29 tot 30:

```python
INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "django.contrib.staticfiles",
    "axes",
    "corsheaders",
    "rest_framework",
    "advice.apps.AdviceConfig",
    "accounts.apps.AccountsConfig",
]

# Still no sessions and no admin. Phase 1 adds something to log in to, and that
# is the only reason `django.contrib.auth` is here; a session is a second way to
# hold an identity and this service holds one, in a cookie, as a JWT.
```

Deze wijziging maakt een bestaande test onwaar. `tests/test_backend_settings.py::test_nothing_authenticates_because_there_is_nothing_to_log_in_to` beweert `assert "django.contrib.auth" not in settings.INSTALLED_APPS`, en dat klopt vanaf deze regel niet meer. Toon dat eerst aan:

```bash
uv run --no-sync pytest tests/test_backend_settings.py::test_nothing_authenticates_because_there_is_nothing_to_log_in_to -q
```

Verwacht: rood op precies die regel, `assert "django.contrib.auth" not in [...]`.

Verwijder in die test de regel `assert "django.contrib.auth" not in settings.INSTALLED_APPS` en laat de drie overige assertions staan. Herschrijf de docstring naar de versmalde belofte die overblijft: geen sessie, geen admin en een lege `DEFAULT_AUTHENTICATION_CLASSES`, niet langer "er is niets om in te loggen".

```python
def test_nothing_authenticates_because_there_is_nothing_to_log_in_to() -> None:
    """Sessions and admin stay absent, and so does an authentication class on
    the public endpoints, even though accounts now exist.

    `django.contrib.auth` itself is no longer absent: task 3 of
    docs/superpowers/plans/2026-09-04-accounts-auth.md adds it, because
    AUTH_USER_MODEL needs it to start. What CLAUDE.md and this test actually
    guard is narrower and still holds: no session middleware, no admin site,
    and REST_FRAMEWORK["DEFAULT_AUTHENTICATION_CLASSES"] stays empty so the
    advice endpoints remain anonymous. A brute force defence with no login to
    defend was the old reading; from this commit there is a login, and axes
    defends it, which is test_authentication_never_arrives_without_its_defences,
    lower in this file.
    """
    from django.conf import settings

    assert settings.REST_FRAMEWORK["DEFAULT_AUTHENTICATION_CLASSES"] == []
    assert "django.contrib.sessions" not in settings.INSTALLED_APPS
    assert "django.contrib.admin" not in settings.INSTALLED_APPS
```

```bash
uv run --no-sync pytest tests/test_backend_settings.py::test_nothing_authenticates_because_there_is_nothing_to_log_in_to -q
```

Verwacht: groen.

Voeg in `MIDDLEWARE` `axes.middleware.AxesMiddleware` toe **als laatste**, onder `XFrameOptionsMiddleware`. Axes schrijft in zijn eigen installatie-instructies dat zijn middleware achteraan hoort, omdat hij het antwoord op een geblokkeerde poging vormt en niets ervoor hoeft te zien.

Voeg daaronder toe:

```python
AUTH_USER_MODEL = "accounts.User"

# Axes first, and that ordering is the whole point: a lockout that runs second
# is a lockout the attempt has already got past. tests/test_backend_settings.py
# asserts this position rather than the mere presence of the entry.
AUTHENTICATION_BACKENDS = [
    "axes.backends.AxesStandaloneBackend",
    "django.contrib.auth.backends.ModelBackend",
]

# Argon2id, and Django's Argon2PasswordHasher is that variant. Argon2 does not
# replace a blank here, it replaces PBKDF2, which Django supplies whether or not
# anybody asked for it. That is the harder kind of default to remember.
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
]

# Twelve and not eight. Length beats composition, and this is the only knob on
# this list that is worth turning.
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 12},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ---------------------------------------------------------------------------
# The lockout, and the two callables that keep it from writing anybody down.
#
# The cache handler rather than the database one, because the database handler
# creates AccessAttempt, AccessLog and AccessFailureLog, each with an
# ip_address column, and docs/dpia.md chapter 2 says there is no IP address in
# any table. Nothing in this repository would have caught that: the test that
# guards the sentence reads backend/advice/models.py, so a third party's models
# do not appear in it.
#
# Measured on 2026-09-04 before this handler was chosen: the counter in
# DatabaseCache is a read followed by a write, so concurrent writers lose some
# increments. What it does not do is stop crossing the threshold a lockout
# fires at, which is the property that matters. See
# tests/test_accounts_lockout_store.py and docs/decisions.md.
# ---------------------------------------------------------------------------
AXES_HANDLER = "axes.handlers.cache.AxesCacheHandler"
AXES_CLIENT_IP_CALLABLE = "accounts.lockout.client_ip"
AXES_USERNAME_CALLABLE = "accounts.lockout.username"
AXES_LOCKOUT_PARAMETERS = [["username", "ip_address"]]
AXES_FAILURE_LIMIT = 5
AXES_COOLOFF_TIME = 1
# Axes answers a locked out attempt itself. 429 rather than its default 403,
# because that is what DRF's own throttle answers and what
# frontend/src/app/_flow/messages.ts already turns into the one sentence where
# waiting is the correct advice.
AXES_HTTP_RESPONSE_CODE = 429

# ---------------------------------------------------------------------------
# The cookies the tokens travel in.
#
# Names and paths as constants, because a cookie name written out in two places
# is a cookie name that eventually differs between the view that sets it and the
# view that reads it, and the symptom of that is a silent logout.
#
# SameSite=Strict works here because in production there is one origin:
# infra/nginx/nginx.conf serves the static export and proxies /api/ in the same
# server block, the deploy builds with an empty NEXT_PUBLIC_API_BASE, and the
# CSP on that block says connect-src 'self'.
# ---------------------------------------------------------------------------
AMPEER_ACCESS_COOKIE = "ampeer_access"
AMPEER_REFRESH_COOKIE = "ampeer_refresh"
#: The access token reaches every API route, because phase 2 puts endpoints
#: outside /api/auth/. The refresh token reaches only the two routes that need
#: it, so it does not travel on every request the access token makes.
AMPEER_ACCESS_COOKIE_PATH = "/api/"
AMPEER_REFRESH_COOKIE_PATH = "/api/auth/"
#: Overridden per environment, like SESSION_COOKIE_SECURE already is.
AMPEER_COOKIE_SECURE = False

CSRF_COOKIE_SAMESITE = "Strict"
#: False on purpose and not a weakening. A double submit token that JavaScript
#: cannot read is a token JavaScript cannot send back.
CSRF_COOKIE_HTTPONLY = False

from datetime import timedelta  # noqa: E402  (kept beside the setting it configures)

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=14),
    # Rotation is done by accounts/tokens.py against RefreshSession, not by this
    # package. Its own rotation needs the token_blacklist app, and that app
    # writes the whole refresh JWT into OutstandingToken.token, which is a
    # working credential in a column. CLAUDE.md forbids exactly that, and
    # docs/dpia.md chapter 2 already made the same call for the advice token.
    "ROTATE_REFRESH_TOKENS": False,
    "BLACKLIST_AFTER_ROTATION": False,
    "AUTH_HEADER_TYPES": (),
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
}
```

Voeg de zes scopes toe aan `DEFAULT_THROTTLE_RATES`, onder de drie die er staan:

```python
        # Een echt huishouden registreert een keer. Dit stopt massaal aanmaken.
        "auth-register": "5/hour",
        # Ruim voor iemand die zich vertypt. Axes doet de lockout, dit doet het volume.
        "auth-login": "10/hour",
        # Vier verversingen per uur per apparaat bij een access token van 15 minuten.
        "auth-refresh": "60/hour",
        # Het beginpunt van elke paginalading, net als advice-read.
        "auth-read": "120/hour",
        # Toestemming, uitloggen en verwijderen: handelingen die een mens een paar keer doet.
        "auth-write": "20/hour",
        # De duurste respons die deze API kent.
        "auth-export": "5/hour",
```

Werk tot slot het commentaar boven `CORS_ALLOW_CREDENTIALS` op regel 165 bij, zodat het niet langer belooft wat alleen in productie waar is:

```python
#: No cookies cross this boundary in production, and there they do not have to:
#: nginx serves the site and proxies /api/ in one server block, so the browser
#: never makes a cross-origin call at all. On a developer machine the two halves
#: are on different ports, which is cross-site, and dev.py therefore turns this
#: on for the three named localhost origins and nothing else. Saying so here
#: means a later view cannot start relying on it in production by accident, and
#: that prod.py never gets the line copied up into it.
CORS_ALLOW_CREDENTIALS = False
```

In `backend/ampeer/settings/dev.py`, onder `CORS_ALLOWED_ORIGINS`:

```python
# Cookies mogen hier wel mee, want zonder dat kan een ontwikkelaar niet inloggen:
# localhost:3000 naar 127.0.0.1:8000 is cross-site en de browser laat een
# SameSite=Strict cookie dan liggen. Alleen voor de drie oorsprongen hierboven.
# prod.py zet dit niet, en base.py legt uit waarom dat daar niet hoeft.
CORS_ALLOW_CREDENTIALS = True
AMPEER_COOKIE_SECURE = False
```

In `backend/ampeer/settings/prod.py`, bij de andere `SECURE_`-regels:

```python
AMPEER_COOKIE_SECURE = True
```

- [ ] **Step 6: Maak de migratie**

```bash
uv run --no-sync python backend/manage.py makemigrations accounts --settings ampeer.settings.dev
```

Verwacht `backend/accounts/migrations/0001_initial.py` met `User`. Lees hem na: hij mag geen `username`, `first_name`, `last_name`, `is_staff`, `is_superuser`, `groups` of `user_permissions` bevatten. Staat daar iets van, dan is `PermissionsMixin` of `AbstractUser` per ongeluk gebruikt.

- [ ] **Step 7: Draai de tests en zie ze slagen**

```bash
uv run --no-sync pytest tests/test_accounts_models.py tests/test_backend_settings.py -q
```

Verwacht: alles groen, inclusief `test_authentication_never_arrives_without_its_defences`. Faalt die, dan noemt hij zelf welke van de vier ontbreekt.

- [ ] **Step 8: Toon aan dat de valstrik werkte**

Haal tijdelijk `"axes"` uit `INSTALLED_APPS` en draai `uv run --no-sync pytest tests/test_backend_settings.py::test_authentication_never_arrives_without_its_defences -q`. Verwacht: `axes is not in INSTALLED_APPS`. Zet hem terug. Doe hetzelfde door `Argon2PasswordHasher` naar de tweede plaats te verplaatsen; verwacht `the first PASSWORD_HASHERS entry is not an Argon2 hasher`.

- [ ] **Step 9: Voeg de twee assertions toe die de spec eist en de bestaande test niet dekt**

In `tests/test_backend_settings.py`, onderaan:

```python
def test_the_argon2_hasher_is_the_id_variant() -> None:
    """CLAUDE.md asks for Argon2id, and that is the hasher's `type` attribute
    rather than its class name. Assuming the variant is right because the class
    is called Argon2 is a check that cannot go red."""
    import argon2
    from django.contrib.auth.hashers import get_hasher

    hasher = get_hasher("argon2")
    assert getattr(hasher, "algorithm", "") == "argon2"
    assert getattr(hasher, "type", None) is argon2.low_level.Type.ID, (
        f"the configured Argon2 hasher uses {getattr(hasher, 'type', None)}, not Argon2id"
    )


def test_production_never_lets_a_cookie_cross_an_origin() -> None:
    """dev.py turns CORS_ALLOW_CREDENTIALS on so a developer can log in at all.
    That line copied one file up is an API whose cookies any allowed origin can
    ride, and the allowed origins in production come from the environment."""
    import ampeer.settings.prod as prod

    assert prod.CORS_ALLOW_CREDENTIALS is False
    assert prod.AMPEER_COOKIE_SECURE is True
```

Draai ze, en toon aan dat de tweede rood kan worden door `CORS_ALLOW_CREDENTIALS = True` tijdelijk in `prod.py` te zetten.

- [ ] **Step 10: Commit**

Boodschap: `feat(accounts): an account, hashed with Argon2id and defended by axes`.

---

### Taak 4: Meting 2, sluit axes echt buiten

**Hangt af van:** taak 3.

`django.contrib.auth.middleware.AuthenticationMiddleware` staat niet in `MIDDLEWARE` en kan er niet in, want die vraagt sessies. Bovendien staat `REST_FRAMEWORK["UNAUTHENTICATED_USER"]` op `None`, dus `request.user` is `None` en niet `AnonymousUser`. Of axes daartegen kan is een empirische vraag, en de gevaarlijkste uitkomst is niet een foutmelding maar een lockout die stil niets doet.

**Files:**
- Create: `tests/test_accounts_lockout.py`

**Interfaces:**
- Consumes: `accounts.models.User.objects.create_user(email, password)`; instelling `AXES_FAILURE_LIMIT`.
- Produces: niets voor latere taken. De uitkomst bevestigt of weerlegt hoofdstuk 9.6 van de spec.

- [ ] **Step 1: Schrijf de test die aantoont dat de lockout vuurt**

Maak `tests/test_accounts_lockout.py`:

```python
"""Does the lockout actually fire in a stack with no session middleware.

Axes is normally installed beside `AuthenticationMiddleware`, and this project
has no such middleware and cannot have one: it needs sessions, and there are
none here. `UNAUTHENTICATED_USER` is `None` besides, so `request.user` is not
the `AnonymousUser` most code assumes.

The failure this guards against is not an exception. It is a lockout that
quietly counts nothing, which looks exactly like a working login from every
angle except an attacker's.
"""

from __future__ import annotations

import pytest
from django.conf import settings
from django.contrib.auth import authenticate
from django.test import RequestFactory

from accounts.models import User

PASSWORD = "een-heel-lang-wachtwoord"


@pytest.fixture
def _account() -> User:
    return User.objects.create_user(email="iemand@voorbeeld.nl", password=PASSWORD)


@pytest.mark.django_db
def test_the_right_password_is_accepted_before_anything_else_is_claimed(_account: User) -> None:
    """The half without which every assertion below could pass on a stack where
    nothing authenticates at all."""
    request = RequestFactory().post("/api/auth/login/")
    user = authenticate(request, username="iemand@voorbeeld.nl", password=PASSWORD)
    assert user is not None and user.pk == _account.pk


@pytest.mark.django_db
def test_the_lockout_fires_without_authentication_middleware(_account: User) -> None:
    from axes.handlers.proxy import AxesProxyHandler

    factory = RequestFactory()
    for _ in range(settings.AXES_FAILURE_LIMIT):
        request = factory.post("/api/auth/login/")
        assert authenticate(request, username="iemand@voorbeeld.nl", password="fout") is None

    locked = factory.post("/api/auth/login/")
    assert not AxesProxyHandler.is_allowed(locked, {"username": "iemand@voorbeeld.nl"}), (
        f"after {settings.AXES_FAILURE_LIMIT} failed attempts axes still allows the next one. "
        "The lockout counts nothing in this stack, and design chapter 9.6 has to be reopened."
    )
    assert authenticate(locked, username="iemand@voorbeeld.nl", password=PASSWORD) is None, (
        "the right password is accepted while the account is locked out, so AxesStandaloneBackend "
        "is not running first in AUTHENTICATION_BACKENDS"
    )
```

- [ ] **Step 2: Draai en noteer de uitkomst**

```bash
uv run --no-sync pytest tests/test_accounts_lockout.py -q
```

Verwacht: groen. **Is hij rood, dan stopt dit plan en gaat hoofdstuk 9.6 terug naar de gebruiker**, want dan is de keuze tussen axes met sessies (die dit project niet heeft) en een eigen lockoutteller een ontwerpvraag en geen implementatiedetail.

- [ ] **Step 3: Toon aan dat de controle rood kan worden**

`test_the_lockout_fires_without_authentication_middleware` leest `settings.AXES_FAILURE_LIMIT` voor zowel het aantal pogingen als voor de drempel waarmee het antwoord vergeleken wordt. `AXES_FAILURE_LIMIT` in `base.py` tijdelijk optrekken naar 500 bewijst dan niets: de lus doet vanzelf evenveel pogingen als de nieuwe drempel, dus de lockout vuurt gewoon, alleen na 500 Argon2-verificaties in plaats van na 5. Het bewijs moet het aantal pogingen vasthouden op een letterlijke 5 terwijl de drempel omhooggaat, zodat de twee losgekoppeld worden.

Voeg toe aan `tests/test_accounts_lockout.py`, tijdelijk, en draai hem apart:

```python
from django.test import override_settings


@pytest.mark.django_db
@override_settings(AXES_FAILURE_LIMIT=500)
def test_the_lockout_check_can_actually_go_red(_account: User) -> None:
    """Proof that the test above is not vacuous.

    Raising AXES_FAILURE_LIMIT and letting the loop read that same setting for
    its attempt count moves both numbers together, so the lockout still fires,
    only slower, and the check cannot go red that way. Here the attempt count
    is a literal 5, independent of the setting, so a threshold raised past it
    is a genuine way to make this assertion fail.
    """
    from axes.handlers.proxy import AxesProxyHandler

    factory = RequestFactory()
    for _ in range(5):
        request = factory.post("/api/auth/login/")
        authenticate(request, username="iemand@voorbeeld.nl", password="fout")

    locked = factory.post("/api/auth/login/")
    assert not AxesProxyHandler.is_allowed(locked, {"username": "iemand@voorbeeld.nl"})
```

```bash
uv run --no-sync pytest tests/test_accounts_lockout.py::test_the_lockout_check_can_actually_go_red -q
```

Verwacht: rood, `AxesProxyHandler.is_allowed` geeft `True` terug na 5 van de 500 benodigde pogingen. Vervang daarna de decorator door `@override_settings(AXES_ENABLED=False)`, draai opnieuw en verwacht dezelfde rode uitslag: nu staat de teller niet eens aan. Verwijder de tijdelijke test na afloop; hij bewijst alleen dat het instrument werkt en hoort niet in de definitieve testset.

- [ ] **Step 4: Noteer de meting**

Schrijf datum en uitkomst op. Taak 12 zet ze in `docs/decisions.md`, naast meting 1.

- [ ] **Step 5: Commit**

Boodschap: `test(accounts): prove the lockout fires in a stack with no session middleware`.

---

## Fase 2: de tabellen

### Taak 5: `Consent`, en de taalgrens

**Hangt af van:** taak 3. Schrijft, net als taak 6, in `backend/accounts/models.py`.

**Files:**
- Modify: `backend/accounts/models.py`
- Create: `backend/accounts/migrations/0002_consent.py`, `backend/accounts/nl.py`, `tests/test_accounts_consent.py`

**Interfaces:**
- Consumes: `accounts.models.User`.
- Produces:
  - `accounts.models.Consent`, met klasseconstanten `METER_LINK: str`, `LEAD_GENERATION: str`, `GRANTED: str`, `WITHDRAWN: str`, `KINDS: frozenset[str]`
  - `accounts.models.Consent.record(user: User, kind: str, action: str) -> Consent`
  - `accounts.models.Consent.current(user: User, kind: str) -> bool`
  - `accounts.nl.NL: dict[str, str]` en `accounts.nl.CONSENT_TEXT_VERSION: str`

- [ ] **Step 1: Schrijf de falende test**

Maak `tests/test_accounts_consent.py`:

```python
"""The four things CLAUDE.md asks of an opt-in, each on its own.

Two separate opt-ins, neither pre-ticked, each with its own timestamp in the
database, and a withdrawal that is recorded. Written as four tests rather than
one, because a single test that checks all four passes for the wrong reason as
soon as three of them hold.
"""

from __future__ import annotations

import pytest

from accounts.models import Consent, User
from accounts.nl import CONSENT_TEXT_VERSION


@pytest.fixture
def _account() -> User:
    return User.objects.create_user(email="iemand@voorbeeld.nl", password="een-lang-wachtwoord")


@pytest.mark.django_db
def test_the_two_consents_are_independent(_account: User) -> None:
    Consent.record(_account, Consent.METER_LINK, Consent.GRANTED)
    assert Consent.current(_account, Consent.METER_LINK) is True
    assert Consent.current(_account, Consent.LEAD_GENERATION) is False


@pytest.mark.django_db
def test_never_asked_is_not_granted(_account: User) -> None:
    """Absence is the answer, and no row is written for a refusal. WITHDRAWN for
    something never granted would be an untruth in a table kept as evidence."""
    assert Consent.current(_account, Consent.METER_LINK) is False
    assert Consent.objects.filter(user=_account).count() == 0


@pytest.mark.django_db
def test_a_withdrawal_is_a_row_and_not_an_erasure(_account: User) -> None:
    Consent.record(_account, Consent.METER_LINK, Consent.GRANTED)
    Consent.record(_account, Consent.METER_LINK, Consent.WITHDRAWN)
    assert Consent.current(_account, Consent.METER_LINK) is False
    assert Consent.objects.filter(user=_account, kind=Consent.METER_LINK).count() == 2


@pytest.mark.django_db
def test_consent_can_be_given_again_after_a_withdrawal(_account: User) -> None:
    """The reason this is an event table and not two nullable columns: a column
    that is filled twice cannot say what happened in between."""
    Consent.record(_account, Consent.METER_LINK, Consent.GRANTED)
    Consent.record(_account, Consent.METER_LINK, Consent.WITHDRAWN)
    Consent.record(_account, Consent.METER_LINK, Consent.GRANTED)
    assert Consent.current(_account, Consent.METER_LINK) is True
    assert Consent.objects.filter(user=_account).count() == 3


@pytest.mark.django_db
def test_every_row_carries_its_own_timestamp_and_the_text_it_agreed_to(_account: User) -> None:
    """Article 7(1) asks to be able to demonstrate what was agreed to, and that
    cannot be demonstrated if the text has been reworded since."""
    row = Consent.record(_account, Consent.LEAD_GENERATION, Consent.GRANTED)
    assert row.occurred_at is not None
    assert row.occurred_at.tzinfo is not None
    assert row.text_version == CONSENT_TEXT_VERSION


@pytest.mark.django_db
def test_an_unknown_kind_is_refused_rather_than_created(_account: User) -> None:
    """A name outside the list cannot open a new column of behaviour, which is
    the same rule DailyCounter.CLIENT_NAMES applies to the funnel counters."""
    with pytest.raises(ValueError):
        Consent.record(_account, "SELL_MY_DATA", Consent.GRANTED)


def test_nothing_that_computes_an_advice_can_see_a_consent() -> None:
    """CLAUDE.md's neutrality rule, made mechanical.

    That rule says any code letting the advice depend on a commercial relation
    is a bug. The obvious test computes one advice with lead consent granted and
    one without and demands they match byte for byte, and that test is worth less
    than it looks: it passes for as long as nobody has written the coupling yet,
    and it is a slow test of a negative.

    This is the same claim stated where it can actually fail. The advice engine
    and the advice app must not so much as mention the consent vocabulary, so
    the coupling cannot be written without turning this red in the same diff.
    The two pure packages are included because the rule is about the advice and
    not about which layer it was spoiled in.
    """
    import pathlib

    root = pathlib.Path(__file__).resolve().parent.parent
    forbidden = ("Consent", "LEAD_GENERATION", "consent_lead")
    offenders = [
        f"{path.relative_to(root)}: {word}"
        for folder in ("backend/advice", "ampeer_advice", "ampeer_sim")
        for path in (root / folder).rglob("*.py")
        for word in forbidden
        if word in path.read_text(encoding="utf-8")
    ]
    assert not offenders, (
        "the advice side of this codebase now knows what a household consented to:\n  "
        + "\n  ".join(offenders)
        + "\nCLAUDE.md calls that a bug rather than a feature, and it holds whether or "
        "not any money has changed hands yet."
    )
```

- [ ] **Step 2: Draai en zie hem falen**

```bash
uv run --no-sync pytest tests/test_accounts_consent.py -q
```

Verwacht: `ImportError: cannot import name 'Consent' from 'accounts.models'`.

- [ ] **Step 3: Maak de taallaag**

`backend/accounts/nl.py`:

```python
"""Dutch text for the account layer, keyed by an English id.

Same idea as `advice/nl.py` one app over, applied to a second vocabulary, and
the two never import each other. The rule that file states applies here too: a
validation message names a field and says what is wrong with it, and addresses
nobody. A message that says "vul uw e-mailadres in" is a sentence somebody is
spoken to in, and then docs/decisions.md entry 1 about the register applies.

The consent texts are the exception, and deliberately so: those are sentences to
a household, so they do use "u". They also carry a version, because article 7(1)
of the GDPR asks to be able to demonstrate what was agreed to, and a reworded
text with no version makes that impossible to answer afterwards.
"""

from __future__ import annotations

from typing import Final

#: Bumped whenever any CONSENT_ text below is reworded, never otherwise. The
#: value is stored on every Consent row, so a bump changes what new rows claim
#: and leaves the old ones pointing at what they actually agreed to.
CONSENT_TEXT_VERSION: Final = "2026-09-04"

NL: Final[dict[str, str]] = {
    "email_taken": "er bestaat al een account met dit e-mailadres",
    "email_invalid": "geen geldig e-mailadres",
    "credentials_invalid": "e-mailadres of wachtwoord klopt niet",
    "password_required": "wachtwoord ontbreekt",
    "not_signed_in": "u bent niet ingelogd",
    "session_expired": "uw sessie is verlopen, log opnieuw in",
    "csrf_failed": "deze pagina stond te lang open, herlaad hem en probeer het opnieuw",
    "consent_kind_unknown": "onbekende toestemming",
    "consent_action_unknown": "onbekende handeling",
    "CONSENT_METER_LINK": (
        "Ik geef Ampeer toestemming om de kwartiergegevens van mijn slimme meter te "
        "verwerken om mijn advies nauwkeuriger te maken. Ik kan deze toestemming op elk "
        "moment intrekken."
    ),
    "CONSENT_LEAD_GENERATION": (
        "Ik geef Ampeer toestemming om mijn gegevens door te geven aan een installateur "
        "als ik daar zelf om vraag. Dit is niet nodig om Ampeer te gebruiken en het "
        "verandert niets aan het advies dat ik krijg."
    ),
}
```

- [ ] **Step 4: Voeg het model toe**

Onderaan `backend/accounts/models.py`:

```python
class Consent(models.Model):
    """One thing a household said yes or no to, and when.

    An event table rather than two nullable datetime columns on `User`. A column
    that can be filled twice cannot say what happened in between, and withdrawing
    and granting again is exactly the sequence a consent record has to survive.

    Deliberately not append-only in the `AuditEvent` sense: a row here is deleted
    when the account is, through CASCADE. Once there is nobody left to process
    data about, there is nothing left to demonstrate consent for, and the audit
    log keeps the fact that the consent existed.
    """

    METER_LINK = "METER_LINK"
    LEAD_GENERATION = "LEAD_GENERATION"
    KINDS: ClassVar[frozenset[str]] = frozenset({METER_LINK, LEAD_GENERATION})

    GRANTED = "GRANTED"
    WITHDRAWN = "WITHDRAWN"
    ACTIONS: ClassVar[frozenset[str]] = frozenset({GRANTED, WITHDRAWN})

    user = models.ForeignKey("accounts.User", on_delete=models.CASCADE, related_name="consents")
    kind = models.CharField(max_length=32, db_index=True)
    action = models.CharField(max_length=16)
    occurred_at = models.DateTimeField(default=timezone.now, editable=False)
    #: Which wording was accepted. See accounts/nl.py.
    text_version = models.CharField(max_length=32)

    class Meta:
        ordering: ClassVar[list[str]] = ["-occurred_at", "-id"]

    @classmethod
    def record(cls, user: User, kind: str, action: str) -> Consent:
        """Write one row. A refusal writes nothing at all, which is why there is
        no third action: absence is what never granted looks like."""
        if kind not in cls.KINDS:
            raise ValueError(f"unknown consent kind: {kind}")
        if action not in cls.ACTIONS:
            raise ValueError(f"unknown consent action: {action}")
        from accounts.nl import CONSENT_TEXT_VERSION

        return cls.objects.create(
            user=user, kind=kind, action=action, text_version=CONSENT_TEXT_VERSION
        )

    @classmethod
    def current(cls, user: User, kind: str) -> bool:
        """The latest word on one kind. No row means never granted.

        Ordered by `occurred_at` and then by `id`, because two rows written in
        the same request can share a timestamp to the microsecond and then the
        order would be whatever the database felt like.
        """
        latest = cls.objects.filter(user=user, kind=kind).order_by("-occurred_at", "-id").first()
        return latest is not None and latest.action == cls.GRANTED
```

- [ ] **Step 5: Migreer en draai**

```bash
uv run --no-sync python backend/manage.py makemigrations accounts --settings ampeer.settings.dev
uv run --no-sync pytest tests/test_accounts_consent.py -q
```

Verwacht: `0002_consent.py` en zes groene tests.

- [ ] **Step 6: Toon aan dat de controles rood kunnen worden**

Laat `current()` tijdelijk `True` teruggeven zodra er een rij is, ongeacht `action`. Verwacht dat `test_a_withdrawal_is_a_row_and_not_an_erasure` valt. Draai `record()` daarna tijdelijk om zodat hij `kind` niet controleert; verwacht dat `test_an_unknown_kind_is_refused_rather_than_created` valt met `DID NOT RAISE`. Zet beide terug.

Voor de neutraliteitstest: zet tijdelijk `# LEAD_GENERATION` als comment in `backend/advice/service.py` en verwacht `backend/advice/service.py: LEAD_GENERATION`. Dat de test een comment al afkeurt is opzet en geen ruwheid: een adviesmodule die de naam kent is een adviesmodule waar iemand de koppeling in aan het schrijven is, en het antwoord daarop hoort een rood build te zijn en geen review-opmerking. Haal het comment weg.

- [ ] **Step 7: Commit**

Boodschap: `feat(accounts): consent as an event, with the wording it agreed to`.

---

### Taak 6: `RefreshSession` en het opruimen

**Hangt af van:** taak 5 (hetzelfde `models.py`).

**Files:**
- Modify: `backend/accounts/models.py`, `tests/test_accounts_models.py`, `infra/systemd/ampeer-purge.service`
- Create: `backend/accounts/migrations/0003_refreshsession.py`, `backend/accounts/management/__init__.py`, `backend/accounts/management/commands/__init__.py`, `backend/accounts/management/commands/purge_expired_sessions.py`

**Interfaces:**
- Consumes: `accounts.models.User`; `advice.models.token_digest(token: str) -> str`.
- Produces: `accounts.models.RefreshSession` met velden `user`, `jti_sha256: str`, `issued_at`, `expires_at`, `rotated_at: datetime | None`, `revoked_at: datetime | None`; management command `purge_expired_sessions`.

- [ ] **Step 1: Schrijf de falende tests**

Voeg toe aan `tests/test_accounts_models.py`:

```python
@pytest.mark.django_db
def test_a_session_stores_a_digest_and_never_the_identifier() -> None:
    """The same call `advice/service.py` makes about the advice token, and for
    the same reason: what is written down must not be what opens the door."""
    from advice.models import token_digest

    from accounts.models import RefreshSession

    user = User.objects.create_user(email="iemand@voorbeeld.nl", password="een-lang-wachtwoord")
    jti = "4f0b2c1d9e8a47f0b2c1d9e8a47f0b2c"
    session = RefreshSession.objects.create(
        user=user,
        jti_sha256=token_digest(jti),
        issued_at=timezone.now(),
        expires_at=timezone.now() + timedelta(days=14),
    )
    assert jti not in session.jti_sha256
    assert session.jti_sha256 == token_digest(jti)
    assert session.rotated_at is None and session.revoked_at is None


@pytest.mark.django_db
def test_the_purge_removes_only_what_has_expired() -> None:
    from django.core.management import call_command

    from accounts.models import RefreshSession

    user = User.objects.create_user(email="iemand@voorbeeld.nl", password="een-lang-wachtwoord")
    now = timezone.now()
    RefreshSession.objects.create(
        user=user, jti_sha256="a" * 64, issued_at=now, expires_at=now - timedelta(seconds=1)
    )
    live = RefreshSession.objects.create(
        user=user, jti_sha256="b" * 64, issued_at=now, expires_at=now + timedelta(days=1)
    )
    call_command("purge_expired_sessions")
    assert list(RefreshSession.objects.values_list("pk", flat=True)) == [live.pk]
```

Voeg bovenaan het bestand toe: `from datetime import timedelta` en `from django.utils import timezone`.

- [ ] **Step 2: Draai en zie ze falen**

Verwacht: `ImportError: cannot import name 'RefreshSession'`.

- [ ] **Step 3: Voeg het model toe**

Onderaan `backend/accounts/models.py`:

```python
class RefreshSession(models.Model):
    """One refresh token's life, without the token and without its identifier.

    simplejwt's own rotation needs the `token_blacklist` app, and that app writes
    the whole refresh JWT into `OutstandingToken.token`. That is a working
    credential in a column, which CLAUDE.md forbids and which docs/dpia.md
    chapter 2 already refused for the advice token in the same words: the token
    is not a reference to the record, it is the only key that opens it.

    `rotated_at` is what makes reuse visible. A token that was exchanged and is
    offered again is the one reliable sign that somebody else has a copy, and the
    answer to it is to end every session this account has, not only this one.
    """

    user = models.ForeignKey(
        "accounts.User", on_delete=models.CASCADE, related_name="refresh_sessions"
    )
    jti_sha256 = models.CharField(max_length=64, unique=True, db_index=True)
    issued_at = models.DateTimeField()
    expires_at = models.DateTimeField(db_index=True)
    rotated_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering: ClassVar[list[str]] = ["-issued_at"]

    @property
    def is_spent(self) -> bool:
        return self.rotated_at is not None or self.revoked_at is not None
```

- [ ] **Step 4: Voeg het opruimen toe**

`backend/accounts/management/__init__.py` en `backend/accounts/management/commands/__init__.py`: leeg.

`backend/accounts/management/commands/purge_expired_sessions.py`:

```python
"""Delete refresh sessions whose token could not be used any more anyway.

A management command called by the same cron that runs `purge_expired_advice`,
and not a Celery task, for the reason section 5 of the advice API design gives:
a daily DELETE over an indexed column needs no queue.

Rows are removed on `expires_at` and not on `rotated_at`. A rotated row is the
evidence that a token was spent, and that evidence is what makes reuse
detectable; dropping it early would turn a stolen token into an unknown one.
"""

from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand
from django.utils import timezone

from accounts.models import RefreshSession


class Command(BaseCommand):
    help = "Remove refresh sessions whose refresh token has expired."

    def handle(self, *args: Any, **options: Any) -> None:
        deleted, _ = RefreshSession.objects.filter(expires_at__lte=timezone.now()).delete()
        self.stdout.write(f"removed {deleted} expired refresh sessions")
```

- [ ] **Step 5: Migreer, draai, en toon aan dat het rood kan**

```bash
uv run --no-sync python backend/manage.py makemigrations accounts --settings ampeer.settings.dev
uv run --no-sync pytest tests/test_accounts_models.py -q
```

Verwacht: `0003_refreshsession.py` en groene tests. Verander daarna het filter tijdelijk in `expires_at__gte`; verwacht dat `test_the_purge_removes_only_what_has_expired` valt met de verkeerde overgebleven rij. Zet het terug.

- [ ] **Step 6: Voeg het commando toe aan de dagelijkse taak**

`infra/systemd/ampeer-purge.service` draait vandaag één `ExecStart` met
`backend/manage.py purge_expired_advice`. Voeg een tweede `ExecStart`-regel toe met
`purge_expired_sessions`, in dezelfde vorm. Systemd draait meerdere `ExecStart`-regels in een
`Type=oneshot`-unit op volgorde, en dat is wat hier gewenst is: een opruiming die niet draait valt
op, een tweede timer erbij niet.

Sla deze stap over als de unit een `Type` heeft die geen tweede `ExecStart` toestaat. Meld dat dan
volgens regel 5 van het werkmodel in plaats van de unit te herschrijven, want die verandering
raakt de deploy en die hoort niet in deze taak.

- [ ] **Step 7: Commit**

Boodschap: `feat(accounts): track a refresh token by its digest and nothing else`.

---

### Taak 7: `StoredAdvice.owner` en de auditwoordenschat

**Hangt af van:** taak 3. Deze taak werkt volledig in de `advice`-app en in `docs/dpia.md`.

**Files:**
- Modify: `backend/advice/models.py`, `tests/test_advice_api.py`, `tests/test_dpia.py`, `docs/dpia.md`
- Create: `backend/advice/migrations/0005_storedadvice_owner.py`

**Interfaces:**
- Consumes: `settings.AUTH_USER_MODEL` (`accounts.User`, uit taak 3).
- Produces: `advice.models.StoredAdvice.owner` (nullable FK, `CASCADE`); de constanten `AuditEvent.ACCOUNT_CREATED`, `LOGIN_SUCCEEDED`, `LOGIN_FAILED`, `LOGOUT`, `CONSENT_GRANTED`, `CONSENT_WITHDRAWN`, `DATA_EXPORTED`, `ACCOUNT_DELETED`.

- [ ] **Step 1: Schrijf de test die de anonimiteit vastpint**

Voeg toe aan `tests/test_advice_api.py`:

```python
@pytest.mark.django_db
def test_ownership_adds_and_takes_nothing_away(client: Any) -> None:
    """The property phase 2 will be under pressure to break.

    An advice that belongs to somebody stays readable on its token, and an
    advice that belongs to nobody keeps working exactly as it did. Ownership is
    an addition; it is not a filter on the route that already exists, and
    `StoredAdvice.get_live` is deliberately unchanged.
    """
    from accounts.models import User
    from advice.models import StoredAdvice

    anonymous = StoredAdvice.create(inputs={"postcode4": "5401"}, advice={"token": "x"})
    owned = StoredAdvice.create(inputs={"postcode4": "5401"}, advice={"token": "y"})
    owned.owner = User.objects.create_user(
        email="iemand@voorbeeld.nl", password="een-lang-wachtwoord"
    )
    owned.save(update_fields=["owner"])

    assert anonymous.owner is None
    for stored in (anonymous, owned):
        response = client.get(f"/api/advice/{stored.token}/")
        assert response.status_code == 200, (
            f"an advice with owner={stored.owner_id} answers {response.status_code} on its token"
        )
```

- [ ] **Step 2: Draai en zie hem falen**

Verwacht: `AttributeError: 'StoredAdvice' object has no attribute 'owner'`.

- [ ] **Step 3: Voeg de kolom toe**

In `backend/advice/models.py`, in `StoredAdvice`, onder `advice`:

```python
    #: Nullable, and null is the normal case. Every advice made before phase 1
    #: has no owner and every advice made anonymously after it has none either.
    #:
    #: `get_live` does not filter on this column and must not start to. Ownership
    #: adds a second way to reach an advice; it does not take the shareable link
    #: away, and the largest group of visitors will never have an account at all.
    #:
    #: CASCADE and not SET_NULL. Deleting an account has to take its advice with
    #: it, because that advice is the only thing this product keeps about that
    #: household. SET_NULL would leave the rows behind as ownerless advice, still
    #: readable on their token for the rest of the ninety days, which turns a
    #: deletion request into a change of name. Nothing writes this column in
    #: phase 1; the column exists now because adding it later is a migration over
    #: every stored advice, which is the same argument `year_field`'s
    #: `shareable_token` was built on.
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="advices",
    )
```

Werk de moduledocstring bovenaan hetzelfde bestand bij. De openingszin "None of them holds a personal detail" is niet meer waar:

```python
"""The three tables the advice API keeps.

`StoredAdvice.inputs` holds the answers a visitor gave, and the serializer that
produces it accepts a four digit postcode and nothing longer, so there is no
address in here and no way to put one in. `AuditEvent` and `DailyCounter` hold
nothing that belongs to anybody at all.

One column is the exception, and it arrived with phase 1: `StoredAdvice.owner`
points at an account, and an account has an email address. It is null on every
row today, nothing in phase 1 writes it, and the route that reads an advice does
not look at it. What it is for is phase 2, and the reason it is here already is
in the note beside it.
"""
```

Voeg de constanten toe aan `AuditEvent`, onder `ADVICE_GENERATED`:

```python
    ACCOUNT_CREATED = "ACCOUNT_CREATED"
    LOGIN_SUCCEEDED = "LOGIN_SUCCEEDED"
    LOGIN_FAILED = "LOGIN_FAILED"
    LOGOUT = "LOGOUT"
    CONSENT_GRANTED = "CONSENT_GRANTED"
    CONSENT_WITHDRAWN = "CONSENT_WITHDRAWN"
    DATA_EXPORTED = "DATA_EXPORTED"
    ACCOUNT_DELETED = "ACCOUNT_DELETED"
```

Voeg boven die blok een noot toe:

```python
    #: What this log records, and every entry here is a handling that exists.
    #: The two from CLAUDE.md's list that are absent, a link being made and a
    #: lead being sent, are absent because those handlings do not exist yet: a
    #: log that named them would describe a processing that is not happening.
    #:
    #: Context carries `user_id` as a plain integer and never the email address.
    #: This table is never purged, so anything in it outlives the account, and an
    #: integer pointing at a deleted row is an empty reference where an address
    #: would be a permanent personal datum in a table with no retention. Same
    #: call as `token_sha256` instead of `token` in service.py.
```

- [ ] **Step 4: Migreer**

```bash
uv run --no-sync python backend/manage.py makemigrations advice --settings ampeer.settings.dev
```

Verwacht `backend/advice/migrations/0005_storedadvice_owner.py` met een `swappable_dependency` op `settings.AUTH_USER_MODEL` en `AddField` met `null=True`. Een nullable kolom zonder default herschrijft de tabel niet in Postgres; staat er wel een default in, verwijder die.

- [ ] **Step 5: De valstrik over het auditlogboek gaat af**

```bash
uv run --no-sync pytest tests/test_dpia.py -q
```

Verwacht: `test_the_audit_log_records_exactly_what_the_document_says_it_does` faalt met `the audit log now records [...]`. Dat is de bedoeling van die test: hij dwingt af dat `docs/dpia.md` in dezelfde commit meebeweegt in plaats van erna.

Werk hoofdstuk 2 van `docs/dpia.md` bij. Wat er moet komen te staan: dat er nu accounts zijn, dus een e-mailadres, een wachtwoordhash en inlogpogingen; dat het auditlogboek acht soorten gebeurtenissen kent en welke; dat er `user_id` in staat en nooit een e-mailadres, met de reden; dat de zin "Er is niets om in te loggen" weg is; en dat de zin "Geen IP-adres in enige tabel" blijft staan met de axes-cachehandler als reden. Vermeld ook `last_login`, dat `AbstractBaseUser` meebrengt.

Werk daarna de assertie in `tests/test_dpia.py` bij:

```python
    assert kinds == [
        "ADVICE_GENERATED",
        "ACCOUNT_CREATED",
        "LOGIN_SUCCEEDED",
        "LOGIN_FAILED",
        "LOGOUT",
        "CONSENT_GRANTED",
        "CONSENT_WITHDRAWN",
        "DATA_EXPORTED",
        "ACCOUNT_DELETED",
    ], (
        f"the audit log now records {kinds}; docs/dpia.md chapter 2 lists what it records "
        "and why the two that are still absent are absent. Both have to change together."
    )
```

Verwijder in dezelfde bewerking de regel `assert "precies een soort gebeurtenis" in TEXT`, iets verderop in dezelfde functie. Die zin ("exactly one kind of event") wordt door de hoofdstuk 2-herschrijving hierboven onwaar: het auditlogboek kent er nu acht bij, niet een. Deze taak bezit zowel de tekst als de assertie, dus dat gebeurt in dit commit en niet in taak 12: een assertie die weet dat ze onwaar is laten staan tot een latere taak zou een bewuste leugen in de repository committen.

- [ ] **Step 6: Draai alles en toon aan dat de nieuwe test rood kan worden**

```bash
uv run --no-sync pytest tests/test_advice_api.py tests/test_dpia.py -q
```

Verwacht: groen. Laat daarna `StoredAdvice.get_live` tijdelijk `owner__isnull=True` toevoegen aan zijn filter, en verwacht dat `test_ownership_adds_and_takes_nothing_away` valt met `an advice with owner=1 answers 404 on its token`. Zet het terug. Dat is precies de wijziging waar deze test tegen bestaat.

- [ ] **Step 7: Commit**

Boodschap: `feat(advice): an advice may have an owner, and its link keeps working`.

---

## Fase 3: de authenticatie

### Taak 8: Cookies, tokens en de authenticatieklasse

**Hangt af van:** taak 6.

**Files:**
- Create: `backend/accounts/cookies.py`, `backend/accounts/tokens.py`, `backend/accounts/authentication.py`, `tests/test_accounts_auth.py`

**Interfaces:**
- Consumes: `accounts.models.User`, `accounts.models.RefreshSession`, `advice.models.token_digest`, `accounts.nl.NL`; instellingen `AMPEER_ACCESS_COOKIE`, `AMPEER_REFRESH_COOKIE`, `AMPEER_ACCESS_COOKIE_PATH`, `AMPEER_REFRESH_COOKIE_PATH`, `AMPEER_COOKIE_SECURE`, `SIMPLE_JWT`.
- Produces:
  - `accounts.tokens.issue(user: User) -> tuple[str, str]` die `(access, refresh)` teruggeeft
  - `accounts.tokens.rotate(raw_refresh: str) -> tuple[str, str]`
  - `accounts.tokens.revoke(raw_refresh: str) -> None`
  - `accounts.tokens.revoke_all(user: User) -> None`
  - `accounts.tokens.TokenReuse` (Exception)
  - `accounts.cookies.set_tokens(response: Response, access: str, refresh: str) -> None`
  - `accounts.cookies.clear_tokens(response: Response) -> None`
  - `accounts.authentication.CookieJWTAuthentication`
  - `accounts.authentication.enforce_csrf(request: HttpRequest) -> None`

- [ ] **Step 1: Schrijf de falende tests**

Maak `tests/test_accounts_auth.py`:

```python
"""Issuing, rotating and refusing a refresh token.

Rotation is written here rather than taken from simplejwt, because simplejwt's
own rotation needs the token_blacklist app and that app stores the whole refresh
JWT in a column. What is stored here is a digest of the token's `jti`, so the
table can say which session a token belongs to and cannot hand anybody a working
credential.
"""

from __future__ import annotations

import pytest
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from accounts import tokens
from accounts.models import RefreshSession, User

PASSWORD = "een-heel-lang-wachtwoord"


@pytest.fixture
def _account() -> User:
    return User.objects.create_user(email="iemand@voorbeeld.nl", password=PASSWORD)


@pytest.mark.django_db
def test_issuing_records_a_session_without_the_token(_account: User) -> None:
    access, refresh = tokens.issue(_account)
    assert access and refresh and access != refresh
    session = RefreshSession.objects.get(user=_account)
    assert refresh not in session.jti_sha256
    assert session.rotated_at is None


@pytest.mark.django_db
def test_a_refresh_token_may_be_exchanged_once(_account: User) -> None:
    _, refresh = tokens.issue(_account)
    access, rotated = tokens.rotate(refresh)
    assert access and rotated != refresh
    assert RefreshSession.objects.filter(user=_account, rotated_at__isnull=False).count() == 1
    assert RefreshSession.objects.filter(user=_account).count() == 2


@pytest.mark.django_db
def test_offering_a_spent_token_again_ends_every_session(_account: User) -> None:
    """The one reliable sign that somebody else has a copy. The answer to it is
    not to refuse this request, it is to end every session this account has."""
    _, refresh = tokens.issue(_account)
    tokens.rotate(refresh)
    with pytest.raises(tokens.TokenReuse):
        tokens.rotate(refresh)
    assert not RefreshSession.objects.filter(user=_account, revoked_at__isnull=True).exists()


@pytest.mark.django_db
def test_a_token_this_service_never_issued_is_refused(_account: User) -> None:
    """A bare `pytest.raises(Exception)` here would pass on a bug in `rotate`
    just as easily as on the real behaviour. `TokenError` is what
    `RefreshToken(raw_refresh)` actually raises on a string it cannot parse,
    and it raises before the session lookup runs at all."""
    with pytest.raises(TokenError):
        tokens.rotate("dit.is.geen.token")


@pytest.mark.django_db
def test_a_well_formed_token_with_no_recorded_session_is_refused(_account: User) -> None:
    """`rotate`'s other branch into `TokenReuse`: the signature verifies fine,
    there is simply no `RefreshSession` row for it, because this token was
    minted with `RefreshToken.for_user` directly and never passed through
    `tokens.issue`. The malformed-token test above cannot reach this branch:
    `RefreshToken(raw_refresh)` already raises before `session is None` is
    ever evaluated.
    """
    orphan = RefreshToken.for_user(_account)
    with pytest.raises(tokens.TokenReuse):
        tokens.rotate(str(orphan))


@pytest.mark.django_db
def test_revoking_ends_only_the_session_that_was_offered(_account: User) -> None:
    _, first = tokens.issue(_account)
    _, second = tokens.issue(_account)
    tokens.revoke(first)
    assert RefreshSession.objects.filter(revoked_at__isnull=True).count() == 1
    tokens.rotate(second)


@pytest.mark.django_db
def test_revoking_a_token_with_no_recorded_session_does_nothing_and_raises_nothing(
    _account: User,
) -> None:
    """`revoke`'s "nothing to revoke" branch. A visitor who logs out twice, or
    whose cookie already pointed at a purged session, gets the same quiet
    success either way, not an exception that a logout route would have to
    catch."""
    orphan = RefreshToken.for_user(_account)
    tokens.revoke(str(orphan))
    assert not RefreshSession.objects.filter(user=_account).exists()
```

- [ ] **Step 2: Draai en zie ze falen**

Verwacht: `ModuleNotFoundError: No module named 'accounts.tokens'`.

- [ ] **Step 3: Schrijf `tokens.py`**

```python
"""Issuing and rotating refresh tokens against a table that holds no credential.

`RefreshSession` stores the sha256 of the token's `jti` and nothing else, using
the same `token_digest` the advice API applies to its own token, with the same
argument: the input is high entropy from a cryptographic source, so there is no
dictionary to run and no salt worth adding.
"""

from __future__ import annotations

from datetime import UTC, datetime

from django.db import transaction
from django.utils import timezone
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import RefreshSession, User
from advice.models import token_digest


class TokenReuse(Exception):
    """A refresh token that had already been spent was offered again."""


def issue(user: User) -> tuple[str, str]:
    """A fresh pair, with the refresh side written down as a digest."""
    refresh = RefreshToken.for_user(user)
    RefreshSession.objects.create(
        user=user,
        jti_sha256=_digest(refresh),
        issued_at=timezone.now(),
        expires_at=datetime.fromtimestamp(float(refresh.payload["exp"]), tz=UTC),
    )
    return str(refresh.access_token), str(refresh)


def rotate(raw_refresh: str) -> tuple[str, str]:
    """Exchange one refresh token for a new pair, exactly once.

    `RefreshToken(raw)` raises `TokenError` on a token this service did not
    issue, on one whose signature does not verify and on an expired one, so the
    cryptographic half is handled before the row is looked up at all.
    """
    token = RefreshToken(raw_refresh)
    with transaction.atomic():
        session = (
            RefreshSession.objects.select_for_update().filter(jti_sha256=_digest(token)).first()
        )
        if session is None:
            raise TokenReuse("no session was ever recorded for this token")
        if session.is_spent:
            revoke_all(session.user)
            raise TokenReuse("this refresh token was already exchanged")
        session.rotated_at = timezone.now()
        session.save(update_fields=["rotated_at"])
        return issue(session.user)


def revoke(raw_refresh: str) -> None:
    """End one session. A token that cannot be read ends nothing and says so."""
    session = RefreshSession.objects.filter(jti_sha256=_digest(RefreshToken(raw_refresh))).first()
    if session is not None and session.revoked_at is None:
        session.revoked_at = timezone.now()
        session.save(update_fields=["revoked_at"])


def revoke_all(user: User) -> None:
    RefreshSession.objects.filter(user=user, revoked_at__isnull=True).update(
        revoked_at=timezone.now()
    )


def _digest(token: RefreshToken) -> str:
    return token_digest(str(token.payload["jti"]))
```

- [ ] **Step 4: Schrijf `cookies.py`**

```python
"""The two cookies, set and cleared in exactly one place.

One place, because a cookie whose name, path or SameSite is written out at both
the setting view and the clearing view is a cookie that will eventually differ
between the two, and the symptom of that is a logout that leaves the visitor
logged in.
"""

from __future__ import annotations

from django.conf import settings
from rest_framework.response import Response

SAMESITE = "Strict"


def set_tokens(response: Response, access: str, refresh: str) -> None:
    response.set_cookie(
        settings.AMPEER_ACCESS_COOKIE,
        access,
        max_age=int(settings.SIMPLE_JWT["ACCESS_TOKEN_LIFETIME"].total_seconds()),
        httponly=True,
        secure=settings.AMPEER_COOKIE_SECURE,
        samesite=SAMESITE,
        path=settings.AMPEER_ACCESS_COOKIE_PATH,
    )
    response.set_cookie(
        settings.AMPEER_REFRESH_COOKIE,
        refresh,
        max_age=int(settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"].total_seconds()),
        httponly=True,
        secure=settings.AMPEER_COOKIE_SECURE,
        samesite=SAMESITE,
        path=settings.AMPEER_REFRESH_COOKIE_PATH,
    )


def clear_tokens(response: Response) -> None:
    """Deleting a cookie only works when the path matches the one it was set
    with, which is the quiet way a logout leaves a working session behind."""
    response.delete_cookie(
        settings.AMPEER_ACCESS_COOKIE,
        path=settings.AMPEER_ACCESS_COOKIE_PATH,
        samesite=SAMESITE,
    )
    response.delete_cookie(
        settings.AMPEER_REFRESH_COOKIE,
        path=settings.AMPEER_REFRESH_COOKIE_PATH,
        samesite=SAMESITE,
    )
```

- [ ] **Step 5: Schrijf `authentication.py`**

```python
"""Reading the identity out of a cookie, and only out of a cookie.

Not out of an `Authorization` header, in either direction. A second accepted
place for a credential is a second place it can leak from, and a header reaches
a proxy log more easily than a cookie does. That is the same argument
docs/dpia.md chapter 8 makes about the advice token sitting in the path.
"""

from __future__ import annotations

from typing import Any

from django.conf import settings
from django.http import HttpRequest
from rest_framework.authentication import CSRFCheck
from rest_framework.exceptions import PermissionDenied
from rest_framework.request import Request
from rest_framework_simplejwt.authentication import JWTAuthentication

from accounts.nl import NL

#: The methods that change nothing, so they need no CSRF token. Same set Django
#: and DRF use, written out here so this file does not depend on which of the
#: two happens to be imported.
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS", "TRACE"})


def enforce_csrf(request: HttpRequest | Request) -> None:
    """Django's own CSRF machinery, on a view DRF has already exempted.

    DRF wraps every `APIView` in `csrf_exempt`, so nothing here is protected
    unless it asks. This is DRF's own `SessionAuthentication.enforce_csrf` with
    one change: the message a visitor reads is Dutch and comes from nl.py.

    SameSite=Strict is the first defence and in this deployment very nearly the
    whole one. This is the second, and it costs one function.
    """

    def dummy_get_response(_request: HttpRequest) -> None:
        return None

    check = CSRFCheck(dummy_get_response)
    check.process_request(request)
    reason = check.process_view(request, None, (), {})
    if reason:
        raise PermissionDenied(NL["csrf_failed"])


class CookieJWTAuthentication(JWTAuthentication):
    """The access token, from the cookie, with a CSRF check on anything unsafe."""

    def authenticate(self, request: Request) -> tuple[Any, Any] | None:
        raw = request.COOKIES.get(settings.AMPEER_ACCESS_COOKIE)
        if not raw:
            return None
        validated = self.get_validated_token(raw.encode())
        user = self.get_user(validated)
        if request.method not in SAFE_METHODS:
            enforce_csrf(request)
        return user, validated

    def authenticate_header(self, request: Request) -> str:
        """Present so DRF answers 401 and not 403 to somebody who is not logged
        in. Without a header DRF cannot tell "you did not authenticate" from
        "you may not do this", and the frontend needs the difference to know
        whether to show a login form."""
        return 'Cookie realm="api"'
```

Voeg niets toe aan `nl.py`: `csrf_failed` staat er al uit taak 5.

- [ ] **Step 6: Draai en toon aan dat het rood kan worden**

```bash
uv run --no-sync pytest tests/test_accounts_auth.py -q
```

Verwacht: groen. Verwijder daarna tijdelijk de `if session.is_spent` tak uit `rotate`, en verwacht dat `test_offering_a_spent_token_again_ends_every_session` valt met `DID NOT RAISE`. Zet hem terug. Verander daarna in `cookies.clear_tokens` het pad van de refresh-cookie naar `/`, en verwacht dat een latere taak dat zou missen: noteer dat dit pas in taak 9 zichtbaar wordt over HTTP, en zet het meteen terug.

- [ ] **Step 7: Commit**

Boodschap: `feat(accounts): a cookie borne access token and a refresh token that rotates once`.

---

### Taak 9: `_AuthAPIView`, registreren, inloggen, verversen en uitloggen

**Hangt af van:** taak 5, taak 7 (importeert de `AuditEvent`-constanten die taak 7 produceert) en taak 8. Taken 9, 10 en 11 schrijven alle drie in `views.py` en `urls.py`.

**Files:**
- Create: `backend/accounts/serializers.py`, `backend/accounts/views.py`, `backend/accounts/urls.py`, `tests/test_accounts_api.py`
- Modify: `backend/ampeer/urls.py`

**Interfaces:**
- Consumes: `accounts.tokens.issue/rotate/revoke/revoke_all/TokenReuse`, `accounts.cookies.set_tokens/clear_tokens`, `accounts.authentication.CookieJWTAuthentication/enforce_csrf`, `accounts.models.User/Consent`, `accounts.nl.NL`, `advice.models.AuditEvent`, `advice.views._NoStoreAPIView`.
- Produces:
  - `accounts.views._AuthAPIView`, de basisklasse die elke latere view erft, met een getypeerde `user`-property (`accounts.models.User`)
  - routes `auth-register`, `auth-login`, `auth-refresh`, `auth-logout` op `/api/auth/`
  - `accounts.serializers.RegisterSerializer`, `accounts.serializers.LoginSerializer`

- [ ] **Step 1: Schrijf de falende tests**

Maak `tests/test_accounts_api.py`:

```python
"""The contract of the auth routes, read off the real response.

The cookie attributes are read out of `response.cookies` one by one and not
inferred from a 200. A test that only checks the status code says nothing about
SameSite, and SameSite is the whole CSRF defence in this deployment.
"""

from __future__ import annotations

from typing import Any

import pytest
from django.conf import settings

from accounts.models import Consent, User
from accounts.nl import NL

PASSWORD = "een-heel-lang-wachtwoord"
BODY = {
    "email": "iemand@voorbeeld.nl",
    "password": PASSWORD,
    "consent_meter_link": True,
    "consent_lead_generation": False,
}


def _csrf(client: Any) -> dict[str, str]:
    """The token every unsafe request carries.

    A GET on a route that only answers POST, so the response is a 405 and the
    cookie rides along on it anyway. That is the property `_AuthAPIView` exists
    for: the cookie is set in `finalize_response`, which DRF also runs for the
    response `handle_exception` builds, so somebody who is not logged in and has
    no token yet can still get one. Task 10 changes this helper to `me/`, which
    is the route a browser actually calls first.
    """
    client.get("/api/auth/login/")
    return {"HTTP_X_CSRFTOKEN": client.cookies["csrftoken"].value}


@pytest.mark.django_db
def test_registering_creates_an_account_and_logs_it_in(client: Any) -> None:
    response = client.post(
        "/api/auth/register/", BODY, content_type="application/json", **_csrf(client)
    )
    assert response.status_code == 201, response.content
    assert User.objects.filter(email="iemand@voorbeeld.nl").exists()
    assert settings.AMPEER_ACCESS_COOKIE in response.cookies
    assert settings.AMPEER_REFRESH_COOKIE in response.cookies


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("cookie", "path"),
    [
        (settings.AMPEER_ACCESS_COOKIE, settings.AMPEER_ACCESS_COOKIE_PATH),
        (settings.AMPEER_REFRESH_COOKIE, settings.AMPEER_REFRESH_COOKIE_PATH),
    ],
)
def test_every_token_cookie_carries_the_attributes_that_protect_it(
    client: Any, cookie: str, path: str
) -> None:
    response = client.post(
        "/api/auth/register/", BODY, content_type="application/json", **_csrf(client)
    )
    morsel = response.cookies[cookie]
    assert morsel["httponly"], f"{cookie} is readable from JavaScript"
    assert morsel["samesite"] == "Strict", f"{cookie} is SameSite={morsel['samesite']!r}"
    assert morsel["path"] == path, f"{cookie} is scoped to {morsel['path']!r}"


@pytest.mark.django_db
def test_registering_records_only_the_consent_that_was_given(client: Any) -> None:
    """A refusal writes nothing. WITHDRAWN for something never granted would be
    an untruth in a table kept as evidence."""
    client.post("/api/auth/register/", BODY, content_type="application/json", **_csrf(client))
    user = User.objects.get(email="iemand@voorbeeld.nl")
    assert Consent.current(user, Consent.METER_LINK) is True
    assert Consent.current(user, Consent.LEAD_GENERATION) is False
    assert Consent.objects.filter(user=user).count() == 1


@pytest.mark.django_db
def test_a_refused_meter_link_still_creates_the_account(client: Any) -> None:
    """Article 7(4): a service made conditional on consent it does not need is a
    service whose consent is not freely given. Phase 2 checks the consent before
    a single reading arrives; registration does not."""
    body = BODY | {"consent_meter_link": False}
    response = client.post(
        "/api/auth/register/", body, content_type="application/json", **_csrf(client)
    )
    assert response.status_code == 201, response.content
    assert Consent.objects.count() == 0


@pytest.mark.django_db
@pytest.mark.parametrize("missing", ["consent_meter_link", "consent_lead_generation"])
def test_a_consent_field_that_is_absent_is_a_refusal_to_answer(client: Any, missing: str) -> None:
    """Not pre-ticked is a property of the serializer and not of the screen: the
    field has no default, so a frontend that forgets the checkbox gets an error
    rather than a consent."""
    body = {key: value for key, value in BODY.items() if key != missing}
    response = client.post(
        "/api/auth/register/", body, content_type="application/json", **_csrf(client)
    )
    assert response.status_code == 400
    assert missing in response.json()


@pytest.mark.django_db
def test_a_short_password_is_refused_in_dutch(client: Any) -> None:
    body = BODY | {"password": "kort"}
    response = client.post(
        "/api/auth/register/", body, content_type="application/json", **_csrf(client)
    )
    assert response.status_code == 400
    assert "password" in response.json()


@pytest.mark.django_db
def test_logging_in_and_out_moves_the_cookies(client: Any) -> None:
    User.objects.create_user(email="iemand@voorbeeld.nl", password=PASSWORD)
    login = client.post(
        "/api/auth/login/",
        {"email": "IEMAND@Voorbeeld.nl", "password": PASSWORD},
        content_type="application/json",
        **_csrf(client),
    )
    assert login.status_code == 200, login.content
    assert client.cookies[settings.AMPEER_ACCESS_COOKIE].value

    logout = client.post("/api/auth/logout/", content_type="application/json", **_csrf(client))
    assert logout.status_code == 204
    assert logout.cookies[settings.AMPEER_ACCESS_COOKIE].value == ""


@pytest.mark.django_db
def test_a_wrong_password_says_the_same_thing_as_an_unknown_address(client: Any) -> None:
    """Telling a caller that an address exists tells them something, which is
    the same reason an unknown and an expired advice token answer alike."""
    User.objects.create_user(email="iemand@voorbeeld.nl", password=PASSWORD)
    wrong = client.post(
        "/api/auth/login/",
        {"email": "iemand@voorbeeld.nl", "password": "verkeerd"},
        content_type="application/json",
        **_csrf(client),
    )
    unknown = client.post(
        "/api/auth/login/",
        {"email": "niemand@voorbeeld.nl", "password": "verkeerd"},
        content_type="application/json",
        **_csrf(client),
    )
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()


@pytest.mark.django_db
def test_refreshing_hands_out_a_new_pair(client: Any) -> None:
    client.post("/api/auth/register/", BODY, content_type="application/json", **_csrf(client))
    before = client.cookies[settings.AMPEER_REFRESH_COOKIE].value
    response = client.post("/api/auth/refresh/", content_type="application/json", **_csrf(client))
    assert response.status_code == 200
    assert client.cookies[settings.AMPEER_REFRESH_COOKIE].value != before


@pytest.mark.django_db
def test_refreshing_without_a_refresh_cookie_is_refused(client: Any) -> None:
    """`RefreshView`'s other branch: no `not_signed_in` error is raised by
    `tokens.rotate`, because `tokens.rotate` is never called at all when there
    is no cookie to hand it. A visitor with no session and a stale CSRF cookie
    should read the same "you are not signed in" as one whose refresh token
    expired, not a 500 from a missing argument."""
    response = client.post("/api/auth/refresh/", content_type="application/json", **_csrf(client))
    assert response.status_code == 401
    assert response.json() == {"detail": NL["not_signed_in"]}


@pytest.mark.django_db
def test_an_unsafe_request_without_the_csrf_token_is_refused(client: Any) -> None:
    client.post("/api/auth/register/", BODY, content_type="application/json", **_csrf(client))
    response = client.post("/api/auth/logout/", content_type="application/json")
    assert response.status_code == 403, (
        "a state changing request went through without a CSRF token, so SameSite is the "
        "only thing standing between this API and a cross site POST"
    )


def test_the_advice_endpoints_did_not_quietly_gain_an_identity() -> None:
    """`DEFAULT_AUTHENTICATION_CLASSES` stays empty and the class is named per
    view, so the three anonymous endpoints cannot start accepting a cookie
    identity because somebody changed a default. Asserted over the resolver
    rather than over the source, because what matters is what is reachable."""
    from django.conf import settings as django_settings
    from django.urls import get_resolver

    assert django_settings.REST_FRAMEWORK["DEFAULT_AUTHENTICATION_CLASSES"] == []
    for entry in get_resolver().url_patterns:
        if str(entry.pattern) != "api/advice/":
            continue
        for route in entry.url_patterns:
            view = route.callback.cls
            assert list(view.authentication_classes) == [], (
                f"api/advice/{route.pattern} is served by {view.__name__}, which now "
                f"authenticates with {view.authentication_classes}"
            )
```

Elke test in dit bestand die `/api/auth/me/` of `/api/auth/consent/` aanroept hoort bij taak 10 en staat daar. Deze taak laat het bestand volledig groen achter.

- [ ] **Step 2: Draai en zie ze falen**

Verwacht: 404 op elke route, want `ampeer/urls.py` monteert `accounts.urls` nog niet.

- [ ] **Step 3: Schrijf de serializers**

`backend/accounts/serializers.py`:

```python
"""The only place an untrusted body becomes something this app acts on."""

from __future__ import annotations

from typing import Any

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from accounts.models import Consent, User
from accounts.nl import NL


class LoginSerializer(serializers.Serializer[dict[str, Any]]):
    email = serializers.EmailField(error_messages={"invalid": NL["email_invalid"]})
    password = serializers.CharField(
        write_only=True, trim_whitespace=False, error_messages={"required": NL["password_required"]}
    )

    def validate_email(self, value: str) -> str:
        return value.strip().lower()


class RegisterSerializer(LoginSerializer):
    #: No default on either, so a body that leaves one out is a 400 and never a
    #: silent True. Not pre-ticked is a property of this line.
    consent_meter_link = serializers.BooleanField()
    consent_lead_generation = serializers.BooleanField()

    def validate_email(self, value: str) -> str:
        normalized = value.strip().lower()
        if User.objects.filter(email=normalized).exists():
            raise serializers.ValidationError(NL["email_taken"])
        return normalized

    def validate_password(self, value: str) -> str:
        """Django's own validators, whose messages arrive in Dutch from Django's
        translations because LANGUAGE_CODE is nl-nl. That keeps four sentences
        out of nl.py without putting any Dutch in the logic."""
        try:
            validate_password(value)
        except DjangoValidationError as error:
            raise serializers.ValidationError(list(error.messages)) from error
        return value

    @property
    def granted_kinds(self) -> list[str]:
        """The consents that were said yes to. A no yields nothing at all."""
        data = self.validated_data
        pairs = [
            (Consent.METER_LINK, data["consent_meter_link"]),
            (Consent.LEAD_GENERATION, data["consent_lead_generation"]),
        ]
        return [kind for kind, given in pairs if given]
```

- [ ] **Step 4: Schrijf de views**

`backend/accounts/views.py`:

```python
"""The account routes. Eight of them, and only `get` and `post` among them.

That is not a workaround for a test. docs/dpia.md chapter 7 describes an API
that reads and computes, and says that rectification adds a row rather than
changing one, so a PUT or a PATCH here would make the chapter wrong in the
direction that matters most. Withdrawing a consent is a new row, and deleting an
account needs a body, which is the other half of the reason.
"""

from __future__ import annotations

from typing import Any, ClassVar

from django.contrib.auth import authenticate
from django.middleware.csrf import get_token
from rest_framework import status
from rest_framework.exceptions import AuthenticationFailed, PermissionDenied
from rest_framework.permissions import AllowAny, BasePermission, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from accounts import cookies, tokens
from accounts.authentication import CookieJWTAuthentication, enforce_csrf
from accounts.models import Consent, User
from accounts.nl import NL
from accounts.serializers import LoginSerializer, RegisterSerializer
from advice.models import AuditEvent
from advice.views import _NoStoreAPIView


class _AuthAPIView(_NoStoreAPIView):
    """Every route under /api/auth/, with the two things they all share.

    `Cache-Control: private, no-store` comes from the base class, because each
    of these answers describes one household.

    The CSRF cookie is set in `finalize_response` and not in a view body, and
    that placement is load bearing. DRF answers an unauthenticated request to a
    view with `IsAuthenticated` before the handler runs, so a cookie set inside
    `me/` would never reach the one person who needs it, namely somebody about
    to log in. `finalize_response` also runs for the response `handle_exception`
    produces, so the cookie rides along on the 401 as well.
    """

    authentication_classes: ClassVar[list[Any]] = [CookieJWTAuthentication]
    permission_classes: ClassVar[list[type[BasePermission]]] = [IsAuthenticated]

    def finalize_response(
        self, request: Request, response: Response, *args: Any, **kwargs: Any
    ) -> Response:
        get_token(request)
        return super().finalize_response(request, response, *args, **kwargs)

    @property
    def user(self) -> User:
        """`self.request.user`, narrowed to what it actually is here.

        drf-stubs types `Request.user` as `AbstractBaseUser | AnonymousUser`,
        which is the right type for a view an anonymous caller may reach and
        the wrong one for everything under this base class: `IsAuthenticated`
        has already refused the request by the time a handler runs, so
        `CookieJWTAuthentication.authenticate` returned this project's own
        `User`. Reading `.email`, `.pk` or `.check_password` straight off
        `request.user` is an `attr-defined` error under `mypy --strict`; this
        property is the one place that narrowing happens, instead of at every
        call site.
        """
        assert isinstance(self.request.user, User)
        return self.request.user


class RegisterView(_AuthAPIView):
    authentication_classes: ClassVar[list[Any]] = []
    permission_classes: ClassVar[list[type[BasePermission]]] = [AllowAny]
    throttle_scope = "auth-register"

    def post(self, request: Request) -> Response:
        # Explicitly, because there is no cookie yet and the authentication class
        # that would have done it does not run. Login CSRF is the attack: it puts
        # a visitor into an account somebody else controls.
        enforce_csrf(request)
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = User.objects.create_user(
            email=serializer.validated_data["email"],
            password=serializer.validated_data["password"],
        )
        AuditEvent.record(AuditEvent.ACCOUNT_CREATED, user_id=user.pk)
        for kind in serializer.granted_kinds:
            Consent.record(user, kind, Consent.GRANTED)
            AuditEvent.record(AuditEvent.CONSENT_GRANTED, user_id=user.pk, kind=kind)
        access, refresh = tokens.issue(user)
        AuditEvent.record(AuditEvent.LOGIN_SUCCEEDED, user_id=user.pk)
        response = Response(status=status.HTTP_201_CREATED)
        cookies.set_tokens(response, access, refresh)
        return response


class LoginView(_AuthAPIView):
    authentication_classes: ClassVar[list[Any]] = []
    permission_classes: ClassVar[list[type[BasePermission]]] = [AllowAny]
    throttle_scope = "auth-login"

    def post(self, request: Request) -> Response:
        enforce_csrf(request)
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]
        # `authenticate` runs AxesStandaloneBackend first, so a locked out
        # attempt never reaches ModelBackend and never checks a password.
        user = authenticate(request, username=email, password=serializer.validated_data["password"])
        if user is None:
            # The audit line carries the user id when the account exists and
            # nothing identifying when it does not. Never the address that was
            # tried: that would be the address of somebody who may not even be a
            # customer, in a table with no retention.
            existing = User.objects.filter(email=email).values_list("pk", flat=True).first()
            AuditEvent.record(AuditEvent.LOGIN_FAILED, user_id=existing)
            # One answer for a wrong password and for an unknown address.
            raise AuthenticationFailed(NL["credentials_invalid"])
        AuditEvent.record(AuditEvent.LOGIN_SUCCEEDED, user_id=user.pk)
        access, refresh = tokens.issue(user)
        response = Response(status=status.HTTP_200_OK)
        cookies.set_tokens(response, access, refresh)
        return response


class RefreshView(_AuthAPIView):
    authentication_classes: ClassVar[list[Any]] = []
    permission_classes: ClassVar[list[type[BasePermission]]] = [AllowAny]
    throttle_scope = "auth-refresh"

    def post(self, request: Request) -> Response:
        enforce_csrf(request)
        raw = request.COOKIES.get(settings.AMPEER_REFRESH_COOKIE)
        if not raw:
            raise AuthenticationFailed(NL["not_signed_in"])
        try:
            access, refresh = tokens.rotate(raw)
        except (tokens.TokenReuse, TokenError) as error:
            # Every failure here ends the session rather than leaving a half
            # usable one behind, and the cookies go with it. `rotate` has already
            # revoked the whole chain when the cause is reuse; this only reports
            # it. Two exception types and not a bare `except`, so a bug inside
            # `rotate` surfaces as a 500 instead of being answered as if the
            # visitor's token were the problem.
            AuditEvent.record(AuditEvent.LOGIN_FAILED, reused=isinstance(error, tokens.TokenReuse))
            response = Response(
                {"detail": NL["session_expired"]}, status=status.HTTP_401_UNAUTHORIZED
            )
            cookies.clear_tokens(response)
            return response
        response = Response(status=status.HTTP_200_OK)
        cookies.set_tokens(response, access, refresh)
        return response


class LogoutView(_AuthAPIView):
    throttle_scope = "auth-write"

    def post(self, request: Request) -> Response:
        raw = request.COOKIES.get(settings.AMPEER_REFRESH_COOKIE)
        if raw:
            tokens.revoke(raw)
        AuditEvent.record(AuditEvent.LOGOUT, user_id=self.user.pk)
        response = Response(status=status.HTTP_204_NO_CONTENT)
        cookies.clear_tokens(response)
        return response
```

Voeg bovenaan toe: `from django.conf import settings` en `from rest_framework_simplejwt.exceptions import TokenError`.

`backend/accounts/urls.py`:

```python
"""The account routes, mounted under /api/auth/ by the root URL configuration.

Which of them may skip the rate limit: none. tests/test_backend_settings.py
walks the resolver and fails on any view here without a scope that has a rate.
"""

from __future__ import annotations

from django.urls import URLPattern, path

from accounts.views import LoginView, LogoutView, RefreshView, RegisterView

urlpatterns: list[URLPattern] = [
    path("register/", RegisterView.as_view(), name="auth-register"),
    path("login/", LoginView.as_view(), name="auth-login"),
    path("refresh/", RefreshView.as_view(), name="auth-refresh"),
    path("logout/", LogoutView.as_view(), name="auth-logout"),
]
```

In `backend/ampeer/urls.py`, één regel erbij:

```python
urlpatterns: list[URLPattern | URLResolver] = [
    path("api/advice/", include("advice.urls")),
    path("api/auth/", include("accounts.urls")),
]
```

- [ ] **Step 5: Draai en toon aan dat de controles rood kunnen worden**

```bash
uv run --no-sync pytest tests/test_accounts_api.py tests/test_backend_settings.py -q
```

Verwacht: groen, inclusief `test_every_public_route_is_rate_limited` over de vier nieuwe routes. Drie demonstraties:

Zet `samesite=SAMESITE` in `cookies.set_tokens` tijdelijk op `"Lax"`; verwacht dat `test_every_token_cookie_carries_the_attributes_that_protect_it` valt met `is SameSite='Lax'`. Haal `throttle_scope` van `LogoutView` weg; verwacht dat `test_every_public_route_is_rate_limited` valt met `throttle_scope=None`. Haal de `enforce_csrf`-aanroep uit `RegisterView.post`; verwacht dat `test_an_unsafe_request_without_the_csrf_token_is_refused` valt zodra hij in taak 10 op een route zonder cookie draait, en noteer dat die demonstratie in taak 10 hoort omdat `logout/` zijn CSRF via de authenticatieklasse krijgt.

- [ ] **Step 6: Commit**

Boodschap: `feat(accounts): register, log in, refresh and log out over cookies`.

---

### Taak 10: `me/` en `consent/`

**Hangt af van:** taak 7 (importeert de `AuditEvent`-constanten die taak 7 produceert) en taak 9.

**Files:**
- Modify: `backend/accounts/views.py`, `backend/accounts/urls.py`, `backend/accounts/serializers.py`, `tests/test_accounts_api.py`

**Interfaces:**
- Consumes: `accounts.views._AuthAPIView`, `accounts.models.Consent.current/record`, `advice.models.AuditEvent`.
- Produces: routes `auth-me` en `auth-consent`; `accounts.serializers.ConsentSerializer`.

- [ ] **Step 1: Schrijf de falende tests**

Zet eerst `_csrf` om naar de route die een browser echt als eerste aanroept. Vervang in `tests/test_accounts_api.py` de regel `client.get("/api/auth/login/")` door `client.get("/api/auth/me/")` en werk de docstring bij: `me/` antwoordt 401 aan een uitgelogde bezoeker en zet de cookie evengoed, wat precies is waar `_AuthAPIView.finalize_response` voor bestaat. Voeg daarna toe:

```python
@pytest.mark.django_db
def test_me_answers_401_to_a_stranger_and_still_hands_out_a_csrf_token(client: Any) -> None:
    """The property `_AuthAPIView.finalize_response` exists for. Without it the
    only route that sets a CSRF cookie sits behind the login that needs one."""
    response = client.get("/api/auth/me/")
    assert response.status_code == 401
    assert "csrftoken" in response.cookies


@pytest.mark.django_db
def test_me_answers_the_address_and_both_consents(client: Any) -> None:
    client.post("/api/auth/register/", BODY, content_type="application/json", **_csrf(client))
    response = client.get("/api/auth/me/")
    assert response.status_code == 200
    assert response.json() == {
        "email": "iemand@voorbeeld.nl",
        "consents": {"METER_LINK": True, "LEAD_GENERATION": False},
    }


@pytest.mark.django_db
def test_a_consent_can_be_withdrawn_and_given_again(client: Any) -> None:
    client.post("/api/auth/register/", BODY, content_type="application/json", **_csrf(client))
    user = User.objects.get(email="iemand@voorbeeld.nl")

    withdraw = client.post(
        "/api/auth/consent/",
        {"kind": "METER_LINK", "action": "WITHDRAWN"},
        content_type="application/json",
        **_csrf(client),
    )
    assert withdraw.status_code == 200
    assert Consent.current(user, Consent.METER_LINK) is False

    again = client.post(
        "/api/auth/consent/",
        {"kind": "METER_LINK", "action": "GRANTED"},
        content_type="application/json",
        **_csrf(client),
    )
    assert again.status_code == 200
    assert Consent.current(user, Consent.METER_LINK) is True
    assert Consent.objects.filter(user=user, kind=Consent.METER_LINK).count() == 3


@pytest.mark.django_db
def test_a_consent_row_can_only_be_written_for_the_caller(client: Any) -> None:
    """Object level permissions: the queryset filters on request.user and there
    is no field in the body that names a user at all."""
    other = User.objects.create_user(email="ander@voorbeeld.nl", password=PASSWORD)
    client.post("/api/auth/register/", BODY, content_type="application/json", **_csrf(client))
    client.post(
        "/api/auth/consent/",
        {"kind": "METER_LINK", "action": "WITHDRAWN", "user": other.pk},
        content_type="application/json",
        **_csrf(client),
    )
    assert Consent.objects.filter(user=other).count() == 0


@pytest.mark.django_db
def test_an_unknown_consent_kind_is_refused(client: Any) -> None:
    client.post("/api/auth/register/", BODY, content_type="application/json", **_csrf(client))
    response = client.post(
        "/api/auth/consent/",
        {"kind": "SELL_MY_DATA", "action": "GRANTED"},
        content_type="application/json",
        **_csrf(client),
    )
    assert response.status_code == 400
    assert "kind" in response.json()


@pytest.mark.django_db
def test_a_withdrawal_is_written_to_the_audit_log(client: Any) -> None:
    from advice.models import AuditEvent

    client.post("/api/auth/register/", BODY, content_type="application/json", **_csrf(client))
    client.post(
        "/api/auth/consent/",
        {"kind": "METER_LINK", "action": "WITHDRAWN"},
        content_type="application/json",
        **_csrf(client),
    )
    line = AuditEvent.objects.filter(event_type=AuditEvent.CONSENT_WITHDRAWN).get()
    assert line.context["kind"] == "METER_LINK"
    assert "voorbeeld" not in str(line.context), "the audit log carries the address"


@pytest.mark.django_db
def test_an_access_token_in_a_header_is_not_accepted(client: Any) -> None:
    """One accepted place for a credential, so there is one place it can leak.

    A header reaches a proxy log more easily than a cookie does, which is the
    same argument docs/dpia.md chapter 8 makes about the advice token sitting in
    a path. simplejwt's own JWTAuthentication reads the header by default, so
    this is a property of the override and not of the package.
    """
    client.post("/api/auth/register/", BODY, content_type="application/json", **_csrf(client))
    raw = client.cookies[settings.AMPEER_ACCESS_COOKIE].value
    client.cookies.clear()
    response = client.get("/api/auth/me/", HTTP_AUTHORIZATION=f"Bearer {raw}")
    assert response.status_code == 401, (
        "an access token was accepted out of a header, so there are two places it can be "
        "replayed from and only one of them was designed for"
    )
```

- [ ] **Step 2: Draai en zie ze falen op 404**

- [ ] **Step 3: Voeg de serializer toe**

In `backend/accounts/serializers.py`:

```python
class ConsentSerializer(serializers.Serializer[dict[str, Any]]):
    """One consent, one action, and no field that names a user.

    The user comes off `request.user` and can therefore not be chosen by the
    caller. That is object level permissions expressed as an absence, which is
    stronger than a check: there is nothing to check because there is nothing to
    send.
    """

    kind = serializers.ChoiceField(
        choices=sorted(Consent.KINDS), error_messages={"invalid_choice": NL["consent_kind_unknown"]}
    )
    action = serializers.ChoiceField(
        choices=sorted(Consent.ACTIONS),
        error_messages={"invalid_choice": NL["consent_action_unknown"]},
    )
```

- [ ] **Step 4: Voeg de views toe**

In `backend/accounts/views.py`:

```python
class MeView(_AuthAPIView):
    """Who is logged in, and what they have said yes to.

    The one route a frontend with httpOnly cookies has to call to know whether
    anybody is logged in at all, which is why it is also where the CSRF cookie
    is picked up on the way to the login form.
    """

    throttle_scope = "auth-read"

    def get(self, request: Request) -> Response:
        return Response(
            {
                "email": self.user.email,
                "consents": {
                    kind: Consent.current(self.user, kind) for kind in sorted(Consent.KINDS)
                },
            }
        )


class ConsentView(_AuthAPIView):
    """Give or withdraw one consent. A POST, because a withdrawal adds a row.

    A PATCH would be the shape that changes one, and docs/dpia.md chapter 7 says
    this API does not do that. It is also the wrong shape for the thing itself:
    the history of a consent is what makes it demonstrable.
    """

    throttle_scope = "auth-write"

    def post(self, request: Request) -> Response:
        serializer = ConsentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        kind = serializer.validated_data["kind"]
        action = serializer.validated_data["action"]
        Consent.record(self.user, kind, action)
        AuditEvent.record(
            AuditEvent.CONSENT_GRANTED
            if action == Consent.GRANTED
            else AuditEvent.CONSENT_WITHDRAWN,
            user_id=self.user.pk,
            kind=kind,
        )
        return Response({"kind": kind, "granted": Consent.current(self.user, kind)})
```

Voeg `ConsentSerializer` toe aan de import bovenin, en twee regels aan `urls.py`.

De fence hieronder zegt `text` en niet `python`, en dat is dragend. Dit zijn
twee elementen uit `urlpatterns`, geen module: als losse regels gelezen zijn
het expressies met een komma erachter, en de formatter die over dit document
loopt maakt daar `(path(...),)` van. Dat is precies wat op 2026-09-04 gebeurde,
bij de commit van taak 1, en het zou taak 9 twee onbruikbare regels in
`urls.py` hebben laten schrijven. Zet deze fence niet terug op `python`.

```text
    path("me/", MeView.as_view(), name="auth-me"),
    path("consent/", ConsentView.as_view(), name="auth-consent"),
```

- [ ] **Step 5: Draai en toon aan dat het rood kan worden**

```bash
uv run --no-sync pytest tests/test_accounts_api.py -q
```

Verwacht: groen. Haal daarna de `finalize_response` uit `_AuthAPIView` weg en verwacht dat `test_me_answers_401_to_a_stranger_and_still_hands_out_a_csrf_token` valt op de ontbrekende cookie, en dat elke andere test die `_csrf` gebruikt met een `KeyError: 'csrftoken'` valt. Dat tweede is het bewijs dat de plaatsing van die aanroep het verschil maakt en niet decoratie is. Zet hem terug.

Voeg daarna tijdelijk `user = serializers.IntegerField()` toe aan `ConsentSerializer` en laat de view `Consent.record(User.objects.get(pk=...), ...)` doen; verwacht dat `test_a_consent_row_can_only_be_written_for_the_caller` valt. Zet het terug.

- [ ] **Step 6: Commit**

Boodschap: `feat(accounts): read who is signed in and change one consent at a time`.

---

### Taak 11: `export/` en `delete/`

**Hangt af van:** taak 7 en taak 10.

**Files:**
- Create: `backend/accounts/service.py`, `tests/test_accounts_deletion.py`
- Modify: `backend/accounts/views.py`, `backend/accounts/urls.py`

**Interfaces:**
- Consumes: `advice.models.StoredAdvice.owner` (taak 7), `accounts.models.Consent`, `accounts.tokens.revoke_all`, `advice.models.AuditEvent`.
- Produces: `accounts.service.export_account(user: User) -> dict[str, Any]`; `accounts.service.delete_account(user: User) -> None`; routes `auth-export` en `auth-delete`.

- [ ] **Step 1: Schrijf de falende tests**

Maak `tests/test_accounts_deletion.py`:

```python
"""Export and deletion, the two rights CLAUDE.md puts in the phase that has accounts.

The advice list in an export is empty for every real account in v1, because
nothing in this phase writes `StoredAdvice.owner`. The shape is still asserted,
on a row these tests attach themselves, so that phase 2 lands in something whose
behaviour is already pinned rather than inventing it then.
"""

from __future__ import annotations

from typing import Any

import pytest

from accounts.models import Consent, RefreshSession, User
from advice.models import AuditEvent, StoredAdvice

PASSWORD = "een-heel-lang-wachtwoord"
BODY = {
    "email": "iemand@voorbeeld.nl",
    "password": PASSWORD,
    "consent_meter_link": True,
    "consent_lead_generation": False,
}


def _csrf(client: Any) -> dict[str, str]:
    client.get("/api/auth/me/")
    return {"HTTP_X_CSRFTOKEN": client.cookies["csrftoken"].value}


def _registered(client: Any) -> User:
    client.post("/api/auth/register/", BODY, content_type="application/json", **_csrf(client))
    return User.objects.get(email="iemand@voorbeeld.nl")


@pytest.mark.django_db
def test_an_export_carries_the_account_and_an_empty_advice_list(client: Any) -> None:
    _registered(client)
    response = client.post("/api/auth/export/", content_type="application/json", **_csrf(client))
    assert response.status_code == 200
    body = response.json()
    assert body["email"] == "iemand@voorbeeld.nl"
    assert [row["kind"] for row in body["consents"]] == ["METER_LINK"]
    assert body["advices"] == [], (
        "nothing in phase 1 writes StoredAdvice.owner, so a real account cannot have one yet"
    )


@pytest.mark.django_db
def test_an_export_hands_back_the_stored_json_unchanged(client: Any) -> None:
    """Amounts are strings because JSON has only floats. An export that rebuilt
    the answer would be one more place a number passes through a parser."""
    user = _registered(client)
    stored = StoredAdvice.create(
        inputs={"postcode4": "5401"}, advice={"headline": {"p50": "700.08"}}
    )
    stored.owner = user
    stored.save(update_fields=["owner"])

    body = client.post("/api/auth/export/", content_type="application/json", **_csrf(client)).json()
    assert body["advices"] == [
        {"inputs": {"postcode4": "5401"}, "advice": {"headline": {"p50": "700.08"}}}
    ]


@pytest.mark.django_db
def test_an_export_reaches_only_the_caller(client: Any) -> None:
    other = User.objects.create_user(email="ander@voorbeeld.nl", password=PASSWORD)
    stranger = StoredAdvice.create(inputs={"postcode4": "1011"}, advice={})
    stranger.owner = other
    stranger.save(update_fields=["owner"])
    _registered(client)

    body = client.post("/api/auth/export/", content_type="application/json", **_csrf(client)).json()
    assert body["advices"] == []


@pytest.mark.django_db
def test_an_export_is_written_to_the_audit_log(client: Any) -> None:
    user = _registered(client)
    client.post("/api/auth/export/", content_type="application/json", **_csrf(client))
    line = AuditEvent.objects.filter(event_type=AuditEvent.DATA_EXPORTED).get()
    assert line.context == {"user_id": user.pk}


@pytest.mark.django_db
def test_deleting_takes_the_account_its_consents_its_sessions_and_its_advice(
    client: Any,
) -> None:
    user = _registered(client)
    owned = StoredAdvice.create(inputs={"postcode4": "5401"}, advice={})
    owned.owner = user
    owned.save(update_fields=["owner"])
    anonymous = StoredAdvice.create(inputs={"postcode4": "5401"}, advice={})

    response = client.post(
        "/api/auth/delete/",
        {"password": PASSWORD},
        content_type="application/json",
        **_csrf(client),
    )
    assert response.status_code == 204
    assert not User.objects.filter(pk=user.pk).exists()
    assert not Consent.objects.filter(user_id=user.pk).exists()
    assert not RefreshSession.objects.filter(user_id=user.pk).exists()
    assert not StoredAdvice.objects.filter(pk=owned.pk).exists()
    assert StoredAdvice.objects.filter(pk=anonymous.pk).exists(), (
        "an advice that belongs to nobody was taken with an account it never belonged to"
    )


@pytest.mark.django_db
def test_deleting_leaves_the_audit_log_standing(client: Any) -> None:
    """An append-only log that records a deletion and wipes itself doing so
    records nothing."""
    user = _registered(client)
    client.post(
        "/api/auth/delete/",
        {"password": PASSWORD},
        content_type="application/json",
        **_csrf(client),
    )
    kinds = set(AuditEvent.objects.values_list("event_type", flat=True))
    assert AuditEvent.ACCOUNT_CREATED in kinds
    assert AuditEvent.ACCOUNT_DELETED in kinds
    line = AuditEvent.objects.filter(event_type=AuditEvent.ACCOUNT_DELETED).get()
    assert line.context == {"user_id": user.pk}


@pytest.mark.django_db
def test_deleting_needs_the_password_again(client: Any) -> None:
    """Without it one stolen session is enough to wipe somebody's data, and it
    is the other reason this route is a POST: a DELETE with a body is something
    proxies and clients disagree about."""
    user = _registered(client)
    response = client.post(
        "/api/auth/delete/",
        {"password": "verkeerd"},
        content_type="application/json",
        **_csrf(client),
    )
    assert response.status_code == 403
    assert User.objects.filter(pk=user.pk).exists()


@pytest.mark.django_db
def test_deleting_refuses_a_body_that_is_not_an_object(client: Any) -> None:
    """`DeleteView`'s `isinstance(request.data, dict)` guard. A JSON body that
    parses to a list has no `.get`, and calling it anyway would be an
    `AttributeError` reaching a visitor as a 500 instead of the same refusal a
    wrong password gets."""
    user = _registered(client)
    response = client.post(
        "/api/auth/delete/",
        data='["verkeerd soort lichaam"]',
        content_type="application/json",
        **_csrf(client),
    )
    assert response.status_code == 403
    assert User.objects.filter(pk=user.pk).exists()
```

- [ ] **Step 2: Draai en zie ze falen op 404**

- [ ] **Step 3: Schrijf `service.py`**

```python
"""The two handlings that have consequences outside their own request.

Kept out of views.py because both are a sequence with an order that matters, and
an order that matters belongs somewhere it can be read in one screen.
"""

from __future__ import annotations

from typing import Any

from django.db import transaction

from accounts import tokens
from accounts.models import Consent, User
from advice.models import AuditEvent, StoredAdvice


def export_account(user: User) -> dict[str, Any]:
    """Everything this service holds about one account.

    `inputs` as well as `advice`, which repairs the gap docs/dpia.md chapter 7
    names: the token route returns the advice and not the answers it was made
    from, so a visitor sees the outcome and not the input. Structurally repaired
    here; materially it changes nothing until phase 2 attaches an advice to an
    account, because nothing in phase 1 writes `owner`.

    The stored JSON is passed through and never rebuilt. Every amount in it is a
    string, because JSON has only floats, and rebuilding is one more place a
    number could pass through a parser.
    """
    advices = StoredAdvice.objects.filter(owner=user).order_by("created_at")
    return {
        "email": user.email,
        "date_joined": user.date_joined.isoformat(),
        "consents": [
            {
                "kind": row.kind,
                "action": row.action,
                "occurred_at": row.occurred_at.isoformat(),
                "text_version": row.text_version,
            }
            for row in Consent.objects.filter(user=user).order_by("occurred_at")
        ],
        "advices": [{"inputs": row.inputs, "advice": row.advice} for row in advices],
    }


def delete_account(user: User) -> None:
    """Remove the account and everything that hangs off it, in one transaction.

    The audit line is written inside the transaction, not before and not after.
    Before, a failed deletion leaves a line saying something happened that did
    not; after, a failed write leaves a deletion nobody recorded. `AuditEvent` is
    the one table here that cannot be rebuilt from anything else.

    `user_id` is read before the delete because afterwards there is no row to
    read it from, and it is a plain integer in the context rather than a foreign
    key: a key would either block this deletion or be taken by it.
    """
    user_id = user.pk
    with transaction.atomic():
        tokens.revoke_all(user)
        AuditEvent.record(AuditEvent.ACCOUNT_DELETED, user_id=user_id)
        # CASCADE takes Consent, RefreshSession and every StoredAdvice with this
        # owner. An advice with owner NULL is not this account's and stays.
        user.delete()
```

- [ ] **Step 4: Voeg de views toe**

In `backend/accounts/views.py`:

```python
class ExportView(_AuthAPIView):
    """A POST and not a GET, for two reasons that both outweigh the convention.

    It writes a DATA_EXPORTED line, and a GET with a side effect is a GET a
    browser or a proxy may repeat. And the answer describes one household in
    full, so it has to fall under `Cache-Control: private, no-store`, which the
    base class already applies.
    """

    throttle_scope = "auth-export"

    def post(self, request: Request) -> Response:
        payload = service.export_account(self.user)
        AuditEvent.record(AuditEvent.DATA_EXPORTED, user_id=self.user.pk)
        return Response(payload)


class DeleteView(_AuthAPIView):
    throttle_scope = "auth-write"

    def post(self, request: Request) -> Response:
        password = request.data.get("password") if isinstance(request.data, dict) else None
        if not isinstance(password, str) or not self.user.check_password(password):
            raise PermissionDenied(NL["credentials_invalid"])
        service.delete_account(self.user)
        response = Response(status=status.HTTP_204_NO_CONTENT)
        cookies.clear_tokens(response)
        return response
```

Voeg `from accounts import cookies, service, tokens` toe bovenin, en twee regels
aan `urls.py`. De fence staat op `text` en niet op `python`, om dezelfde reden
als bij taak 10: dit zijn twee elementen uit `urlpatterns` en geen module, en
de formatter die over dit document loopt maakt van zulke losse regels
`(path(...),)`. Zet deze fence niet terug op `python`.

```text
    path("export/", ExportView.as_view(), name="auth-export"),
    path("delete/", DeleteView.as_view(), name="auth-delete"),
```

- [ ] **Step 5: Draai en toon aan dat het rood kan worden**

```bash
uv run --no-sync pytest tests/test_accounts_deletion.py tests/test_backend_settings.py -q
```

Verwacht: groen, met alle acht routes onder een scope. Zet daarna `on_delete` op de `owner`-kolom tijdelijk op `SET_NULL` (en `makemigrations`), en verwacht dat `test_deleting_takes_the_account_its_consents_its_sessions_and_its_advice` valt op het achtergebleven advies. Draai terug, inclusief de migratie. Laat daarna `DeleteView` de wachtwoordcontrole over, en verwacht dat `test_deleting_needs_the_password_again` valt met een verdwenen account.

- [ ] **Step 6: Commit**

Boodschap: `feat(accounts): export what we hold, and delete it on request`.

---

## Fase 4: de documenten en de poorten

### Taak 12: De documenten, en de controles die de nieuwe app moeten lezen

**Hangt af van:** taak 11.

Zonder deze taak is de suite groen over een boom die hij niet meer helemaal leest, en dat is precies de faalvorm die hoofdstuk 3.2 van de spec beschrijft.

**Files:**
- Modify: `docs/dpia.md`, `docs/decisions.md`, `docs/superpowers/specs/2026-09-04-accounts-auth-design.md`, `tests/test_dpia.py`, `backend/advice/views.py`
- Create: `tests/test_accounts_privacy.py`

**Interfaces:**
- Consumes: alles uit taak 3 tot en met 11.
- Produces: `tests/test_dpia.py` met `VIEWS` als lijst en `ACCOUNT_MODELS` als nieuwe padconstante, die samen `backend/accounts/` meelezen; `MODELS` blijft één pad.

- [ ] **Step 1: Verbreed wat de verb-check leest, en geef de adrescheck een tweede constante**

`MODELS` blijft één pad. Twee andere tests lezen `MODELS.read_text` rechtstreeks,
`test_the_document_quotes_the_length_of_a_token` en
`test_the_audit_log_records_exactly_what_the_document_says_it_does`, en allebei gaan
ze over `backend/advice/models.py` specifiek: de tokenlengte en `AuditEvent` staan
daar en nergens anders. `MODELS` in een lijst veranderen breekt die twee met een
`AttributeError` op `.read_text`, en deze taak noemt geen van beide in zijn Files-blok
om ze te repareren. `VIEWS` heeft dat probleem niet: de enige plek die `VIEWS.read_text`
rechtstreeks aanroept is hieronder al voorzien van een eigen vaste `backend/advice/views.py`.

In `tests/test_dpia.py`:

```python
#: One path, unchanged. Two tests read MODELS.read_text directly for a property
#: of backend/advice/models.py specifically (the token length, and AuditEvent's
#: own kinds), and widening this to a list would break both with an
#: AttributeError that this task does not own the file to fix.
MODELS = REPO_ROOT / "backend" / "advice" / "models.py"

#: The second address to check, kept separate rather than folded into MODELS for
#: the reason above. _model_field_names is the only reader of both; every other
#: use of MODELS stays about backend/advice/models.py alone.
ACCOUNT_MODELS = REPO_ROOT / "backend" / "accounts" / "models.py"

#: A list rather than one path, because the app that actually holds the personal
#: details would otherwise escape the verb check entirely. A guard that reads one
#: file while its commit claims a property of the package is the failure
#: advice/nl.py already carries a note about.
VIEWS = [
    REPO_ROOT / "backend" / "advice" / "views.py",
    REPO_ROOT / "backend" / "accounts" / "views.py",
]
```

Pas `_model_field_names` aan zodat hij `MODELS` en `ACCOUNT_MODELS` allebei parst en de twee resultaten samenvoegt; dat is de enige functie die `ACCOUNT_MODELS` noemt. Pas `_handlers_per_view` aan zodat hij over de `VIEWS`-lijst loopt en zijn resultaten samenvoegt, en pas `test_the_document_says_which_data_an_access_request_does_not_reach` aan zodat hij expliciet `REPO_ROOT / "backend" / "advice" / "views.py"` leest in plaats van `VIEWS`, want die assertie gaat over de tokenroute en niet over de accountroutes.

```bash
uv run --no-sync pytest tests/test_dpia.py -q
```

Verwacht: `test_no_table_has_a_column_for_an_address` blijft groen (geen enkel veld in `accounts/models.py` lijkt op een adres), `test_the_api_answers_only_the_verbs_the_document_describes` blijft groen (alle acht routes zijn `get` of `post`), en `test_the_document_quotes_the_length_of_a_token` en `test_the_audit_log_records_exactly_what_the_document_says_it_does` blijven allebei groen omdat `MODELS` nog steeds één pad is. Is een van de eerste twee dat niet, dan is dat een echte bevinding en geen testprobleem.

- [ ] **Step 2: Toon aan dat de verbreding werkt**

Voeg tijdelijk `client_ip = models.CharField(max_length=45)` toe aan `RefreshSession` en verwacht dat `test_no_table_has_a_column_for_an_address` valt met `RefreshSession.client_ip`. Haal hem weg. Voeg tijdelijk een `def delete(self, request)` toe aan `DeleteView` en verwacht dat de werkwoordtest valt met `the API now answers ['delete', 'get', 'post']`. Haal hem weg. Zonder deze twee is stap 1 een groene uitslag van een instrument waarvan niemand weet of het de nieuwe map leest.

- [ ] **Step 3: Schrijf de privacytest**

Maak `tests/test_accounts_privacy.py`:

```python
"""What the account layer may and may not have written down.

The claims in docs/dpia.md chapter 2 are checked against values here and not
against a field list, for the reason section 13.9 of the advice API design
gives: a field list is fixed at import and can never contain what came in at
runtime, so a test over one cannot fail.
"""

from __future__ import annotations

import re
from typing import Any

import pytest

from accounts.models import Consent, RefreshSession, User
from advice.models import AuditEvent

EMAIL = re.compile(r"[^@\s]+@[^@\s]+\.[a-z]{2,}", re.IGNORECASE)


def _values(value: Any) -> list[str]:
    if isinstance(value, dict):
        return [text for item in value.items() for entry in item for text in _values(entry)]
    if isinstance(value, (list, tuple)):
        return [text for entry in value for text in _values(entry)]
    return [str(value)]


@pytest.mark.django_db
def test_no_audit_line_the_account_layer_writes_carries_an_address(client: Any) -> None:
    body = {
        "email": "iemand@voorbeeld.nl",
        "password": "een-heel-lang-wachtwoord",
        "consent_meter_link": True,
        "consent_lead_generation": True,
    }
    client.get("/api/auth/me/")
    csrf = {"HTTP_X_CSRFTOKEN": client.cookies["csrftoken"].value}
    client.post("/api/auth/register/", body, content_type="application/json", **csrf)
    client.post("/api/auth/logout/", content_type="application/json", **csrf)
    client.post(
        "/api/auth/login/",
        {"email": "iemand@voorbeeld.nl", "password": "verkeerd"},
        content_type="application/json",
        **csrf,
    )

    assert AuditEvent.objects.count() >= 4, "this test is no longer exercising the routes"
    for line in AuditEvent.objects.all():
        for text in _values(line.context):
            assert not EMAIL.search(text), (
                f"{line.event_type} wrote {text!r} into a table with no retention"
            )


@pytest.mark.django_db
def test_a_failed_login_for_an_unknown_address_records_nothing_identifying(client: Any) -> None:
    """The address of somebody who may not even be a customer, permanently."""
    client.get("/api/auth/me/")
    csrf = {"HTTP_X_CSRFTOKEN": client.cookies["csrftoken"].value}
    client.post(
        "/api/auth/login/",
        {"email": "niemand@voorbeeld.nl", "password": "verkeerd"},
        content_type="application/json",
        **csrf,
    )
    line = AuditEvent.objects.filter(event_type=AuditEvent.LOGIN_FAILED).get()
    assert line.context.get("user_id") is None


@pytest.mark.django_db
def test_no_session_row_carries_anything_that_opens_a_session() -> None:
    from accounts import tokens

    user = User.objects.create_user(email="iemand@voorbeeld.nl", password="een-lang-wachtwoord")
    _, refresh = tokens.issue(user)
    session = RefreshSession.objects.get(user=user)
    assert refresh not in session.jti_sha256
    for part in refresh.split("."):
        assert part not in session.jti_sha256


@pytest.mark.django_db
def test_a_consent_row_holds_no_free_text() -> None:
    """The wording lives in nl.py under a version. A copy of the sentence in
    every row would be a second place it can drift from the one people read."""
    user = User.objects.create_user(email="iemand@voorbeeld.nl", password="een-lang-wachtwoord")
    row = Consent.record(user, Consent.METER_LINK, Consent.GRANTED)
    assert " " not in row.text_version
    assert len(row.text_version) <= 32
```

- [ ] **Step 4: Schrijf de documenten bij**

`docs/dpia.md`, de zes hoofdstukken die dit met zich meebrengen. Hoofdstuk 2 is in taak 7 al bijgewerkt; hier komen 0, 1, 4, 7, 9 en 10 aan de beurt. Hoofdstuk 0 staat niet in de lijst van hoofdstuk 14 van de spec, en moet toch mee: hij opent met "Vijf dingen zijn beslissingen van de verwerkingsverantwoordelijke" en dat wordt onwaar zodra hoofdstuk 10 van vijf open punten naar vier gaat. `test_the_opening_points_at_the_chapter_that_holds_the_open_decisions` leest die openingszin tegen de telling in hoofdstuk 10 en valt anders. Let op vier tests die letterlijke zinnen lezen: `test_the_api_answers_only_the_verbs_the_document_describes` eist `"Er is geen vierde."` en `"Er is geen verwijderknop en geen verwijderendpoint."`, en die twee zinnen zijn nu onwaar en moeten weg, dus die assertions moeten in dezelfde bewerking mee. `test_every_section_is_numbered_consecutively`, `test_the_document_carries_no_em_dashes` en `test_the_chapter_of_open_decisions_states_how_many_there_are` blijven gelden: hoofdstuk 10 gaat van vijf open punten naar vier, want punt 4 over verwijderen is beantwoord.

Wat er inhoudelijk in moet, per hoofdstuk: in 0 wordt "Vijf dingen zijn" "Vier dingen zijn"; in 1 dat de conclusie voor fase 0.5 gold en dat een beoordeling nu waarschijnlijk wel verplicht is; in 4 dat de bewaartermijnen en de back-upruil ook gelden voor een verwijderd account, met de acht dagen erbij; in 7 dat inzage, overdraagbaarheid en verwijdering voor een accounthouder alle drie veranderen en voor de anonieme tokenroute geen van drieën, en dat de export de invoer structureel bereikbaar maakt en materieel pas in fase 2; in 9 dat dit geen vooruitblik meer is; in 10 dat punt 4 met ja is beantwoord en punt 2 voorlopig op toestemming staat.

`docs/decisions.md` krijgt zes entries in het bestaande formaat: het eigen gebruikersmodel en waarom `AUTH_USER_MODEL` niet uitgesteld kon worden; `CASCADE` op `owner` en waarom `SET_NULL` een verwijderverzoek in een naamsverandering verandert; `RefreshSession` in plaats van `token_blacklist`, met de plaintextkolom als reden; de axes-cachehandler, met **de twee gemeten getallen uit taak 2 en taak 4 en hun datum**; het ontbreken van wachtwoordherstel met het gevolg dat het verwijderendpoint dan onbereikbaar is, plus dat `PasswordResetTokenGenerator` al geïnstalleerd is en alleen een SMTP-kanaal ontbreekt; en dat de valstrik in taak 3 (`django.contrib.auth` in `INSTALLED_APPS` maakt `test_nothing_authenticates_because_there_is_nothing_to_log_in_to`'s adresassertie onwaar) precies zo afging als bedoeld, met wat de test ervoor in de plaats kreeg.

`docs/superpowers/specs/2026-09-04-accounts-auth-design.md` krijgt in de tabel van hoofdstuk 2 één rij erbij:

```
| `backend/accounts/lockout.py` | de twee callables die axes een gehashte identiteit geven |
```

Diezelfde bewerking corrigeert 9.3: die zegt vandaag dat `AXES_CLIENT_IP_CALLABLE` "met een eigen `KEY_SALT`" digest, en `backend/accounts/lockout.py` doet dat niet, `client_ip` hergebruikt de digest die de snelheidslimiet al berekent. Dat is geen fout in de code, het is een afweging die 9.3 niet als afwijking benoemt. De paragraaf krijgt een zin die zegt dat `client_ip` bewust hergebruikt in plaats van zelf zout toevoegt, en waarom dat geen twee definities van "dezelfde bezoeker" oplevert: axes en de snelheidslimiet zijn allebei een digest van dezelfde bezoeker, dus de koppeling is gewenst.

`backend/advice/views.py`, de moduledocstring. De openingszin "Three endpoints, anonymous, no cookie, no session" blijft waar voor dat bestand en moet dat blijven; er komt een zin bij die zegt waar het wel gebeurt en dat deze drie endpoints daar met opzet buiten vallen.

- [ ] **Step 5: Draai de volledige suite**

```bash
uv run --no-sync pytest -q
```

Verwacht: alles groen behalve `test_a_plan_marked_in_progress_is_actually_unfinished[2026-09-04-accounts-auth.md]`, die nu rood is omdat elk bestand dat dit plan noemt bestaat. Dat is de zelfvervallende marker uit taak 1 die zijn werk doet, en taak 13 zet hem om.

- [ ] **Step 6: Commit**

Boodschap: `docs(dpia): describe the service that has accounts, and read the app that holds them`.

---

### Taak 13: De status omzetten en de poorten draaien

**Hangt af van:** taak 12.

**Files:**
- Modify: `docs/superpowers/plans/2026-09-04-accounts-auth.md`

**Interfaces:**
- Consumes: de statusregel uit taak 1.
- Produces: niets.

- [ ] **Step 1: Zie de rode test**

```bash
uv run --no-sync pytest tests/test_plans.py -q
```

Verwacht: `2026-09-04-accounts-auth.md is marked 'in progress' and every file it names is in the tree. The work is done`.

- [ ] **Step 2: Zet de status om**

Vervang bovenin dit bestand de regel

    **Status:** in progress

(hierboven met vier spaties ingesprongen weergegeven, en niet als peilbaar codeblok op kolom 0: taak 1 legt uit waarom dat load-bearing is) door een blokquote in de vorm die de eerdere plannen gebruiken, met een statusregel die niet `in progress` is:

```
**Status:** delivered

> **Status op 2026-09-04: opgeleverd.** Elk bestand dat dit plan noemt staat in de
> boom, wat `tests/test_plans.py` voor alle zeven plannen controleert en wat rood
> wordt op de dag dat een ervan niet meer klopt. Wat die test niet kan zeggen is
> of elke stap is uitgevoerd zoals hij hier staat; daar zijn de commitgeschiedenis
> en de suite voor.
```

- [ ] **Step 3: Draai alle poorten**

Deze ene regel omzetten is genoeg voor twee bestanden. `tests/test_pipeline_contract.py::test_every_test_file_named_in_a_comment_exists` (taak 1) hield de spec vrijgesteld via `_plan_that_speaks_for`, die naar dit plan wijst en niet naar een eigen statusregel op de spec: zodra deze regel iets anders dan `in progress` zegt, valt die vrijstelling voor beide weg. Dat is hier geen probleem, want elk bestand dat het plan of de spec noemt bestaat inmiddels echt.

```bash
uv run --no-sync pytest -q
bash scripts/gates.sh
```

Beoordeel elke poort op de exitcode en nooit op een grep over de uitvoer. Let op:

- **dekking**: de drempel staat op 98,00 met `precision = 2`. Ligt het resultaat erboven, verhoog de drempel dan naar het gemeten getal op twee decimalen. Omlaag mag nooit.
- **`quality`**: `manage.py check --deploy --fail-level WARNING` draait tegen `ampeer.settings.prod`. Nieuwe instellingen kunnen daar een waarschuwing opleveren.
- **`sast`**: bandit leest nu ook `backend/accounts/`. Een `nosec` mag alleen met de uitleg op een eigen regel erboven en niets dan het test-id erachter, zoals `dev.py` uitlegt.
- **`dependencies`**: drie nieuwe pakketten in de SBOM en in `pip-audit`.
- **`secrets`**: gitleaks over de nieuwe testbestanden. De wachtwoorden daarin zijn fixtures; komt er een melding, los die op met een uitsluiting die het bestand noemt en niet met een patroon.
- **mypy**: `--strict` over `backend`, inclusief de nieuwe app.

- [ ] **Step 4: Commit en open de pull request**

Boodschap: `docs(plans): the accounts plan is delivered`.

De pull request gaat naar `dev` en daarna naar `main`, met alle vereiste checks groen. Nooit direct op `main`.
