import type { Metadata } from "next";
import Link from "next/link";
import { PriceGap } from "@/components/gap/PriceGap";
import { PageJsonLd } from "../_shell/JsonLd";
import styles from "../_shell/content.module.css";

const PATH = "/einde-saldering/";
const TITLE = "Einde salderingsregeling: wat het bij u doet";
const DESCRIPTION =
  "Op 1 januari 2027 stopt de salderingsregeling. Wat er verandert, waarom een gemiddeld bedrag u niets zegt, en hoe u het voor uw eigen huis doorrekent.";

export const metadata: Metadata = {
  title: TITLE,
  description: DESCRIPTION,
  // A string and not a URL instance. Next treats a URL here as a base and
  // resolves it against the current pathname, so `new URL(SITE_ORIGIN)` on
  // this route would canonicalise to the site root. The trailing slash is
  // added from `trailingSlash: true` once metadataBase makes this absolute.
  alternates: { canonical: PATH },
  // Deliberately absent: `openGraph`. Metadata merging is shallow, so setting
  // any part of it here would replace the root layout's siteName, locale and
  // type for this route. Next copies title and description into the inherited
  // object on its own.
};

/** The three routes, in the API's own words, so two files cannot disagree. */
const ROUTES: readonly (readonly [string, string])[] = [
  [
    "Gratis: uw eigen ritme verschuiven",
    "De wasmachine, de vaatwasser en de droger draaien op het moment dat uw panelen leveren. Dit kost niets en het is bij veel huishoudens de grootste post.",
  ],
  [
    "Gratis of bijna gratis: slimmer sturen met wat u al heeft",
    "Uw boiler, uw laadpaal of uw warmtepomp anders inregelen, of kijken of een ander contract bij uw patroon past. Apparaten die u al heeft, anders gebruikt.",
  ],
  [
    "Investeren: stroom opslaan in een thuisbatterij",
    "Alleen als het bij u uitkomt. Voor een deel van de huishoudens is het antwoord nee, en dat is bij ons een geldige en volwaardige uitkomst.",
  ],
];

/** What we do not know, condensed from chapter 19 of the methodology. */
const UNKNOWNS: readonly string[] = [
  "Wij weten niet hoeveel schaduw er op uw dak valt en vragen er niet naar.",
  "Wij weten niet welke apparaten u heeft of wanneer u ze aanzet.",
  "Wij weten niet hoe oud uw panelen zijn, dus rekenen wij ze als nieuw. Bij oudere panelen valt het bedrag bij u hoger uit dan bij ons.",
  "Niemand weet wat de terugleververgoeding in 2027 werkelijk wordt. Wij rekenen met een band en niet met een getal.",
];

/**
 * The page a search brings somebody to.
 *
 * WHAT IT IS FOR. The landing page is a front door for somebody who already
 * knows the name. This one answers a question somebody typed, in the order they
 * asked it: what changes first, why the number they came for does not exist
 * second, and only then what this product does about it. A page that introduces
 * itself before answering is a page people leave.
 *
 * WHAT IT MAY NOT DO. Neither of the two calls to action from the frontend spec
 * appears here, and that is not an oversight. "Verfijn uw antwoord" refers to
 * an answer that does not exist yet, and "bewaar deze link" to a link that does
 * not either; both live on the advice page, where they have a referent. What
 * this page carries is the way into the questions, twice, which is the same
 * navigation the landing page has. Two is the ceiling. A third, or a sticky
 * bar, or a repeat halfway down, is how a way in becomes a funnel.
 *
 * There is no euro amount anywhere on it. Every euro figure this product knows
 * comes out of a simulation of one household with a band around it, and the
 * per-kilowatt-hour prices in the figure are the tariff landscape rather than
 * anybody's answer. Multiply one of them by a volume and you have invented a
 * household.
 */
