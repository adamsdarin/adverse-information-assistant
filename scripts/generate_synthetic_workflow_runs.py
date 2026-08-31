#!/usr/bin/env python3
"""Generate and gate 20 fictional end-to-end workflow runs.

The artifacts are testing examples, not legal advice and not adjudicative
predictions. Each run contains the synthetic user's inputs, every workflow
question and answer, the gated session state, and the assembled report.
"""
from __future__ import annotations

import argparse
from difflib import SequenceMatcher
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def event(title, guidelines, incident_types, narrative, basis, updates=(), documents=(), persons=()):
    profiles = ["general-incident"]
    if "G" in guidelines or "H" in guidelines:
        profiles.append("substance-use-or-treatment")
    if "J" in guidelines:
        profiles.append("arrest-or-criminal-process")
    if "B" in guidelines or "C" in guidelines or "L" in guidelines:
        profiles.append("foreign-contact-or-influence")
    if "F" in guidelines:
        profiles.append("financial-event")
    if "K" in guidelines or "M" in guidelines:
        profiles.append("information-or-technology")
    facts = [s.strip() for s in re.split(r"(?<=[.!?])\s+", narrative) if s.strip()]
    while len(facts) < 8:
        facts.append(facts[-1])
    return {
        "title": title,
        "guidelines": guidelines,
        "incident_types": incident_types,
        "future_update_topics": list(updates),
        "incident_development": {
            "profiles": profiles,
            "complete": True,
            "phases": {
                "before": {"status": "answered", "evidence": facts[0]},
                "precipitating_circumstances": {"status": "answered", "evidence": facts[1]},
                "decisions_and_actions": {"status": "answered", "evidence": facts[2]},
                "incident": {"status": "answered", "evidence": facts[3]},
                "immediate_aftermath": {"status": "answered", "evidence": facts[4]},
                "later_consequences": {"status": "answered", "evidence": facts[5]},
                "current_status": {"status": "answered", "evidence": facts[-2]},
                "future_developments": {"status": "answered", "evidence": facts[-1]},
            },
        },
        "narrative": narrative,
        "reporting": {
            "reportable": "yes",
            "channel": "Security office reporting route determined in final analysis",
            "timeline": "Report promptly; do not wait for final court, treatment, or administrative outcomes.",
            "basis": list(basis),
        },
        "documents": [
            {"name": name, "source": source, "timing": "can_follow"}
            for name, source in documents
        ],
        "persons": [{"label": label, "role": role} for label, role in persons],
        "declined_elements": [],
        "prior_disclosure": {"status": "not_asked"},
    }


