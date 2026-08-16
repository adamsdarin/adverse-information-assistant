# Publishing This to GitHub — Step by Step

> **Start with `RUNBOOK.md` instead** if you want the whole path — move the
> folder, test it, publish, then build the corpus. This file is the GitHub
> chapter in more detail, for when a step here needs unpacking.

Written for Windows, assuming you've never used GitHub. Nothing here requires
you to type commands into a black window. Total time: about 45 minutes, most
of it waiting on downloads.

If a screen looks slightly different from what's described, that's normal —
websites get redesigned. Go by what the button *does*, not exactly where it is.

---

## What you're doing and why

You have a folder of files. You want it on GitHub so that anyone can copy it
to their own computer and run it. GitHub is essentially a public folder with a
history — every change is tracked, and anyone can take a copy without touching
your original.

Three things to install, one account to make, then you publish.

---

## Part 1 — Get the files onto your computer

1. Download the `adverse-information-assistant.zip` file from our conversation.
   It lands in your **Downloads** folder.
2. Open **File Explorer** and go to Downloads.
3. **Right-click** the zip file → **Extract All…**
4. In the box that appears, change the destination to:

   ```
   C:\Users\<your-username>\src\adverse-information-assistant
   ```

   Replace `<your-username>` with your actual Windows username. `src` is the
   conventional place for this. **Do not put it in OneDrive** — OneDrive and
   Git fight over file locks, and anything you generate while testing would
   sync to Microsoft's cloud.
5. Click **Extract**.
6. Open the extracted folder. You should see `README.md`, `agents`, `corpus`,
   `scripts`, and others.

