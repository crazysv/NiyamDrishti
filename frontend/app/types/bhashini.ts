export interface SupportedLanguage {
  code: string;
  name: string;
  native_name: string;
  script: string;
}

export interface SupportedLanguagesResponse {
  total: number;
  languages: SupportedLanguage[];
}

export interface TranslationResponse {
  source_language: string;
  target_language: string;
  source_text: string;
  translated_text: string;
  is_offline_fallback: boolean;
}

export interface TTSResponse {
  language: string;
  audio_format: string;
  audio_content_base64: string;
  is_offline_fallback: boolean;
}

export interface InspectionFieldTranslation {
  field_id: string;
  field_type: string;
  label: string;
  original_value: string;
  translated_value: string;
}

export interface InspectionViolationTranslation {
  violation_id: string;
  rule_id: string;
  severity: string;
  original_description: string;
  translated_description: string;
  citation: string;
}

export interface InspectionTranslationResponse {
  inspection_id: string;
  target_language: string;
  target_language_name: string;
  is_offline_fallback: boolean;
  summary_narration: string;
  fields: InspectionFieldTranslation[];
  violations: InspectionViolationTranslation[];
}
