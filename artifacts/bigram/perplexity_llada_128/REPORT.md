# Quick LLaDA-8B-Instruct perplexity comparison

Saved generations: 100/100; scored: 100/100.

10 standard questions; one seed (1234); 128-token canvas; one block; delayed EOS/EOT retention; early stopping disabled. All generation and reference scoring runs on Hugging Face ZeroGPU.

Baseline: existing app confidence-guided sampler, temperature 0.7, top-k 3. Viterbi: PMI, diffusion confidence, temperature 2, top-k 16, fixed weight 0.5, minimum count 1, clipping ±2, ending-delay strength 10. This compares the practical setups, including their different sampling/ending settings; it does not isolate the effect of Viterbi or exactly replicate the paper.

Reference: microsoft/phi-4, NF4 with double quantization and BF16 compute. Standalone answers scored without question conditioning. Perplexity is exp(total negative log likelihood / total scored reference tokens). Only matched prompts are compared at each NFE.

| NFE | Paired prompts | Confidence PPL | PMI PPL | PMI / confidence | Paired 95% bootstrap interval |
|---:|---:|---:|---:|---:|---:|
| 8 | 10 | 148.85 | 4.71 | 0.032 | 0.003–0.369 |
| 16 | 10 | 32.75 | 4.55 | 0.139 | 0.016–0.888 |
| 32 | 10 | 3.96 | 3.27 | 0.826 | 0.713–1.005 |
| 64 | 10 | 3.21 | 2.95 | 0.918 | 0.829–1.027 |
| 128 | 10 | 2.66 | 2.55 | 0.958 | 0.862–1.072 |

Bootstrap: 10,000 paired prompt resamples, seed 1234. The interval captures prompt variability for these outputs; it does not capture variation across generation seeds.

Lower perplexity means more predictable text under Phi-4. Repetition and shorter or generic answers can also lower perplexity; it is not a correctness or factuality score. See saved answers for qualitative review.

| NFE | Confidence mean words | PMI mean words |
|---:|---:|---:|
| 8 | 94.0 | 108.6 |
| 16 | 92.2 | 104.3 |
| 32 | 104.4 | 110.1 |
| 64 | 102.9 | 108.2 |
| 128 | 105.2 | 109.0 |

Median per-answer perplexity and paired win counts supplement the token-pooled metric above. They help show whether the result is concentrated in a few failed answers. A win means lower per-answer PPL, not a manual quality judgment.

| NFE | Confidence median PPL | PMI median PPL | PMI PPL wins |
|---:|---:|---:|---:|
| 8 | 18.56 | 4.43 | 8/10 |
| 16 | 6.31 | 4.81 | 8/10 |
| 32 | 4.30 | 3.51 | 9/10 |
| 64 | 3.41 | 3.23 | 7/10 |
| 128 | 2.63 | 2.57 | 6/10 |

Distinct-1 (LLaDA-8B-Instruct tokenizer) is the number of unique token types divided by the total number of tokens in the complete generated answer, excluding special tokens and the prompt. Each answer is measured separately; the table averages those ratios and unique-token counts across questions. Higher ratios indicate less token repetition. This is not a grammaticality score.

| NFE | Confidence Distinct-1 | PMI Distinct-1 | Confidence mean unique tokens | PMI mean unique tokens |
|---:|---:|---:|---:|---:|
| 8 | 0.328 | 0.359 | 19.6 | 45.1 |
| 16 | 0.297 | 0.467 | 28.6 | 58.8 |
| 32 | 0.433 | 0.506 | 54.2 | 63.7 |
| 64 | 0.509 | 0.517 | 61.4 | 65.2 |
| 128 | 0.489 | 0.517 | 59.4 | 65.2 |

## Interpretation and spot checks

PMI substantially reduces pooled perplexity at 8 and 16 NFE under these transferred settings. The baseline often collapses into long function-word loops at those budgets; one 8-NFE photosynthesis answer scores 1577.97 per-answer perplexity. Per-question wins and medians are included to show how broad the improvement is beyond large outliers.

