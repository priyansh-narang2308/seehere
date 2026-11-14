import Link from "next/link";
import { LandingHero } from "@/components/landing/landing-hero";
import "@/components/landing/landing.css";

const REPO = "https://github.com/priyansh-narang2308/seehere";

const steps = [
  {
    title: "Upload",
    body: "Drop in a recorded lecture (MP4, MOV, WebM or MKV, up to 30 minutes). Add the slide deck if you have it. Files are deleted after 24 hours.",
  },
  {
    title: "Analyse",
    body: "Fourteen queued jobs run on the server: speech-to-text with word timings, slide changes, on-screen text, and a vision model for charts, tables and diagrams.",
  },
  {
    title: "Review",
    body: "Each description shows its evidence and a verification state. Approve, edit, reject or regenerate it. Uncertain ones are held until a person decides.",
  },
  {
    title: "Publish",
    body: "Download a WebVTT description track, a described MP4, an accessible transcript, the voice clips and a coverage and verification report.",
  },
];

const features = [
  {
    title: "Seen versus said",
    body: "Every visual is compared with what the lecturer says around it. Visuals that are already read aloud are skipped; the unspoken ones come first.",
  },
  {
    title: "“This one here”, resolved",
    body: "Spoken pointers like “this line” or “over here” are linked to the region of the slide they point at, or flagged when it is unclear.",
  },
  {
    title: "Claims checked against the screen",
    body: "Quoted text and numbers are matched against what OCR read from the frame and the slide deck. Each description gets a verification state.",
  },
  {
    title: "Never talks over the lecturer",
    body: "An OR-Tools CP-SAT solver places descriptions in natural pauses and is compared with a greedy baseline on every run.",
  },
  {
    title: "Timed with the real voice",
    body: "Descriptions are voiced, their actual clip lengths are measured, and the plan is checked again. Anything that no longer fits is re-planned or dropped.",
  },
  {
    title: "A person has the last word",
    body: "Nothing is published until an instructor reviews it. Descriptions the evidence cannot support are held back, not guessed.",
  },
];

