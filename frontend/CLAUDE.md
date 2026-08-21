@AGENTS.md

# Werken in frontend/

`AGENTS.md` hierboven is door Next zelf geschreven en wordt door `next dev` opnieuw
aangemaakt als je hem weghaalt. Het staat er omdat het waar is: Next 16 wijkt op punten af
van wat een model erover geleerd heeft, en `node_modules/next/dist/docs/` is de bron die
wel klopt. Dit bestand is van ons en staat erboven, zodat de instructie die hier geladen
wordt er een is die dit project heeft geschreven.

Lees `docs/superpowers/specs/2026-08-21-frontend-design.md` voordat je hier iets bouwt.
Wat hieronder staat is de samenvatting die je sowieso nodig hebt.

## De vijf regels die de pagina eerlijk houden

1. **Geen enkel getal wordt groter afgebeeld dan zijn eigen band.** Waar een band bestaat,
   is de band het object en het middelpunt een markering daarin. Dit is de kleinste regel
   van de vijf en hij draagt het meeste: dat ene stijlbesluit is het volledige verschil
   tussen een bandbreedte en een groot getal met versiering.
2. **`confidence_label` staat in het eerste scherm.** Niet onder de vouw, niet achter een
   uitklapper.
3. **Alle drie de routes renderen altijd, in de volgorde van de API, gratis eerst.** Een
   lege route toont "hier is niets meer te halen" en wordt nooit verborgen. Een lege sectie
   is zelf een antwoord.
4. **Geen aftelklok, geen schaarste, geen sociale bewijsvoering.** Geen "nog 14 maanden",
   geen bezoekersaantallen.
5. **Precies twee soorten oproep tot actie:** verfijn je antwoord, en bewaar deze link.
   Er is geen derde en geen ervan leidt naar een verkopende partij.

## Twee dingen die stil fout gaan

**Bedragen zijn strings en blijven strings.** JSON kent alleen floats, dus een bedrag dat
door een JSON-parser gaat wordt afgerond door wie er het laatst aan zat. `parseFloat` op
een bedrag om het te tonen is precies de fout die dit project overal elders vermijdt. Er
staat een semgrep-regel op.

**Geen Nederlandse adviestekst in deze broncode.** `title`, `text`, `confidence_label` en
`basis_text` komen uit de API, die de taalgrens is. De frontend schrijft navigatie en
formuliertekst, en verder niets. Interfacetekst die de vorm van een figuur benoemt mag
wel; een zin die het huishouden vertelt wat het moet doen niet.

## Praktisch

- pnpm, niet npm. `corepack enable` en dan `pnpm install --frozen-lockfile`.
- `pnpm lint`, `pnpm typecheck`, `pnpm test`, `pnpm build`, `pnpm e2e`.
- Er is geen `pnpm start`: de site wordt statisch geexporteerd, dus er draait in productie
  geen Node-proces.
- De browser praat rechtstreeks met de adviesAPI. Niets rendert per verzoek, en dat is een
  gevolg van hoe de API het tempolimiet per IP-adres bijhoudt, niet een voorkeur.
