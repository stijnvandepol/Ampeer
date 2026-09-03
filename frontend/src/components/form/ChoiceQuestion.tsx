"use client";

interface Option {
  readonly value: string;
  readonly label: string;
}

interface Base {
  readonly id: string;
  readonly options: readonly Option[];
  readonly value: string | null;
  readonly onChange: (value: string) => void;
}

/**
 * How this group gets its name, and it is one way or the other.
 *
 * `labelledBy` is the id of something already on the screen that asks the
 * question, which on this route is QuestionShell's heading. `label` is a
 * legend this component writes itself, for a group that is not the question
 * the screen is about: the heat pump screen asks how much the pump uses
 * underneath the yes-or-no, and that second control needs a name of its own.
 *
 * A union rather than two optional props, because "neither" is a radio group
 * with no accessible name and "both" is the defect this was written to remove:
 * one question, asked twice, in two wordings that were not the same question.
 */
type Naming =
  | { readonly label: string; readonly labelledBy?: undefined }
  | { readonly label?: undefined; readonly labelledBy: string };

type Props = Base & Naming;

/**
 * A closed set of answers, as native radios.
 *
 * Native radios because the keyboard behaviour a visitor already knows (tab in,
 * arrows between) is behaviour nobody has to reimplement, and every
 * reimplementation of it is a chance to get it wrong for the people who depend
 * on it most.
 */
export function ChoiceQuestion({
  id,
  label,
  labelledBy,
  options,
  value,
  onChange,
}: Props) {
  const legendId = `${id}-label`;

  return (
    // A fieldset with no legend is a fieldset whose name comes from
    // aria-labelledby, which HTML-AAM lets take precedence over a legend
    // anyway. Rendering both would put the same words on the screen twice.
    <fieldset className="flex flex-col gap-3" aria-labelledby={labelledBy}>
      {label !== undefined && <legend id={legendId}>{label}</legend>}
      {options.map((option) => {
        const inputId = `${id}-${option.value}`;
        return (
          <div key={option.value} className="flex items-center gap-2">
            <input
              type="radio"
              id={inputId}
              name={id}
              value={option.value}
              checked={value === option.value}
              onChange={() => onChange(option.value)}
            />
            <label htmlFor={inputId}>{option.label}</label>
          </div>
        );
      })}
    </fieldset>
  );
}
