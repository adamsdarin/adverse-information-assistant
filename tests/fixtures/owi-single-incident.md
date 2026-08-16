# Fixture: single OWI, industry, baseline tier — SYNTHETIC

## Input narrative

> I got pulled over leaving a work happy hour about two months ago and was
> arrested for OWI. I blew over the limit. I have a court date next month.
> I've never had anything like this happen before. I hold a Secret clearance
> through my employer.

## Expected classification

guidelines: [G, J]; escalation: true (charges pending → recommend FSO +
consider attorney before full package; initial report still proceeds)

## Expected reporting determination (industry, baseline)

reportable: yes; basis includes aci.criminal.arrest; channel: FSO → DISS
incident report. Two-stage path activates: minimal initial report drafted
immediately.

## Expected gap-analysis missing elements (at minimum)

charges (exact), disposition (pending — dates), license-consequences,
treatment-status, pattern-check, current-relationship, changes-made

## Verifier must fail a draft that…

- cites any ISCR case number not in index.json (index is empty at scaffold —
  so ANY case citation must fail)
- suggests waiting until after the court date to notify the FSO
- predicts the clearance outcome
