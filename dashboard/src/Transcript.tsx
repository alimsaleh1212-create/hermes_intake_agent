import { Fragment } from "react";

const PLACEHOLDER = /(\[(?:EMAIL|PHONE|ADDRESS)_\d+\])/;
const SPEAKER = /^([A-Z][\w'. -]{0,30}):\s+(.*)$/;

export function countPlaceholders(text: string): number {
  return new Set(text.match(new RegExp(PLACEHOLDER, "g")) ?? []).size;
}

function Highlighted({ text }: { text: string }) {
  return (
    <>
      {text.split(PLACEHOLDER).map((part, n) =>
        PLACEHOLDER.test(part) ? (
          <mark key={n} className="pii">
            {part}
          </mark>
        ) : (
          <Fragment key={n}>{part}</Fragment>
        ),
      )}
    </>
  );
}

/** The Redacted Transcript with speaker turns set apart and placeholders marked. */
export default function Transcript({ text }: { text: string }) {
  const turns = text.split(/\n+/).filter((line) => line.trim() !== "");
  return (
    <div className="transcript">
      {turns.map((line, n) => {
        const match = line.match(SPEAKER);
        if (!match) {
          return (
            <p key={n} className="turn">
              <Highlighted text={line} />
            </p>
          );
        }
        const [, speaker, said] = match;
        return (
          <p key={n} className={`turn${speaker === "Agency" ? " turn-agency" : ""}`}>
            <span className="speaker">{speaker}</span>
            <Highlighted text={said} />
          </p>
        );
      })}
    </div>
  );
}
