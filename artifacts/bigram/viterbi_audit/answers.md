# Amsterdam audit: verbatim outputs

All runs use 64 output tokens, a 64-token block, top-k 16, seed 42, delayed EOS/EOT retention on, and early stopping on. NFE values below are requested budgets; actual forward counts may be lower when a finished answer is retained. Ending strength is 10 except the explicitly labeled 1000 cases. The raw-confidence experiment was reverted.

## before / pmi_t1 / 16 requested steps

Revision: `977a9266f2482a17e03b67eedd1f9b44c7f95f81`. Temperature 1.0; ending strength 10.0; actual steps 16.

Weak: repeated Netherlands, incomplete province phrase, duplicated punctuation and topics.

````text
Amsterdam is the capital of the Netherlands, Netherlands. It is the capital of the province of North and is one of the most popular cities in Europe. It is known for its canals, art museums, and history, and culture.. Amsterdam is known for its canals, art,, history, and culture.
````

## before / pmi_t2 / 16 requested steps

Revision: `977a9266f2482a17e03b67eedd1f9b44c7f95f81`. Temperature 2.0; ending strength 10.0; actual steps 16.

More fluent than T1, but still repeats Netherlands and contains an incomplete province phrase.

````text
Amsterdam is the capital of the Netherlands, Netherlands. It is the center of the province of North and is one of the most populous cities in the Netherlands. It is known for its historic architecture, vibrant culture, museums, theaters, and canals. Additionally, Amsterdam is known for its art, history, and culture.
````

## before / previous_conditional_default / 16 requested steps

Revision: `977a9266f2482a17e03b67eedd1f9b44c7f95f81`. Temperature 1.0; ending strength 10.0; actual steps 16.

Starts fluently, then becomes malformed and adds unsupported claims.

````text
Amsterdam is the capital of the Netherlands, and is one of the most popular cities in the world. It is known for its canals, historic architecture, and culture, and its vibrant nightlife. It is also known for the location of the Dutch East, and West and the headquarters of the U.S. Army.
````

## before / pmi_t1 / 32 requested steps

Revision: `977a9266f2482a17e03b67eedd1f9b44c7f95f81`. Temperature 1.0; ending strength 10.0; actual steps 23.

Mostly fluent, with one of of repetition.

````text
Amsterdam is the capital of the Netherlands and one of of the most popular cities in the world. It is known for its canals, museums, and nightlife, and is a major center for tourism, finance, and culture.
````

## before / pmi_t2 / 32 requested steps

Revision: `977a9266f2482a17e03b67eedd1f9b44c7f95f81`. Temperature 2.0; ending strength 10.0; actual steps 23.

Fluent, generic short answer; cleaner than T1 on this prompt.

````text
Amsterdam is the capital of the Netherlands, and is known for its canals, museums, and vibrant nightlife. It is one of the most popular cities in the world, and is a popular destination for tourists and business travelers.
````

## before / previous_conditional_default / 32 requested steps

Revision: `977a9266f2482a17e03b67eedd1f9b44c7f95f81`. Temperature 1.0; ending strength 10.0; actual steps 23.

Fluent short answer.

````text
Amsterdam is the capital of the Netherlands and is one of the most popular cities in the world. It is known for its picturesque canals, museums, and vibrant nightlife. It is also known for its liberal policies and tolerance.
````

## after / pmi_t1 / 16 requested steps

Revision: `2d5f62fff44a3ac452dafc1220f0d79eb70f133a`. Temperature 1.0; ending strength 10.0; actual steps 11.

Raw-confidence experiment: worse than before; strong repetition and malformed phrasing.

````text
Amsterdam is the capital of the Netherlands, Netherlands. It is a city of the Netherlands, Europe,, Netherlands,, Netherlands, and Europe. It is the capital city of the province of North.
````

## after / pmi_t2 / 16 requested steps

Revision: `2d5f62fff44a3ac452dafc1220f0d79eb70f133a`. Temperature 2.0; ending strength 10.0; actual steps 13.

Raw-confidence experiment: worse than before; repeated museums and confused administrative phrasing.

````text
Amsterdam is the capital of the Netherlands, Netherlands. It is a city of the province of Amsterdam, and the municipality, region, and province. It is known for the canals, museums, and museums.
````

## after / pmi_t1 / 32 requested steps

Revision: `2d5f62fff44a3ac452dafc1220f0d79eb70f133a`. Temperature 1.0; ending strength 10.0; actual steps 23.

Exactly the same answer as before the confidence experiment.

````text
Amsterdam is the capital of the Netherlands and one of of the most popular cities in the world. It is known for its canals, museums, and nightlife, and is a major center for tourism, finance, and culture.
````

## after / pmi_t2 / 32 requested steps

Revision: `2d5f62fff44a3ac452dafc1220f0d79eb70f133a`. Temperature 2.0; ending strength 10.0; actual steps 23.

Exactly the same answer as before the confidence experiment.

````text
Amsterdam is the capital of the Netherlands, and is known for its canals, museums, and vibrant nightlife. It is one of the most popular cities in the world, and is a popular destination for tourists and business travelers.
````

## after_stronger_ending_delay / pmi_t1 / 16 requested steps

Revision: `2d5f62fff44a3ac452dafc1220f0d79eb70f133a`. Temperature 1.0; ending strength 1000.0; actual steps 16.

Longer continuation of the same weak prefix; repetitions persist and answer reaches token cap.

````text
Amsterdam is the capital of the Netherlands, Netherlands. It is a city of the Netherlands, Europe,, Netherlands,, Netherlands, and Europe. It is the capital city of the province of North. It is the largest city of the Netherlands of the Netherlands, Netherlands, Europe, and Europe, and the largest city of
````

## after_stronger_ending_delay / pmi_t2 / 16 requested steps

Revision: `2d5f62fff44a3ac452dafc1220f0d79eb70f133a`. Temperature 2.0; ending strength 1000.0; actual steps 16.

Longer continuation of the same weak prefix; repeats museums and largest city.

````text
Amsterdam is the capital of the Netherlands, Netherlands. It is a city of the province of Amsterdam, and the municipality, region, and province. It is known for the canals, museums, and museums. It is the largest city of the Netherlands, the capital of the Netherlands, and the largest city of the Netherlands.
````
