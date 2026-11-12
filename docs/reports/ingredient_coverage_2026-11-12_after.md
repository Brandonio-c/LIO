# Ingredient coverage report

| Measure | Before | After |
|---|---|---|
| Open Food Facts | 12/20 | 12/20 |
| USDA FDC Branded | 7/20 | 7/20 |
| NIH DSLD | 4/20 | 4/20 |
| openFDA label (by UPC) | 4/20 | 4/20 |
| openFDA NDC (UPC 3 + NDC) | 0/20 | 0/20 |
| Pipeline: product found | 19/20 | 20/20 |
| Pipeline: ingredient list | 18/20 | 19/20 |
| Pipeline: list of 50+ characters | 17/20 | 19/20 |
| Pipeline: parts with their origin field | 0/20 | 19/20 |
| Pipeline used FDC | 6/20 | 7/20 |
| Pipeline used DSLD | 3/20 | 4/20 |
| Pipeline used openFDA (UPC) | 4/20 | 4/20 |
| Pipeline used openFDA/DailyMed (NDC) | 0/20 | 0/20 |
| Pipeline used OFF | 12/20 | 12/20 |
| Any source has a list | 19/20 | 19/20 |

## Per barcode

### 0300680418301: Citrucel orange
- From: library scan LIO-F-00001. Check digit OK; GTIN-14 00300680418301.
- OFF: tried [as_given+, upca+, gtin14+]; matched with as_given: ingredients_parsed=0, ingredients_text=False, ingredients_text_languages=[], nutriments=False
- FDC: tried [gtin14-, ean13-, upca-]; no match
- DSLD: tried [spaced:3 00680 41830 1-, spaced:0 300680 418301-, upca-, ean13-]; no match
- openFDA label: tried [ean13-, upca-, gtin14-]; no match
- openFDA NDC: tried [openfda package 0068-0418-30-, openfda product 0068-0418-, dailymed 0068-0418-30-, openfda package 00680-418-30-, openfda product 00680-418-, dailymed 00680-418-30-, openfda package 00680-4183-0-, openfda product 00680-4183-, dailymed 00680-4183-0-]; no match
- Pipeline: found=True, sources=['openfoodfacts'], list=NO
- Matched forms: openfoodfacts=UPC-A 300680418301
- **Issue:** no source has an ingredient list for any barcode form

### 051500255162: Jif Creamy Peanut Butter 16 oz
- From: FDC (golden record). Check digit OK; GTIN-14 00051500255162.
- OFF: tried [as_given+, ean13+, gtin14+]; matched with as_given: ingredients_parsed=6, ingredients_text=True, ingredients_text_languages=['en', 'zh'], nutriments=True
- FDC: tried [gtin14+, ean13-, upca-]; matched with gtin14: ingredients=True, ingredients_chars=121, ingredients_ends_cleanly=True, servingSize=True (stored as '00051500255162')
- DSLD: tried [spaced:0 51500 25516 2-, spaced:0 051500 255162-, upca-, ean13-]; no match
- openFDA label: tried [ean13-, upca-, gtin14-]; no match
- Pipeline: found=True, sources=['usda', 'openfoodfacts'], list=yes (121 chars, )
- Matched forms: openfoodfacts=UPC-A 051500255162, usda=GTIN-14 00051500255162
- Parts: food<usda.ingredients>, food<openfoodfacts.ingredients_text>, food<openfoodfacts.ingredients_text_zh>

### 702669934398: Nutricost Magnesium Oxide
- From: DSLD (golden record). Check digit OK; GTIN-14 00702669934398.
- OFF: tried [as_given-, ean13-, gtin14-]; no match
- FDC: tried [gtin14-, ean13-, upca-]; no match
- DSLD: tried [spaced:7 02669 93439 8+]; matched with spaced:7 02669 93439 8: dietary_ingredients=1, other_ingredients=4 (stored as '7 02669 93439 8')
- openFDA label: tried [ean13-, upca-, gtin14-]; no match
- Pipeline: found=True, sources=['dsld'], list=yes (102 chars, )
- Matched forms: dsld=UPC-A spaced 7 02669 93439 8
- Parts: dietary<dsld.ingredientRows>, other<dsld.otheringredients.ingredients>