PMI still degenerates at low NFE: the 8-NFE search answer repeatedly emits “web pages,” and the friendship answer loops on “understanding.” At 32 NFE, the PMI Amsterdam answer incorrectly lists Red Square as an Amsterdam landmark. At 64 NFE, the PMI seasons answer contradicts the hemispheric explanation by assigning winter to a Southern Hemisphere tilted toward the Sun. Lower perplexity is not a factuality score.

At 128 NFE the baseline refrigerator answer still loops on “cold air,” while the PMI refrigerator answer gives a sustained explanation. Most other 128-NFE answers from both methods are fluent. The pooled gains at 32–128 NFE are smaller, and their paired bootstrap intervals include no gain in this 10-question, one-seed sample.

Delay EOS/EOT retention is on for both methods. PMI additionally uses ending prediction delay strength 10; the baseline has that penalty disabled. The 8-NFE baseline Amsterdam answer ends after “It” despite retention delay, showing that the option does not enforce a minimum answer length. This is a settings-bundle comparison in the shared app sampler, not an isolated Viterbi ablation or the official LLaDA benchmark sampler.


## Representative examples by NFE and decoding method

Both methods use the same LLaDA-8B-Instruct model. These examples come from the 10-question, 128-token-limit experiment.

I read all saved answers and selected a good, average, and bad example within each method/NFE group. Selection considers readability, relevance, coherence, repetition, and obvious content problems; it is not based on perplexity rank and is not a comprehensive factual audit. Average means typical of the group, not the mathematical median. Selections are made independently within each group, so prompts can differ between methods.

**The labels are relative.** Good means one of the stronger answers in that group, not necessarily an acceptable answer. At low NFE even good examples can be flawed; at high NFE a bad example can still be mostly fluent. These are illustrative selections, not a separate benchmark score.

Full outputs are quoted verbatim, including duplicated words, punctuation, line breaks, and unfinished endings. PPL is per-answer Phi-4 perplexity. Distinct-1 is unique token types / total tokens in the complete answer, using the model’s native tokenizer and excluding special tokens. Unique-token counts are shown alongside the ratios.

### NFE 8

#### Confidence-guided baseline

**Good example — question 7**

**Prompt:** How does vaccination help protect a population?

**Metrics:** PPL 11.39; Distinct-1 0.516; 64/124 unique token types / total tokens.

**Selection note:** One of the few sustained answers in this group: it discusses population protection and vulnerable people. Several sentences are garbled, so this is only a relative good example.

> Vaccination helps protect a population by creating community immunity or herd immunity against infectious disease. When a large enough percentage of the population is vaccinated, the immune system response of the immune system population becomes immunity to the specific strain of the virus that causes the disease. The more immunity, the lower the chances of the disease spreading to the rest of the population. This level of community immunity helps to control the spread of the disease, even if the vaccinated of not not vaccinated.. Vaccination can helps protect those populations who are vulnerable to be vaccinated, such as infants,, infants, and the elderly by preventing the spread of the disease.

**Average example — question 9**

**Prompt:** Explain the basic idea behind supply and demand.

**Metrics:** PPL 3.34; Distinct-1 0.151; 19/126 unique token types / total tokens.

**Selection note:** A recognizable economics opening turns into repetitive and inconsistent supply/price statements, typical of the low-budget breakdowns here.

> The and idea behind supply and demand is that the price of a product is determined by supply and demand, the higher the the supply of the product, the higher the demand, the higher the price, the higher the the supply, the lower the price, the higher the the supply, the higher, the higher, the higher, the higher the the the supply of the product, the higher the demand, the higher the price, the higher the the supply, the lower the price, the higher the the the supply, the lower the price, the higher the the supply, the higher the the supply, the lower the price.

**Bad example — question 5**

**Prompt:** Explain how a refrigerator keeps food cold.

**Metrics:** PPL 9045.49; Distinct-1 0.095; 12/126 unique token types / total tokens.

**Selection note:** The answer almost immediately collapses into repeated the tokens without explaining refrigeration.

> A refrigerator keeps food cold by using a cycle of the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the.

#### PMI Viterbi + diffusion confidence

**Good example — question 6**

**Prompt:** Why do we have different seasons on Earth?

**Metrics:** PPL 4.75; Distinct-1 0.424; 53/125 unique token types / total tokens.

**Selection note:** A relatively fluent, sustained seasons explanation with a recognizable axial-tilt argument. It also muddles the role of the elliptical orbit, so fluency does not establish correctness.