CASES = [
    {
        "slug": "01-owi-arrest-holder", "title": "OWI arrest — clearance holder",
        "role": "holder", "population": "industry", "form": "incident_report", "access": "baseline",
        "initial": "Last Friday I was arrested for OWI after a traffic stop. My breath result was 0.14 and the court case is still pending.",
        "qas": [
            ("When did the traffic stop occur?", "August 21, 2026, at about 11:40 p.m."),
            ("Where did it occur?", "In Cedar County, Iowa, near the junction of Highway 30 and County Road X40."),
            ("What were you doing in the hours before you began drinking?", "I attended a coworker's retirement dinner after work and stayed at the restaurant afterward with several coworkers."),
            ("What was happening that led you to drink on that occasion?", "I drank during the dinner and continued drinking while talking with coworkers afterward."),
            ("How did you come to decide to drive after drinking?", "I had planned to drive myself home. When I left, I underestimated how impaired I was and did not arrange another ride."),
            ("Was drinking that amount and then driving typical for you at that time?", "No. I sometimes drank at social events, but I ordinarily limited myself when driving or arranged a ride. I did neither that night."),
            ("What offense were you arrested for?", "Operating while intoxicated, first offense."),
            ("Were you booked or jailed?", "I was booked into the county jail and released the next morning."),
            ("What is the court case status?", "The case is pending; no disposition date exists."),
            ("Was anyone injured or was there a collision?", "No."),
            ("Have counseling or treatment occurred because of this incident?", "No counseling or treatment has occurred as of today."),
            ("Who knows about the incident?", "Person 1, my spouse, and Person 2, my supervisor."),
        ],
        "events": [event("OWI arrest", ["G", "J"], ["Alcohol Consumption", "Criminal Conduct"],
            "On August 21, 2026, I attended a coworker's retirement dinner after work and stayed at the restaurant afterward with several coworkers. I drank during dinner and continued drinking while talking with them. I had planned to drive myself home. When I left, I underestimated how impaired I was and did not arrange another ride. Drinking that amount and then driving was not typical for me at that time; I sometimes drank at social events, but I ordinarily limited myself when driving or arranged a ride. I did neither that night. At about 11:40 p.m., I was stopped in Cedar County, Iowa, and arrested for operating while intoxicated, first offense. My breath result was 0.14. I was booked into the county jail and released the next morning. There was no collision and nobody was injured. The court case is pending, and no disposition date exists. No counseling or treatment has occurred as of this report. Person 1, my spouse, and Person 2, my supervisor, know about the incident.",
            ["aci.criminal.arrest"], ["Any charge, hearing, plea, sentence, license action, or final court disposition", "Any alcohol evaluation, counseling, education, or treatment resulting from this incident"],
            [("Arrest or booking record", "Arresting agency"), ("Court filings and final disposition when issued", "Clerk of court")], [("Person 1", "my spouse"), ("Person 2", "my supervisor")])],
    },
    {
        "slug": "02-assault-arrest-holder", "title": "Assault arrest — federal clearance holder",
        "role": "holder", "population": "federal", "form": "incident_report", "access": "baseline",
        "initial": "I was arrested after punching another patron during an argument outside a restaurant.",
        "qas": [
            ("When did this happen?", "July 3, 2026, at approximately 12:20 a.m."),
            ("What happened immediately before the physical contact?", "We argued about a spilled drink; I punched him once."),
            ("Was the other person injured?", "He had a cut lip and was treated at the scene."),
            ("What offense was listed at booking?", "Simple assault."),
            ("What is the court status?", "Arraignment is scheduled; there is no disposition."),
            ("Was any protective or no-contact order issued?", "A temporary no-contact order was issued at arraignment paperwork processing."),
            ("Who witnessed the event?", "Person 1, another patron."),
        ],
        "events": [event("Assault arrest", ["J"], ["Criminal Conduct"],
            "On July 3, 2026, at approximately 12:20 a.m., I argued with another patron outside a restaurant about a spilled drink and punched him once. He sustained a cut lip and was treated at the scene. I was arrested and booked for simple assault. An arraignment is scheduled, no disposition exists, and a temporary no-contact order was issued. Person 1 witnessed the event.",
            ["aci.criminal.arrest"], ["Any change to the charge, no-contact order, court schedule, plea, sentence, or disposition", "Any anger-management counseling or other treatment required or undertaken because of the incident"],
            [("Arrest or booking record", "Arresting agency"), ("Court and no-contact-order records", "Clerk of court")], [("Person 1", "witness")])],
    },
    {
        "slug": "03-domestic-violence-alcohol-holder", "title": "Domestic violence, alcohol, and arrest — one incident",
        "role": "holder", "population": "industry", "form": "incident_report", "access": "ts_q",
        "initial": "I was drinking, argued with my spouse, shoved them, and was arrested for domestic assault. It is all one incident.",
        "qas": [
            ("When and where did the incident occur?", "August 9, 2026, at our residence in Polk County, Iowa."),
            ("What physical conduct occurred?", "During the argument I shoved my spouse once with both hands."),
            ("Was your spouse injured?", "They reported shoulder pain but did not go to the hospital."),
            ("How much alcohol had you consumed?", "Approximately six beers over four hours."),
            ("What offense were you arrested for?", "Domestic abuse assault causing bodily injury."),
            ("Were you booked or jailed?", "I was booked and held overnight."),
            ("Was a protective or no-contact order issued?", "Yes, a temporary no-contact order prohibits contact with my spouse."),
            ("What is the court status?", "The case is pending and a preliminary hearing is scheduled."),
            ("Have counseling or treatment occurred because of this incident?", "No services have occurred as of today."),
        ],
        "events": [event("Domestic violence arrest involving alcohol", ["E", "G", "J"], ["Personal Conduct", "Alcohol Consumption", "Criminal Conduct"],
            "On August 9, 2026, at our residence in Polk County, Iowa, I argued with my spouse after consuming approximately six beers over four hours. During the argument I shoved my spouse once with both hands. My spouse reported shoulder pain but did not go to the hospital. I was arrested for domestic abuse assault causing bodily injury, booked, and held overnight. A temporary no-contact order prohibits contact with my spouse. The case is pending and a preliminary hearing is scheduled. No counseling or treatment has occurred as of this report.",
            ["aci.criminal.arrest"], ["Any modification or termination of the no-contact order", "Any charge, hearing, plea, sentence, probation requirement, or final disposition", "Any domestic-violence, alcohol, behavioral, or other evaluation, counseling, education, or treatment resulting from the incident"],
            [("Arrest or booking record", "Arresting agency"), ("Court and no-contact-order records", "Clerk of court")])],
    },
    {
        "slug": "04-foreign-contact-holder", "title": "Continuing foreign contact — clearance holder",
        "role": "holder", "population": "federal", "form": "incident_report", "access": "ts_q",
        "initial": "I have been in regular contact with a citizen and resident of India whom I met through an engineering association.",
        "qas": [
            ("When did the contact begin?", "February 2026."),
            ("How often do you communicate?", "About twice each month by email and video call."),
            ("What is the nature of the relationship?", "Professional friendship with an ongoing personal connection."),
            ("What personal information has been exchanged?", "We discussed our employers, families, travel plans, and professional interests."),
            ("Has the person requested classified, controlled, or nonpublic government information?", "No."),
            ("Have money, gifts, or business commitments been exchanged?", "No."),
        ],
        "events": [event("Continuing association with a foreign national", ["B"], ["Foreign Influence"],
            "Since February 2026, I have communicated about twice each month by email and video call with a citizen and resident of India whom I met through an engineering association. We have a professional friendship with an ongoing personal connection and have discussed our employers, families, travel plans, and professional interests. The person has not requested classified, controlled, or nonpublic government information. We have not exchanged money or gifts and have no business commitments.",
            ["aci.foreign-contact.continuing"], ["Any material change in the frequency, closeness, financial connection, shared residence, travel, or requests for information associated with this contact"])]
    },
    {
        "slug": "05-gambling-debt-holder", "title": "Gambling-related delinquent debt — clearance holder",
        "role": "holder", "population": "industry", "form": "incident_report", "access": "baseline",
        "initial": "Online sports betting contributed to credit-card debt that is now more than 120 days delinquent.",
        "qas": [
            ("When did the gambling activity begin and end?", "It increased from January through May 2026; I stopped betting on May 18."),
            ("What amount is more than 120 days delinquent?", "$18,400 across three credit-card accounts."),
            ("When did the accounts first become delinquent?", "March 2026."),
            ("What is the current repayment status?", "I entered written payment plans with all three creditors in July and have made two payments."),
            ("Did you borrow from another person or engage in illegal gambling?", "No."),
            ("Have counseling or treatment occurred concerning the gambling?", "I met twice with a licensed gambling counselor in June and continue monthly appointments."),
        ],
        "events": [event("Gambling-related delinquent debt", ["F"], ["Financial Considerations"],
            "From January through May 18, 2026, online sports betting contributed to $18,400 in credit-card debt across three accounts. The accounts first became delinquent in March and are now more than 120 days delinquent. I stopped betting on May 18. In July I entered written payment plans with all three creditors and have made two payments. I did not borrow from another person or participate in illegal gambling. I met twice with a licensed gambling counselor in June and continue monthly appointments.",
            ["aci.finance.bankruptcy-delinquency"], ["Any missed or modified payment plan, collection action, lawsuit, garnishment, bankruptcy filing, or new delinquency", "Any material change in gambling counseling or treatment connected to this matter"],
            [("Account statements and payment plans", "Creditors")])],
    },
    {
        "slug": "06-marijuana-use-applicant", "title": "Marijuana use — initial applicant",
        "role": "applicant", "population": "industry", "form": "sf86", "access": "not_applicable",
        "initial": "I have not submitted my SF-86. I used marijuana about monthly while it was legal under state law, most recently in April 2026.",
        "qas": [
            ("When did the use begin?", "June 2024."),
            ("How often did you use it?", "Approximately once a month."),
            ("When was the most recent use?", "April 12, 2026."),
            ("How did you obtain it?", "I purchased it from a state-licensed dispensary."),
            ("Did you use, possess, or purchase it while holding a clearance?", "No; I have never held a clearance."),
            ("Have counseling or treatment occurred because of the use?", "No."),
        ],
        "events": [event("Marijuana use", ["H"], [],
            "I used marijuana approximately once a month from June 2024 through April 12, 2026. I purchased it from a state-licensed dispensary. I have never held a security clearance and did not use, possess, or purchase it while holding one. No counseling or treatment occurred because of the use.",
            ["Initial SF-86 drug-involvement disclosure review"], ["Any additional use, purchase, possession, drug-related charge, evaluation, counseling, or treatment before submission or while the investigation is pending"])]
    },
    {
        "slug": "07-bankruptcy-in-process", "title": "Bankruptcy filed while investigation is pending",
        "role": "in_process", "population": "industry", "form": "sf86", "access": "not_applicable",
        "initial": "I submitted my SF-86 in May. In August I filed Chapter 7 bankruptcy after a prolonged loss of household income.",
        "qas": [
            ("When was the bankruptcy petition filed?", "August 14, 2026."),
            ("Where was it filed?", "United States Bankruptcy Court for the District of Nebraska."),
            ("What debt is included?", "Approximately $64,000 in unsecured medical and credit-card debt."),
            ("What caused the financial difficulty?", "My spouse was unemployed for ten months and we had uninsured medical expenses."),
            ("What is the case status?", "The creditors meeting is scheduled; no discharge has been entered."),
            ("Have you received financial counseling?", "I completed the required pre-filing credit counseling course."),
        ],
        "events": [event("Chapter 7 bankruptcy after SF-86 submission", ["F"], [],
            "After submitting my SF-86 in May 2026, I filed a Chapter 7 bankruptcy petition on August 14, 2026, in the United States Bankruptcy Court for the District of Nebraska. The petition includes approximately $64,000 in unsecured medical and credit-card debt. The financial difficulty followed my spouse's ten months of unemployment and uninsured medical expenses. The creditors meeting is scheduled and no discharge has been entered. I completed the required pre-filing credit counseling course.",
            ["aci.finance.bankruptcy-delinquency"], ["Any amendment, creditors meeting result, dismissal, discharge, repayment arrangement, new delinquency, or additional financial counseling connected to the bankruptcy"],
            [("Bankruptcy petition and schedules", "Bankruptcy court")])],
    },
    {
        "slug": "08-information-technology-misuse-holder", "title": "Unauthorized software on government system",
        "role": "holder", "population": "federal", "form": "incident_report", "access": "baseline",
        "initial": "I installed unauthorized remote-access software on my government laptop so I could reach files from home.",
        "qas": [
            ("When was the software installed?", "July 28, 2026."),
            ("What system was involved?", "My unclassified government-issued laptop."),
            ("What did you access through it?", "Unclassified work files; I did not access classified systems or data."),
            ("How was it discovered?", "Endpoint monitoring alerted the help desk on August 2."),
            ("What action has the organization taken?", "IT removed the software and my supervisor issued a written counseling memorandum."),
            ("Did anyone else receive access?", "No."),
        ],
        "events": [event("Unauthorized remote-access software", ["E", "M"], ["Personal Conduct", "Use of Information Technology"],
            "On July 28, 2026, I installed unauthorized remote-access software on my unclassified government-issued laptop so I could reach work files from home. I accessed unclassified work files and did not access classified systems or data. Endpoint monitoring alerted the help desk on August 2. IT removed the software, my supervisor issued a written counseling memorandum, and no other person received access.",
            ["Security-office review of IT misuse"], ["Any additional administrative, disciplinary, access, investigative, or remedial action arising from this incident"],
            [("IT incident record", "Agency IT security office"), ("Written counseling memorandum", "Supervisor")])],
    },
    {
        "slug": "09-protected-information-holder", "title": "Mishandling protected information",
        "role": "holder", "population": "industry", "form": "incident_report", "access": "ts_q",
        "initial": "I accidentally sent a controlled unclassified technical attachment to my personal email address.",
        "qas": [
            ("When did the transmission occur?", "August 5, 2026."),
            ("What information was involved?", "A controlled unclassified technical drawing; no classified information was involved."),
            ("Who received it?", "Only my personal email account."),
            ("When and how did you report it?", "I reported it to my supervisor and security office about forty minutes later."),
            ("What containment occurred?", "IT confirmed deletion from the personal mailbox and preserved the incident logs."),
            ("What is the investigation status?", "The internal review remains open."),
        ],
        "events": [event("Transmission of controlled unclassified information", ["E", "K"], ["Personal Conduct", "Handling Protected Information"],
            "On August 5, 2026, I accidentally sent a controlled unclassified technical drawing to my personal email account. No classified information was involved and no other recipient received it. I reported the transmission to my supervisor and security office about forty minutes later. IT confirmed deletion from the personal mailbox and preserved the incident logs. The internal review remains open.",
            ["Security-office review of protected-information handling"], ["Any investigative finding, disciplinary action, access change, retraining, or other disposition resulting from the incident"],
            [("Security incident record", "Security office")])],
    },
    {
        "slug": "10-foreign-passport-applicant", "title": "Foreign passport — initial applicant",
        "role": "applicant", "population": "federal", "form": "pvq", "access": "not_applicable",
        "initial": "I have not submitted my personnel vetting questionnaire. I am a dual citizen and possess a current Canadian passport.",
        "qas": [
            ("How was the foreign citizenship acquired?", "By birth in Canada to a Canadian parent."),
            ("When was the current passport issued?", "September 2023."),
            ("When does it expire?", "September 2033."),
            ("Have you used it for travel?", "Yes, for two trips to Canada in 2024 before I began this application."),
            ("Have you applied for or exercised other benefits of Canadian citizenship?", "No other benefits beyond the passport and citizenship by birth."),
        ],
        "events": [event("Canadian citizenship and passport", ["B", "C"], [],
            "I acquired Canadian citizenship by birth in Canada to a Canadian parent and possess a Canadian passport issued in September 2023 that expires in September 2033. I used the passport for two trips to Canada in 2024 before beginning this clearance application. I have not applied for or exercised other benefits of Canadian citizenship beyond the passport and citizenship by birth.",
            ["Initial PVQ foreign-citizenship and passport disclosure review"], ["Any renewal, use, surrender, loss, or other material change involving the passport or foreign citizenship before submission or while the investigation is pending"])]
    },
    {
        "slug": "11-foreign-business-holder", "title": "Direct involvement in a foreign business",
        "role": "holder", "population": "industry", "form": "incident_report", "access": "ts_q",
        "initial": "I invested in and became an unpaid adviser to a small software company incorporated in Germany.",
        "qas": [
            ("When did the involvement begin?", "June 10, 2026."),
            ("What is your ownership interest?", "A 4 percent equity interest purchased for $12,000."),
            ("What activities do you perform?", "One monthly video call providing general product advice."),
            ("Do the activities involve classified, export-controlled, or employer-proprietary information?", "No."),
            ("Who controls the company?", "Two German-citizen founders who reside in Germany."),
            ("Have you received income?", "No income or distributions."),
        ],
        "events": [event("Foreign business ownership and advisory role", ["B", "L"], ["Foreign Influence", "Outside Activities"],
            "On June 10, 2026, I purchased a 4 percent equity interest for $12,000 in a software company incorporated in Germany and became an unpaid adviser. I participate in one monthly video call and provide general product advice. The work does not involve classified, export-controlled, or employer-proprietary information. Two German-citizen founders residing in Germany control the company. I have received no income or distributions.",
            ["tsq.foreign-business"], ["Any ownership, control, compensation, duties, foreign contacts, travel, information access, or other material change associated with the business"])]
    },
    {
        "slug": "12-compulsive-gambling-treatment-holder", "title": "Compulsive gambling treatment and financial effects",
        "role": "holder", "population": "federal", "form": "incident_report", "access": "ts_q",
        "initial": "I sought treatment for compulsive gambling after losing $27,000, although none of my accounts are over 120 days delinquent.",
        "qas": [
            ("When did the gambling losses occur?", "Between November 2025 and June 2026."),
            ("What was the total loss?", "Approximately $27,000."),
            ("Are any debts over 120 days delinquent?", "No."),
            ("When did treatment begin?", "July 7, 2026."),
            ("What treatment is occurring?", "Weekly outpatient counseling with a licensed provider."),
            ("What financial controls are in place?", "I self-excluded from the betting platforms and Person 1, my spouse, reviews our accounts weekly."),
        ],
        "events": [event("Compulsive gambling treatment and losses", ["E", "F"], ["Personal Conduct", "Financial Considerations"],
            "Between November 2025 and June 2026, I lost approximately $27,000 through gambling. No account is more than 120 days delinquent. I began weekly outpatient counseling with a licensed provider on July 7, 2026. I self-excluded from the betting platforms, and Person 1, my spouse, reviews our accounts weekly.",
            ["Final security-office review of gambling treatment and financial impact"], ["Any change in treatment status, renewed gambling, new debt, delinquency, collection activity, or change to the financial controls described above"], persons=[("Person 1", "my spouse")])],
    },
    {
        "slug": "13-prescription-misuse-arrest-holder", "title": "Prescription-drug misuse and arrest",
        "role": "holder", "population": "industry", "form": "incident_report", "access": "baseline",
        "initial": "I was arrested after police found prescription stimulants that were not prescribed to me.",
        "qas": [
            ("When did the arrest occur?", "June 18, 2026."),
            ("What substance and quantity were involved?", "Four amphetamine tablets prescribed to a friend."),
            ("How did you obtain them?", "The friend gave them to me to help me stay awake while studying."),
            ("How many times had you used the substance?", "Three occasions in May and June 2026."),
            ("What charge was filed?", "Possession of a controlled substance without a prescription."),
            ("What is the court status?", "The case is pending; no disposition exists."),
            ("Have counseling or treatment occurred?", "I completed a substance-use evaluation; no treatment recommendation has been issued."),
        ],
        "events": [event("Prescription-drug misuse and arrest", ["H", "J"], ["Drug Involvement and Substance Misuse", "Criminal Conduct"],
            "On June 18, 2026, I was arrested after police found four amphetamine tablets prescribed to a friend. The friend gave them to me to help me stay awake while studying. I used the substance on three occasions in May and June 2026. I was charged with possession of a controlled substance without a prescription. The case is pending and no disposition exists. I completed a substance-use evaluation, and no treatment recommendation has been issued.",
            ["aci.criminal.arrest"], ["Any charge, plea, sentence, probation requirement, or final disposition", "Any recommendation, counseling, education, testing, or treatment resulting from the substance-use evaluation or incident"],
            [("Arrest or booking record", "Arresting agency"), ("Court filings and final disposition when issued", "Clerk of court"), ("Substance-use evaluation", "Evaluation provider")])],
    },
    {
        "slug": "14-workplace-theft-in-process", "title": "Theft arrest while investigation is pending",
        "role": "in_process", "population": "federal", "form": "pvq", "access": "not_applicable",
        "initial": "After submitting my questionnaire, I was arrested for taking equipment from my private-sector employer.",
        "qas": [
            ("When did the arrest occur?", "August 3, 2026."),
            ("What property was involved?", "Two used computer monitors valued by the employer at $600 total."),
            ("What happened?", "I removed them from a storage room without permission and put them in my vehicle."),
            ("What charge was filed?", "Misdemeanor theft."),
            ("What employment action occurred?", "The employer terminated me on August 4."),
            ("What is the court status?", "The first court appearance is scheduled; there is no disposition."),
        ],
        "events": [event("Workplace theft arrest after questionnaire submission", ["E", "J"], [],
            "After submitting my personnel vetting questionnaire, I was arrested on August 3, 2026, for removing two used computer monitors, valued by my employer at $600 total, from a storage room without permission and placing them in my vehicle. I was charged with misdemeanor theft. My employer terminated me on August 4. The first court appearance is scheduled and no disposition exists.",
            ["aci.criminal.arrest"], ["Any change in the charge, employment action, hearing, plea, sentence, restitution, or final disposition"],
            [("Arrest or booking record", "Arresting agency"), ("Court filings and final disposition when issued", "Clerk of court"), ("Termination notice", "Former employer")])],
    },
    {
        "slug": "15-sexual-misconduct-charge-applicant", "title": "Pending sexual-misconduct criminal charge — applicant",
        "role": "applicant", "population": "industry", "form": "sf86", "access": "not_applicable",
        "initial": "Before submitting my SF-86, I need to disclose a pending criminal charge alleging nonconsensual sexual contact.",
        "qas": [
            ("When did the alleged incident occur?", "May 2, 2026."),
            ("When were you arrested or charged?", "I was arrested and charged on May 20, 2026."),
            ("What is the exact charge listed in the court record?", "Abusive sexual contact."),
            ("What is the present court status?", "The case is pending and a motions hearing is scheduled."),
            ("Was a protective or no-contact order issued?", "Yes, a no-contact order remains in effect."),
            ("Have counseling or treatment occurred because of this incident?", "No."),
        ],
        "events": [event("Pending abusive-sexual-contact charge", ["D", "J"], [],
            "An incident alleging nonconsensual sexual contact occurred on May 2, 2026. I was arrested and charged with abusive sexual contact on May 20, 2026. The case is pending, a motions hearing is scheduled, and a no-contact order remains in effect. No counseling or treatment has occurred because of this incident.",
            ["Initial SF-86 police-record and conduct disclosure review", "aci.criminal.arrest"], ["Any change to the charge, no-contact order, hearing schedule, plea, sentence, treatment requirement, or final disposition"],
            [("Arrest or booking record", "Arresting agency"), ("Court and no-contact-order records", "Clerk of court")])],
    },
    {
        "slug": "16-unofficial-foreign-travel-holder", "title": "Unreported unofficial foreign travel",
        "role": "holder", "population": "industry", "form": "incident_report", "access": "baseline",
        "initial": "I took a personal trip to Mexico last month without obtaining the required security-office approval beforehand.",
        "qas": [
            ("What were the travel dates?", "July 10 through July 15, 2026."),
            ("Where did you travel?", "Cancun, Mexico."),
            ("What was the purpose?", "Vacation with Person 1, my spouse."),
            ("What passport did you use?", "My United States passport."),
            ("Did any itinerary deviation or security incident occur?", "No."),
            ("When did you notify the security office?", "I notified it on August 1 after realizing the requirement."),
        ],
        "events": [event("Unofficial travel to Mexico", ["E"], ["Personal Conduct"],
            "I traveled to Cancun, Mexico, for vacation with Person 1, my spouse, from July 10 through July 15, 2026. I used my United States passport. I did not obtain security-office approval before traveling. No itinerary deviation or security incident occurred. I notified the security office on August 1 after realizing the requirement.",
            ["aci.travel.unofficial"], ["Any security-office follow-up, foreign contact, itinerary correction, or security concern associated with the trip"], persons=[("Person 1", "my spouse and travel companion")])],
    },
    {
        "slug": "17-large-gambling-winnings-holder", "title": "Unusual infusion from gambling winnings",
        "role": "holder", "population": "federal", "form": "incident_report", "access": "ts_q",
        "initial": "I won $42,000 in a legal poker tournament and deposited the funds into my checking account.",
        "qas": [
            ("When did you win the funds?", "August 8, 2026."),
            ("Where did the winnings come from?", "A licensed casino poker tournament in Nevada."),
            ("What was the gross amount?", "$42,000."),
            ("How and when were the funds deposited?", "The casino issued a check that I deposited on August 10."),
            ("Do you have documentation of the source?", "Yes, the tournament receipt, tax form, and deposit record."),
            ("Did the gambling create debt or delinquency?", "No."),
        ],
        "events": [event("Large legal gambling winnings", ["F"], ["Financial Considerations"],
            "On August 8, 2026, I won $42,000 in a licensed casino poker tournament in Nevada. The casino issued a check, which I deposited into my checking account on August 10. I retain the tournament receipt, tax form, and deposit record. The gambling did not create debt or delinquency.",
            ["tsq.finance.anomalies"], ["Any correction to the source, amount, tax documentation, deposit, or ownership of the funds"],
            [("Tournament receipt and tax form", "Casino"), ("Deposit record", "Financial institution")])],
    },
    {
        "slug": "18-domestic-violence-plus-foreign-contact", "title": "Two independent incidents in one session",
        "role": "holder", "population": "industry", "form": "incident_report", "access": "ts_q",
        "initial": "I need to report a domestic violence arrest involving alcohol. Separately, I have an ongoing close contact with a citizen of Brazil.",
        "qas": [
            ("What happened in the domestic-violence incident?", "On July 26 I drank four mixed drinks, argued with my partner, grabbed their wrist, and was arrested."),
            ("Was your partner injured?", "They had bruising on the wrist but did not receive medical care."),
            ("What charge was filed?", "Domestic battery."),
            ("Was a protective or no-contact order issued?", "Yes, a temporary no-contact order remains active."),
            ("What is the court status?", "The case is pending; no disposition exists."),
            ("Have counseling or treatment occurred because of that incident?", "I completed an alcohol evaluation; recommendations are pending."),
            ("We will visit that individual reportable incident after we complete this report. When did the foreign contact begin?", "January 2026."),
            ("What is the nature of the foreign contact?", "A close friendship with a Brazilian citizen and resident whom I met online."),
            ("How often do you communicate and what do you discuss?", "Weekly; family, work, travel, and personal matters."),
            ("Have money, gifts, business interests, or requests for protected information been involved?", "No."),
        ],
        "events": [
            event("Domestic violence arrest involving alcohol", ["E", "G", "J"], ["Personal Conduct", "Alcohol Consumption", "Criminal Conduct"],
                "On July 26, 2026, I consumed four mixed drinks, argued with my partner, and grabbed their wrist. My partner sustained bruising but did not receive medical care. I was arrested and charged with domestic battery. A temporary no-contact order remains active. The case is pending and no disposition exists. I completed an alcohol evaluation, and its recommendations are pending.",
                ["aci.criminal.arrest"], ["Any change to the charge, no-contact order, court schedule, plea, sentence, probation, or final disposition", "Any recommendation, counseling, education, or treatment resulting from the alcohol evaluation or domestic-violence incident"],
                [("Arrest or booking record", "Arresting agency"), ("Court and no-contact-order records", "Clerk of court"), ("Alcohol evaluation", "Evaluation provider")]),
            event("Continuing association with a Brazilian national", ["B"], ["Foreign Influence"],
                "Since January 2026, I have maintained a close friendship with a citizen and resident of Brazil whom I met online. We communicate weekly about family, work, travel, and personal matters. We have not exchanged money or gifts, have no business interests together, and there have been no requests for classified, controlled, or nonpublic information.",
                ["aci.foreign-contact.continuing"], ["Any material change in closeness, frequency, financial connection, travel, shared residence, business activity, or requests for information associated with the contact"]),
        ],
    },
    {
        "slug": "19-alcohol-treatment-holder", "title": "Alcohol treatment without arrest",
        "role": "holder", "population": "industry", "form": "incident_report", "access": "baseline",
        "initial": "I voluntarily entered outpatient alcohol treatment after my drinking began affecting attendance at work. There was no arrest.",
        "qas": [
            ("When did treatment begin?", "August 12, 2026."),
            ("What type of treatment is occurring?", "An eight-week outpatient alcohol program with weekly counseling."),
            ("What prompted treatment?", "I missed three work shifts in July after drinking the night before."),
            ("Did the employer take action?", "My supervisor issued written attendance counseling; I remain employed."),
            ("Was there any arrest, charge, accident, or injury?", "No."),
            ("What is the current treatment status?", "I have completed three sessions and remain enrolled."),
        ],
        "events": [event("Outpatient alcohol treatment", ["E", "G"], ["Personal Conduct", "Alcohol Consumption"],
            "I began an eight-week outpatient alcohol program with weekly counseling on August 12, 2026, after missing three work shifts in July because I had been drinking the night before. My supervisor issued written attendance counseling, and I remain employed. There was no arrest, charge, accident, or injury. I have completed three sessions and remain enrolled.",
            ["aci.treatment.alcohol-drug"], ["Any treatment recommendation, completion, discharge, relapse, renewed attendance issue, employer action, or change in treatment status"],
            [("Treatment enrollment or completion record", "Treatment provider"), ("Attendance counseling", "Employer")])],
    },
    {
        "slug": "20-tax-delinquency-garnishment-holder", "title": "Tax delinquency and garnishment — military holder",
        "role": "holder", "population": "federal", "form": "incident_report", "access": "ts_q",
        "initial": "I owe federal income tax from two years and a wage garnishment started this month.",
        "qas": [
            ("Which tax years are involved?", "2023 and 2024."),
            ("What amount is currently owed?", "Approximately $31,600 including penalties and interest."),
            ("When did the debt become more than 120 days delinquent?", "December 2025."),
            ("When did the garnishment begin?", "August 15, 2026."),
            ("What caused the unpaid balance?", "I under-withheld while earning self-employment income and did not reserve funds for taxes."),
            ("What steps have you taken?", "I filed all returns, entered an installment agreement, changed withholding, and met with a financial counselor."),
        ],
        "events": [event("Federal tax delinquency and wage garnishment", ["F"], ["Financial Considerations"],
            "I owe approximately $31,600, including penalties and interest, in federal income tax for 2023 and 2024. The debt became more than 120 days delinquent in December 2025, and a wage garnishment began on August 15, 2026. The balance resulted from under-withholding on self-employment income and my failure to reserve funds for taxes. I filed all required returns, entered an installment agreement, changed my withholding, and met with a financial counselor.",
            ["aci.finance.bankruptcy-delinquency", "tsq.finance.anomalies"], ["Any missed or modified installment payment, levy, lien, garnishment change, new tax balance, collection action, or additional financial counseling connected to this matter"],
            [("Account transcript and installment agreement", "Tax authority"), ("Garnishment notice", "Payroll office")])],
    },
]