### 3017620422003: Nutella 400 g (France)
- From: OFF (golden record). Check digit OK; GTIN-14 03017620422003.
- OFF: tried [as_given+, gtin14+]; matched with as_given: ingredients_parsed=2, ingredients_text=True, ingredients_text_languages=['ab', 'ar', 'de', 'en', 'es', 'fr', 'hi', 'it', 'nl', 'or'], nutriments=True
- FDC: tried [gtin14-, ean13-]; no match
- DSLD: tried [spaced:3 017620 422003-, ean13-]; no match
- openFDA label: tried [ean13-, gtin14-]; no match
- Pipeline: found=True, sources=['openfoodfacts'], list=yes (169 chars, )
- Matched forms: openfoodfacts=EAN-13 3017620422003
- Parts: food<openfoodfacts.ingredients_text>, food<openfoodfacts.ingredients_text_ab>, food<openfoodfacts.ingredients_text_ar>, food<openfoodfacts.ingredients_text_de>, food<openfoodfacts.ingredients_text_es>, food<openfoodfacts.ingredients_text_it>, food<openfoodfacts.ingredients_text_nl>

### 016000275287: Cheerios
- From: FDC search 'cheerios cereal'. Check digit OK; GTIN-14 00016000275287.
- OFF: tried [as_given+, ean13+, gtin14+]; matched with as_given: ingredients_parsed=16, ingredients_text=True, ingredients_text_languages=['en', 'la'], nutriments=True
- FDC: tried [gtin14+, ean13-, upca-]; matched with gtin14: ingredients=True, ingredients_chars=406, ingredients_ends_cleanly=True, servingSize=True (stored as '00016000275287')
- DSLD: tried [spaced:0 16000 27528 7-, spaced:0 016000 275287-, upca-, ean13-]; no match
- openFDA label: tried [ean13-, upca-, gtin14-]; no match
- Pipeline: found=True, sources=['usda', 'openfoodfacts'], list=yes (406 chars, )
- Matched forms: openfoodfacts=UPC-A 016000275287, usda=GTIN-14 00016000275287
- Parts: food<usda.ingredients>, food<openfoodfacts.ingredients_text>, food<openfoodfacts.ingredients_text_en>

### 051000273482: Campbell's Tomato Soup
- From: FDC search 'campbell tomato soup'. Check digit OK; GTIN-14 00051000273482.
- OFF: tried [as_given+, ean13+, gtin14+]; matched with as_given: ingredients_parsed=12, ingredients_text=True, ingredients_text_languages=['en'], nutriments=True
- FDC: tried [gtin14+, ean13-, upca-]; matched with gtin14: ingredients=True, ingredients_chars=266, ingredients_ends_cleanly=True, servingSize=True (stored as '00051000273482')
- DSLD: tried [spaced:0 51000 27348 2-, spaced:0 051000 273482-, upca-, ean13-]; no match
- openFDA label: tried [ean13-, upca-, gtin14-]; no match
- Pipeline: found=True, sources=['usda', 'openfoodfacts'], list=yes (266 chars, )
- Matched forms: openfoodfacts=UPC-A 051000273482, usda=GTIN-14 00051000273482
- Parts: food<usda.ingredients>, food<openfoodfacts.ingredients_text>

### 818290019790: Chobani Honey Vanilla Greek
- From: FDC search 'chobani greek yogurt'. Check digit OK; GTIN-14 00818290019790.
- OFF: tried [as_given+, ean13+, gtin14+]; matched with as_given: ingredients_parsed=10, ingredients_text=True, ingredients_text_languages=['en'], nutriments=True
- FDC: tried [gtin14+, ean13-, upca-]; matched with gtin14: ingredients=True, ingredients_chars=261, ingredients_ends_cleanly=True, servingSize=True (stored as '00818290019790')
- DSLD: tried [spaced:8 18290 01979 0-, spaced:0 818290 019790-, upca-, ean13-]; no match
- openFDA label: tried [ean13-, upca-, gtin14-]; no match
- Pipeline: found=True, sources=['usda', 'openfoodfacts'], list=yes (261 chars, )
- Matched forms: openfoodfacts=UPC-A 818290019790, usda=GTIN-14 00818290019790
- Parts: food<usda.ingredients>, food<openfoodfacts.ingredients_text>

