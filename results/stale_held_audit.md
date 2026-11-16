# Stale held state after `home` (audit)

Episodes scanned: 5584. Times `pick` came directly after `home`: 9. Times `pick` answered "already holding": 10, of which 7 came after a false hold (a `close_gripper` that said `holding` with the fingers under 3 cm apart). Episodes containing a false hold: 120.

| run | phase | episode | call | the three calls before it |
|---|---|---|---|---|
| claude-haiku-5-5__stack__none__quirk__p12__s3 | practice | 2 | 7 | move_to > move_to > close_gripper |
| claude-haiku-5-5__stack__none__quirk__p12__s7 | eval_disturbed | 0 | 7 | move_to > move_to > close_gripper |
| claude-haiku-5-5__stack__none__quirk__p12__s9 | eval_disturbed | 3 | 10 | move_to > move_to > close_gripper |
| gpt-6-luna__bins__replay__quirk__p12__s8 | eval | 2 | 5 | pick > move_to > place |
| gpt-6-luna__stack__none__quirk__p12__s4 | eval_disturbed | 3 | 7 | pick > place > pick |
| gpt-6-luna__stack__none__quirk__p12__s9 | eval_disturbed | 2 | 12 | pick > place > place |
| claude-haiku-5-5__stack__none__quirk__p12__s12 | practice | 2 | 6 | move_to > move_to > close_gripper |
| claude-haiku-5-5__stack__none__quirk__p12__s14 | practice | 1 | 10 | pick > move_to > close_gripper |
| claude-haiku-5-5__stack__none__quirk__p12__s16 | practice | 0 | 8 | move_to > move_to > close_gripper |
| claude-haiku-5-5__stack__replay__quirk__p12__s13 | practice | 0 | 8 | move_to > move_to > close_gripper |

Most common call just before: [(('move_to', 'move_to', 'close_gripper'), 6), (('pick', 'move_to', 'place'), 1), (('pick', 'place', 'pick'), 1)]. Each listed episode could have been affected only if the object had in fact been lost during `home` (check its log); an honest "already holding" after a successful pick is not a defect.