DEEP_QUESTIONS = [
    "What was happening before the earliest event you described?",
    "What specifically set the matter in motion?",
    "What actions did you take, in order?",
    "Who was directly involved or witnessed the material events?",
    "Which organizations, agencies, courts, providers, or institutions are involved?",
    "What happened immediately after the central event?",
    "What identifying numbers, notices, orders, or records exist?",
    "What later consequences occurred at home, work, financially, medically, or administratively?",
    "Had anything materially similar happened before?",
    "What changed or what controls were put in place afterward?",
    "What remains unresolved as of this report?",
    "What future event, decision, payment, review, counseling, treatment, or update is expected?",
]

# These answers deliberately add facts beyond the short opening account. The
# generator refuses a case unless every question has a case-specific answer.
DEEP_ANSWERS = {
    "01-owi-arrest-holder": [
        "I worked a normal shift, then attended a coworker's retirement dinner and remained at the restaurant afterward.",
        "I continued drinking while talking with coworkers and left when the gathering ended.",
        "I drank, decided I could drive, left alone, traveled toward home, and was stopped after crossing the center line.",
        "Several coworkers saw me at dinner; Person 1 knew when I was released, and Person 2 learned the next workday.",
        "The state patrol made the stop, the Cedar County jail handled booking, and the county district court has the pending case.",
        "I completed roadside tests, provided a breath sample, was arrested, and spent the night in jail before release.",
        "The citation, booking number, temporary-license notice, and pending court docket identify the matter; the final disposition does not exist yet.",
        "My license is temporarily restricted, I paid towing and bond costs, and I told my supervisor; no collision or injury occurred.",
        "I had no earlier arrest or alcohol-related driving incident and had not previously driven after that amount of alcohol.",
        "I stopped drinking when driving is possible, use a designated driver or rideshare, and gave my spouse access to transportation plans.",
        "The criminal charge, administrative license action, and any alcohol-evaluation requirement remain unresolved.",
        "A court appearance, license review, possible evaluation, and final disposition are expected and will be provided to the security office.",
    ],
    "02-assault-arrest-holder": [
        "I ate dinner and had two drinks inside the restaurant before patrons began leaving near closing time.",
        "Another patron accused me of spilling a drink and followed me outside while continuing the argument.",
        "I argued, stepped toward him, punched him once, stopped when others intervened, and waited for police.",
        "The injured patron, Person 1, two restaurant employees, and several patrons were present.",
        "City police arrested me, the municipal detention center booked me, and the county criminal court is handling the charge.",
        "Staff separated us, treated the cut with first-aid supplies, and called police and emergency medical personnel.",
        "An arrest report, booking record, complaint, release order, and temporary no-contact order exist; a final disposition does not.",
        "I missed one work shift while detained and paid bond; the other person received treatment at the scene and made no known civil claim.",
        "I have no prior assault arrest, workplace violence event, or similar physical altercation.",
        "I avoid the restaurant and the other person, comply with the order, and leave confrontational situations rather than continuing them.",
        "Arraignment, the charging decision, the duration of the no-contact order, and the case outcome remain pending.",
        "The next court date, any counseling requirement, and the final disposition will be reported when issued.",
    ],
    "03-domestic-violence-alcohol-holder": [
        "My spouse and I were at home after dinner, and I had been drinking beer for about four hours.",
        "An argument about household expenses escalated after we both raised our voices.",
        "I continued arguing, moved toward my spouse, shoved them once, stepped back, and did not make further physical contact.",
        "My spouse was directly involved, and a neighbor heard the argument and called law enforcement.",
        "City police responded, the county jail booked me, and the county district court issued the temporary no-contact order.",
        "Police separated us, photographed the area, spoke to my spouse, arrested me, and held me overnight.",
        "The incident report, booking record, criminal complaint, bond paperwork, no-contact order, and pending docket exist.",
        "I cannot return to the shared residence while the order is active, missed work after release, and paid bond and temporary lodging costs.",
        "There was no prior domestic-violence arrest, protective order, or alcohol-related assault.",
        "I comply with the no-contact order, avoid alcohol, stay elsewhere, and communicate only through permitted court channels.",
        "The injury allegation, criminal charge, residence arrangements, and preliminary-hearing outcome remain unresolved.",
        "Court dates, any domestic-violence or alcohol evaluation, order changes, and the final disposition will require security-office updates.",
    ],
    "04-foreign-contact-holder": [
        "I joined an international engineering association and participated in an online technical discussion group.",
        "The contact sent me a private message after we discussed the same engineering conference presentation.",
        "We exchanged professional messages, added personal topics, began video calls, and continued communicating about twice each month.",
        "The foreign contact and I communicate directly; Person 1, my spouse, knows of the friendship.",
        "The engineering association and our personal email and video-call services are the only organizations or platforms involved.",
        "After the first exchange, we continued discussing family, employment, hobbies, and possible personal travel.",
        "I retain the contact's name, citizenship, residence, employer description, email address, and message history for submission through the security office.",
        "There has been no money, gift, employment action, travel, sponsorship, or request for government information.",
        "I had not previously reported this person because the continuing personal association developed after my last investigation.",
        "I do not discuss classified, controlled, proprietary, or nonpublic work and will report any request or material change.",
        "No request, pressure, government connection, financial tie, or planned meeting is unresolved; the association itself continues.",
        "Any increase in closeness, travel, shared finances, business activity, unusual questions, or change in residence or citizenship will be reported.",
    ],
    "05-gambling-debt-holder": [
        "Before the delinquency, I used online sports-betting applications several evenings each week and paid balances from ordinary income.",
        "Losses increased during a three-month period, and I used credit cards to continue betting after exhausting available cash.",
        "I placed bets, took cash advances, missed minimum payments, stopped betting, contacted creditors, and entered payment plans.",
        "I alone controlled the accounts; Person 1, my spouse, learned of the debt when collection notices arrived.",
        "Three card issuers, the betting platforms, and a licensed gambling counselor are involved.",
        "After recognizing the total debt, I self-excluded from the platforms and disclosed all accounts to my spouse.",
        "Monthly statements, delinquency notices, self-exclusion confirmations, payment plans, and counseling attendance records exist.",
        "The debt affected household savings and credit, but there is no lawsuit, garnishment, personal loan, or illegal gambling.",
        "I had gambled recreationally before but had no earlier gambling debt, delinquency, or counseling.",
        "Betting access is blocked, my spouse reviews accounts weekly, and scheduled payments are automatic.",
        "The balances remain delinquent while repayment continues; none of the creditors has issued a judgment.",
        "Monthly counseling, creditor payments, any collection escalation, and eventual payoff or account resolution will be updated.",
    ],
    "06-marijuana-use-applicant": [
        "Before applying, I lived in a state where adult marijuana sales were permitted and used it socially on some weekends.",
        "Friends used marijuana at a private gathering, and I chose to participate.",
        "I purchased small personal quantities, stored them at home, used approximately monthly, and stopped in April before beginning the application.",
        "I used with adult friends; no coworker, supervisor, foreign national, or minor was involved.",
        "A state-licensed dispensary was the source; no law-enforcement, court, employer, or treatment provider is involved.",
        "There was no arrest, accident, workplace event, medical emergency, or other immediate consequence.",
        "Purchase receipts may exist in the dispensary account, but there is no police, court, or treatment record.",
        "The use did not cause debt, missed work, discipline, injury, or legal proceedings.",
        "The monthly use from June 2024 through April 2026 is the complete history; there was no other illegal-drug use.",
        "I stopped using, discarded remaining products, and do not intend to use marijuana while seeking or holding a national-security position.",
        "No charge or treatment matter is unresolved; the dates and frequency must be disclosed accurately on the initial form.",
        "Any additional use, purchase, drug-related contact, evaluation, or treatment before adjudication would be reported to the sponsor.",
    ],
    "07-bankruptcy-in-process": [
        "Before filing, my household relied on one income for ten months while uninsured medical bills and ordinary expenses accumulated.",
        "Minimum payments became unsustainable after savings were exhausted and interest increased the unsecured balances.",
        "I reviewed every account, completed credit counseling, retained filing assistance, signed the petition, and filed Chapter 7.",
        "My spouse shares the household impact; the petition lists institutional creditors and no debt to friends or relatives.",
        "The bankruptcy court, trustee, credit-counseling provider, medical creditors, and card issuers are involved.",
        "The court opened the case, assigned a case number and trustee, stayed collection activity, and scheduled the creditors meeting.",
        "The petition, schedules, counseling certificate, trustee notice, creditor matrix, and docket exist.",
        "Collection calls stopped under the stay; no wage garnishment or employment action occurred.",
        "I had no prior bankruptcy, foreclosure, repossession, or tax delinquency.",
        "I use a written budget, no longer use credit cards, maintain current household bills, and completed required counseling.",
        "The creditors meeting, any trustee requests, and the discharge decision remain unresolved.",
        "I will update the sponsoring security office with amendments, dismissal, discharge, new delinquency, or any repayment requirement.",
    ],
    "08-information-technology-misuse-holder": [
        "Before installing the software, I was working remotely and wanted access to unclassified files outside the approved connection method.",
        "The approved remote service was unavailable, and I chose an unapproved shortcut instead of contacting the help desk.",
        "I downloaded the program, installed it, connected from home, opened work files, disconnected, and left the software installed.",
        "I was the only user; the help desk, IT security staff, my supervisor, and security office later became involved.",
        "The government laptop, agency network, endpoint-monitoring service, and IT security office are involved.",
        "Endpoint monitoring generated an alert, IT isolated the laptop, removed the software, and interviewed me.",
        "The alert, endpoint logs, incident ticket, software-removal record, and written counseling memorandum exist.",
        "My remote access was temporarily suspended, I completed retraining, and I received written counseling; no data recipient was identified.",
        "I had no earlier unauthorized-software, access-control, or remote-access incident.",
        "I use only approved connections, contact the help desk when access fails, and cannot install software without administrator approval.",
        "The internal security review remains open, although the device has been remediated and returned.",
        "Any investigative finding, discipline, access change, or closure memorandum will be reported.",
    ],
    "09-protected-information-holder": [
        "Before the email, I was preparing an unclassified technical package at work and wanted to continue reviewing it at home.",
        "I selected my personal address from autocomplete without checking the recipient or the controlled marking on the attachment.",
        "I attached the drawing, sent the message, noticed the address, contacted my supervisor, and reported to security within forty minutes.",
        "I was the sender; my supervisor, security staff, and IT responders handled containment, and no outside person received the file.",
        "The employer email system, my personal mailbox provider, the security office, and IT incident-response team are involved.",
        "IT preserved logs, confirmed deletion, disabled synchronization, and checked for forwarding or additional access.",
        "The sent-message record, incident ticket, deletion confirmation, access logs, and open review file exist.",
        "I completed remedial handling training and temporarily lost external-email privileges; there was no classified-data exposure.",
        "I had no earlier mishandling, unauthorized transmission, or personal-email incident.",
        "I verify recipients and markings before sending, use only approved storage, and do not forward work to personal accounts.",
        "The internal finding and any final administrative action remain unresolved.",
        "The security-office closure, discipline decision, access restoration, and any additional training will be updated.",
    ],
    "10-foreign-passport-applicant": [
        "I was born in Canada, moved to the United States as a child, and retained Canadian citizenship by birth.",
        "I renewed a Canadian passport in 2023 for identification and family travel.",
        "I applied through the Canadian passport office, received the passport, used it twice for Canada travel, and retained it.",
        "My Canadian parent and relatives know of the citizenship; no foreign official has contacted me beyond routine passport processing.",
        "The Canadian passport authority and border agencies are involved; no foreign employer, bank, political party, or military is involved.",
        "The two trips ended normally with no security incident, unusual contact, or government inquiry.",
        "The passport number, issue and expiration dates, application record, and travel dates are available for the form.",
        "There was no financial benefit, voting, foreign service, property ownership, or employment consequence.",
        "The citizenship has existed since birth; this is the only foreign passport I have possessed.",
        "I will disclose the citizenship and passport fully and will notify the sponsor of renewal, use, loss, or surrender.",
        "Nothing is pending with Canadian authorities; the current passport remains valid and in my possession.",
        "Any travel, passport transaction, or new exercise of foreign-citizenship rights during the investigation will be reported.",
    ],
    "11-foreign-business-holder": [
        "Before investing, I knew one founder through an international software forum and reviewed the company's public product materials.",
        "The founders offered a small equity interest and informal advisory role after several technical conversations.",
        "I reviewed the agreement, transferred $12,000 from personal savings, received shares, and began monthly advisory calls.",
        "The two German founders and I are the directly involved people; Person 1, my spouse, knows of the investment.",
        "The German company, its German bank, my United States bank, and the video-call service are involved.",
        "After investing, I received corporate documents and attended monthly calls but performed no operational work.",
        "The share agreement, wire record, capitalization table, meeting invitations, and company registration details exist.",
        "No income or distribution has been received, no employer resource was used, and no classified or proprietary information was discussed.",
        "I had no prior foreign-business ownership, foreign bank account, or paid foreign outside activity.",
        "I separate the activity from government work, share no protected information, and will obtain approval before any expanded role.",
        "The equity remains owned, the advisory relationship continues, and the company has not announced a distribution or sale.",
        "Any ownership change, payment, travel, new duty, government connection, or information request will be reported.",
    ],
    "12-compulsive-gambling-treatment-holder": [
        "Before seeking help, I gambled online several nights a week and concealed the total losses from my spouse for several months.",
        "A bank alert showed repeated transfers and led me to calculate the full $27,000 loss.",
        "I disclosed the losses, stopped betting, self-excluded, contacted a counselor, and transferred account-monitoring access to my spouse.",
        "I controlled the gambling accounts; Person 1, my spouse, now knows and participates in financial controls.",
        "The betting platforms, bank, licensed counselor, and household creditors are involved.",
        "I closed the betting sessions, saved transaction histories, and scheduled the first counseling appointment.",
        "Bank statements, platform histories, self-exclusion confirmations, and counseling attendance records exist.",
        "Savings decreased, but all bills remain current and there is no collection, lawsuit, borrowing, or delinquency.",
        "I gambled recreationally before November 2025 but had no earlier treatment or comparable loss period.",
        "I remain self-excluded, attend weekly counseling, use spending limits, and review all accounts with my spouse.",
        "Treatment is ongoing and the long-term financial recovery plan remains active.",
        "Counseling progress, renewed gambling, debt, delinquency, or changes to account controls will be reported.",
    ],
    "13-prescription-misuse-arrest-holder": [
        "Before the arrest, I was studying after work and had slept poorly for several nights.",
        "A friend offered prescription stimulant tablets and I accepted them to remain awake.",
        "I used tablets on three occasions, kept four unused tablets, carried them in my vehicle, and police found them during a stop.",
        "The friend supplied the tablets; the arresting officer, booking staff, evaluator, and court are involved.",
        "City police, the county jail, the county criminal court, and a licensed substance-use evaluator are involved.",
        "Police seized the tablets, arrested and booked me, and released me with a court notice.",
        "The seizure report, booking record, complaint, docket, and completed evaluation exist; no final disposition exists.",
        "I paid bond, disclosed the matter at work, and completed an evaluation; there was no injury or workplace use.",
        "There was no earlier misuse of another person's prescription, illegal-drug arrest, or treatment.",
        "I do not possess or use medication not prescribed to me and use sleep and study planning instead of stimulants.",
        "The charge, evaluator recommendation, and any court-ordered testing or treatment remain unresolved.",
        "Court dates, disposition, probation conditions, testing, counseling, or treatment recommendations will be updated.",
    ],
    "14-workplace-theft-in-process": [
        "Before removal, I worked for the employer and knew the monitors were stored as surplus but had no permission to take them.",
        "I wanted monitors for home use and incorrectly treated the storage status as permission.",
        "I entered the storage room, removed two monitors, put them in my vehicle, left work, and returned them after being contacted.",
        "I acted alone; a security-camera reviewer, supervisor, loss-prevention employee, and police officer became involved.",
        "The former employer, city police, booking facility, and county criminal court are involved.",
        "The employer reviewed video, contacted me, recovered the monitors, terminated me, and referred the matter to police.",
        "Video, inventory records, recovery receipt, termination notice, arrest record, complaint, and pending docket exist.",
        "I lost the job, returned the property undamaged, paid bond, and currently have no restitution figure.",
        "I had no prior theft, unauthorized removal of property, termination for misconduct, or criminal arrest.",
        "I do not retain employer property without written authorization and have provided the sponsor with current employment information.",
        "The misdemeanor charge, any restitution, and the investigation's effect on sponsorship remain unresolved.",
        "Court dates, plea, disposition, restitution, employment developments, and sponsor instructions will be reported.",
    ],
    "15-sexual-misconduct-charge-applicant": [
        "Before the alleged contact, I attended a private social gathering where several adults were present.",
        "The complainant and I spoke privately after the gathering; the criminal complaint alleges that later contact was nonconsensual.",
        "I interacted with the complainant, left the gathering, later responded to investigators, and was arrested when the charge was filed.",
        "The complainant, other gathering attendees, investigators, and I are identified in the police and court records.",
        "The police department, booking facility, criminal court, and office that issued the no-contact order are involved.",
        "Investigators interviewed witnesses, I was booked and released, and the court imposed a no-contact order.",
        "The incident report, interview records, booking record, complaint, docket, and no-contact order exist.",
        "I comply with the order and changed social routines; no employment action or separate civil case has been reported.",
        "I have no prior sexual-misconduct complaint, arrest, no-contact order, or similar workplace allegation.",
        "I have no contact with the complainant and preserve all communications requested by investigators or the court.",
        "The allegation, motions, trial schedule, charge, and case outcome remain unresolved.",
        "Order changes, hearings, plea, disposition, sentence, evaluation, counseling, or treatment will be reported.",
    ],
    "16-unofficial-foreign-travel-holder": [
        "Before travel, Person 1 and I planned a five-day vacation and booked commercial flights and a hotel.",
        "I failed to recognize that personal Mexico travel required advance security-office approval.",
        "I booked the trip, traveled using my United States passport, followed the itinerary, returned, recognized the omission, and notified security.",
        "Person 1 traveled with me; hotel and airline employees were routine contacts, and no continuing foreign contact developed.",
        "The airline, hotel, passport-control authorities, and my security office are involved.",
        "We returned as scheduled with no detention, loss, unusual approach, itinerary change, or security incident.",
        "Flight confirmations, hotel receipt, passport entry information, itinerary, and security-office notification exist.",
        "There was no financial anomaly, medical event, law-enforcement contact, employer discipline, or loss of equipment.",
        "I had no earlier unreported foreign travel or prior warning about a missed travel-reporting requirement.",
        "I entered future travel into the security process early and use a pre-travel checklist before purchasing tickets.",
        "The security office has not yet closed its review of the late notification.",
        "Any follow-up question, corrective action, newly remembered contact, or itinerary correction will be reported.",
    ],
    "17-large-gambling-winnings-holder": [
        "Before the tournament, I registered with personal funds and traveled to Nevada for the scheduled event.",
        "I advanced through the tournament and received the posted prize after the final round.",
        "I paid the entry fee, played, won $42,000, received a casino check and tax form, and deposited the check two days later.",
        "I was the sole winner and owner of the funds; Person 1, my spouse, knew of the trip and deposit.",
        "The licensed casino, tournament operator, tax-reporting office, and my United States bank are involved.",
        "The casino verified my identity, issued the payment and tax form, and recorded the result.",
        "The entry receipt, results sheet, casino check, tax form, deposit receipt, and bank statement exist.",
        "The deposit increased available assets; it caused no debt, loan, collection action, or employment consequence.",
        "I had no prior gambling win or other unusual asset infusion of $10,000 or more.",
        "I retained source records, set aside estimated taxes, and did not transfer the funds to another person or foreign account.",
        "The tax liability will not be final until the applicable return is filed.",
        "Any corrected tax form, ownership dispute, returned deposit, or tax assessment will be reported.",
    ],
    "18-domestic-violence-plus-foreign-contact": [
        "Before the domestic incident I was drinking at home with my partner; separately, the Brazilian friendship had continued online since January.",
        "The domestic argument escalated over plans for the evening; the foreign contact began through a shared online hobby group.",
        "I argued and grabbed my partner's wrist, was arrested and evaluated; separately, I continued weekly messages with the foreign contact.",
        "My partner, responding officers, and medical personnel relate to incident one; the Brazilian contact relates only to incident two.",
        "Police, jail, court, evaluation provider, no-contact-order office, and the online communications platform are involved.",
        "Police separated us and arrested me; the unrelated foreign communications continued without any request for protected information.",
        "Incident one has arrest, booking, complaint, order, docket, and evaluation records; incident two has contact-identification and message records.",
        "The domestic incident changed residence and communication arrangements; the foreign contact caused no financial, employment, or legal consequence.",
        "There was no earlier domestic arrest or foreign-contact report involving either person.",
        "I comply with the order and evaluation process; I keep protected information out of foreign communications and report material changes.",
        "The domestic case and evaluation recommendations remain pending; the foreign friendship remains ongoing but otherwise unchanged.",
        "Court, order, treatment, or disposition changes and any change in the foreign relationship will be separately updated.",
    ],
    "19-alcohol-treatment-holder": [
        "Before treatment, my drinking increased over several months and I sometimes drank late on work nights.",
        "Missing three shifts after drinking led my supervisor to issue attendance counseling and prompted me to seek help.",
        "I disclosed the attendance cause, contacted a provider, completed intake, enrolled in eight weeks of outpatient care, and attended three sessions.",
        "I am the patient; Person 1, my spouse, my supervisor, and the treatment provider know the relevant facts.",
        "My employer, outpatient provider, and security office are involved; no police, court, or licensing agency is involved.",
        "My supervisor documented the absences, I returned to work, and the provider established a weekly schedule.",
        "Attendance records, written workplace counseling, provider enrollment, treatment plan, and later completion record exist or will exist.",
        "I remain employed and current on attendance; there was no arrest, injury, accident, debt, or license action.",
        "I had no prior alcohol treatment or alcohol-related arrest, although the increased work-night drinking lasted several months.",
        "I attend weekly sessions, avoid alcohol, involve my spouse in scheduling, and follow the provider's recommendations.",
        "Five sessions and formal completion remain; the provider has not issued the final outcome record.",
        "Completion, discharge, changed recommendations, recurrence, missed treatment, or new employer action will be reported.",
    ],
    "20-tax-delinquency-garnishment-holder": [
        "Before the debt, I earned salary and self-employment income but did not increase withholding or reserve estimated taxes.",
        "Filing the returns showed balances I could not pay, and penalties and interest accumulated after notices were not fully resolved.",
        "I filed all returns, communicated with the tax authority, entered an installment agreement, changed withholding, and attended financial counseling.",
        "I am responsible for the returns; Person 1, my spouse, and a financial counselor know the repayment plan.",
        "The federal tax authority, payroll office, financial counselor, and my bank are involved.",
        "The tax authority issued collection notices and a garnishment order, and payroll began withholding on August 15.",
        "Tax returns, account transcripts, notices, installment agreement, garnishment order, pay statements, and counseling record exist.",
        "Net pay decreased and household budgeting changed; there is no bankruptcy, foreclosure, or unpaid state tax.",
        "I had no prior tax lien, levy, garnishment, or debt over 120 days delinquent.",
        "Withholding is corrected, installment payments are automatic, self-employment taxes are reserved monthly, and spending follows a written budget.",
        "The $31,600 balance, garnishment, and installment agreement remain active.",
        "Payments, balance changes, lien or levy action, agreement changes, payoff, and additional counseling will be reported.",
    ],
}


