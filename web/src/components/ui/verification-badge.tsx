import { CircleAlert, CircleCheck, CircleHelp, Link2 } from "lucide-react";
import { Badge } from "./badge";

/**
 * Evidence verification states used across the product. Each state has a distinct icon and
 * text label, so meaning never depends on colour alone.
 */
export const VERIFICATION_STATES = {
  verified_text_match: {
    label: "Verified text match",
    tone: "success",
    Icon: CircleCheck,
    help: "A quoted word or number matches text extracted from the source frame or slide.",
  },
  corroborated: {
    label: "Corroborated",
    tone: "accent",
    Icon: Link2,
    help: "Relevant slide or frame evidence supports the statement.",
  },
  uncertain: {
    label: "Uncertain",
    tone: "warning",
    Icon: CircleHelp,
    help: "Evidence is incomplete or ambiguous.",
  },
  needs_review: {
    label: "Needs human review",
    tone: "danger",
    Icon: CircleAlert,
    help: "The system cannot safely support this claim. An instructor must check it.",
  },
} as const;

export type VerificationState = keyof typeof VERIFICATION_STATES;

export function VerificationBadge({ state }: { state: VerificationState }) {
  const { label, tone, Icon, help } = VERIFICATION_STATES[state];
  return (
    <Badge tone={tone} title={help}>
      <Icon aria-hidden="true" />
      {label}
    </Badge>
  );
}
