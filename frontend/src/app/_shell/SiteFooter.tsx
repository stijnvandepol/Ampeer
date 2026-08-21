import Link from "next/link";

/**
 * What this is and what it is not.
 *
 * The sentence about selling nothing is the one claim on the page that is
 * about Ampeer rather than about the visitor's house, and it belongs at the
 * bottom rather than in a banner. It is interface text: it says what this site
 * is, not what the household should do.
 */
export function SiteFooter() {
  return (
    <footer className="mt-auto border-t border-hairline">
      <div className="mx-auto flex w-full max-w-3xl flex-col gap-2 px-6 py-8 text-sm text-ink-muted">
        <p>
          Ampeer verkoopt geen panelen, geen batterijen en geen energiecontract,
          en plaatst geen advertenties.
        </p>
        <p>
          <Link href="/methodologie/" className="underline underline-offset-4">
            Hoe Ampeer rekent
          </Link>
        </p>
      </div>
    </footer>
  );
}