SPECIAL_EVENT_DETAILS = {
    "18-domestic-violence-plus-foreign-contact": [
        (
            "Before the incident on July 26, 2026, I consumed four mixed drinks at home with my partner. An "
            "argument about evening plans escalated, and I grabbed my partner's wrist. My partner sustained "
            "bruising but did not receive medical care. My partner, responding officers, and medical "
            "personnel were involved; the unrelated Brazilian contact was not involved. Police separated "
            "us, documented the bruising, arrested me for domestic battery, and took me to the county jail. The arrest report, "
            "booking record, complaint, temporary no-contact order, court docket, and alcohol-evaluation "
            "record identify the matter. I completed the alcohol evaluation, but its recommendations are "
            "pending. I am living separately and complying with the order. There was no "
            "earlier domestic-violence arrest or protective order. The charge, order, court disposition, and "
            "evaluation recommendations remain unresolved. I will update the security office about any "
            "hearing, plea, disposition, sentence, order change, counseling, education, or treatment."
        ),
        (
            "The separate friendship began through an online hobby group in January 2026. The contact is a "
            "citizen and resident of Brazil, and we communicate weekly about family, work, travel, and "
            "personal matters. The domestic incident, police, court, and evaluation provider have no "
            "connection to this friendship. I retain the contact's identifying information and relevant "
            "message history. We have not exchanged money or gifts, shared a residence, conducted business, "
            "planned travel together, or discussed classified, controlled, proprietary, or nonpublic work. "
            "There has been no request for government information and no known foreign-government connection. "
            "I have not met the contact in person, sponsored immigration, or made plans to share a residence. "
            "The friendship remains ongoing. I will report any material change in closeness, frequency, travel, "
            "shared finances, business activity, residence, citizenship, unusual questions, or requests for "
            "information."
        ),
    ]
}