### 021000037377: Kraft Macaroni & Cheese
- From: FDC search 'kraft macaroni cheese'. Check digit OK; GTIN-14 00021000037377.
- OFF: tried [as_given+, ean13+, gtin14+]; matched with as_given: ingredients_parsed=9, ingredients_text=True, ingredients_text_languages=['en'], nutriments=True
- FDC: tried [gtin14-, ean13-, upca+]; matched with upca: ingredients=True, ingredients_chars=711, ingredients_ends_cleanly=True, servingSize=True (stored as '021000037377')
- DSLD: tried [spaced:0 21000 03737 7-, spaced:0 021000 037377-, upca-, ean13-]; no match
- openFDA label: tried [ean13-, upca-, gtin14-]; no match
- Pipeline: found=True, sources=['usda', 'openfoodfacts'], list=yes (711 chars, )
- Matched forms: openfoodfacts=UPC-A 021000037377, usda=UPC-A 021000037377
- Parts: food<usda.ingredients>, food<openfoodfacts.ingredients_text>

### 842379108549: Solimo Melatonin 3 mg
- From: DSLD label 239571. Check digit OK; GTIN-14 00842379108549.
- OFF: tried [as_given-, ean13-, gtin14-]; no match
- FDC: tried [gtin14-, ean13-, upca-]; no match
- DSLD: tried [spaced:8 42379 10854 9+]; matched with spaced:8 42379 10854 9: dietary_ingredients=1, other_ingredients=4 (stored as '8 42379 10854 9')
- openFDA label: tried [ean13-, upca-, gtin14-]; no match
- Pipeline: found=True, sources=['dsld'], list=yes (114 chars, )
- Matched forms: dsld=UPC-A spaced 8 42379 10854 9
- Parts: dietary<dsld.ingredientRows>, other<dsld.otheringredients.ingredients>

### 766298017891: Pure Encapsulations Melatonin-SR
- From: DSLD label 277770. Check digit OK; GTIN-14 00766298017891.
- OFF: tried [as_given-, ean13-, gtin14-]; no match
- FDC: tried [gtin14-, ean13-, upca-]; no match
- DSLD: tried [spaced:7 66298 01789 1+]; matched with spaced:7 66298 01789 1: dietary_ingredients=1, other_ingredients=6 (stored as '7 66298 01789 1')
- openFDA label: tried [ean13-, upca-, gtin14-]; no match
- Pipeline: found=True, sources=['dsld'], list=yes (186 chars, )
- Matched forms: dsld=UPC-A spaced 7 66298 01789 1
- Parts: dietary<dsld.ingredientRows>, other<dsld.otheringredients.ingredients>

### 5453003821090: SuperSmart Melatonin 2 mg
- From: DSLD label 332395. Check digit OK; GTIN-14 05453003821090.
- OFF: tried [as_given-, gtin14-]; no match
- FDC: tried [gtin14-, ean13-]; no match
- DSLD: tried [spaced:5 453003 821090+]; matched with spaced:5 453003 821090: dietary_ingredients=1, other_ingredients=1 (stored as '5 453003 821090')
- openFDA label: tried [ean13-, gtin14-]; no match
- Pipeline: found=True, sources=['dsld'], list=yes (66 chars, )
- Matched forms: dsld=EAN-13 spaced 5 453003 821090
- Parts: dietary<dsld.ingredientRows>, other<dsld.otheringredients.ingredients>

### 070038610953: Valu Pain Reliever Extra Strength
- From: openFDA label (openfda.upc). Check digit OK; GTIN-14 00070038610953.
- OFF: tried [as_given-, ean13-, gtin14-]; no match
- FDC: tried [gtin14-, ean13-, upca-]; no match
- DSLD: tried [spaced:0 70038 61095 3-, spaced:0 070038 610953-, upca-, ean13-]; no match
- openFDA label: tried [ean13+, upca-, gtin14-]; matched with ean13: active_ingredient=True, inactive_ingredient=True, other_information=True
- Pipeline: found=True, sources=['openfda'], list=yes (361 chars, )
- Matched forms: openfda=EAN-13 0070038610953
- Parts: active<openfda.active_ingredient[0]>, inactive<openfda.inactive_ingredient[0]>

