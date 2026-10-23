# BYOD default temperature: 0.3

The default temperature is 0.3 in all eight BYOD Spaces on Ruurd and Dovelove,
covering Gemma, Llama, Qwen and Ministral. Both the visible slider and the
`/generate` API default were verified on each newly deployed runtime revision.
The shared app template and deployment documentation use the same default.

Only the app default and its documentation changed. The expanded scorer pins,
model weights and remaining generation settings are unchanged. This update
checks configuration; it does not include a new quality evaluation or GPU
inference run. Native LLaDA retains its separate temperature default of 0.7.

- [Deployed revisions](deployment.json)
- [UI and API verification](verification.json)
- [Prepared source hashes](prepared.json)