def integrated_sentences(sentences):
    """Keep one readable statement while preferring specific overlapping facts."""
    kept = []
    stop = {"a", "an", "and", "as", "at", "for", "from", "in", "is", "it", "of", "on", "the", "to", "was", "were", "with"}

    def terms(sentence):
        return {w.lower() for w in re.findall(r"[A-Za-z0-9'-]+", sentence) if w.lower() not in stop}

    def specificity(sentence):
        return (len(re.findall(r"\d", sentence)) * 20) + len(sentence)

    for sentence in sentences:
        candidate = sentence.strip()
        if not candidate:
            continue
        candidate_terms = terms(candidate)
        duplicate_at = None
        for index, existing in enumerate(kept):
            existing_terms = terms(existing)
            denominator = min(len(candidate_terms), len(existing_terms))
            overlap = len(candidate_terms & existing_terms) / denominator if denominator else 0
            sequence_similarity = SequenceMatcher(
                None, candidate.lower(), existing.lower()
            ).ratio()
            if overlap >= 0.48 or sequence_similarity >= 0.56:
                duplicate_at = index
                break
        if duplicate_at is None:
            kept.append(candidate)
        elif specificity(candidate) > specificity(kept[duplicate_at]):
            kept[duplicate_at] = candidate
    return " ".join(kept)