> We have different seasons on Earth due to the Earth's tilt on its axis and the Earth's elliptical orbit around the Sun. The tilt of the Earth on its axis causes a variation in the angle of the surface of the Earth facing the Sun. This results in a shift in the position of the Sun over the course of the year, leading to the seasons of the year,, spring, summer, autumn, and winter. Additionally, the Earth's elliptical orbit around the Sun also affects the amount of sunlight and received by the Sun different parts of the Earth over the course of the year, resulting in different weather patterns and seasons.

**Average example — question 8**

**Prompt:** What is the difference between weather and climate?

**Metrics:** PPL 4.07; Distinct-1 0.413; 52/126 unique token types / total tokens.

**Selection note:** The weather/climate distinction is present, but long runs of humidity and repeated phrasing interrupt it.

> Weather refers to the short-term conditions of atmospheric conditions at a specific place. It can include factors such as temperature, humidity, humidity, humidity, humidity, humidity, humidity, humidity, precipitation, and visibility. Weather conditions can vary greatly from one day to the next. Climate, on the other hand, refers to the long-term patterns of atmospheric conditions over a specific geographic region. It includes factors such as temperature, humidity, humidity, humidity, humidity, humidity, humidity, humidity, humidity, humidity, precipitation patterns, wind, and wind direction. Climate conditions are more stable and trends and trends over a longer period of time.

**Bad example — question 10**

**Prompt:** How does a search engine find relevant web pages?

**Metrics:** PPL 3.24; Distinct-1 0.119; 15/126 unique token types / total tokens.

**Selection note:** A search-engine opening degenerates into a long web pages loop; the closing sentence does not rescue the missing explanation.

> A search engine uses relevant web pages by scanning the web pages web pages web pages web pages web pages web pages web pages web pages web pages web pages web pages web pages web pages web pages web pages web pages web pages web pages web pages web pages web pages web pages web pages web pages web pages pages web pages the web pages web pages the web pages web pages the web pages in the web pages web pages the web pages web pages the web pages web pages the web pages in the web pages in the web pages web pages the web pages in the web pages the search engine will display the web pages in the relevant search results.

### NFE 16

#### Confidence-guided baseline

**Good example — question 9**

**Prompt:** Explain the basic idea behind supply and demand.

**Metrics:** PPL 2.59; Distinct-1 0.357; 45/126 unique token types / total tokens.

**Selection note:** A coherent, relevant supply-and-demand explanation, with small duplications but no long repetition collapse.

> The basic idea behind supply and demand is that the price of a good or service is determined by the interaction of supply and demand between buyers and sellers. Supply refers to the quantity of a good or service that sellers are willing to sell at a given price, while demand refers refers to the quantity of a good or service that buyers are willing to purchase at a given price. When supply is greater than demand, the price of a given good or service will decrease, and similarly, when demand is greater than supply, the price will rise. Thus, the price of a good or service is determined by the balance between supply and demand.

**Average example — question 3**

**Prompt:** How do plants convert sunlight into energy?

**Metrics:** PPL 6.65; Distinct-1 0.376; 47/125 unique token types / total tokens.

**Selection note:** It identifies photosynthesis and glucose, but the mechanism is garbled and the last portion collapses into repeated the tokens.

> Plants convert sunlight into energy through a process called photosynthesis. During this process, the energy, carbon dioxide, water, and carbon dioxide from the into the glucose molecules. This glucose is then used as a primary source of energy for the plant. Essentially, the energy from the sun is used to power the plant of growth, processes, and reproduction,. The process occurs in the the the chloroplasts of the the the the the the the the the the the the the the the the the the the the the, the the the the the the the the the the the the the the the the the the the the the.

**Bad example — question 5**

**Prompt:** Explain how a refrigerator keeps food cold.

**Metrics:** PPL 10015.17; Distinct-1 0.093; 11/118 unique token types / total tokens.

**Selection note:** The refrigerator answer contains little beyond a prompt paraphrase and a long function-word loop.

> A refrigerator keeps food cold by using a the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the air of the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the the

#### PMI Viterbi + diffusion confidence

**Good example — question 6**

**Prompt:** Why do we have different seasons on Earth?

