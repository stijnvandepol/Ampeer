import Link from "next/link";
import { ThemeToggle } from "./ThemeToggle";

/**
 * Navigation, and nothing that sells.
 *
 * Every label here is interface text written by the frontend, which is the one
 * category of Dutch this codebase is allowed to write. There is no third call
 * to action hiding in a navigation bar: these are the names of pages that
 * exist, and the methodology is one of them because the document this product
 * is judged on should be one click away from the answer it produced.
 */
export function SiteHeader() {
  return (
    <header className="border-b border-hairline">
      <div className="mx-auto flex w-full max-w-3xl flex-wrap items-center justify-between gap-4 px-6 py-4">
        <Link href="/" className="font-medium tracking-tight text-ink">
          Ampeer
        </Link>
        <nav aria-label="Hoofdnavigatie" className="flex items-center gap-5">
          <Link href="/berekenen/" className="text-sm text-ink-muted underline-offset-4 hover:underline">
            Berekenen
          </Link>
          <Link href="/methodologie/" className="text-sm text-ink-muted underline-offset-4 hover:underline">
            Methodologie
          </Link>
          <ThemeToggle />
        </nav>
      </div>
    </header>
  );
}
