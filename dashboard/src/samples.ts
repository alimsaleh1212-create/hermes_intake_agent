// Copies of the demo Transcripts in /transcripts, so the dashboard builds on its own.
// samples.test.ts fails if they drift from the originals.
import injection from "./samples/injection_example.txt?raw";
import mikes from "./samples/mikes_roofing.txt?raw";
import pii from "./samples/pii_example.txt?raw";

export interface Sample {
  id: string;
  clientName: string;
  note: string;
  transcript: string;
}

export const SAMPLES: Sample[] = [
  {
    id: "mikes_roofing",
    clientName: "Mike's Roofing",
    note: "The reference call: WordPress, Google Ads, Jobber and a missed-calls problem.",
    transcript: mikes,
  },
  {
    id: "pii_example",
    clientName: "Clearflow Plumbing",
    note: "Emails, phone numbers and a street address that get redacted.",
    transcript: pii,
  },
  {
    id: "injection_example",
    clientName: "Arctic Air HVAC",
    note: "The Client tries to instruct the agent, which raises an Injection Flag.",
    transcript: injection,
  },
];