**Metrics:** PPL 3.20; Distinct-1 0.444; 56/126 unique token types / total tokens.

**Selection note:** A sustained explanation of axial tilt and opposing hemispheric seasons, with only small wording omissions.

> We have different seasons on Earth due to the tilt of the Earth's axis relative to its orbit around the Sun. This tilt causes different parts of the Earth to receive varying amounts of sunlight throughout the course of the year. During the Northern Hemisphere's summer, the Northern Hemisphere is tilted towards the Sun, receiving more direct, while during the Northern Hemisphere's winter, the hemisphere is tilted away from the Sun, resulting in less direct sunlight. Similarly, the Southern Hemisphere experiences summer when the Southern Hemisphere is tilted towards the Sun, and experiences winter when the Southern Hemisphere is tilted away from the Sun. This is why we have different seasons.

**Average example — question 10**

**Prompt:** How does a search engine find relevant web pages?

**Metrics:** PPL 5.16; Distinct-1 0.444; 56/126 unique token types / total tokens.

**Selection note:** The search-engine workflow is recognizable, but missing verbs and broken transitions weaken the explanation.

> A search engine finds relevant web pages by using a web of algorithms, data, and other techniques. When a user enters a search query, the search engine breaks down the query to identify the main keywords and phrases. It then uses its algorithms to search for web pages that contain these keywords and phrases. It then the relevant web pages. Using algorithms, the search engine ranking of the web pages based on various factors such as the quality of the page, the popularity of the page, and the context of the query. Finally, the search engine returns a list of web pages that are the most relevant to the user's search query.

**Bad example — question 4**

**Prompt:** What makes a good friend?

**Metrics:** PPL 10.17; Distinct-1 0.365; 46/126 unique token types / total tokens.

**Selection note:** Relevant friendship advice is undermined by malformed words, duplicated items, and many empty lines; this illustrates formatting degeneration as well as repetition.

> A good friend is someone who is kind, understanding, and supportive. They.
>
> 1. Listen toively without interrupting or judging.
>
>
> 2. Show empathy for your feelings and feelings.
>
>
> 3. Offer emotional support and encouragement.
>
>
>
>
>
> 4. Be honest and trustworthy.
>
>
>
>
>
>
> 5. Be reliable and understanding.
>
>
>
>
>
>
>
> 6. Be reliable and understanding.
>
>
>
>
>
>
>
>
>
>
>
>
>
> A good friend is someone who makes you feel safe, loved, and valued and valued.

### NFE 32

#### Confidence-guided baseline

**Good example — question 8**

**Prompt:** What is the difference between weather and climate?

**Metrics:** PPL 4.94; Distinct-1 0.456; 57/125 unique token types / total tokens.

**Selection note:** A clear short-term/long-term contrast with organized paragraphs; a few duplicated words and punctuation marks remain.

> Weather refers to the short-term state of atmospheric conditions in a particular place, from day to day. It includes factors such as temperature, temperature, humidity, precipitation, wind speed, and visibility. Weather is variable and and can change quickly.
>
> Climate refers to the average state of atmospheric conditions over a longer period, such as years, decades, etc.. It includes factors such as temperature, humidity, precipitation, and, on average, wind speed. Climate is more stable and can change over time.
>
> In summary, weather is the short-term state of atmospheric conditions while climate is long-term average of atmospheric conditions.

**Average example — question 1**

**Prompt:** What do you know about Amsterdam?

**Metrics:** PPL 5.35; Distinct-1 0.540; 67/124 unique token types / total tokens.

**Selection note:** A mostly coherent Amsterdam overview with duplicated landmarks, repeated nightlife references, and a missing phrase.

> Amsterdam is the capital and largest city of the Netherlands. It is known for its rich history, culture, and architecture.. The city is famous for its picturesque canals, charming streets, and vibrant nightlife.. It is also home to a number of historic landmarks, museums, and galleries, such as the Anne Anne Frank House, Anne Frank House, and Van Gogh Museum. The city is also known for its, scene, and nightlife, with many cafes, bars, and music venues. Amsterdam is also known for its friendly people, cycling culture, and food, making it a popular destination from all over the world.

**Bad example — question 4**

**Prompt:** What makes a good friend?

