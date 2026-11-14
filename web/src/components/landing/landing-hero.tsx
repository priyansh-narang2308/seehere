"use client";

// Hero adapted from Originkit hero-51: the two "o"s in "look" are live WebGL eyes that follow the pointer.
// They are decorative (aria-hidden); the h1 carries the full sentence as its accessible name.
import Link from "next/link";
import GrinIris from "./grin-iris";

const EYE = {
  background: "transparent",
  advanced: { maxTurn: 30 },
  scale: 138,
  irisColor: "#2F5BFF",
  scleraColor: "#FFFFFF",
  pupilSize: 0,
  follow: "page" as const,
  reach: 10,
  dilate: 5.2,
  wander: 10,
  float: 10,
};

export function LandingHero() {
  return (
    <section className="hero" aria-labelledby="hero-title">
      <div className="wrap">
        <p className="kicker">
          <i aria-hidden="true" />
          Audio descriptions for lecture videos
        </p>
        <h1 id="hero-title" aria-label="Hear what they look at.">
          <span className="soft" aria-hidden="true">
            Hear what
          </span>
          <br aria-hidden="true" />
          <span aria-hidden="true">they l</span>
          <span className="eye" aria-hidden="true">
            <GrinIris {...EYE} />
          </span>
          <span className="eye" aria-hidden="true">
            <GrinIris {...EYE} />
          </span>
          <span aria-hidden="true">k at.</span>
        </h1>
        <div className="below">
          <p className="sub">
            When a lecturer says “look at this chart”, a blind student hears nothing. SeeHere watches the
            recording, finds what is on screen but never said, and describes it in the pauses, with every line
            linked to its evidence.
          </p>
          <div className="buttons">
            <Link className="btn" href="/upload">
              Upload a lecture
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
                <path d="M3 8h10M9 4l4 4-4 4" />
              </svg>
            </Link>
            <a className="link" href="#how">
              See how it works
            </a>
          </div>
          <div className="readout">
            <h2>Live run · photosynthesis.mp4 · 1:36</h2>
            <dl>
              <div>
                <dt>Visuals found on screen</dt>
                <dd>14</dd>
              </div>
              <div>
                <dt>Already said aloud</dt>
                <dd>3</dd>
              </div>
              <div>
                <dt>Described in the pauses</dt>
                <dd>9</dd>
              </div>
              <div>
                <dt>Held for a person to check</dt>
                <dd className="hot">1 · the equation</dd>
              </div>
              <div>
                <dt>Upload to ready</dt>
                <dd>≈ 55 s</dd>
              </div>
            </dl>
            <p>Observed on the Vultr deployment, 14 Nov 2026.</p>
          </div>
        </div>
      </div>
    </section>
  );
}
