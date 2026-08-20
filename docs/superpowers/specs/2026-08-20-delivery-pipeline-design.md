# Ontwerp: leverstraat Ampeer (deelproject 1)

Datum: 2026-08-20
Status: vastgesteld, klaar voor implementatieplan
Betreft: vertakkingsmodel, CI-poorten, security-scanning en de lokale ontwikkellus

## 1. Doel en afbakening

Elke regel code die in `main` terechtkomt, is langs een vaste set geautomatiseerde
poorten gegaan. Dat geldt ook voor code die de eigenaar zelf schrijft.

Binnen scope:

- Vertakkingsmodel met `dev` als standaardbranch en `main` als beschermde branch
- Repository rulesets die dat afdwingen, zonder uitzondering voor de eigenaar
- `ci.yml`: stijl, types, tests en dekking
- `security.yml`: afhankelijkheden, statische analyse, geheimen en een stuklijst
- `dependabot.yml` voor Python en voor GitHub Actions
- Overstap naar uv met een lockfile
- pre-commit voor de snelle lokale controles
- Regels hierover in `CLAUDE.md`

Buiten scope, eigen deelproject:

- De self-hosted runner, de Proxmox LXC en de deploy-workflow (deelproject 2)
- De adviesregels en de Django-API (deelproject 3)
- De frontend en het ontwerpsysteem (deelproject 4)

## 2. Uitgangspunten, geverifieerd op 2026-08-20

- De repository `stijnvandepol/Ampeer` is **private**. Standaardbranch is nu `main`
- **Repository rulesets werken op deze repository.** Geverifieerd door er een aan te
  maken en weer te verwijderen. Blokkerende poorten zijn dus echt afdwingbaar
- **CodeQL en GitHub's eigen secret scanning zitten achter GitHub Advanced Security**,
  wat op een private repository betaald is. Het ontwerp gaat er niet vanuit dat die
  beschikbaar zijn en gebruikt open-source equivalenten. Die zijn hier ook beter: ze
  draaien overal, ze zijn na te lezen, en ze zijn niet aan een leverancier gebonden
- `gh` versie 2.89 is lokaal beschikbaar, dus de rulesets kunnen via de API gezet worden
- De testdekking is op dit moment **97 procent** over `ampeer_sim` en `tools`
- `main` staat lokaal twaalf commits voor op `origin/main`

## 3. Vertakkingsmodel

```
feat/iets ──PR──> dev ──PR──> main ──tag──> deploy (deelproject 2)
              (CI)      (alle poorten)
```

`dev` wordt de standaardbranch. Een verse kloon komt daar uit en dat is waar het
dagelijkse werk gebeurt.

| Branch | Regels | Reden |
|---|---|---|
| `main` | Geen directe push. PR verplicht. Alle vereiste checks groen. Lineaire geschiedenis. Geen force-push. Geen verwijderen. Geen bypass voor de eigenaar | Dit is wat er straks draait |
| `dev` | Geen force-push. Geen verwijderen. CI draait op elke push, directe commits toegestaan | Werken zonder voor elke regel een PR te openen |
| `feat/**` | Geen bescherming, CI draait wel mee | Wegwerpbaar |

De ruleset op `main` krijgt een lege `bypass_actors`. Een regel met een uitzondering
voor de eigenaar is bij een eenpersoonsproject geen regel.

Voorwaarde vooraf: `main` moet eerst gepusht worden, anders wordt `dev` van een
verouderde `main` afgetakt.

## 4. Workflows

Voor beide geldt: expliciete `permissions:` op workflowniveau, standaard
`contents: read`, en elke `uses:` op een commit-SHA met de versie als comment erachter.

Reden voor dat SHA-pinnen: een tag kan verplaatst worden door wie de action beheert.
`uses: actions/checkout@v4` betekent letterlijk "voer uit wat daar nu staat". Bij de
tj-actions-inbraak van maart 2025 is precies dat misbruikt.

### ci.yml

Triggers: push naar `dev` en `feat/**`, en `pull_request` naar `dev` en `main`.
Concurrency-groep per branch met `cancel-in-progress`, zodat een nieuwe push de vorige
run afbreekt.

| Job | Naam in de ruleset | Inhoud |
|---|---|---|
| Kwaliteit | `quality` | `ruff check`, `ruff format --check`, `mypy --strict` |
| Tests | `test` | `pytest` met dekkingsmeting, drempel 97 procent |

De dekkingsdrempel staat gelijk aan de gemeten stand en mag alleen omhoog. Een drempel
onder de huidige stand maakt achteruitgang onzichtbaar.

### security.yml

Triggers: `pull_request` naar `dev` en `main`, een wekelijks schema, en handmatig via
`workflow_dispatch`.

| Job | Naam in de ruleset | Gereedschap | Vangt |
|---|---|---|---|
| Afhankelijkheden | `dependencies` | pip-audit tegen de lockfile | bekende CVE's |
| Statische analyse | `sast` | bandit over `ampeer_sim` en `tools` | onveilige patronen in eigen code |
| Geheimen | `secrets` | gitleaks, zie hieronder | een sleutel die is meegecommit |
| Stuklijst | `sbom` | CycloneDX, als artefact | wat er precies in de build zit |

