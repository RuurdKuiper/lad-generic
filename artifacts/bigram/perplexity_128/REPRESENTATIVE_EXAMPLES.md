## Representative examples by NFE and decoding method

Both methods use the same Gemma model. These examples come from the 10-question, 128-token-limit experiment.

I read all saved answers and selected a good, average, and bad example within each method/NFE group. Selection considers readability, relevance, coherence, repetition, and obvious content problems; it is not based on perplexity rank and is not a comprehensive factual audit. Average means typical of the group, not the mathematical median. Selections are made independently within each group, so prompts can differ between methods.

**The labels are relative.** Good means one of the stronger answers in that group, not necessarily an acceptable answer. At low NFE even good examples can be flawed; at high NFE a bad example can still be mostly fluent. These are illustrative selections, not a separate benchmark score.

Full outputs are quoted verbatim, including duplicated words, punctuation, line breaks, and unfinished endings. PPL is per-answer Phi-4 perplexity. Distinct-1 is unique token types / total tokens in the complete answer, using the model’s native tokenizer and excluding special tokens. Unique-token counts are shown alongside the ratios.

### NFE 8

#### Confidence-guided baseline

**Good example — question 8**

**Prompt:** What is the difference between weather and climate?

**Metrics:** PPL 41.66; Distinct-1 0.512; 21/41 unique token types / total tokens.

**Selection note:** One of the more recognizable answers in this group: it retains the short-term versus long-term distinction, despite broken grammar and an unfinished ending.

> Weather is the short- conditions, conditions of a specific at a particular time,, and temperature. climate climate is the the the the the average- of a a a region over of a a a a a

**Average example — question 3**

**Prompt:** How do plants convert sunlight into energy?

**Metrics:** PPL 42.37; Distinct-1 0.360; 18/50 unique token types / total tokens.

**Selection note:** Relevant photosynthesis terms are present, but duplication and punctuation fragments prevent a coherent explanation.

> Plants convert sunlight sunlight into energy energy process process process called as called called,,, photosynthesis, process,,, water,,,,, and carbon,,, and, to,, glucose, and, into glucose, and oxygen,,, and,,, oxygen, and oxygen,,, glucose,, energy,,,

**Bad example — question 5**

**Prompt:** Explain how a refrigerator keeps food cold.

**Metrics:** PPL 7.08; Distinct-1 0.143; 15/105 unique token types / total tokens.

**Selection note:** A long loop of function words and temperature/refrigerator fragments overwhelms the initial idea.

> A refrigerator keeps food cold by using a refrigerant that absorbs absorbs the the the the of the the air of the the the the the temperature of the refrigerator of the the the the the the the temperature of the the the of the the the of the the the the the the the the of the the the the the temperature temperature the of the temperature of the temperature of the refrigerator of the refrigerator of the the of the temperature of the refrigerator of the the of the temperature of the refrigerator of the temperature of of the temperature of the of

#### PMI Viterbi + diffusion confidence

**Good example — question 10**

**Prompt:** How does a search engine find relevant web pages?

**Metrics:** PPL 19.60; Distinct-1 0.595; 25/42 unique token types / total tokens.

**Selection note:** A relatively short, recognizable search-engine answer. Grammar is awkward and links/algorithms repeat, so this is only good relative to this weak group.

> A search engine uses relevant web pages by using a variety of algorithms, such as keywords, and content, and algorithms, and links, and links, and algorithms, and analyzing the quality of the search page.

**Average example — question 6**

**Prompt:** Why do we have different seasons on Earth?

**Metrics:** PPL 12.61; Distinct-1 0.360; 32/89 unique token types / total tokens.

**Selection note:** It identifies axial tilt, but the subsequent causal explanation becomes garbled and repeatedly refers to Earth and its axis.

> We have different seasons on the Earth because the tilt of the Earth's axis around the axis of the Sun. This causes changes the amount of the Earth's surface that receives sunlight by the Earth's axis, the angle of the Earth at the Earth's orbit the Earth's because the Earth's of the Earth's axis is directly from the Sun. This causes seasons of the amount of the surface of the Earth.

**Bad example — question 1**

**Prompt:** What do you know about Amsterdam?