**Metrics:** PPL 2.00; Distinct-1 0.089; 11/124 unique token types / total tokens.

**Selection note:** Almost the entire answer becomes a listens/and loop rather than usable advice.

> A good friend is someone who listens, listens,, listens, and, and, and,, and, and, and, and, and, and, and, and, and, and, and, and, and, and, and, and, and, and, and, and, and, and, and, and, and, and, and, and, and, and, and, and, and, and, and, and, and, and, and, and, and, and, and, and, and, and, and, and, and, and, and, and, and.

#### PMI Viterbi + diffusion confidence

**Good example — question 10**

**Prompt:** How does a search engine find relevant web pages?

**Metrics:** PPL 3.53; Distinct-1 0.532; 67/126 unique token types / total tokens.

**Selection note:** A coherent sequence of crawling, indexing, relevance ranking, and returning search results, without a major repetition loop.

> A search engine finds relevant web pages by using a web crawler, known as a spider or bot, to browse the internet and collect information about web pages. The crawler analyzes the content of each web page and stores it in a database. The database engine then uses various algorithms to rank the web pages based on their relevance to the search query. These algorithms take into account factors such as keywords, the location of the website, and the content of the web pages. When a user enters a search query, the search engine goes through the database and returns a list of web pages that are most relevant to the specific search query.

**Average example — question 9**

**Prompt:** Explain the basic idea behind supply and demand.

**Metrics:** PPL 2.29; Distinct-1 0.397; 50/126 unique token types / total tokens.

**Selection note:** The definitions are mostly understandable, but the equilibrium-price sentence becomes grammatically and conceptually muddled.

> The basic idea behind supply and demand is that the price of a good or service is determined by the interaction of the quantity supplied and the quantity demanded. Supply refers to the amount of a good or service that producers are willing and able to sell at a given price, while demand refers to the amount of a good or service that consumers are willing and able to buy at a given price. When supply and demand, the quantity of a good or service that is produced is sold at a particular price is known as the equilibrium price. In other words, the price of a good or service is determined by the balance between supply and demand.

**Bad example — question 1**

**Prompt:** What do you know about Amsterdam?

**Metrics:** PPL 3.95; Distinct-1 0.603; 76/126 unique token types / total tokens.

**Selection note:** Fluent prose still names Red Square as an Amsterdam landmark and repeats Anne Frank House. This is an obvious content failure rather than a grammatical collapse.

> Amsterdam is the capital and largest city of the Netherlands. It is known for its vibrant history, rich culture, and lively atmosphere. The city is famous for its iconic landmarks, such as the Red Square, Anne Frank House, and the Anne Frank House. Amsterdam is also renowned for its picturesque canals, which are lined by the historic buildings and bridges. The city is home to its famous museums, such as Rijksmuseum and Van Gogh Museum, and well-known markets, such as the Jordaan Market and the Central Market. Overall, Amsterdam is a popular tourist destination that attracts visitors from all over the world.

### NFE 64

#### Confidence-guided baseline

**Good example — question 4**

**Prompt:** What makes a good friend?

**Metrics:** PPL 3.27; Distinct-1 0.476; 60/126 unique token types / total tokens.

**Selection note:** A fluent, coherent paragraph describing supportive friendship, with no conspicuous broken wording or repetition loop.

> A good friend is someone who is caring, understanding, and supportive. They are there for you when you need them, and they listen to your thoughts and feelings. A good friend is also reliable and trustworthy, and they respect your boundaries and privacy. They are honest and authentic, and they are responsive to your needs and concerns. A good friend is also positive and encouraging, and they help you achieve your goals and dreams. They are patient and compassionate, and they are willing to learn and grow with you. Ultimately, a good friend is someone who enhances your life and well-being, and who makes you feel valued and loved.

**Average example — question 1**

**Prompt:** What do you know about Amsterdam?

**Metrics:** PPL 3.92; Distinct-1 0.496; 62/125 unique token types / total tokens.

**Selection note:** A readable but generic overview that repeats known for and includes canals canals and the malformed Van Gogh-Amuseum name.

