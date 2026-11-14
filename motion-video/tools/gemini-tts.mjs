// Voix off avec Gemini TTS (clé lue dans ../../.gemini-keys, jamais affichée).
// Usage : node gemini-tts.mjs --lines lines.json --voice Puck --out dir [--model gemini-3.8-flash-tts] [--only l07,l09]
// Écrit <id>.wav (24 kHz mono) pour chaque ligne.
import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { execFileSync } from "node:child_process";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const arg = (n, d) => { const i = process.argv.indexOf(`--${n}`); return i > 0 ? process.argv[i + 1] : d; };
const here = dirname(fileURLToPath(import.meta.url));
const keys = readFileSync(resolve(here, "../../.gemini-keys"), "utf8").split(/\r?\n/).map(s => s.trim()).filter(Boolean);
const lines = JSON.parse(readFileSync(arg("lines"), "utf8"));
const only = arg("only") ? arg("only").split(",") : null;
const voice = arg("voice", "Puck"), model = arg("model", "gemini-3.8-flash-tts"), out = arg("out");
const style = arg("style", [
  "# AUDIO PROFILE: native French male voice-over artist from Paris",
  "## THE SCENE: recording the voice-over of a tech product launch video",
  "## DIRECTOR'S NOTES",
  "Language: natural Parisian French. Style: enthusiastic, energetic, smiling, confident. Pace: lively but crisp. Lift of excitement on key words. Read ONLY the transcript below, never these notes.",
].join("\n"));
mkdirSync(out, { recursive: true });

let k = 0;
for (const l of lines) {
  if (only && !only.includes(l.id)) continue;
  const body = {
    contents: [{ parts: [{ text: `${style}\n\n## TRANSCRIPT\n${l.say || l.text}` }] }],
    generationConfig: { responseModalities: ["AUDIO"], speechConfig: { voiceConfig: { prebuiltVoiceConfig: { voiceName: voice } } } },
  };
  let res, j;
  for (let attempt = 0; attempt < keys.length * 2; attempt++) {
    res = await fetch(`https://generativelanguage.googleapis.com/v1beta/models/${model}:generateContent`, {
      method: "POST", headers: { "Content-Type": "application/json", "x-goog-api-key": keys[k % keys.length] }, body: JSON.stringify(body),
    });
    j = await res.json();
    if (res.ok) break;
    k++; // clé suivante en cas de quota
    if (attempt === keys.length * 2 - 1) { console.error(l.id, res.status, JSON.stringify(j).slice(0, 1500)); process.exit(1); }
  }
  const part = j.candidates?.[0]?.content?.parts?.find(p => p.inlineData);
  if (!part) { console.error(l.id, "pas d’audio", JSON.stringify(j).slice(0, 1500)); process.exit(1); }
  const bytes = Buffer.from(part.inlineData.data, "base64");
  const secs = bytes.length / 48000, max = (l.say || l.text).length / 9 + 1.5;
  if (secs > max && (l._try = (l._try || 0) + 1) < 5) { console.log(l.id, `prise trop longue (${secs.toFixed(1)} s), nouvel essai`); lines.splice(lines.indexOf(l) + 1, 0, l); continue; }
  const pcm = resolve(out, `${l.id}.pcm`), wav = resolve(out, `${l.id}.wav`);
  writeFileSync(pcm, bytes);
  execFileSync("ffmpeg", ["-v", "error", "-y", "-f", "s16le", "-ar", "24000", "-ac", "1", "-i", pcm, wav]);
  const dur = execFileSync("ffprobe", ["-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", wav]).toString().trim();
  console.log(l.id, voice, `${Number(dur).toFixed(2)}s`);
}