**Metrics:** PPL 2.24; Distinct-1 0.108; 11/102 unique token types / total tokens.

**Selection note:** The answer collapses into 45 occurrences of Netherlands. Its very low perplexity illustrates why examples were not selected by perplexity rank.

> Amsterdam is the capital city of the Netherlands, Netherlands, Netherlands, Netherlands, Netherlands, Netherlands, Netherlands, Netherlands, Netherlands, Netherlands,, and Netherlands, Netherlands, Netherlands, and Netherlands, and Netherlands, and Netherlands, and Netherlands, Netherlands, Netherlands, Netherlands, Netherlands, Netherlands, Netherlands, Netherlands, Netherlands, Netherlands, Netherlands, Netherlands, Netherlands, Netherlands, Netherlands, Netherlands, Netherlands, Netherlands, Netherlands, Netherlands, Netherlands, Netherlands, Netherlands, Netherlands, Netherlands, Netherlands, Netherlands, Netherlands, Netherlands.

### NFE 16

#### Confidence-guided baseline

**Good example — question 3**

**Prompt:** How do plants convert sunlight into energy?

**Metrics:** PPL 15.39; Distinct-1 0.600; 30/50 unique token types / total tokens.

**Selection note:** One of the more informative attempts: it names photosynthesis and its main vocabulary. It still repeats words, muddles the mechanism, and includes the nonsensical phrase oxygen dioxide.

> Plants convert sunlight sunlight into energy energy through the process called photosynthesis photosynthesis.. During photosynthesis chlorophyll, sunlight, carbon, dioxide, and water, combine to produce glucose and oxygen, and oxygen dioxide. Glucose is then a the source the energy. of energy.

**Average example — question 5**

**Prompt:** Explain how a refrigerator keeps food cold.

**Metrics:** PPL 10.09; Distinct-1 0.333; 24/72 unique token types / total tokens.

**Selection note:** The intended inside-to-outside heat transfer is partly recognizable, but missing words, duplicated articles, and confused wording make the explanation difficult to follow.

> A refrigerator keeps food cold by using a refrigerant to that absorbs the the the heat of the food. the refrigerator coils of the refrigerant is in the inside of the refrigerator and the refrigerant releases the the heat of of the food to the the outside of the the refrigerator. the the temperature of the the refrigerant is in the outside of of the outside of the refrigerator.

**Bad example — question 9**

**Prompt:** Explain the basic idea behind supply and demand.

**Metrics:** PPL 5.96; Distinct-1 0.242; 22/91 unique token types / total tokens.

**Selection note:** Repeated quantity/price fragments fail to explain the relationship between supply, demand, and price.

> Supply and demand is the idea that the price of a product is primarily determined on the quantity of the product available and the the quantity of the product, and the quantity the price of the product. When the quantity of product, the quantity of product the the quantity of the product, and the the price of the product, the more the price of the product. When the less of the quantity of the product, then the less the price of the product.

#### PMI Viterbi + diffusion confidence

**Good example — question 10**

**Prompt:** How does a search engine find relevant web pages?

**Metrics:** PPL 21.66; Distinct-1 0.612; 30/49 unique token types / total tokens.

**Selection note:** Mostly follows a coherent search-engine explanation and stays relevant, with grammatical errors and some duplicated keywords.

> A search engine finds relevant web pages by using a complex algorithms to analyze the content of the web content, including links,, keywords, and keywords, and location, and ranking of pages on the web, and matching the search of the user query.

**Average example — question 1**

**Prompt:** What do you know about Amsterdam?

**Metrics:** PPL 6.60; Distinct-1 0.435; 30/69 unique token types / total tokens.

**Selection note:** The answer gives recognizable facts about Amsterdam but keeps revisiting canals, nightlife, culture, and museums.

> Amsterdam is the capital city of the Netherlands, Netherlands. It is the center of the Netherlands, and is one of the most popular tourist cities in the world. It is known primarily for its canals, and canals, and nightlife, and culture, and nightlife.. It is also known for its museums, and museums, and culture, and nightlife...

**Bad example — question 9**

**Prompt:** Explain the basic idea behind supply and demand.

