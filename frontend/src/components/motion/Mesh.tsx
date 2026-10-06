"use client";

import { useReducedMotion } from "@/design/motion";
import styles from "./mesh.module.css";

/**
 * The slow gradient field behind the hero.
 *
 * WHERE TO TUNE IT. `mesh.module.css`, on `.mesh`: `--mesh-period` is how long
 * one full drift takes (90s shipped, and slower is almost always better here),
 * `--mesh-travel` is how far each blob wanders, and `--mesh-strength` is the
 * opacity of the whole field. Above about 0.5 it starts competing with the
 * headline sitting on top of it.
 *
 * WHY IT IS THREE DIVS AND NOT A CANVAS. A canvas mesh is a per-frame paint on
 * the main thread for something that never changes shape. Three radial
 * gradients moved by `transform` are composited on the GPU, cost nothing per
 * frame, and hold 60fps on a laptop that is also running a build.
 *
 * WHY THE COLOURS ARE THE PRODUCT'S OWN. The three are the confidence tones,
 * which is the palette this product uses for how sure it is of something. That
 * is not decoration reaching for a palette: the hero says the answer depends on
 * your house, and these are the colours the answer is drawn in further down.
 *
 * It is behind everything and hidden from the accessibility tree. Under
 * prefers-reduced-motion the blobs stand still: the field is the texture, the
 * drift is the polish, and only the drift goes.
 */
export function Mesh() {
  const reduced = useReducedMotion();
  return (
    <div
      className={styles.mesh}
      data-drifting={String(!reduced)}
      data-role="hero-mesh"
      aria-hidden="true"
    >
      <span className={`${styles.blob} ${styles.one}`} />
      <span className={`${styles.blob} ${styles.two}`} />
      <span className={`${styles.blob} ${styles.three}`} />
    </div>
  );
}
