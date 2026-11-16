# No-memory pilot

Layouts 50,000 and up, which no reported result uses. One try per layout, no memory. Final code (protocol 1.3). Skills tools: call budget 20, 8 layouts per job (50,000 to 50,007). Pose tools (no pick or place): call budget 60, 6 layouts per job. Haiku 5.5 and GPT-6 Luna.

| model | tools | task | episodes | success | mean calls | said done but wrong | dollars per episode |
|---|---|---|---|---|---|---|---|
| claude-haiku-5-5 | pose | stack | 6 | 2/6 | 54.7 | 1 | $0.0080 |
| claude-haiku-5-5 | pose | bins | 6 | 6/6 | 25.3 | 0 | $0.0022 |
| claude-haiku-5-5 | pose | flasks | 6 | 1/6 | 41.0 | 4 | $0.0069 |
| claude-haiku-5-5 | skills | stack | 8 | 1/8 | 19.9 | 0 | $0.0026 |
| claude-haiku-5-5 | skills | bins | 8 | 8/8 | 18.8 | 0 | $0.0019 |
| claude-haiku-5-5 | skills | flasks | 8 | 8/8 | 10.2 | 0 | $0.0010 |
| gpt-6-luna | pose | stack | 6 | 2/6 | 21.7 | 4 | $0.0028 |
| gpt-6-luna | pose | bins | 6 | 5/6 | 28.0 | 1 | $0.0037 |
| gpt-6-luna | pose | flasks | 6 | 5/6 | 18.8 | 1 | $0.0021 |
| gpt-6-luna | skills | stack | 8 | 7/8 | 7.9 | 1 | $0.0009 |
| gpt-6-luna | skills | bins | 8 | 8/8 | 15.0 | 0 | $0.0018 |
| gpt-6-luna | skills | flasks | 8 | 7/8 | 11.5 | 1 | $0.0014 |