def deepen_cases():
    """Attach the detailed interview and its facts before artifacts are built."""
    for case in CASES:
        answers = DEEP_ANSWERS.get(case["slug"])
        if answers is None or len(answers) != len(DEEP_QUESTIONS):
            raise RuntimeError(f"{case['slug']}: missing complete deep-interview answers")
        case["qas"].extend(zip(DEEP_QUESTIONS, answers))

        special = SPECIAL_EVENT_DETAILS.get(case["slug"])
        if special:
            if len(special) != len(case["events"]):
                raise RuntimeError(f"{case['slug']}: event-detail count does not match incident count")
            for developed_event, final_narrative in zip(case["events"], special):
                developed_event["narrative"] = final_narrative
            additions = [""] * len(case["events"])
        else:
            # Build one chronological statement. The short event narrative is
            # the central event; interview facts supply the lead-in and the
            # aftermath. They are not rendered as a second, labelled report.
            original_sentences = [
                s.strip()
                for s in re.split(r"(?<=[.!?])\s+", case["events"][0]["narrative"].strip())
                if s.strip()
            ]
            integrated = integrated_sentences([answers[0], answers[1], *original_sentences, *answers[3:]])
            case["events"][0]["narrative"] = integrated
            additions = [""]

        for developed_event, addition in zip(case["events"], additions):
            if addition:
                developed_event["narrative"] += "\n\n" + addition
            declared_people = {person["label"] for person in developed_event["persons"]}
            for label, replacement in (("Person 1", "my spouse"), ("Person 2", "another person known to me")):
                if label not in declared_people:
                    developed_event["narrative"] = developed_event["narrative"].replace(
                        f"{label}, my spouse,", "my spouse"
                    ).replace(
                        f"{label}, my spouse", "my spouse"
                    ).replace(label, replacement)
            facts = [
                s.strip()
                for s in re.split(r"(?<=[.!?])\s+", developed_event["narrative"])
                if s.strip()
            ]
            phases = developed_event["incident_development"]["phases"]
            evidence_order = [0, 1, 2, 3, 4, 5, -2, -1]
            for phase, fact_index in zip(phases.values(), evidence_order):
                phase["evidence"] = facts[fact_index]


