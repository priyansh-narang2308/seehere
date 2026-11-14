# Narration script — SeeHere HackGlobal 2026 demo

Voice: **Kokoro TTS, voice `af_heart`** (kokoro-onnx 1.0 model, `speed=0.95`, `lang=en-us`), one voice for the whole video.

The script below is the approved on-screen/subtitle text. The text sent to Kokoro used phonetic spellings so names are pronounced correctly; each substitution is listed at the end.


## Scene 01 — The hook

**[0:01.5 – 0:04.7]** A lecturer points at the screen and says: look at this chart.  
**[0:09.0 – 0:20.5]** For most students, that sentence is enough. For a blind or low-vision student, it's a gap. The chart, its labels, its numbers: all of it is on screen, and none of it is spoken aloud.  

## Scene 02 — Introducing SeeHere

**[0:24.4 – 0:25.5]** This is SeeHere.  
**[0:28.3 – 0:44.6]** SeeHere takes a recorded lecture and adds short audio descriptions of what's on screen that the lecturer never reads aloud. Every description is linked to its evidence, placed in a natural pause, and reviewed by the instructor before anything is published.  

## Scene 03 — How it works

**[0:46.2 – 1:04.7]** Here's how it works. The video is split into audio and frames. Speech is transcribed with word timings. Slide changes become keyframes. On-screen text is read with OCR, and a vision model on Vultr Serverless Inference finds the charts, tables and diagrams.  
**[1:05.2 – 1:26.3]** SeeHere compares what's shown with what's said, and keeps the visuals that are never spoken. When the lecturer says this, or here, it works out which region they mean. Descriptions are written only from that evidence, every claim is checked, and a constraint solver places them in the pauses. Then the voice is generated, and the timing is checked again.  

## Scene 04 — The real product (live site)

**[1:28.7 – 1:38.3]** Let's run it on the live site. I upload a 96-second lecture on photosynthesis, give it a title, and confirm I have permission to process it.  
**[1:45.7 – 1:59.6]** Processing starts straight away. Each step is a real job on the server: preparing the media, transcribing speech, detecting slide changes, reading on-screen text, and asking the vision model what each slide shows.  
**[2:00.4 – 2:02.7]** In under a minute, the lecture is ready.  
**[2:19.3 – 2:29.4]** The player shows the original lecture, with each description voiced in a gap in the speech. Next to it is the transcript, with the descriptions placed where they'll be heard.  
**[2:32.3 – 2:44.9]** Every description carries a verification state. Open its evidence, and you see where it came from: the keyframe, the region on screen, the text that was read, and what the lecturer was saying at that moment.  
**[2:47.4 – 2:55.0]** One description is held back. The text reader got the equation wrong, so SeeHere won't voice it until the instructor checks it.  
**[2:56.5 – 3:11.5]** The schedule shows where each description sits between stretches of speech. And everything exports: a WebVTT description track, a described video, the audio clips, an accessible transcript, and a coverage and verification report.  

## Scene 05 — Technical differentiation

**[3:15.6 – 3:19.4]** What makes SeeHere different is that it doesn't trust itself blindly.  
**[3:19.9 – 3:44.2]** Descriptions come only from evidence it can point to. Quoted text and numbers are checked against what was read on screen. A constraint solver, built on Google's OR-Tools, chooses which descriptions fit the pauses, so it never talks over the lecturer. After the voice is generated, the real clip lengths are measured and the plan is checked again. And when the evidence is uncertain, a person decides.  

## Scene 06 — Vultr deployment proof

**[3:45.7 – 3:56.5]** All of this runs on Vultr. The app, the API, the database and the processing worker run on a Vultr Cloud Compute instance, served over HTTPS.  
**[3:57.8 – 4:08.3]** The live status page shows the health of every part, the measured time of every stage, and every call to Vultr Serverless Inference, with its tokens and latency.  

## Scene 07 — Closing

**[4:11.0 – 4:13.9]** SeeHere. Making every part of a lecture accessible.  

*Between 2:05 and 2:19 the narrator is silent while the real described-lecture audio plays (the lecturer, then SeeHere's own description voice), taken from the project's `lecture-described.mp4` export.*

## Pronunciation spellings sent to Kokoro

| On screen | Sent to TTS |
|---|---|
| SeeHere | See Here |
| Vultr | Vulture |
| OCR | O C R |
| WebVTT | Web V T T |
| OR-Tools | O R Tools |
| API | A P I |
| HTTPS | H T T P S |
| 96-second | ninety-six second |

Total narration: 195.2 s of speech in a 256.4 s video.
