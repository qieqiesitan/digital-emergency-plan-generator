UPDATE enterprises
SET org_structure = (
    SELECT jsonb_agg(
        CASE
            WHEN jsonb_typeof(elem->'members') = 'array'
                 AND jsonb_array_length(elem->'members') > 0
            THEN elem - 'members' || '{"members": []}'::jsonb
            ELSE elem
        END
    )
    FROM jsonb_array_elements(org_structure) AS elem
)
WHERE id = '94804158-cc33-464d-9aef-025ec90226be';