def enforce_detail_floor(case):
    """Fail closed when a synthetic run is too abbreviated to test the workflow."""
    if len(case["qas"]) < 17:
        raise RuntimeError(f"{case['slug']}: fewer than 17 substantive follow-up answers")
    for question, answer in case["qas"][-len(DEEP_QUESTIONS):]:
        if len(answer.split()) < 3:
            raise RuntimeError(f"{case['slug']}: low-information answer to {question!r}")
    for developed_event in case["events"]:
        word_count = len(re.findall(r"\b[\w'-]+\b", developed_event["narrative"]))
        if word_count < 125:
            raise RuntimeError(
                f"{case['slug']}: incident narrative has only {word_count} words; minimum is 125"
            )


OPENING = (
    "This workflow helps prepare a complete factual security report. It does not "
    "provide legal advice or predict how a security report may interact with a "
    "separate criminal proceeding, including confidentiality, disclosure, "
    "discoverability, or evidentiary use. Do not provide classified information."
)


def route_qas(case):
    if case["role"] == "applicant":
        return [
            ("Do you currently hold a security clearance?", "No."),
            ("Have you submitted your initial SF-86 or PVQ?", "No."),
        ]
    if case["role"] == "in_process":
        return [
            ("Do you currently hold a security clearance?", "No."),
            ("Have you submitted your initial SF-86 or PVQ?", "Yes."),
            ("Did this matter occur while the investigation was pending?", "Yes."),
        ]
    return [("Do you currently hold a security clearance?", "Yes.")]


