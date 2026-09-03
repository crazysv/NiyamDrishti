import {
  InspectionTranslationResponse,
  SupportedLanguagesResponse,
  TranslationResponse,
  TTSResponse,
} from "../types/bhashini";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

function getAuthHeaders(token?: string): Record<string, string> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  const authToken =
    token ||
    (typeof window !== "undefined" ? localStorage.getItem("access_token") : null);
  if (authToken) {
    headers["Authorization"] = `Bearer ${authToken}`;
  }
  return headers;
}

/**
 * Fetches the 12 supported Indian regional languages.
 */
export async function getSupportedLanguages(): Promise<SupportedLanguagesResponse> {
  const res = await fetch(`${API_BASE}/bhashini/languages`, {
    headers: { "Content-Type": "application/json" },
  });
  if (!res.ok) {
    throw new Error(`Failed to fetch supported languages: ${res.status}`);
  }
  return res.json();
}

/**
 * Translates text between English and an Indic language.
 */
export async function translateText(
  text: string,
  targetLanguage: string = "hi",
  sourceLanguage: string = "en",
  token?: string
): Promise<TranslationResponse> {
  const res = await fetch(`${API_BASE}/bhashini/translate`, {
    method: "POST",
    headers: getAuthHeaders(token),
    body: JSON.stringify({
      text,
      target_language: targetLanguage,
      source_language: sourceLanguage,
    }),
  });
  if (!res.ok) {
    throw new Error(`Translation failed: ${res.status}`);
  }
  return res.json();
}

/**
 * Synthesizes text into spoken audio (base64) via Bhashini TTS.
 */
export async function synthesizeSpeech(
  text: string,
  language: string = "hi",
  gender: string = "female",
  token?: string
): Promise<TTSResponse> {
  const res = await fetch(`${API_BASE}/bhashini/tts`, {
    method: "POST",
    headers: getAuthHeaders(token),
    body: JSON.stringify({
      text,
      language,
      gender,
    }),
  });
  if (!res.ok) {
    throw new Error(`TTS synthesis failed: ${res.status}`);
  }
  return res.json();
}

/**
 * Translates an entire inspection report into an Indic language and produces a spoken narration.
 */
export async function translateInspectionReport(
  inspectionId: string,
  targetLanguage: string = "hi",
  token?: string
): Promise<InspectionTranslationResponse> {
  const res = await fetch(
    `${API_BASE}/bhashini/inspections/${inspectionId}/translate?target_language=${targetLanguage}`,
    {
      method: "POST",
      headers: getAuthHeaders(token),
    }
  );
  if (!res.ok) {
    throw new Error(`Failed to translate inspection: ${res.status}`);
  }
  return res.json();
}

/**
 * Speaks the vernacular narration using browser Web Speech API with fallback.
 */
export function playVernacularAudio(narrationText: string, langCode: string = "hi"): Promise<void> {
  return new Promise((resolve) => {
    if (typeof window === "undefined" || !("speechSynthesis" in window)) {
      resolve();
      return;
    }

    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(narrationText);
    utterance.lang = langCode === "hi" ? "hi-IN" : langCode === "mr" ? "mr-IN" : "en-IN";
    utterance.rate = 0.95;
    utterance.onend = () => resolve();
    utterance.onerror = () => resolve();

    window.speechSynthesis.speak(utterance);
  });
}
