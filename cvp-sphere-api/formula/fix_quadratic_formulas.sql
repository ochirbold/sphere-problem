-- SQL script to fix quadratic formulas in database
-- Run this in your Oracle database to correct the mathematically incorrect formulas

-- First, check what formulas exist for indicator 17690659377261
SELECT 
    main_indicator_id,
    column_name,
    expression_string
FROM kpi_indicator_indicator_map
WHERE main_indicator_id = 17690659377261
  AND expression_string IS NOT NULL
ORDER BY column_name;

-- Update X1 formula from incorrect to correct
UPDATE kpi_indicator_indicator_map
SET expression_string = '(-Y - DISCREMNANT) / (2 * X)'
WHERE main_indicator_id = 17690659377261
  AND column_name = 'X1'
  AND expression_string = '-1 * Y - DISCREMNANT / 2 * X';

-- Update X2 formula from incorrect to correct  
UPDATE kpi_indicator_indicator_map
SET expression_string = '(-Y + DISCREMNANT) / (2 * X)'
WHERE main_indicator_id = 17690659377261
  AND column_name = 'X2'
  AND expression_string = '-1 * Y + DISCREMNANT / 2 * X';

-- Also check for other variations that might be wrong
-- Common incorrect patterns:
-- 1. Missing parentheses: -Y - DISCREMNANT / 2 * X
-- 2. Wrong order: DISCREMNANT / 2 * X - Y
-- 3. Missing 2*X denominator

-- More comprehensive fix for any quadratic root formulas:
UPDATE kpi_indicator_indicator_map
SET expression_string = 
    CASE 
        WHEN column_name LIKE 'X1' AND expression_string LIKE '%DISCREMNANT%' THEN
            '(-Y - DISCREMNANT) / (2 * X)'
        WHEN column_name LIKE 'X2' AND expression_string LIKE '%DISCREMNANT%' THEN
            '(-Y + DISCREMNANT) / (2 * X)'
        ELSE expression_string
    END
WHERE main_indicator_id = 17690659377261
  AND column_name IN ('X1', 'X2')
  AND expression_string LIKE '%DISCREMNANT%';

-- Verify the fixes
SELECT 
    column_name,
    expression_string,
    'Fixed' as status
FROM kpi_indicator_indicator_map
WHERE main_indicator_id = 17690659377261
  AND column_name IN ('X1', 'X2')
  AND expression_string IS NOT NULL;

-- Commit the changes
COMMIT;

-- Optional: Create a view to see all quadratic-related formulas
CREATE OR REPLACE VIEW quadratic_formulas_v AS
SELECT 
    main_indicator_id,
    column_name,
    expression_string,
    CASE 
        WHEN expression_string LIKE '%sqrt(pow(Y,2) - 4 * X * Z)%' THEN 'DISCREMNANT'
        WHEN expression_string LIKE '%(-Y - DISCREMNANT) / (2 * X)%' THEN 'X1 (correct)'
        WHEN expression_string LIKE '%(-Y + DISCREMNANT) / (2 * X)%' THEN 'X2 (correct)'
        WHEN expression_string LIKE '%DISCREMNANT%' AND column_name IN ('X1', 'X2') THEN 'CHECK - might be wrong'
        ELSE 'Other'
    END as formula_type
FROM kpi_indicator_indicator_map
WHERE expression_string LIKE '%DISCREMNANT%'
   OR expression_string LIKE '%sqrt(pow(Y,2) - 4 * X * Z)%'
ORDER BY main_indicator_id, column_name;

-- Query the view
SELECT * FROM quadratic_formulas_v;