Het wekelijkse schema is de reden dat dit een eigen workflow is. De CVE-database
verandert dagelijks, de code niet. Zonder schema hoor je pas van een nieuw lek in een
ongewijzigde afhankelijkheid wanneer je toevallig iets commit.

gitleaks draait in twee standen. Op een pull request scant hij alleen de commits die de
PR toevoegt, en dan is hij blokkerend. In de wekelijkse run scant hij de volledige
geschiedenis, en dan rapporteert hij alleen.

Die splitsing lost een echt probleem op. Zou de PR-run de hele geschiedenis scannen, dan
blokkeert een vondst uit 2024 een PR die daar niets aan kan doen, en dan wordt de check
binnen een week weggeklikt. Zo blokkeert hij precies wat de PR zelf toevoegt, wat de
enige vondst is waar de auteur iets mee kan.

gitleaks draait als binary en niet via de officiele action, omdat die voor organisaties
een licentiesleutel vraagt. De binary heeft die beperking niet.

### dependabot.yml

Wekelijks, voor twee ecosystemen: `pip` en `github-actions`.

Dit is geen extraatje maar de tegenhanger van het SHA-pinnen. Pinnen zonder
automatische updates ruilt het risico van een verplaatste tag in voor het risico van
een verouderde, lekke versie.

## 5. Vereiste checks op main

De ruleset op `main` eist deze vijf checknamen letterlijk:

- `quality`
- `test`
- `dependencies`
- `sast`
- `secrets`

`sbom` draait mee maar is niet vereist: die produceert een artefact en geen oordeel.

Omdat de ruleset op namen matcht, zijn jobnamen een publieke interface. Een hernoemde
job levert een check op die nooit binnenkomt en een PR die eeuwig blijft hangen. Dat
staat als waarschuwing bij de jobs in de workflow zelf.

## 6. Lokale ontwikkellus

### uv

uv vervangt pip. `uv.lock` legt exacte versies met hashes vast, platformonafhankelijk,
zodat de Windows-machine, de Ubuntu-runner en straks de LXC hetzelfde installeren.
`uv sync` in plaats van `pip install -e ".[dev]"`, `uv run` voor commando's.

De lockfile wordt gecommit. Elke nieuwe afhankelijkheid gaat via `uv add`.

### pre-commit

Hooks: `ruff`, `ruff-format`, `gitleaks`, plus hygiëne (geen achtergebleven
merge-markers, geen grote bestanden, elk bestand eindigt op een nieuwe regel).

**Mypy staat er bewust niet in.** Die duurt seconden, en een hook die traag is wordt
overgeslagen met `--no-verify`. Een omzeilde poort is slechter dan geen poort, want je
denkt dat hij er staat. Vuistregel: onder de twee seconden hoort in pre-commit, al het
andere in CI.

### .gitattributes

Toevoegen: `*.sh text eol=lf`.

Nu staat er alleen `* text=auto`, waardoor een shellscript op Windows met CRLF wordt
uitgecheckt. Zodra dat script in een Linux-container terechtkomt, faalt het met een
foutmelding die niets met de inhoud te maken heeft. Dat wordt in deelproject 2 relevant.

## 7. Wijzigingen in CLAUDE.md

Een blok `## Werkwijze en poorten` met:

- Werk op `dev` of op een `feat/**`-branch, nooit direct op `main`
- Naar `main` gaat alleen een PR waarvan alle vereiste checks groen zijn
- Elke nieuwe afhankelijkheid gaat via `uv add`, de lockfile wordt meegecommit
- Elke GitHub Action staat op een commit-SHA, met de versie als comment erachter
- Jobnamen in workflows zijn een interface met de rulesets en worden niet hernoemd
  zonder de ruleset mee te wijzigen

## 8. Wat dit deelproject expliciet niet doet

- **Geen self-hosted runner.** Die hoort bij deelproject 2 en brengt zijn eigen
  risico mee: een self-hosted runner die pull requests bouwt, voert code van derden uit
  op eigen hardware achter de eigen firewall. Het ontwerp daarvoor moet dat expliciet
  afvangen met ephemeral runners, een gescheiden LXC en nooit `pull_request` van forks
- **Geen verplichte review op de PR.** Bij een eenpersoonsproject betekent dat jezelf
  goedkeuren via een tweede account of de regel omzeilen, en dat holt hem uit
- **Geen CodeQL.** Niet beschikbaar zonder GitHub Advanced Security op een private
  repository. Als de repository ooit publiek wordt, is dit het eerste om toe te voegen
- **Geen conventional commits of commitlint.** Waardevol in een team, overhead alleen

## 9. Definition of done

- `dev` is de standaardbranch en `main` is beschermd, zonder bypass voor de eigenaar
- Een directe push naar `main` wordt geweigerd, aantoonbaar met een poging
- Een PR van `dev` naar `main` toont vijf vereiste checks en kan niet mergen zolang er
  een rood staat, aantoonbaar met een opzettelijk falende PR
- `uv sync` werkt op een schone kloon en `uv.lock` staat in de repository
- `pre-commit run --all-files` is groen en de hooks draaien onder de twee seconden
- Alle `uses:` in beide workflows staan op een SHA
- `CLAUDE.md` bevat het blok uit hoofdstuk 7