### 341520314643: Care One Ibuprofen
- From: openFDA label (openfda.upc). Check digit OK; GTIN-14 00341520314643.
- OFF: tried [as_given-, ean13-, gtin14-]; no match
- FDC: tried [gtin14-, ean13-, upca-]; no match
- DSLD: tried [spaced:3 41520 31464 3-, spaced:0 341520 314643-, upca-, ean13-]; no match
- openFDA label: tried [ean13+, upca-, gtin14-]; matched with ean13: active_ingredient=True, inactive_ingredient=True, other_information=True
- openFDA NDC: tried [openfda package 4152-0314-64-, openfda product 4152-0314-, dailymed 4152-0314-64-, openfda package 41520-314-64-, openfda product 41520-314-, dailymed 41520-314-64-, openfda package 41520-3146-4-, openfda product 41520-3146-, dailymed 41520-3146-4-]; no match
- Pipeline: found=True, sources=['openfda'], list=yes (347 chars, )
- Matched forms: openfda=EAN-13 0341520314643
- Parts: active<openfda.active_ingredient[0]>, inactive<openfda.inactive_ingredient[0]>

### 032251921049: Family Wellness Daytime Cold and Flu
- From: openFDA label (openfda.upc). Check digit OK; GTIN-14 00032251921049.
- OFF: tried [as_given-, ean13-, gtin14-]; no match
- FDC: tried [gtin14-, ean13-, upca-]; no match
- DSLD: tried [spaced:0 32251 92104 9-, spaced:0 032251 921049-, upca-, ean13-]; no match
- openFDA label: tried [ean13+, upca-, gtin14-]; matched with ean13: active_ingredient=True, inactive_ingredient=True, other_information=True
- Pipeline: found=True, sources=['openfda'], list=yes (313 chars, )
- Matched forms: openfda=EAN-13 0032251921049
- Parts: active<openfda.active_ingredient[0]>, inactive<openfda.inactive_ingredient[0]>

### 070038599760: Valu Allergy Relief
- From: openFDA label (openfda.upc). Check digit OK; GTIN-14 00070038599760.
- OFF: tried [as_given-, ean13-, gtin14-]; no match
- FDC: tried [gtin14-, ean13-, upca-]; no match
- DSLD: tried [spaced:0 70038 59976 0-, spaced:0 070038 599760-, upca-, ean13-]; no match
- openFDA label: tried [ean13+, upca-, gtin14-]; matched with ean13: active_ingredient=True, inactive_ingredient=True, other_information=True
- Pipeline: found=True, sources=['openfda'], list=yes (170 chars, )
- Matched forms: openfda=EAN-13 0070038599760
- Parts: active<openfda.active_ingredient[0]>, inactive<openfda.inactive_ingredient[0]>

### 5449000000996: Coca-Cola Original (EU)
- From: OFF. Check digit OK; GTIN-14 05449000000996.
- OFF: tried [as_given+, gtin14+]; matched with as_given: ingredients_parsed=5, ingredients_text=True, ingredients_text_languages=['ar', 'bg', 'de', 'en', 'es', 'fr', 'it', 'lt', 'pl', 'ro', 'ru', 'sq', 'zh'], nutriments=True
- FDC: tried [gtin14-, ean13-]; no match
- DSLD: tried [spaced:5 449000 000996-, ean13-]; no match
- openFDA label: tried [ean13-, gtin14-]; no match
- Pipeline: found=True, sources=['openfoodfacts'], list=yes (191 chars, )
- Matched forms: openfoodfacts=EAN-13 5449000000996
- Parts: food<openfoodfacts.ingredients_text>, food<openfoodfacts.ingredients_text_ar>, food<openfoodfacts.ingredients_text_bg>, food<openfoodfacts.ingredients_text_de>, food<openfoodfacts.ingredients_text_en>, food<openfoodfacts.ingredients_text_fr>, food<openfoodfacts.ingredients_text_it>, food<openfoodfacts.ingredients_text_lt>, food<openfoodfacts.ingredients_text_pl>, food<openfoodfacts.ingredients_text_ro>, food<openfoodfacts.ingredients_text_ru>, food<openfoodfacts.ingredients_text_sq>, food<openfoodfacts.ingredients_text_zh>

