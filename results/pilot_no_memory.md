# No-memory pilot

Layouts 50,000 and up, which no reported result uses. One try per layout, no memory. Final code (hash 4d59e8f26cd2a9b6), run 16 Nov 2026 after the last round of fixes; layouts 50000+, excluded from every result. The earlier pilot on the previous code gave Haiku 1, 8, 8 and Luna 7, 8, 7 of 8 on stack, bins and flasks, so eight layouts per cell is noisy.

| model | tools | task | episodes | success | mean calls | said done but wrong | dollars per episode |
|---|---|---|---|---|---|---|---|
| claude-haiku-5-5 | pose | stack | 6 | 2/6 | 55.3 | 2 | $0.0080 |
| claude-haiku-5-5 | pose | bins | 6 | 6/6 | 24.5 | 0 | $0.0021 |
| claude-haiku-5-5 | pose | flasks | 6 | 4/6 | 35.8 | 2 | $0.0056 |
| claude-haiku-5-5 | skills | stack | 8 | 4/8 | 17.9 | 1 | $0.0024 |
| claude-haiku-5-5 | skills | bins | 8 | 6/8 | 19.0 | 1 | $0.0019 |
| claude-haiku-5-5 | skills | flasks | 8 | 8/8 | 9.0 | 0 | $0.0011 |
| gpt-6-luna | pose | stack | 6 | 3/6 | 22.7 | 3 | $0.0030 |
| gpt-6-luna | pose | bins | 6 | 4/6 | 29.2 | 2 | $0.0040 |
| gpt-6-luna | pose | flasks | 6 | 5/6 | 21.7 | 1 | $0.0027 |
| gpt-6-luna | skills | stack | 8 | 7/8 | 8.4 | 1 | $0.0009 |
| gpt-6-luna | skills | bins | 8 | 7/8 | 15.2 | 0 | $0.0019 |
| gpt-6-luna | skills | flasks | 8 | 8/8 | 13.0 | 0 | $0.0016 |