> Amsterdam is the capital and largest city of the Netherlands. It is known for its rich history, beautiful architecture, and vibrant culture. The city is famous for its canals canals, which are a unique feature of the city.. Amsterdam is also known for its museums, including the Van Gogh-Amuseum and the Rijksmuseum. The city is known for its many unique shops, cafes, and restaurants. Amsterdam is also known for its vibrant cultural scene, with many festivals, concerts, and events taking place throughout the year. Overall, Amsterdam is known for its friendly people, beautiful scenery, and vibrant culture.

**Bad example — question 3**

**Prompt:** How do plants convert sunlight into energy?

**Metrics:** PPL 2.52; Distinct-1 0.580; 47/81 unique token types / total tokens.

**Selection note:** Mostly fluent text ends by saying the glucose is released into the atmosphere as a byproduct. The content error makes it a relative weak answer despite the readable surface.

> Plants convert sunlight into energy through a process called photosynthesis. During photosynthesis, energy from the sun is absorbed by chlorophyll in the plant's leaves. This energy is then used to convert carbon dioxide from the air, and water from the soil, into glucose, a type of sugar. This glucose is used by the plant for energy and growth, and is also released into the atmosphere as a byproduct.

#### PMI Viterbi + diffusion confidence

**Good example — question 9**

**Prompt:** Explain the basic idea behind supply and demand.

**Metrics:** PPL 1.97; Distinct-1 0.452; 57/126 unique token types / total tokens.

**Selection note:** A coherent explanation that defines supply, demand, and equilibrium price and stays on topic.

> The basic idea behind supply and demand is that the price of a good or service is determined by the amount of supply and demand for the product. Supply refers to the amount of a product or service that a producer is willing to sell at a given price, while demand refers to the amount of a product or service that a consumer is willing to buy at a given price. The interaction between supply and demand determines the equilibrium price, which is the price at which the quantity supplied equals the quantity demanded. This concept is fundamental to understanding how markets work and how changes in supply and demand can affect the price and quantity of goods and services.

**Average example — question 1**

**Prompt:** What do you know about Amsterdam?

**Metrics:** PPL 3.61; Distinct-1 0.548; 69/126 unique token types / total tokens.

**Selection note:** Mostly fluent descriptive prose, with generic repetition and a missing item in festivals, concerts, and taking place.

> Amsterdam is the capital and largest city of the Netherlands. It is known for its rich history, vibrant culture, and stunning architecture. The city is famous for its picturesque canals, which wind through the city, creating a unique and charming atmosphere. Amsterdam is also renowned for its thriving arts scene, with many cultural festivals, concerts, and taking place throughout the year. The city is also known for its excellent food scene, with many excellent restaurants and cafes serving traditional Dutch and international cuisine. Additionally, Amsterdam is home to numerous museums, galleries, and cultural institutions, making it a popular destination for history, culture, and the arts.

**Bad example — question 5**

**Prompt:** Explain how a refrigerator keeps food cold.

**Metrics:** PPL 3.46; Distinct-1 0.468; 59/126 unique token types / total tokens.

**Selection note:** It repeats coils and presents a confused refrigeration mechanism, including releasing cold refrigerant into the surrounding air.

> A refrigerator keeps food cold by using a combination of coils, coils, and insulation materials. The coils coils are located inside the refrigerator and are filled with a refrigerant. As the refrigerant flows through the coils, it absorbs heat from the air inside the refrigerator, cooling it down. The coils coils then release the cold refrigerant into the surrounding air, which lowers the temperature inside the refrigerator. The insulation materials inside the refrigerator also help to keep the cold air inside and prevent heat from escaping into the environment. As a result, the food inside the refrigerator is kept at a low temperature, which helps to preserve its freshness and prevent spoilage.

### NFE 128

#### Confidence-guided baseline

**Good example — question 9**

**Prompt:** Explain the basic idea behind supply and demand.

**Metrics:** PPL 2.10; Distinct-1 0.429; 54/126 unique token types / total tokens.

**Selection note:** A clear, complete explanation of supply, demand, and equilibrium, with consistent terminology.

> The basic idea behind supply and demand is that the price of a good or service is determined by the interaction between the quantity supplied and the quantity demanded. Supply refers to the quantity of a good or service that producers are willing and able to sell at various prices, while demand refers to the quantity of a good or service that consumers are willing and able to buy at various prices. The price of a good or service at which the quantity supplied equals the quantity demanded is called the equilibrium price. At the equilibrium price, the market is in balance, and there is no oversupply or shortfall between the quantity supplied and the quantity demanded.

