# Findability: where Ampeer stood, what changed, what is the owner's

**Measured on:** 2026-10-01 and 2026-10-02. Search Console figures come from
the owner's export "Performance on Search" of 2026-10-01 (last three months,
web). Keyword and channel findings come from two research passes on those
dates; every claim below says whether it was observed at a source or inferred.

**Measured against:** the owner's Search Console export named above, the live
site on 2026-10-01, and the routes listed in `frontend/src/app/_shell/site.ts`
as they stood that day.

## 1. The baseline

Search Console, 14 to 28 September 2026: 19 impressions and 8 clicks. All
8 clicks came from the query "ampeer". The only non-brand queries were "btw
thuisbatterij" in three spellings (position 2 to 2.5), "salderen"
(position 1) and "thuisbatterij" (position 9), and none of them was clicked.
`/thuisbatterij/` had 10 impressions at position 4.9 and no clicks.
`/thuisbatterij-btw/` was not in the report yet.

The separate `http://ampeer.nl/` row is historical: on 2026-10-01 the edge
answers http with a 301 to https. `www.ampeer.nl` still does not resolve.

## 2. What the audience types (observed)

- **The term.** "thuisbatterij" outweighs "thuisaccu" by about ten to one
  (Google Trends, NL, twelve months, average 49.8 against 4.9). The site
  uses "thuisbatterij" and names "thuisaccu" once per battery page as the
  same thing.
- **The phrases.** Google's suggestions on 2026-10-01 included "thuisbatterij
  rendabel", "wat moet ik met mijn zonnepanelen in 2027", "ik heb zonnepanelen
  wat moet ik doen" and "salderingsregeling stopt wat nu". The last was
  rising that week.
- **Who ranks for them.** Milieu Centraal and the Consumentenbond give
  verdicts but no calculator. At least ten calculators call themselves
  independent. The Q4 checklists come from comparison sites and end on a
  contract switch.

## 3. What changed in the repository

- **`/zonnepanelen-2027/`**, a new page. It is a checklist for "what do I
  arrange before 1 January" whose answer is calm: nothing that cannot wait.
  The battery step is last and works as a brake. The regeling claims are
  sourced to Rijksoverheid (read 2026-10-01). It is linked from the home page
  and the header, and it is in the sitemap.
- **Titles and descriptions.**
  - Home: "Zonnepanelen na 2027: wat nu, en loont een thuisbatterij?"
  - `/thuisbatterij/`: "Thuisbatterij rendabel? Voor wie wel, en voor wie
    niet". The H1 keeps the question as the visitor asks it.
- **Links inside running text now look like links.** Tailwind's preflight had
  made them identical to the text around them.
- **The redesign.** The site moved from an instrument look to daylight. That
  covers the palette, the type, the header navigation, the home page and the
  step markers. Each file says why in its own comments.

## 4. The owner's, in order (owner actions are outside this repository)

1. **Search Console.** Submit `/sitemap.xml`, then use URL Inspection and
   "Request indexing" for every route in it, starting with
   `/zonnepanelen-2027/`. Observed: roughly 10 to 12 requests a day are
   allowed.
2. **Bing Webmaster Tools.** Use "Import from Search Console", which verifies
   the site and brings the sitemap along (observed). Copilot answers ground on
   Bing (observed). OpenAI runs its own OAI-SearchBot, which robots.txt
   already admits.
3. **Energiecafés and energy co-operatives.** Sessions about the end of
   saldering ran in Epe, Nunspeet and Son in September 2026, and Triada runs
   a series (observed). They are the best-matched offline channel found.
   Offer the checklist page as a reference, one co-operative at a time.
   Public bodies checked so far link only to Milieu Centraal (observed), so
   co-operatives and energy coaches are the realistic source of links
   (inferred).
4. **Timing.** Suppliers announce 1 January tariffs at least 30 days ahead
   (ACM, observed), so expect a search peak in late November and early
   December (inferred). Battery registrations peaked in January 2026
   (observed).
5. **Forums.** Answer on Tweakers and Reddit only where the page answers the
   question, and say you own the site. Neither forum's rules could be fetched.

## 5. Considered and not done, with the reason

- **llms.txt.** Ahrefs measured that 97 percent of llms.txt files received no
  request in May 2026 (observed).
- **IndexNow.** It would need a key file and a ping at deploy time. The ping
  is outbound HTTP to a new destination, and CLAUDE.md requires that to be an
  `OUTBOUND_MODULES` decision first. Note that `robots.ts` disallows `/*.txt$`,
  so the key file would need its own `Allow` line.
- **Meta ads.** Meta has refused political and social-issue ads in the EU
  since October 2025 (observed). An ad about the end of a law risks that
  classification (inferred).
- **Google Ad Grants.** It is only open to a stichting, vereniging, ANBI or
  church (observed).
- **An embeddable widget.** No comparable Dutch tool shows demand for one
  (inferred).
