UPDATE model_providers
SET enabled_models = (
  SELECT jsonb_agg(
    CASE
      WHEN elem->>'id' = 'Qwen/Qwen3-VL-8B-Instruct'
      THEN elem || '{"input_modalities": ["text", "image"]}'::jsonb
      ELSE elem
    END
  )
  FROM jsonb_array_elements(enabled_models::jsonb) AS elem
)
WHERE provider_id = 'siliconflow-cn';