**Metrics:** PPL 4.06; Distinct-1 0.202; 22/109 unique token types / total tokens.

**Selection note:** The output repeatedly cycles through quantity and price without developing a meaningful explanation.

> Supply and demand is a basic economic principle that the relationship between the quantity of a product that the market is willing depends on the quantity of the price of the price of the product. The quantity of the product is the quantity of the price of the product is the quantity of the price of the product. The quantity of the product is the quantity of the price of the product is the quantity of the price of the price of the product. The quantity quantity of the product is the quantity of the price of the product of the product of the product.

### NFE 32

#### Confidence-guided baseline

**Good example — question 9**

**Prompt:** Explain the basic idea behind supply and demand.

**Metrics:** PPL 4.46; Distinct-1 0.484; 30/62 unique token types / total tokens.

**Selection note:** A clear, largely coherent explanation of how high supply/low demand and low supply/high demand affect price, with minor wording errors.

> Supply and demand is the idea that the price of a good or service is the interaction between the quantity of it and the quantity of people wanting for it. When supply is high and the demand is low, the price will decrease. When supply is very low and the demand is high, the price will increase.

**Average example — question 8**

**Prompt:** What is the difference between weather and climate?

**Metrics:** PPL 15.65; Distinct-1 0.589; 33/56 unique token types / total tokens.

**Selection note:** The main weather/climate distinction is recognizable, but duplicated punctuation and the malformed at least00 years ending weaken it.

> Weather is the short-term atmospheric conditions of a particular place at a time, including, but temperature,, humidity,, and precipitation. Climate, is the long-term average of the weather and other atmospheric conditions of a particular place over a period of of at least00 years.

**Bad example — question 10**

**Prompt:** How does a search engine find relevant web pages?

**Metrics:** PPL 13.96; Distinct-1 0.339; 38/112 unique token types / total tokens.

**Selection note:** A relevant opening develops into repeated crawling/ranking fragments and broken sentences about pages and search results.

> A search engine finds relevant web pages by using algorithms for web crawling, crawling, indexing, and ranking, crawling,, and ranking, which involves analyzing the content of the web pages, identifying the keywords, keywords used, and links, and ranking the pages of websites based the relevance of the. In the keywords of the process, the search engine the web of the pages of the websites, and then ranks the based the relevance of the pages. the search engine then displays results of the rankings of the pages. the search results of the rankings of the pages pages.

#### PMI Viterbi + diffusion confidence

**Good example — question 10**

**Prompt:** How does a search engine find relevant web pages?

**Metrics:** PPL 6.18; Distinct-1 0.500; 42/84 unique token types / total tokens.

**Selection note:** A coherent sequence of crawling, content analysis, and ranking. The duplicated Then and awkward final wording are minor relative to the other answers here.

> A search engine finds relevant web pages by using a combination of algorithms, including web crawling, text analysis, and ranking algorithms. The process starts by web crawling, where the search engine automatically visits web pages and analyzes their content. Then. Then, the engine analyzes the text on the page and determines the relevance of the web page. Finally, the engine uses a ranking algorithm to rank the web pages by the search query.

**Average example — question 8**

**Prompt:** What is the difference between weather and climate?

**Metrics:** PPL 5.69; Distinct-1 0.423; 33/78 unique token types / total tokens.

**Selection note:** The main distinction is conveyed, but the answer repeatedly restates long periods, weather conditions, temperature, and humidity.

> Weather refers to the atmospheric conditions in a particular place at a particular time, while climate refers to the average weather or weather conditions over a long period over a long period of a region. Weather refers to factors such as the temperature,, humidity, humidity, and precipitation, while climate refers to the average temperature, average temperature, humidity, and precipitation in a region over a long period of time.

**Bad example — question 4**

**Prompt:** What makes a good friend?

**Metrics:** PPL 4.89; Distinct-1 0.208; 26/125 unique token types / total tokens.

**Selection note:** A plausible opening degenerates into a long list of repeated They are trustworthy and They are willing phrases.

