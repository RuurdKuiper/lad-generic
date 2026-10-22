# Live integration examples

One prompt, seed 1234, 32 new tokens, block length 16, four total denoising evaluations, temperature 2, top-k 16, EOS/EOT retention delay enabled, ending strength 10, early stopping disabled. These are smoke checks, not a quality benchmark.

## Ruurd/byod-gemma-2-9b: original

```text
Amsterdam is the capital city of the Netherlands, Netherlands. It is the city of canals, and canals and canals and canals and canals, and canals.
```

## Ruurd/byod-gemma-2-9b: gamma_zero

```text
Amsterdam is the capital city of the Netherlands, Netherlands. It is the city of canals, and canals and canals and canals and canals, and canals.
```

## Ruurd/byod-gemma-2-9b: gamma_one

```text
Amsterdam is the capital city of the Netherlands, Netherlands. It is a city of canals, and canals, and canals and canals and culture.
```

## Ruurd/byod-gemma-2-9b: gamma_ten

```text
Amsterdam is the capital city of the Netherlands, Netherlands). It is a city, which is the capital of the Netherlands, Amsterdam, and Zealand, etc.
```

## Ruurd/llada-8b-instruct: original

```text
Amsterdam is the city of the city of the city of the city of the city of the city of the city of the city of the city.
```

## Ruurd/llada-8b-instruct: gamma_zero

```text
Amsterdam is the city of the city of the city of the city of the city of the city of the city of the city of the city.
```

## Ruurd/llada-8b-instruct: gamma_one

```text
Amsterdam is the city of the Netherlands. It is known for its canals, museums,, and museums, and its history of art and culture..
```

## Ruurd/llada-8b-instruct: gamma_ten

```text
Amsterdam is the city of the Netherlands, and it is known for its history, culture, and architecture. So, you do you know something else?
```
