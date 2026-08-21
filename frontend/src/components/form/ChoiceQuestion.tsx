"use client";

interface Option {
  readonly value: string;
  readonly label: string;
}

interface Props {
  readonly id: string;
  readonly label: string;
  readonly options: readonly Option[];
  readonly value: string | null;
  readonly onChange: (value: string) => void;
}

/**
 * A closed set of answers, as native radios.
 *
 * Native radios because the keyboard behaviour a visitor already knows (tab in,
 * arrows between) is behaviour nobody has to reimplement, and every
 * reimplementation of it is a chance to get it wrong for the people who depend
 * on it most.
 */
export function ChoiceQuestion({ id, label, options, value, onChange }: Props) {
  const legendId = `${id}-label`;

  return (
    <fieldset className="flex flex-col gap-3">
      <legend id={legendId}>{label}</legend>
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
