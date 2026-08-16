# Get Started

For anyone who wants to run this and doesn't have any of it set up yet. No
technical background assumed. About 30 minutes, mostly downloads.

> ⚠️ **Not affiliated with, endorsed by, or reviewed by DCSA, DOHA, ODNI, or
> any U.S. Government agency.** The Government makes all adjudicative
> determinations. This tool ensures nothing. Read
> [`DISCLAIMER.md`](DISCLAIMER.md) before you use it.

---

## What you're setting up

This isn't an app you install. It's a folder of written instructions that an
AI assistant reads and follows. So you need two things:

1. **An AI assistant** that can read files in a folder — one of several free
   or paid options below.
2. **This folder**, copied to your computer.

Then you point the assistant at the folder and it takes over.

Because it works this way, **your information never goes to a server run by
this project.** There isn't one. Whatever you type goes only to the AI
provider you chose, under their terms.

---

## Step 1 — Pick an AI assistant

Any of these work. Pick one; you don't need more than one.

| Assistant | Where | Notes |
|---|---|---|
| **Claude Code / Cowork** | claude.ai/code | From Anthropic, who make Claude. |
| **OpenAI Codex** | openai.com | From OpenAI, who make ChatGPT. |
| **Cursor** | cursor.com | A code editor with an assistant built in. Free tier available. |
| **Google Antigravity** | Google | From Google, who make Gemini. |

All of them require an account and most require a paid plan for meaningful
use. That cost is between you and them — this project doesn't take any of it
and doesn't know which one you picked.

Install your choice and sign in before continuing.

> **Ordinary chat (ChatGPT, Claude.ai, Gemini in a browser) will partly work**,
> but it can't read the folder or run the safety checks, so you'd be pasting
> files in by hand and checking the output yourself. Workable in a pinch, much
> worse. See "Using a plain chat window" at the bottom.

---

## Step 2 — Get the folder

### The easy way

1. Go to the project's GitHub page.
2. Click the green **Code** button.
3. Click **Download ZIP**.
4. Find the file in your **Downloads** folder.
5. **Windows:** right-click → **Extract All…** → choose where to put it.
   **Mac:** double-click it.

Remember where you put it. You'll point your assistant there in a moment.

### If you'd rather use Git

```bash
git clone https://github.com/<owner>/adverse-information-assistant
```

---

## Step 3 — Install the helper

The folder includes small programs that check the tool's work — they catch
things like a made-up legal citation or your own phone number ending up
somewhere it shouldn't. They need Python.

1. Go to **https://www.python.org/downloads/** and click the big download
   button.
2. Run the installer.
3. **Windows only, and this is the step people miss:** on the first screen
   there's a checkbox at the bottom reading **"Add python.exe to PATH."**
   Check it. It's off by default, and skipping it breaks things later with an
   error that won't explain itself.
4. Finish the install.
5. Open a terminal:
   - **Windows:** press the Windows key, type `powershell`, press Enter.
   - **Mac:** press Cmd+Space, type `terminal`, press Enter.
6. Type this and press Enter:

   ```
   pip install pyyaml
   ```

Wait for `Successfully installed`. Done.

---

## Step 4 — Understand what's missing before you run it

**This project deliberately ships without any official government text.** No
SEAD 3, no SEAD 4 guideline language, no DOHA case decisions.

That's on purpose. AI models will happily produce text that *sounds* like a
regulation or a court decision and is entirely invented. A fabricated case
citation in a document you hand to your security officer is worse than no
citation at all. So the project refuses to include anything a human hasn't
verified against the official source.

**What that means for you:**

- The tool still runs, and the interview still works.
- It will not cite regulations or cases.
- When it isn't certain whether something is reportable, it says "check with
  your security office" rather than guessing.

If you or your organization want the full capability, `corpus/README.md`
explains how to populate it from the official sources. That's real work and
requires someone who knows the material.

---

## Step 5 — Run it

Open the folder in your AI assistant. In most of them that's **File → Open
Folder**, then pick the folder from Step 2.

Then paste this into the chat. (In Claude Code you can just type `/report`
instead — the rules load themselves.)

```
Read agents/conductor.md and run the session it describes, exactly as written.
Follow the stage order. Use the agent prompt files in agents/core/ and
agents/optional/ as the instructions for each step. Only cite things that
exist as files in corpus/. Before showing me any final package, run
scripts/verify_output.py and do not give me output that fails it. When we
finish, give me the exact verify_output.py command to run myself and the
SHA-256 it printed, so I can confirm the file I have is the file that passed.
```

That's it. It will greet you, tell you what it is and isn't, ask what level of
privacy you want, and go from there.

---

## What to expect

It calls you **John Doe** and never asks your real name. Early on it asks how
much you want to share about *other people* — the default keeps everyone
anonymous as "Person 1," "Person 2," and you keep a note of who's who. It
never asks for a Social Security number or date of birth at any setting.

Then it asks what you need to report, in your own words, and works out what
policy requires. **If something is reportable it tells you right away**, because
the clock started when the event happened, not when you finish writing.

Then it asks a lot of questions. That's the point — the questions are what
make the report complete. Some are required by the form and can't be skipped;
the rest you can decline. If something you mention turns out to be separately
reportable on its own, it asks whether you want to cover that too.

At the end you get a package to hand your security officer, with your real
name still to be filled in and a list of anything still outstanding.

---

## Before you submit anything it produces

Read every word yourself. The automated checks catch invented citations,
prohibited language, and personal data that shouldn't be there. They
**cannot** catch a sentence that quietly understates what actually happened.

You're signing it. You're the last check.

---

## Using a plain chat window

If you only have ChatGPT, Claude, or Gemini in a browser:

1. Open `agents/conductor.md` in Notepad or TextEdit, copy all of it, and
   paste it as your first message with: *"Follow these instructions."*
2. When it refers to another agent — `core/interviewer`, say — open that file
   and paste it in too.
3. The safety scripts won't run. You'll need to check the output yourself
   against the list in `agents/verifier` and `README.md`.

This works but drops most of the automated protection. Prefer Step 1's options
if you have any of them available.