**Average example — question 1**

**Prompt:** What do you know about Amsterdam?

**Metrics:** PPL 2.39; Distinct-1 0.579; 73/126 unique token types / total tokens.

**Selection note:** A readable and relevant Amsterdam overview that uses several generic known for and also constructions, typical of the stronger outputs here.

> Amsterdam is the capital and largest city of the Netherlands. It is known for its rich history, beautiful architecture, and vibrant culture. The city is famous for its canals, which are a distinctive feature of the cityscape. Amsterdam is also home to many world-class museums, including the Rijksmuseum, the Van Gogh Museum, and the Anne Frank House. The city is also known for its lively nightlife and food scene, with many restaurants, cafes, and music venues. Overall, Amsterdam is a city that combines history, culture, and modernity, making it a popular destination for visitors from all over the world.

**Bad example — question 5**

**Prompt:** Explain how a refrigerator keeps food cold.

**Metrics:** PPL 2.25; Distinct-1 0.127; 16/126 unique token types / total tokens.

**Selection note:** Even at 128 NFE, this answer collapses into a long cold air loop and never explains the heat-transfer mechanism.

> A refrigerator keeps food cold by using a small fan to circulate the cold air and the cold air and the cold air and the cold air and the cold air and the cold air and the cold air and the cold air and the cold air and the cold air and the cold air and the cold air and the air and the cold air and the cold air and the cold air and the cold air and the cold air and the cold air and the cold air and the cold air and the cold air and the cold air and the cold air and the cold air and the cold air and the cold air and the cold air and the air.

#### PMI Viterbi + diffusion confidence

**Good example — question 3**

**Prompt:** How do plants convert sunlight into energy?

**Metrics:** PPL 1.92; Distinct-1 0.556; 70/126 unique token types / total tokens.

**Selection note:** A coherent photosynthesis explanation with consistent reactants/products and a balanced summary equation.

> Plants convert sunlight into energy through a process called photosynthesis. During photosynthesis, plants absorb energy from the sun through the chlorophyll pigments in their leaves. This energy is then used to convert carbon dioxide (CO2) and water (H2O) into glucose (a type of sugar) and oxygen (O2). The glucose produced is used by the plant for energy and growth, while the oxygen is released into the atmosphere. The process can be summarized by the equation: 6CO2 + 6H2O + light energy → C6H12O6 (glucose) + 6O2.

**Average example — question 8**

**Prompt:** What is the difference between weather and climate?

**Metrics:** PPL 2.70; Distinct-1 0.484; 61/126 unique token types / total tokens.

**Selection note:** The main distinction is clear, but the time-scale examples are vague and the concluding summary repeats the earlier definition.

> Weather refers to the short-term atmospheric conditions in a specific location, such as temperature, humidity, precipitation, and wind speed. These conditions can vary from day to day, and even from hour to hour. Climate, on the other hand, refers to the long-term average weather patterns in a particular region over a period of time, such as a year or a decade. It is the result of the cumulative effects of weather patterns over a longer period of time. In summary, weather is the current and temporary state of the atmosphere in a specific location, while climate is the average of those atmospheric conditions over a longer period of time.

**Bad example — question 1**

**Prompt:** What do you know about Amsterdam?

**Metrics:** PPL 2.45; Distinct-1 0.548; 69/126 unique token types / total tokens.

**Selection note:** A relative weak example, not a collapse: it remains fluent but lists Anne Frank House twice and repeats generic descriptions of the city.

> Amsterdam is the capital and largest city of the Netherlands. It is known for its rich history, vibrant culture, and lively atmosphere. The city is famous for its picturesque canals, beautiful architecture, and iconic landmarks such as the Anne Frank House, the Royal Palace, and the Anne Frank House. Amsterdam is also renowned for its thriving arts scene, with numerous museums, galleries, and theaters. The city is a popular destination for tourists and is known for its charming streets, trendy shops, and lively nightlife. Amsterdam is a city that offers a unique blend of tradition and modernity, making it a fascinating destination for visitors and residents alike.