> **Watch for a doubled folder.** Windows sometimes creates
> `adverse-information-assistant\adverse-information-assistant\`. If you see
> the same name twice, move the *inner* folder's contents up one level so
> `README.md` sits directly inside your `src\adverse-information-assistant`
> folder.

---

## Part 2 — Install Python

Python runs the checking scripts (`validate_corpus.py`, `verify_output.py`).
You don't have to write any Python — you just need it installed.

1. Go to **https://www.python.org/downloads/**
2. Click the big yellow **Download Python** button.
3. Run the downloaded file.
4. **This next part matters more than anything else on this page.** On the
   very first installer screen, at the bottom, there is a checkbox:

   > ☐ Add python.exe to PATH

   **Check it.** It is unchecked by default. If you miss it, nothing will work
   later and the error message won't tell you why. If you already clicked
   through, run the installer again and choose *Modify*.
5. Click **Install Now** and wait.
6. When it finishes, click **Disable path length limit** if offered. Then Close.

### Confirm it worked

1. Press the **Windows key**, type `powershell`, press **Enter**. A blue window opens.
2. Type this and press Enter:

   ```powershell
   python --version
   ```

3. You should see something like `Python 3.13.1`.

**If instead the Microsoft Store opens**, Windows is intercepting the command.
Fix it: press Windows key → type `manage app execution aliases` → Enter → turn
**off** both switches named `python.exe` and `python3.exe`. Close PowerShell,
open it again, try once more.

### Install the one add-on the scripts need

In the same PowerShell window:

```powershell
pip install pyyaml
```

Wait for it to say `Successfully installed`. You're done with Python.

---

## Part 3 — Make a GitHub account

1. Go to **https://github.com** and click **Sign up**.
2. Use an email you'll keep. Pick a username — this becomes part of your
   public web address, so choose something you'd put on a resume.
3. Verify your email when they send the code.

> **A word about your username and repo name.** Both will be publicly visible
> and permanent-ish. Avoid anything implying government affiliation. Something
> like `darinadams/adverse-information-assistant` is clean.

---

## Part 4 — Install GitHub Desktop

This is the app that moves files from your computer to GitHub. There's a
command-line way to do this; ignore it. This is easier and does the same thing.

1. Go to **https://desktop.github.com**
2. Click **Download for Windows**. Run it. It installs itself with no options
   to pick.
3. When it opens, click **Sign in to GitHub.com** and log in with the account
   you just made.
4. It asks for a name and email for your commit history. Use your GitHub
   username and the same email.

---

## Part 5 — Publish the folder

1. In GitHub Desktop, click **File** → **Add local repository**.
2. Click **Choose…** and select your
   `C:\Users\<your-username>\src\adverse-information-assistant` folder.
3. It will say *"This directory does not appear to be a Git repository."* with
   a blue link: **create a repository**. Click that link.
4. On the form that appears:
   - **Name:** `adverse-information-assistant`
   - **Description:** `Helps clearance holders prepare complete adverse-information self-reports. Not affiliated with any U.S. Government agency.`
   - **Git ignore:** leave as None — the folder already contains a `.gitignore`
   - **License:** leave as None — the folder already contains `LICENSE`
5. Click **Create repository**.
6. You'll now see a long list of files on the left under *Changes*. That's
   correct — everything is new.
7. Bottom left, in the **Summary** box, type: `Initial commit`
8. Click **Commit to main**.
9. Top of the window, click **Publish repository**.
10. **Uncheck "Keep this code private."** Leaving it checked means nobody can
    clone it, which defeats the purpose.
11. Click **Publish repository** and wait.

---

## Part 6 — Check that it worked

1. In GitHub Desktop, click **Repository** → **View on GitHub**. Your browser
   opens to your new page.
2. You should see the file list, and below it your README rendered as a
   formatted page.
3. Click on **PROCESS.md**. The diagrams should render as actual pictures, not
   as code. If they render, everything published correctly.

Your clone address is the web address of that page. Anyone can now copy it.

---

## Part 7 — Making changes later

Whenever you edit a file — adding DOHA cases, pasting in SEAD 3 text,
correcting a checklist:

1. Open GitHub Desktop. Your changes appear automatically on the left.
2. Type a short note in the **Summary** box describing what you changed.
   `Added 12 Guideline G cases` is a good note. `update` is not.
3. Click **Commit to main**.
4. Click **Push origin** at the top.

That's the whole loop. Commit, push. Nothing else.

---

## Part 8 — Run the checking scripts

Before you push corpus changes, make sure you haven't broken anything.

1. In File Explorer, open your `adverse-information-assistant` folder.
2. Click the address bar at the top, type `powershell`, press Enter. A
   PowerShell window opens already in the right folder.
3. Run:

   ```powershell
   python tests\run_tests.py
   python scripts\build_index.py
   python scripts\validate_corpus.py
   ```

**Reading the output:**

- `41 passed, 0 failed` — the scripts and the safety gates are intact.
- `0 error(s)` — good, push it.
- Any `ERROR` lines — something is broken. The message says which file. Fix
  and re-run.
- `WARN` lines — expected right now. Every corpus file ships marked unverified
  until a human checks it against the official source. Warnings will decrease
  as you do that work.

---

## Before you tell anyone about it

- [ ] The README's DCSA no-affiliation disclaimer is visible on the repo page
- [ ] `validate_corpus.py` reports 0 errors
- [ ] You have **not** committed any real person's information — check that
      `output/` is empty and no session files snuck in
- [ ] The corpus in the repo is still an empty **skeleton** — the two
      "shipped corpus must stay a skeleton" tests pass. Official government
      text belongs in the separately distributed corpus, not here.
- [ ] `corpus-sources.yaml` has a real Google Drive link and contact, not the
      shipped `TODO` placeholders — otherwise a user who clones this has no
      way to obtain the corpus
- [ ] The repository is **public**
- [ ] You've read `DEPLOYMENT.md` and the README's privacy claims are true of
      how you're actually distributing it

---

## If you get stuck

The most common problems, in order of how often they happen:

| What you see | What it means |
|---|---|
| `python is not recognized` | The PATH checkbox in Part 2 step 4 was missed. Re-run the installer, choose Modify, check the box. |
| Microsoft Store opens instead of Python | Turn off the app execution aliases — see Part 2. |
| `No module named yaml` | You skipped `pip install pyyaml`. |
| Files missing on GitHub | You committed but didn't **Push origin**. |
| `.gitignore` hid something you wanted | That's intentional for `output/`. It exists so a draft containing your adverse information can never be published by accident. |
| A test fails about the corpus "skeleton" | Government text ended up in the repo's `corpus/`. Move it to your separate corpus folder and restore the empty template. |
