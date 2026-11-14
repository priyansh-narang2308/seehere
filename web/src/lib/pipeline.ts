/**
 * The processing pipeline, in order. This is the single source of truth for what the UI says is
 * built. Flip a stage to "built" only in the commit that implements and tests it.
 */
export type StageStatus = "built" | "not_built";

export type PipelineStage = {
  id: string;
  name: string;
  summary: string;
  status: StageStatus;
  optional?: boolean;
};

export const pipelineStages: readonly PipelineStage[] = [
  {
    id: "upload",
    name: "Upload and rights check",
    summary: "You confirm you own the video or may process it. The file is size-capped and identified by its content.",
    status: "built",
  },
  {
    id: "media",
    name: "Media inspection",
    summary: "The video is checked again and prepared: a 16 kHz speech track and one frame per second.",
    status: "built",
  },
  {
    id: "speech",
    name: "Speech-to-text with word timings",
    summary: "Every spoken word gets a start and end time, so pauses can be measured. Runs locally with Whisper.",
    status: "built",
  },
  {
    id: "scenes",
    name: "Scene and slide changes",
    summary: "Keyframes are taken where the picture changes, such as a new slide. A slide shown again is recognized, not counted twice.",
    status: "built",
  },
  {
    id: "ocr",
    name: "On-screen text (OCR)",
    summary: "Text and numbers are read from each keyframe, with their position and confidence.",
    status: "built",
  },
  {
    id: "slides",
    name: "Slide deck matching",
    summary: "If you add the PDF or PPTX, each slide's text is matched to the moment it appears.",
    status: "built",
    optional: true,
  },
  {
    id: "vision",
    name: "Visual analysis",
    summary:
      "What is on screen, with its region and when it is shown: text blocks from OCR, plus charts and diagrams from an optional vision model (not yet live-tested).",
    status: "built",
  },
  {
    id: "seen-said",
    name: "Seen versus said",
    summary: "Each visual is compared with what the lecturer says around it. Unspoken visuals are prioritized.",
    status: "built",
  },
  {
    id: "references",
    name: "Reference resolution",
    summary: "Phrases like “this blue line here” are linked to a screen region, or flagged when unclear.",
    status: "built",
  },
  {
    id: "generate",
    name: "Description writing",
    summary: "Short, medium and long descriptions are written only from the recorded evidence.",
    status: "built",
  },
  {
    id: "verify",
    name: "Claim verification",
    summary: "Quoted text and numbers are checked against OCR and slides. Each cue gets a verification state.",
    status: "built",
  },
  {
    id: "schedule",
    name: "Speech-safe scheduling",
    summary: "Descriptions are placed inside natural pauses so they never talk over the lecturer.",
    status: "built",
  },
  {
    id: "voice",
    name: "Speech synthesis",
    summary: "Each scheduled description is spoken by a local voice and its real length is measured.",
    status: "built",
  },
  {
    id: "timing",
    name: "Timing check",
    summary: "Descriptions whose real audio does not fit their pause are re-scheduled or dropped.",
    status: "built",
  },
  {
    id: "review",
    name: "Instructor review",
    summary: "An instructor approves, edits or rejects every description before anything is published.",
    status: "not_built",
  },
  {
    id: "export",
    name: "Export",
    summary: "WebVTT descriptions, audio, a described video and an accessible transcript.",
    status: "built",
  },
];

export function countBuilt(stages: readonly PipelineStage[] = pipelineStages): number {
  return stages.filter((s) => s.status === "built").length;
}