### 8000500310427: Nutella Biscuits
- From: OFF. Check digit OK; GTIN-14 08000500310427.
- OFF: tried [as_given+, gtin14+]; matched with as_given: ingredients_parsed=20, ingredients_text=True, ingredients_text_languages=['de', 'en', 'es', 'fr', 'it', 'pt'], nutriments=True
- FDC: tried [gtin14-, ean13-]; no match
- DSLD: tried [spaced:8 000500 310427-, ean13-]; no match
- openFDA label: tried [ean13-, gtin14-]; no match
- Pipeline: found=True, sources=['openfoodfacts'], list=yes (579 chars, )
- Matched forms: openfoodfacts=EAN-13 8000500310427
- Parts: food<openfoodfacts.ingredients_text>, food<openfoodfacts.ingredients_text_de>, food<openfoodfacts.ingredients_text_en>, food<openfoodfacts.ingredients_text_es>, food<openfoodfacts.ingredients_text_pt>

### 3228857000166: Harrys 100% mie complet
- From: OFF. Check digit OK; GTIN-14 03228857000166.
- OFF: tried [as_given+, gtin14+]; matched with as_given: ingredients_parsed=12, ingredients_text=True, ingredients_text_languages=['en', 'fr'], nutriments=True
- FDC: tried [gtin14-, ean13-]; no match
- DSLD: tried [spaced:3 228857 000166-, ean13-]; no match
- openFDA label: tried [ean13-, gtin14-]; no match
- Pipeline: found=True, sources=['openfoodfacts'], list=yes (264 chars, )
- Matched forms: openfoodfacts=EAN-13 3228857000166
- Parts: food<openfoodfacts.ingredients_text>, food<openfoodfacts.ingredients_text_en>

### 049000028911: Diet Coke (US)
- From: OFF. Check digit OK; GTIN-14 00049000028911.
- OFF: tried [as_given+, ean13+, gtin14+]; matched with as_given: ingredients_parsed=7, ingredients_text=True, ingredients_text_languages=['en'], nutriments=True
- FDC: tried [gtin14+, ean13-, upca-]; matched with gtin14: ingredients=True, ingredients_chars=139, ingredients_ends_cleanly=True, servingSize=True (stored as '00049000028911')
- DSLD: tried [spaced:0 49000 02891 1-, spaced:0 049000 028911-, upca-, ean13-]; no match
- openFDA label: tried [ean13-, upca-, gtin14-]; no match
- Pipeline: found=True, sources=['usda', 'openfoodfacts'], list=yes (139 chars, )
- Matched forms: openfoodfacts=UPC-A 049000028911, usda=GTIN-14 00049000028911
- Parts: food<usda.ingredients>, food<openfoodfacts.ingredients_text>

### 04963406: Coca-Cola can, UPC-E
- From: OFF (UPC-E). Check digit OK; GTIN-14 00049000006346; UPC-E 04963406.
- OFF: tried [as_given+, upca+, ean13+, gtin14+]; matched with as_given: ingredients_parsed=6, ingredients_text=True, ingredients_text_languages=['en'], nutriments=True
- FDC: tried [gtin14+, ean13-, upca-, as_given-]; matched with gtin14: ingredients=True, ingredients_chars=102, ingredients_ends_cleanly=True, servingSize=True (stored as '00049000006346')
- DSLD: tried [spaced:0 49000 00634 6-, spaced:0 049000 006346-, upca-, ean13-]; no match
- openFDA label: tried [ean13-, upca-, gtin14-]; no match
- Pipeline: found=True, sources=['usda', 'openfoodfacts'], list=yes (102 chars, )
- Matched forms: openfoodfacts=UPC-A 049000006346, usda=GTIN-14 00049000006346
- Parts: food<usda.ingredients>, food<openfoodfacts.ingredients_text>