> A good friend is someone who is trustworthy, trustworthy, and supportive, understanding, and supportive. They are willing to listen and advice, and they are willing to help when you need.
>
> . They are trustworthy.
> . They. They are trustworthy..
> . They. They are trustworthy.
> . They are trustworthy.
> . They are trustworthy.
> .. They are willing to listen advice.
> . They are willing to listen advice.
> . They are willing to listen advice.
> . They are willing to listen advice.
> . They are willing to help advice.
> . They are willing to help advice.

### NFE 64

#### Confidence-guided baseline

**Good example — question 10**

**Prompt:** How does a search engine find relevant web pages?

**Metrics:** PPL 3.96; Distinct-1 0.617; 50/81 unique token types / total tokens.

**Selection note:** A coherent explanation of crawling, indexing, ranking, and query interpretation, with a small omission in natural language.

> A search engine finds relevant web pages by using a combination of algorithms and techniques, including web crawling, indexing, ranking, and natural language. It crawls the web pages, extracts the text, analyzes and stores them in an index, and then ranks the pages based on their relevance to the search query. It also uses natural language processing to understand the intent of the search query and return the most relevant results.

**Average example — question 8**

**Prompt:** What is the difference between weather and climate?

**Metrics:** PPL 4.31; Distinct-1 0.520; 39/75 unique token types / total tokens.

**Selection note:** The distinction is mostly clear, with duplicated words and an awkward final sentence that restates the point.

> Weather is the short-term state of the atmospheric conditions in a a particular location, such as temperature, humidity, and precipitation. Climate is the long-term average of the weather conditions in a particular location, over a period of at least 30 years. Weather is the day of weather, while climate is the average of the weather over a long period of time.

**Bad example — question 5**

**Prompt:** Explain how a refrigerator keeps food cold.

**Metrics:** PPL 4.54; Distinct-1 0.337; 33/98 unique token types / total tokens.

**Selection note:** The answer starts with the right heat-transfer idea but repeatedly loops through inside/outside wording and fails to explain a clear cycle.

> A refrigerator keeps food cold by using a refrigerant to absorb heat from the inside of the refrigerator and release it to the outside. The refrigerant absorbs the heat from inside the the inside of the refrigerator and releases it to the outside the the inside of the the outside of the refrigerator. As the refrigerant evaporates the heat from inside the refrigerator, releases the heat from the the inside of the refrigerator to the outside of the refrigerator. This process helps maintain the temperature of the the inside of the refrigerator.

#### PMI Viterbi + diffusion confidence

**Good example — question 9**

**Prompt:** Explain the basic idea behind supply and demand.

**Metrics:** PPL 2.38; Distinct-1 0.448; 39/87 unique token types / total tokens.

**Selection note:** A fluent, relevant supply-and-demand explanation with a clear relationship between scarcity, demand, and price.

> Supply and demand is an economic principle that describes the relationship between the quantity of a product that is available, and the quantity of the product that consumers want to purchase. When demand is high and supply is low, the price of the product will increase. When demand is low and supply is high, the price of the product will decrease. This principle is the basis of the market economy and helps to determine the price of goods and services.

**Average example — question 4**

**Prompt:** What makes a good friend?

**Metrics:** PPL 4.72; Distinct-1 0.519; 41/79 unique token types / total tokens.

**Selection note:** Mostly fluent and relevant, but the missing verb in also to celebrate and the unfinished final They show remaining generation errors.

> A good friend is someone who is trustworthy, loyal, honest, supportive, and understanding. They are willing to listen to your problems and concerns, and they are willing to help you through difficult times. They are also to celebrate your successes and achievements and to support you in your goals. They are willing to accept your flaws and imperfections, and they are willing to forgive you for your mistakes. They

**Bad example — question 5**

**Prompt:** Explain how a refrigerator keeps food cold.

**Metrics:** PPL 3.54; Distinct-1 0.359; 46/128 unique token types / total tokens.

**Selection note:** The answer mixes up the refrigeration mechanism, repeats much of the heat-transfer description, and ends mid-sentence.

