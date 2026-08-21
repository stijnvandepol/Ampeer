import Link from "next/link";

/**
 * The landing page: what changes, and the way in.
 *
 * Everything here is a statement of fact about the rules or about this site.
 * There is no euro amount on this page and there will not be one, because
 * every euro amount this product knows comes out of a simulation of one
 * specific household, with a band around it. A number printed here would be a
 * number nobody computed for the person reading it.
 *
 * There is no date arithmetic either. A page that counts down to 1 January
 * 2027 is manufacturing urgency out of a calendar, and rule four exists
 * precisely because that is the easiest thing in the world to add.
 */
export default function Home() {
  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col gap-10 px-6 py-16">
      <section className="flex flex-col gap-5">
        <p className="text-sm uppercase tracking-wide text-ink-muted">Salderen stopt in 2027</p>
        <h1 className="text-3xl font-bold">
          Wat kost het einde van de saldering uw huishouden?
        </h1>
        <p className="text-lg text-ink-muted">
          Vanaf 1 januari 2027 vervalt de salderingsregeling. Een kWh die u zelf gebruikt is
          vanaf dat moment meer waard dan diezelfde kWh die u teruglevert. Hoeveel dat voor u
          scheelt hangt af van uw dak, uw verbruik en uw contract.
        </p>
      </section>

      <section className="flex flex-col gap-4">
        <h2 className="text-xl font-medium">Wat u terugkrijgt</h2>
        <ul className="flex list-disc flex-col gap-2 pl-5 text-ink-muted">
          <li>Een bedrag per jaar met de marge eromheen, niet een enkel getal.</li>
          <li>Hoe zeker die uitkomst is, meteen naast de uitkomst zelf.</li>
          <li>
            Drie routes, met de gratis routes eerst: uw ritme verschuiven, slimmer sturen met wat
            u al heeft, en opslag.
          </li>
          <li>Een link waarmee u er later bij kunt, zonder account.</li>
        </ul>
      </section>

      <section className="flex flex-col gap-4">
        <h2 className="text-xl font-medium">Wat wij niet doen</h2>
        <p className="text-ink-muted">
          Wij verkopen geen panelen, geen batterijen en geen energiecontract, en wij sturen u
          niet door naar een partij die dat wel doet. &quot;Geen batterij&quot; is hier een geldige
          uitkomst.
        </p>
      </section>

      <p>
        <Link
          href="/berekenen/"
          className="inline-flex rounded-md bg-accent px-5 py-3 font-medium text-on-accent"
        >
          Beantwoord vier vragen
        </Link>
      </p>
    </div>
  );
}
