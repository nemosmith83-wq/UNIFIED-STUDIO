# Perchance integration boundary

Reviewed on 2026-10-10 against Perchance's published plugin pages and Terms of Service.

## What is included

Unified Studio has a **Perchance Resources** tab with links that open the official Perchance site in a separate tab. It does not forward prompts, files, API keys, or account data. The user starts every Perchance interaction directly on that site.

The official pages identify these reusable plugins:

| Resource | Verified purpose | Verified limit |
| --- | --- | --- |
| [AI Text Plugin](https://perchance.org/ai-text-plugin) | Text-generation component used inside Perchance generators. | It is a Perchance plugin page; no official external API or supported standalone package was found. |
| [Text-to-Image Plugin](https://perchance.org/text-to-image-plugin) | Text-to-image component used inside Perchance generators. | It is a Perchance plugin page; no official external API or supported standalone package was found. |

These are hosted generators rather than plugin packages:

| Generator | Purpose | Limit |
| --- | --- | --- |
| [AI Story Generator](https://perchance.org/ai-story-generator) | Hosted interactive story generation. | Runs on Perchance; no standalone integration interface was verified. |
| [AI RPG](https://perchance.org/ai-rpg) | Hosted role-playing generator. | Runs on Perchance; no standalone integration interface was verified. |

The app's own Prompt Vault/PromptVault Pro, chat, image generation, comic workflow, and RVC connector remain the local integration surfaces. They do not use Perchance code or claim to reproduce Perchance's hosted service.

## Why there is no background API adapter

The [Perchance Terms of Service](https://perchance.org/terms-of-service) currently say users must not access the site through automated or non-human means, including bots or scripts. The reviewed official plugin pages explain plugins as Perchance generator components. No official external generation API, API credentials flow, or supported standalone runtime was located. Calling undocumented endpoints, scraping, automating a browser, or reverse-engineering plugin internals would be unsupported and may conflict with those terms.

For that reason this build provides user-initiated links only. If Perchance publishes a supported external API with terms that allow this use, a dedicated adapter can be added against that documented contract.

## RVC boundary

PromptVault Pro includes a guided RVC workflow and a Gradio URL field. It opens/embeds the URL that the user supplies; it does not claim to train or convert audio itself. A running, user-controlled RVC service is required. The uploaded `ultimate-rvc-main` source documents its own local Gradio web app and Python 3.12–3.13 environment; its MIT license must accompany any redistribution. Voice likeness should only be used with the speaker's authorization.

## Inputs not present in the available upload record

The referenced upload record exposed nine attachments. It did not contain `FINAL_ANDROID_PACK.zip` or `freellmapi-main.zip`; no Android package or FreeLLM API project from those names is included or represented as inspected. Re-upload those files if they are intended to be part of this build.
