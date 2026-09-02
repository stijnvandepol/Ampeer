"use client";

import { useReducedMotion } from "@/design/motion";
import styles from "./hero-heading.module.css";

/**
 * The hero headline, arriving one character at a time out of a blur.
 *
 * WHERE TO TUNE IT. Everything is in `hero-heading.module.css` under
 * `.character`: `--reveal-duration` is how long one character takes,
 * `--reveal-step` is the gap between neighbours, `--reveal-blur` is how soft a
 * character starts and `--reveal-rise` how far it travels. The whole run is
 * `--reveal-step * characters + --reveal-duration`, so at the shipped values a
 * thirty character headline finishes in about 0,8 seconds. The step is the one
 * to be careful with: long headlines get slow fast.
 *
 * WHY IT SPLITS ON WORDS FIRST. Each word is its own `inline-block`, so a line
 * can only break between words. Splitting straight into characters lets the
 * browser break inside a word, and a hero heading that comes apart mid-word on
 * a phone is worse than no animation at all.
 *
 * WHAT A SCREEN READER GETS. The whole sentence, once, from the heading's
 * `aria-label`, with every span hidden from the accessibility tree. Without
 * that, a wall of one-character elements is announced one character at a time.
 *
 * WHY BLUR AND NOT A FADE. A fade to `opacity: 0` composites text against the
 * surface and fails contrast for as long as it runs. That is measured rather
 * than theoretical: the product page's first section reveal did exactly that
 * and axe found nineteen violations, reporting colours that appear in no
 * stylesheet in this repository because they were blends. A blur keeps the
 * colour it was given and moves only the sharpness.
 *
 * THERE IS NO `will-change` HERE, and that is a decision rather than an
 * omission. The property is for an element that is ABOUT to animate, so the
 * browser can promote it in advance; these animate on the frame they are
 * mounted, and a running animation is promoted anyway. What a permanent hint on
 * a few hundred spans buys is a compositor layer per character for the rest of
 * the session. The first version carried the hint plus a piece of state whose
 * only job was to take it away again, which is two mechanisms in service of an
 * optimisation neither of them was making.
 */

interface Props {
  readonly text: string;
  readonly id?: string | undefined;
  readonly className?: string | undefined;
}

export function HeroHeading({ text, id, className }: Props) {
  const reduced = useReducedMotion();

  if (reduced) {
    // Not the same animation faster: no animation, and the finished headline.
    // The reveal says nothing the still headline does not.
    return (
      <h1 id={id} className={className}>
        {text}
      </h1>
    );
  }

  const words = text.split(" ");
  let index = 0;

  return (
    <h1
      id={id}
      className={className}
      aria-label={text}
      data-role="hero-heading"
    >
      {words.map((word, at) => (
        <span key={`${word}-${at}`}>
          <span className={styles.word} aria-hidden="true">
            {[...word].map((character, position) => {
              const delay = index;
              index += 1;
              return (
                <span
                  key={position}
                  className={styles.character}
                  style={{ ["--at" as string]: String(delay) }}
                >
                  {character}
                </span>
              );
            })}
          </span>
          {/*
            An ordinary space, and BETWEEN the words rather than inside one.
            Inside, it belongs to a `white-space: nowrap` element and the break
            opportunity travels with it. The first version of this file also had
            a non-breaking space here by accident, which is the one character
            that can stop a hero heading wrapping at all.
          */}
          {at < words.length - 1 ? " " : null}
        </span>
      ))}
    </h1>
  );
}
