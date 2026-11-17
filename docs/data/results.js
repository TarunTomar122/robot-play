/* Numbers behind the charts on docs/index.html.
   Every value is copied from results/RESULTS.md (section numbers in the "src" fields).
   If a number here ever differs from RESULTS.md, RESULTS.md is right. */
window.RESULTS = {
  /* Registered comparison: held-out success, no memory against own notebook. RESULTS.md sections 2. */
  q1: {
    src: "RESULTS.md section 2",
    unit: "%",
    a: "Keeps a notebook",
    b: "No memory",
    groups: [
      { name: "Claude Haiku 5.5", rows: [
        { label: "All three jobs", a: 99, b: 76, tip: "Haiku, all three jobs (116 held-out episodes per condition): 99% with a notebook, 76% with no memory. Difference +23.3 points, 97.5% interval +14.0 to +32.6. Registered." },
        { label: "stack", a: 100, b: 32, tip: "Haiku, stack: 100% against 32%. Difference +67.5 points, 95% interval +52.5 to +82.5." },
        { label: "bins", a: 98, b: 100, tip: "Haiku, bins: 98% against 100%. Difference -2.5 points, 95% interval -10.4 to +5.4." },
        { label: "flasks", a: 100, b: 97, tip: "Haiku, flasks: 100% against 97%. Difference +2.8 points, 95% interval -6.0 to +11.5." }
      ] },
      { name: "GPT-6 Luna", rows: [
        { label: "All three jobs", a: 100, b: 91, tip: "Luna, all three jobs (116 held-out episodes per condition): 100% with a notebook, 91% with no memory. Difference +8.6 points, 97.5% interval +1.2 to +16.0. Registered." },
        { label: "stack", a: 100, b: 100, tip: "Luna, stack: 100% against 100%. Difference 0.0 points, 95% interval -6.5 to +6.5." },
        { label: "bins", a: 100, b: 92, tip: "Luna, bins: 100% against 92%. Difference +7.5 points, 95% interval -2.5 to +17.5." },
        { label: "flasks", a: 100, b: 81, tip: "Luna, flasks: 100% against 81%. Difference +19.4 points, 95% interval -1.6 to +40.4." }
      ] }
    ]
  },

  /* Calls to success, lower is better. RESULTS.md section 3. */
  calls: {
    src: "RESULTS.md section 3",
    unit: " calls",
    a: "Keeps a notebook",
    b: "No memory",
    max: 20,
    rows: [
      { label: "Claude Haiku 5.5", a: 9.9, b: 15.6, tip: "Haiku: 15.6 calls with no memory, 9.9 with a notebook. Difference -5.7 calls, 95% interval -6.5 to -4.9." },
      { label: "GPT-6 Luna", a: 8.1, b: 12.1, tip: "Luna: 12.1 calls with no memory, 8.1 with a notebook. Difference -4.0 calls, 95% interval -4.9 to -3.2." }
    ]
  },

  /* Haiku on stack, no practice, one fixed text in the memory slot. RESULTS.md sections 6d and 6g (run seeds 20 to 29, 40 episodes per row). */
  ladder: {
    src: "RESULTS.md sections 6d and 6g",
    unit: "%",
    rows: [
      { label: "No memory", v: 50, base: true, tip: "No memory: 50% of 40 held-out episodes." },
      { label: "A neutral sentence", v: 40, tip: "The neutral sentence that names no setting and gives no advice: 40%." },
      { label: "Opening sentence only", v: 50, tip: "Only the opening sentence (\"Defaults do not suit every object or surface.\"): 50%." },
      { label: "Opening sentence and an instruction to change the call", v: 70, tip: "The opening sentence and the instruction to change how the tool is called, with no setting names: 70%. Difference from no memory +20.0 points, 95% interval -10.2 to +50.2." },
      { label: "Opening sentence and the four setting names", v: 92, tip: "The opening sentence and the four setting names: 92%. Difference from no memory +42.5 points, 95% interval +20.1 to +64.9." },
      { label: "All three parts together", v: 92, tip: "Opening sentence, instruction and names together: 92%. Difference from no memory +42.5 points, 95% interval +21.8 to +63.2." },
      { label: "A sentence that names the fix", v: 100, tip: "\"Pick the green cube with grip_level firm.\" 100%." },
      { label: "Own notebook, 12 practice episodes", v: 100, tip: "The model's own notebook, 12 practice episodes: 100%." }
    ]
  },

  /* Haiku on stack, own notebook after n practice episodes, 20 runs pooled. RESULTS.md section 6i. */
  dose: {
    src: "RESULTS.md section 6i",
    unit: "%",
    a: "Solved within the 20 calls",
    b: "Solved within 10 calls",
    rows: [
      { label: "No memory", a: 49, b: 18, tip: "No memory: 49% within 20 calls, 18% within 10 (80 held-out episodes)." },
      { label: "1 practice episode", a: 85, b: 50, tip: "1 practice episode: 85% within 20 calls, 50% within 10. Against no memory +36.2 points, 95% interval +20.4 to +52.1." },
      { label: "3 practice episodes", a: 94, b: 75, tip: "3 practice episodes: 94% within 20 calls, 75% within 10. Against no memory +45.0 points, 95% interval +30.5 to +59.5." },
      { label: "6 practice episodes", a: 90, b: 72, tip: "6 practice episodes: 90% within 20 calls, 72% within 10. Against no memory +41.2 points, 95% interval +20.7 to +61.8." },
      { label: "12 practice episodes", a: 100, b: 89, tip: "12 practice episodes: 100% within 20 calls, 89% within 10. Against 1 episode +15.0 points, 95% interval +4.7 to +25.3." }
    ]
  },

  /* A notebook written by another model, read with no practice. RESULTS.md section 6e. 20 runs per model. */
  borrowed: {
    src: "RESULTS.md section 6e",
    unit: "%",
    groups: [
      { name: "Claude Haiku 5.5 (20 runs)", rows: [
        { label: "No memory", v: 71, base: true, tip: "Haiku with no memory: 71% (15.7 calls per solved episode)." },
        { label: "Its own notebook", v: 100, tip: "Haiku with its own notebook: 100% (9.1 calls)." },
        { label: "Sonnet's notebook, no practice", v: 100, tip: "Haiku reading Sonnet's notebook with no practice of its own: 100% (8.0 calls)." }
      ] },
      { name: "GPT-6 Luna (20 runs)", rows: [
        { label: "No memory", v: 94, base: true, tip: "Luna with no memory: 94% (11.2 calls)." },
        { label: "Its own notebook", v: 100, tip: "Luna with its own notebook: 100% (7.1 calls)." },
        { label: "Sonnet's notebook, no practice", v: 100, tip: "Luna reading Sonnet's notebook with no practice of its own: 100% (7.8 calls)." }
      ] }
    ]
  },

  /* The two-sided job with and without an error message. RESULTS.md sections 6m and 6n. 40 layouts per cell. */
  mixed: {
    src: "RESULTS.md sections 6m and 6n",
    unit: "%",
    a: "With an error message",
    b: "No error message",
    groups: [
      { name: "Claude Haiku 5.5", rows: [
        { label: "No memory", a: 50, b: 35, tip: "Haiku, no memory: 50% with the message, 35% without." },
        { label: "Sentence listing the four settings", a: 90, b: 45, tip: "Haiku, sentence listing the four settings: 90% with the message, 45% without." },
        { label: "Wrong rule: firm for every cube", a: 72, b: 0, tip: "Haiku, \"pick every cube with grip_level firm\": 72% with the message, 0% without. Difference -72.5 points, 95% interval -86.9 to -58.1." },
        { label: "Own notebook, 12 episodes", a: 82, b: 28, tip: "Haiku, own notebook: 82% with the message, 28% without. Difference -55.0 points, 95% interval -86.3 to -23.7." },
        { label: "Procedure written by us", a: 100, b: 100, tip: "Haiku, written procedure (try the default grip, firm only if the pick fails): 100% both ways." }
      ] },
      { name: "GPT-6 Luna", rows: [
        { label: "No memory", a: 100, b: 57, tip: "Luna, no memory: 100% with the message, 57% without. Difference -42.5 points, 95% interval -58.2 to -26.8." },
        { label: "Sentence listing the four settings", a: 92, b: 45, tip: "Luna, sentence listing the four settings: 92% with the message, 45% without." },
        { label: "Wrong rule: firm for every cube", a: 85, b: 0, tip: "Luna, \"pick every cube with grip_level firm\": 85% with the message, 0% without. Difference -85.0 points, 95% interval -97.2 to -72.8." },
        { label: "Own notebook, 12 episodes", a: 90, b: 35, tip: "Luna, own notebook: 90% with the message, 35% without. Difference -55.0 points, 95% interval -81.4 to -28.6." },
        { label: "Procedure written by us", a: 100, b: 100, tip: "Luna, written procedure: 100% both ways." }
      ] }
    ]
  },

  /* May the notebook writer guess? No error message. RESULTS.md sections 6n and 6o. 40 layouts per row. */
  guess: {
    src: "RESULTS.md sections 6n and 6o",
    unit: "%",
    groups: [
      { name: "Claude Haiku 5.5", rows: [
        { label: "No memory", v: 35, base: true, tip: "Haiku, no memory: 14 of 40 layouts (35%)." },
        { label: "Own notebook, facts only", v: 28, tip: "Haiku, notebook written from facts only: 11 of 40 (28%)." },
        { label: "Own notebook, writer may guess", v: 25, tip: "Haiku, notebook that may hold marked guesses: 10 of 40 (25%). Against facts only -2.5 points, 95% interval -45.9 to +40.9." }
      ] },
      { name: "GPT-6 Luna", rows: [
        { label: "No memory", v: 57, base: true, tip: "Luna, no memory: 23 of 40 layouts (57%)." },
        { label: "Own notebook, facts only", v: 35, tip: "Luna, notebook written from facts only: 14 of 40 (35%)." },
        { label: "Own notebook, writer may guess", v: 35, tip: "Luna, notebook that may hold marked guesses: 14 of 40 (35%)." }
      ] }
    ]
  }
};
