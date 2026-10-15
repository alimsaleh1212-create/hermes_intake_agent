// Copies of the demo Transcripts in /transcripts, so the dashboard builds on its own.
// samples.test.ts fails if they drift from the originals.
import injection from "./samples/injection_example.txt?raw";
import mikes from "./samples/mikes_roofing.txt?raw";
import pii from "./samples/pii_example.txt?raw";
import quickInjection from "./samples/quick_injection.txt?raw";
import quickPii from "./samples/quick_pii.txt?raw";
import quickSystems from "./samples/quick_systems.txt?raw";

export type SampleGroup = "Quick examples" | "Full calls";

export interface Sample {
  id: string;
  group: SampleGroup;
  clientName: string;
  note: string;
  transcript: string;
}

export const SAMPLE_GROUPS: SampleGroup[] = ["Quick examples", "Full calls"];

export const SAMPLES: Sample[] = [
  {
    id: "quick_systems",
    group: "Quick examples",
    clientName: "Bright Coat Painting",
    note: "Five lines: three systems, and a text-back the Client rules out every workaround for.",
    transcript: quickSystems,
  },
  {
    id: "quick_pii",
    group: "Quick examples",
    clientName: "Oak & Pine Carpentry",
    note: "One email, one phone number and one address, all redacted.",
    transcript: quickPii,
  },
  {
    id: "quick_injection",
    group: "Quick examples",
    clientName: "Summit Landscaping",
    note: "One line asks the agent to approve itself, which raises an Injection Flag.",
    transcript: quickInjection,
  },
  {
    id: "mikes_roofing",
    group: "Full calls",
    clientName: "Mike's Roofing",
    note: "The reference call: WordPress, Google Ads, Jobber and a missed-calls problem.",
    transcript: mikes,
  },
  {
    id: "pii_example",
    group: "Full calls",
    clientName: "Clearflow Plumbing",
    note: "Emails, phone numbers and a street address that get redacted.",
    transcript: pii,
  },
  {
    id: "injection_example",
    group: "Full calls",
    clientName: "Arctic Air HVAC",
    note: "The Client tries to instruct the agent, which raises an Injection Flag.",
    transcript: injection,
  },
];