export default function EindeSalderingPage() {
  return (
    <div className={styles.page}>
      <PageJsonLd path={PATH} name={TITLE} description={DESCRIPTION} />

      <header className={styles.hero}>
        <p className={styles.eyebrow}>Wat er verandert</p>
        <h1 className={styles.title}>
          Het einde van de saldering, en hoe u uitrekent wat het bij u doet
        </h1>
        <p className={styles.lead}>
          Op 1 januari 2027 stopt de salderingsregeling. Wat dat u kost hangt
          niet af van hoeveel panelen u heeft, maar van wanneer u stroom
          gebruikt. Deze pagina legt uit wat er precies verandert, waarom een
          gemiddeld bedrag u niets zegt, en wat u eraan kunt doen.
        </p>
      </header>

      <section className={styles.section} aria-labelledby="verandert">
        <h2 id="verandert" className={styles.heading}>
          Wat er op 1 januari 2027 verandert
        </h2>
        <p className={styles.body}>
          De salderingsregeling laat u de stroom die u teruglevert wegstrepen
          tegen de stroom die u afneemt. Dat wegstrepen stopt. U blijft leveren
          en afnemen, maar de twee worden niet meer tegen elkaar weggestreept.
        </p>

        <h3 className={styles.subheading}>Wat salderen nu voor u doet</h3>
        <p className={styles.body}>
          Uw meter houdt twee standen bij: wat u afnam en wat u teruggaf. Bij
          salderen wordt het kleinste van de twee van het grootste afgetrokken
          en betaalt u alleen het verschil. Een kilowattuur die in juni het net
          op ging, streept er zo een weg die in december binnenkwam. Het moment
          waarop iets gebeurde doet niet mee.
        </p>

        <h3 className={styles.subheading}>Wat ervoor in de plaats komt</h3>
        <p className={styles.body}>
          U krijgt een terugleververgoeding voor wat u teruglevert. Daar staat
          tegenover dat u de volle prijs betaalt voor wat u afneemt. U leest
          vaak dat die vergoeding 3 tot 8 cent wordt. Dat is de brutovergoeding:
          daar gaan de terugleverkosten nog vanaf, en die rekenen leveranciers
          per teruggeleverde kilowattuur.
        </p>
        <PriceGap />

        <h3 className={styles.subheading}>
          Waarom het bedrag per huishouden zo verschilt
        </h3>
        <p className={styles.body}>
          Omdat het verschil tussen die twee banden alleen telt voor de
          kilowatturen die u daadwerkelijk teruglevert. Twee huizen met precies
          dezelfde panelen en precies hetzelfde jaarverbruik krijgen een ander
          antwoord, alleen doordat de een overdag thuis is en de ander niet.
        </p>
      </section>

      <section className={styles.section} aria-labelledby="gemiddeld">
        <h2 id="gemiddeld" className={styles.heading}>
          Waarom een gemiddeld bedrag u niets zegt
        </h2>
        <p className={styles.body}>
          Bijna elke rekentool geeft u een enkel bedrag. Wij doen dat niet, en
          niet uit voorzichtigheid. Het antwoord hangt af van dingen die nog
          niet vaststaan, zoals de terugleververgoeding in 2027 en de
          stroomprijs, en van dingen die per huis verschillen, zoals wanneer u
          thuis bent.
        </p>
        <p className={styles.body}>
          Wij rekenen daarom niet één keer maar 243 keer door, met die
          onzekerheden op verschillende standen, en tonen de bandbreedte die
          daaruit komt. Het middelpunt is een markering in die band en niet het
          antwoord. Een enkel getal uit die 243 groot afdrukken zou de band
          weggooien, en de band is wat het antwoord eerlijk maakt.
        </p>
      </section>

      <section className={styles.section} aria-labelledby="uitrekent">
        <h2 id="uitrekent" className={styles.heading}>
          Wat Ampeer voor u uitrekent
        </h2>

        <h3 className={styles.subheading}>
          Vier vragen, geen account, geen koppeling
        </h3>
        <p className={styles.body}>
          De eerste vier cijfers van uw postcode, hoeveel wattpiek er ligt, hoe
          het dak ligt en uw jaarverbruik. Meer niet. Wij bouwen daar een
          kwartierprofiel van een heel jaar mee op, 35.040 kwartieren, en
          rekenen dat door op de tarieven van nu en die van 2027.
        </p>

        <h3 className={styles.subheading}>
          Een bedrag met een bandbreedte, niet één getal
        </h3>
        <p className={styles.body}>
          U krijgt een bedrag per jaar met de marge eromheen, en de band is het
          object op het scherm. Daaronder ziet u uw eigen jaar in kwartieren:
          per kwartier of u vooral uw eigen opwek gebruikte, stroom van het net
          haalde, of teruglevede.
        </p>

        <h3 className={styles.subheading}>Hoe zeker het antwoord is</h3>
        <p className={styles.body}>
          Boven uw bedrag staat of het indicatief, goed of precies is. Dat staat
          er direct naast en niet in een voetnoot, want hoe zeker een antwoord
          is hoort bij het antwoord. Vier vragen geeft indicatief. Negen vragen
          geeft goed.
        </p>

        <p className={styles.act}>
          <Link href="/berekenen/" className="button-accent">
            Beantwoord vier vragen
          </Link>
        </p>
      </section>

      <section className={styles.section} aria-labelledby="routes">
        <h2 id="routes" className={styles.heading}>
          De drie routes, en de gratis routes eerst
        </h2>
        <p className={styles.body}>
          Wij tonen altijd alle drie de routes, in deze volgorde, ook als er bij
          u aan een ervan niets te halen valt. Een lege route is zelf een
          antwoord.
        </p>
        <ol className={styles.routes}>
          {ROUTES.map(([name, text]) => (
            <li key={name} className={styles.route}>
              <h3 className={styles.routeName}>{name}</h3>
              <p className={styles.routeText}>{text}</p>
            </li>
          ))}
        </ol>
        {/*
          Two of the three routes have a page of their own now. Linked from
          here rather than from the site header, which carries four entries on
          purpose: this is the section that already names them, so this is
          where a reader looking for more is standing.
        */}
        <p className={styles.body}>
          De eerste twee routes hebben een eigen pagina:{" "}
          <Link href="/zelf-verbruiken/">
            meer van uw eigen stroom gebruiken
          </Link>{" "}
          en{" "}
          <Link href="/thuisbatterij/">is een thuisbatterij iets voor mij</Link>
          .
        </p>
      </section>

      <section className={styles.section} aria-labelledby="getallen">
        <h2 id="getallen" className={styles.heading}>
          Waar onze getallen vandaan komen
        </h2>
        <p className={styles.body}>
          De vorm van uw verbruik komt uit de standaardprofielen die
          netbeheerders publiceren. De opwek van uw dak komt uit PVGIS, de
          rekentool van de Europese Commissie, op basis van echte
          instralingsmetingen voor uw postcodegebied. De tarieven komen uit
          gepubliceerde cijfers, en welke dat zijn staat er per bedrag bij.
        </p>
        <p className={styles.body}>
          Dat staat allemaal uitgeschreven, met de aannames en de bandbreedtes
          erbij, in <Link href="/methodologie/">onze methodologie</Link>. Dat
          document is er om nagerekend te worden.
        </p>
      </section>

      <section className={styles.section} aria-labelledby="onbekend">
        <h2 id="onbekend" className={styles.heading}>
          Wat wij niet weten
        </h2>
        <ul className={styles.unknowns}>
          {UNKNOWNS.map((text) => (
            <li key={text} className={styles.unknown}>
              {text}
            </li>
          ))}
        </ul>
      </section>

      <section className={styles.section} aria-labelledby="nietdoen">
        <h2 id="nietdoen" className={styles.heading}>
          Wat wij niet doen
        </h2>
        <p className={styles.body}>
          Wij verkopen geen zonnepanelen, geen thuisbatterijen en geen
          energiecontract. Wij plaatsen geen advertenties. Er is geen knop op
          deze site die naar een verkopende partij leidt.
        </p>
        <p className={styles.body}>
          Wat er niet in zit, is het belangrijkste: niemand betaalt ons voor de
          uitkomst die u krijgt. Er is geen installateur, geen leverancier en
          geen fabrikant die er beter van wordt als hier &quot;wel een
          batterij&quot; uitkomt. Dat is ook waarom &quot;nu geen batterij&quot;
          bij ons een geldige uitkomst is. Een adviseur die aan batterijen
          verdient kan die zin niet schrijven.
        </p>
        <p className={styles.body}>
          Wij zeggen niet dat Ampeer nooit geld gaat verdienen. Wat wij wel
          vastleggen is dat uw antwoord er niet van afhangt: code die het advies
          laat meebewegen met een commerciele afspraak geldt in dit project als
          een fout, en dat staat zo in de projectafspraken. Verandert er iets
          aan hoe Ampeer betaald wordt, dan staat het op deze pagina en op
          &quot;over ons&quot; voordat het gebeurt.
        </p>
        <p className={styles.body}>
          Op dit webadres zat eerder een andere dienst, die wel Nederlandse
          energiecontracten bemiddelde. Die heeft niets met dit product te
          maken. Ampeer bemiddelt niets en heeft geen eigen contract.
        </p>
      </section>

      <section
        className={styles.section}
        aria-labelledby="tweeduizendnegenentwintig"
      >
        <h2 id="tweeduizendnegenentwintig" className={styles.heading}>
          Wat er in 2029 nog bij komt
        </h2>
        <p className={styles.body}>
          Netbeheerders hebben een tijdsafhankelijk nettarief voorgesteld: het
          transporttarief hangt dan af van het moment van de dag en het seizoen,
          met een klein aantal prijsniveaus over een klein aantal tijdsblokken.
          Dat maakt het moment waarop u stroom gebruikt nog belangrijker dan het
          vanaf 2027 al wordt.
        </p>
        <p className={styles.body}>
          Twee dingen erbij, want zonder die twee is dit een belofte. Het is een
          voorstel dat bij de ACM ligt en nog geen regel. En ons model rekent
          het nog niet door: wat u vandaag bij ons krijgt gaat over 2027 en niet
          over 2029.
        </p>
      </section>

      <section className={styles.section} aria-labelledby="vragen">
        <h2 id="vragen" className={styles.heading}>
          Veelgestelde vragen
        </h2>
        <dl className={styles.faq}>
          <dt className={styles.question}>
            Moet ik mijn zonnepanelen nu weghalen?
          </dt>
          <dd className={styles.answer}>
            Nee. Panelen leveren stroom die u anders had moeten kopen, en dat
            blijft na 2027 zo. Wat verandert is wat de stroom opbrengt die u
            niet zelf gebruikt.
          </dd>
          <dt className={styles.question}>
            Zijn zonnepanelen na 2027 nog rendabel?
          </dt>
          <dd className={styles.answer}>
            Voor de meeste huishoudens wel, maar minder dan nu, en hoeveel
            minder verschilt sterk. Dat is precies het bedrag dat wij voor u
            uitrekenen.
          </dd>
          <dt className={styles.question}>
            Wat is het verschil tussen terugleververgoeding en terugleverkosten?
          </dt>
          <dd className={styles.answer}>
            De vergoeding is wat u krijgt per teruggeleverde kilowattuur. De
            terugleverkosten zijn wat uw leverancier daarvoor in rekening
            brengt. De veelgenoemde 3 tot 8 cent is de vergoeding met de kosten
            er nog voor.
          </dd>
          <dt className={styles.question}>Heb ik een slimme meter nodig?</dt>
          <dd className={styles.answer}>
            Niet om bij ons een antwoord te krijgen. Wij bouwen uw jaar op uit
            standaardprofielen en uw eigen opgave. Echte meetgegevens maken het
            antwoord scherper, maar zijn geen voorwaarde.
          </dd>
          <dt className={styles.question}>
            Moet ik overstappen op een dynamisch contract?
          </dt>
          <dd className={styles.answer}>
            Soms, en soms niet. Op een dynamisch contract zitten geen aparte
            terugleverkosten, maar beweegt uw prijs per uur mee. Of het bij u
            gunstig uitpakt hangt af van uw patroon, en dat rekenen wij door.
          </dd>
          <dt className={styles.question}>Slaan jullie mijn gegevens op?</dt>
          <dd className={styles.answer}>
            Wij bewaren uw antwoorden en uw uitkomst achter de link die u
            krijgt, zodat u er later bij kunt. Er is geen account, wij vragen
            geen e-mailadres, en van uw postcode slaan wij alleen de vier
            cijfers op.
          </dd>
        </dl>
      </section>

      <div className={styles.close}>
        <p className={styles.body}>
          Vier vragen, en u weet wat het bij u doet in plaats van gemiddeld.
        </p>
        <Link href="/berekenen/" className="button-accent">
          Beantwoord vier vragen
        </Link>
        <p className={styles.note}>
          Zonder inloggen, en zonder dat u iets hoeft te koppelen.
        </p>
      </div>
    </div>
  );
}