export default function Home() {
  return (
    <div className="lp">
      <LandingHero />

      {/* The gap, shown with a real moment from the demo lecture */}
      <section className="block" aria-labelledby="gap-title">
        <div className="wrap gap-grid">
          <div>
            <p className="kicker">
              <i aria-hidden="true" />
              The gap
            </p>
            <h2 id="gap-title" className="h2">
              “Look at this.” <span className="soft">Three words that leave a student behind.</span>
            </h2>
            <p className="lede">
              Lectures lean on slides. Charts, equations, labelled diagrams and tables carry the content, and the
              narration points at them instead of reading them. For blind and low-vision students, that part of
              the lecture is simply missing.
            </p>
            <p className="lede">
              SeeHere fills the gap with short descriptions placed in the pauses, so the lecture still sounds like
              the lecture.
            </p>
          </div>
          <figure className="tape">
            <ol>
              <li className="said">
                <time>0:29</time>
                <span>“Now this chart. Notice how the energy changes from stage to stage.”</span>
              </li>
              <li className="desc">
                <time>0:34</time>
                <span>
                  <b>Description · </b>Chart: Bar chart of energy captured per stage. “Light”. “Electron transport”.
                </span>
              </li>
              <li className="desc">
                <time>0:39</time>
                <span>
                  <b>Description · </b>On screen: “ATP yield falls by 68% from light capture to the Calvin cycle”.
                </span>
              </li>
              <li className="said">
                <time>0:47</time>
                <span>“And here is the overall equation, which you should memorize.”</span>
              </li>
            </ol>
            <figcaption>Real output from the demo lecture: lecturer in black, SeeHere in blue.</figcaption>
          </figure>
        </div>
      </section>

      {/* How it works */}
      <section id="how" className="block" aria-labelledby="how-title">
        <div className="wrap">
          <p className="kicker">
            <i aria-hidden="true" />
            How it works
          </p>
          <h2 id="how-title" className="h2">
            From recording to described lecture <span className="soft">in about a minute.</span>
          </h2>
          <ol className="steps">
            {steps.map((s, i) => (
              <li key={s.title}>
                <span className="num">0{i + 1}</span>
                <h3>{s.title}</h3>
                <p>{s.body}</p>
              </li>
            ))}
          </ol>
        </div>
      </section>

      {/* Evidence ledger */}
      <section className="block" aria-labelledby="ev-title">
        <div className="wrap ev-grid">
          <div>
            <p className="kicker">
              <i aria-hidden="true" />
              Visual evidence ledger
            </p>
            <h2 id="ev-title" className="h2">
              Every line <span className="soft">can be checked.</span>
            </h2>
            <p className="lede">
              A description is only as good as what it is based on. SeeHere keeps the trail for each one, so an
              instructor can see why it says what it says.
            </p>
            <ul className="checks">
              <li>
                <b>Keyframe</b>The exact frame and the region of the slide it describes.
              </li>
              <li>
                <b>On-screen text</b>What OCR read there, with its confidence.
              </li>
              <li>
                <b>Transcript</b>What the lecturer was saying while it was shown.
              </li>
              <li>
                <b>Verdict</b>Each quote and number: matched, corroborated, uncertain or needs review.
              </li>
            </ul>
          </div>
          <figure className="shot">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src="/landing/evidence-ledger.png"
              width={1110}
              height={765}
              alt="SeeHere's evidence panel for a bar chart description: the keyframe with the chart outlined, the quotes found on screen and the verification result for each statement."
            />
            <figcaption>Evidence panel for the bar chart in the demo lecture.</figcaption>
          </figure>
        </div>
      </section>

      {/* What makes it different */}
      <section className="block navy" aria-labelledby="feat-title">
        <div className="wrap">
          <p className="kicker">
            <i aria-hidden="true" />
            Methodology
          </p>
          <h2 id="feat-title" className="h2">
            Careful by design. <span className="soft">It does not trust itself blindly.</span>
          </h2>
          <ul className="feats">
            {features.map((f, i) => (
              <li key={f.title} className="feat">
                <span className="num">0{i + 1}</span>
                <h3>{f.title}</h3>
                <p>{f.body}</p>
              </li>
            ))}
          </ul>
        </div>
      </section>

      {/* Infrastructure */}
      <section className="block" aria-labelledby="stack-title">
        <div className="wrap">
          <p className="kicker">
            <i aria-hidden="true" />
            Infrastructure
          </p>
          <h2 id="stack-title" className="h2">
            Running live on Vultr. <span className="soft">Measured, not promised.</span>
          </h2>
          <p className="lede">
            The app, API, database and processing worker run on one Vultr Cloud Compute instance over HTTPS. The
            status page shows the health of every part, the time each stage takes and every hosted-model call.
          </p>
          <div className="stack">
            <div className="tile primary">
              <span className="label">Hosting</span>
              <strong>Vultr Cloud Compute</strong>
              <p>Docker Compose, Caddy with automatic HTTPS, Postgres as database and job queue.</p>
            </div>
            <div className="tile">
              <span className="label">Vision</span>
              <strong>Vultr Serverless Inference</strong>
              <p>A vision model reads charts, tables and diagrams on each keyframe. OCR-only if it is unavailable.</p>
            </div>
            <div className="tile">
              <span className="label">Hearing</span>
              <strong>faster-whisper</strong>
              <p>Speech-to-text with word timings, run on the server. Tesseract reads the on-screen text.</p>
            </div>
            <div className="tile">
              <span className="label">Timing &amp; voice</span>
              <strong>OR-Tools · Piper</strong>
              <p>A CP-SAT solver schedules the pauses; Piper voices each description on the server.</p>
            </div>
          </div>
          <div className="row-links">
            <Link className="link" href="/status">
              Live system status
            </Link>
            <Link className="link" href="/methodology">
              Full methodology
            </Link>
            <a className="link" href={REPO}>
              Source code on GitHub
            </a>
          </div>
        </div>
      </section>

      {/* Honest limits */}
      <section className="block" aria-labelledby="limits-title">
        <div className="wrap">
          <p className="kicker">
            <i aria-hidden="true" />
            Limits
          </p>
          <h2 id="limits-title" className="h2">
            A research prototype, <span className="soft">and honest about it.</span>
          </h2>
          <ul className="limits">
            <li>
              <b>Evidence, not fact-checking</b>
              Verification checks quoted text and numbers against what was read on screen. It does not prove a
              description is complete or correct.
            </li>
            <li>
              <b>Not a WCAG certification</b>
              The exports help make a lecture accessible. They are not a conformance certificate, and an
              instructor should review them before publishing.
            </li>
            <li>
              <b>OCR can misread</b>
              Small or stylised text can be read wrongly. When the evidence does not support a claim, SeeHere holds
              the description for review instead of voicing it.
            </li>
          </ul>
        </div>
      </section>

      {/* Closing call to action */}
      <div className="wrap cta-wrap">
        <section className="cta" aria-labelledby="cta-title">
          <div>
            <h2 id="cta-title" className="h2">
              Make your next lecture accessible.
            </h2>
            <p>Upload a recording and review its descriptions in about a minute. No account needed for the demo.</p>
          </div>
          <Link className="btn dark" href="/upload">
            Upload a lecture
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
              <path d="M3 8h10M9 4l4 4-4 4" />
            </svg>
          </Link>
        </section>
      </div>
    </div>
  );
}
