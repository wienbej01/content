-- Product-contract audio/visual policy fields exposed by Seedance truth test.

ALTER TABLE render_units ADD COLUMN product_audio_policy TEXT;
ALTER TABLE render_units ADD COLUMN actual_render_duration_ms INTEGER;
ALTER TABLE render_units ADD COLUMN product_contract_json TEXT;

DROP TRIGGER IF EXISTS trg_ru_audio_policy;
DROP TRIGGER IF EXISTS trg_ru_audio_policy_upd;

CREATE TRIGGER trg_ru_audio_policy
    BEFORE INSERT ON render_units
    WHEN NEW.audio_policy IS NOT NULL
     AND NEW.audio_policy NOT IN ('HERO_SYNC_LOCKED','BROLL_FLEX','BROLL_SYNCED_ACTION',
                                  'AMBIENCE_OR_SFX','MUSIC_BED','SILENT_GRAPHIC',
                                  'narration_overlay','silent','baked_in','generated_tts',
                                  'strip','ambient',
                                  'HERO_PROVIDER_AUDIO_ISLAND',
                                  'VIDEO_ONLY_OVER_CANONICAL_NARRATION',
                                  'SILENT_VISUAL')
BEGIN
    SELECT RAISE(ABORT, 'invalid audio_policy');
END;

CREATE TRIGGER trg_ru_audio_policy_upd
    BEFORE UPDATE ON render_units
    WHEN NEW.audio_policy IS NOT NULL
     AND NEW.audio_policy NOT IN ('HERO_SYNC_LOCKED','BROLL_FLEX','BROLL_SYNCED_ACTION',
                                  'AMBIENCE_OR_SFX','MUSIC_BED','SILENT_GRAPHIC',
                                  'narration_overlay','silent','baked_in','generated_tts',
                                  'strip','ambient',
                                  'HERO_PROVIDER_AUDIO_ISLAND',
                                  'VIDEO_ONLY_OVER_CANONICAL_NARRATION',
                                  'SILENT_VISUAL')
BEGIN
    SELECT RAISE(ABORT, 'invalid audio_policy');
END;

CREATE TRIGGER trg_ru_product_audio_policy
    BEFORE INSERT ON render_units
    WHEN NEW.product_audio_policy IS NOT NULL
     AND NEW.product_audio_policy NOT IN ('HERO_PROVIDER_AUDIO_ISLAND',
                                          'VIDEO_ONLY_OVER_CANONICAL_NARRATION',
                                          'SILENT_VISUAL')
BEGIN
    SELECT RAISE(ABORT, 'invalid product_audio_policy');
END;

CREATE TRIGGER trg_ru_product_audio_policy_upd
    BEFORE UPDATE ON render_units
    WHEN NEW.product_audio_policy IS NOT NULL
     AND NEW.product_audio_policy NOT IN ('HERO_PROVIDER_AUDIO_ISLAND',
                                          'VIDEO_ONLY_OVER_CANONICAL_NARRATION',
                                          'SILENT_VISUAL')
BEGIN
    SELECT RAISE(ABORT, 'invalid product_audio_policy');
END;