> A refrigerator keeps food cold by using a system called a refrigerant. The refrigerant absorbs heat from the air inside the refrigerator and releases it into the air outside the refrigerator. The refrigerant is circulated through a series of coils, which are located by the evaporator and the condenser. The evaporator is located on the inside walls of the refrigerator, while the condenser is located on the outside of the refrigerator door. The refrigerant absorbs heat from the air inside the refrigerator through the evaporator, and releases it into the air outside the refrigerator through the condenser. The process of the refrigerant is driven by a compressor, which turns the refrigerant into a liquid and then it into a

### NFE 128

#### Confidence-guided baseline

**Good example — question 2**

**Prompt:** Why is the sky blue?

**Metrics:** PPL 4.14; Distinct-1 0.692; 36/52 unique token types / total tokens.

**Selection note:** A concise, coherent explanation naming Rayleigh scattering and connecting it to the observed sky color.

> The sky is blue because of a phenomenon known as Rayleigh scattering. When sunlight enters the atmosphere, it is scattered by the molecules in the air. Blue light is scattered more than the other colors in the spectrum, which is why we see the sky as blue.

**Average example — question 3**

**Prompt:** How do plants convert sunlight into energy?

**Metrics:** PPL 3.25; Distinct-1 0.671; 47/70 unique token types / total tokens.

**Selection note:** The main photosynthesis explanation is understandable, but the final relative clause is malformed and chlorophyll is duplicated.

> Plants convert sunlight into energy through the process of photosynthesis. During photosynthesis, plants use the energy from sunlight to convert carbon dioxide and water into glucose, a type of sugar that serves as energy for the plant. This process takes place in the chloroplasts of plants, which are organelles contain chlorophyll chlorophyll, which is the pigment that gives plants their green color.

**Bad example — question 5**

**Prompt:** Explain how a refrigerator keeps food cold.

**Metrics:** PPL 3.69; Distinct-1 0.308; 28/91 unique token types / total tokens.

**Selection note:** The initial heat-transfer explanation is followed by repetitive, largely unintelligible inside/outside-temperature sentences.

> A refrigerator keeps food cold by using a refrigerant to absorb heat from the inside of the refrigerator and release it to the outside. The refrigerant circulates the temperature of the inside of the refrigerator and the temperature of the outside of the outside of the refrigerator. As the refrigerant absorbs the heat from inside the inside of the refrigerator to the outside of the refrigerator, the temperature of the inside of the refrigerator and the temperature of the outside of the inside of the refrigerator.

#### PMI Viterbi + diffusion confidence

**Good example — question 4**

**Prompt:** What makes a good friend?

**Metrics:** PPL 3.86; Distinct-1 0.673; 35/52 unique token types / total tokens.

**Selection note:** A clear, relevant, complete paragraph with no conspicuous grammatical errors or repetition loops.

> A good friend is someone who is trustworthy, loyal, honest, supportive, and understanding. They are willing to listen to your problems, offer advice, and support you through tough times. They are also able to celebrate your successes and help you achieve your goals.

**Average example — question 8**

**Prompt:** What is the difference between weather and climate?

**Metrics:** PPL 3.59; Distinct-1 0.588; 40/68 unique token types / total tokens.

**Selection note:** The main distinction is clear, but the final sentence awkwardly repeats the short-term/long-term explanation.

> Weather refers to the atmospheric conditions at a particular location and time, such as temperature, humidity, precipitation, and wind speed. Climate refers to the average weather patterns over a long period of time, such as decades or centuries. Weather is a short-term condition of a time, while climate is a long-term average of weather patterns.

**Bad example — question 5**

**Prompt:** Explain how a refrigerator keeps food cold.

**Metrics:** PPL 2.62; Distinct-1 0.398; 43/108 unique token types / total tokens.

**Selection note:** A relative weak example rather than a collapse: it reads fluently, but the compressor/liquid/gas sequence is confused and the cycle is described repetitively.

> A refrigerator keeps food cold by using a substance called a refrigerant. The refrigerant absorbs heat from the air inside the refrigerator and releases it to the outside of the refrigerator. The refrigerant is circulated by a compressor, which turns the refrigerant into a liquid and then turns it into a gas. The refrigerant then passes through the condenser, where it releases heat to the outside of the refrigerator. The refrigerant then passes through the evaporator, where it absorbs heat from the air inside the refrigerator. The refrigerant is then returned to the compressor and the process is repeated.