def session_for(case):
    initial = case["initial"]
    return {
        "privacy_tier": "high",
        "privacy_tier_chosen_by_user": True,
        "mapping_notice_delivered": True,
        "user_confirmations": {"mapping_notice": "I will keep the private mapping for each Person number."},
        "population": case["population"],
        "role": case["role"],
        "form": case["form"],
        "access_tier": case["access"],
        "position_type": "national_security",
        "final_analysis_complete": True,
        "narrative": initial,
        "narrative_sha256": hashlib.sha256(initial.encode("utf-8")).hexdigest(),
        "deployment_mode_disclosed": True,
        "stage_log": [
            {"stage": "intake", "note": "Synthetic intake and role route completed."},
            {"stage": "requirements", "note": "Internal requirements pass; no conclusion shown yet."},
            {"stage": "classification", "note": "Applicable guidelines identified."},
            {"stage": "question_sourcing", "note": "Scenario questions sourced."},
            {"stage": "gap_loop", "note": "One-fact-at-a-time interview completed."},
            {"stage": "thread_detection", "note": "Independent incidents grouped."},
            {"stage": "consistency", "note": "Factual consistency checked."},
            {"stage": "documents", "note": "Document custodians identified without delaying report."},
            {"stage": "narrative", "note": "First-person incident narrative prepared."},
            {"stage": "candor", "note": "Internal-only candor review completed; no findings exposed."},
            {"stage": "triage_checkpoint", "note": "All queued incidents completed."},
            {"stage": "final_analysis", "note": "Combined final reporting analysis completed."},
        ],
        "events": case["events"],
        "entities": [],
        "outstanding_required": [],
        "data_you_must_supply": [],
    }


def transcript_for(case):
    rows = [
        f"# Synthetic workflow transcript: {case['title']}", "",
        "> FICTIONAL TEST DATA — no person or event in this transcript is real.", "",
        "This transcript preserves the initial statement and every workflow question and answer. The submission-ready, integrated statement is in `report.md`.", "",
        "## Initial instructions and intake", "",
        "**Workflow:** " + OPENING, "",
        "**Workflow:** This test uses the high-privacy mode. Keep your own mapping for numbered people; the tool does not collect their identities.", "",
        "**Synthetic user:** I will keep the private mapping for each Person number.", "",
    ]
    for q, a in route_qas(case):
        rows.extend([f"**Workflow:** {q}", "", f"**Synthetic user:** {a}", ""])
    rows.extend(["## Initial statement", "", "**Workflow:** What happened?", "", f"**Synthetic user:** {case['initial']}", "", "## Detailed interview", ""])
    for q, a in case["qas"]:
        rows.extend([f"**Workflow:** {q}", "", f"**Synthetic user:** {a}", ""])
    rows.extend([
        "**Workflow:** I have completed the current incident. I will return to triage for any independent incident and will wait until all incidents are developed before providing the final reporting analysis.", "",
        "**Synthetic user:** No other independent incident remains beyond those already stated.", "",
        "**Workflow:** The final combined analysis is complete. The attached report uses one narrative for each factually independent incident and lists every applicable DISS incident type only for clearance-holder output.", "",
    ])
    return "\n".join(rows)


def complete_record_for(case, transcript_text, report_text):
    return "\n".join([
        f"# Complete synthetic case record: {case['title']}",
        "",
        "> FICTIONAL TEST DATA — no person or event in this record is real.",
        "",
        "This file preserves what was initially provided, every question and answer, and the single integrated final report.",
        "",
        "## Intake and interview record",
        "",
        transcript_text,
        "",
        "## Integrated final report",
        "",
        report_text,
        "",
    ])


def run(cmd):
    result = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True)
    if result.returncode:
        raise RuntimeError(f"Command failed ({' '.join(map(str, cmd))}):\n{result.stdout}{result.stderr}")
    return result.stdout.strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-o", "--output", default="output/synthetic-workflow-runs-20")
    args = ap.parse_args()
    out = ROOT / args.output
    out.mkdir(parents=True, exist_ok=True)
    index = [
        "# Twenty fictional adverse-information workflow runs", "",
        "> All people, dates, organizations, and events are synthetic test data.", "",
        "Each case includes the complete workflow transcript, gated session state, and deterministically assembled and verified report.", "",
        "| # | Scenario | Route | Incidents | Artifacts |", "|---:|---|---|---:|---|",
    ]
    deepen_cases()
    verification = []
    for number, case in enumerate(CASES, 1):
        enforce_detail_floor(case)
        case_dir = out / case["slug"]
        case_dir.mkdir(parents=True, exist_ok=True)
        transcript = case_dir / "transcript.md"
        session_path = case_dir / "session.json"
        report_path = case_dir / "report.md"
        transcript_text = transcript_for(case)
        transcript.write_text(transcript_text, encoding="utf-8")
        session_path.write_text(json.dumps(session_for(case), indent=2) + "\n", encoding="utf-8")
        run([sys.executable, "scripts/validate_session.py", str(session_path)])
        run([sys.executable, "scripts/assemble_package.py", str(session_path), "-o", str(report_path)])
        verified = run([sys.executable, "scripts/verify_output.py", str(report_path), str(session_path)])
        report_text = report_path.read_text(encoding="utf-8")
        (case_dir / "complete-record.md").write_text(
            complete_record_for(case, transcript_text, report_text), encoding="utf-8"
        )
        digest = hashlib.sha256(report_path.read_bytes()).hexdigest()
        verification.append({"case": case["slug"], "sha256": digest, "verified": "PASS" in verified})
        rel = case["slug"]
        index.append(f"| {number} | {case['title']} | {case['role']} / {case['population']} | {len(case['events'])} | [complete record]({rel}/complete-record.md) · [transcript]({rel}/transcript.md) · [session]({rel}/session.json) · [final report]({rel}/report.md) |")
    (out / "verification.json").write_text(json.dumps(verification, indent=2) + "\n", encoding="utf-8")
    index.extend(["", "## Verification", "", f"All {len(CASES)} sessions validated, assembled, and passed the deterministic output verifier. Hashes are recorded in `verification.json` and alongside each report.", ""])
    (out / "README.md").write_text("\n".join(index), encoding="utf-8")
    print(f"Generated and verified {len(CASES)} synthetic workflow runs in {out}")


if __name__ == "__main__":
    main()
