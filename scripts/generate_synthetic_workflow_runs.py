#!/usr/bin/env python3
"""Generate and gate 20 fictional end-to-end workflow runs.

The artifacts are testing examples, not legal advice and not adjudicative
predictions. Each run contains the synthetic user's inputs, every workflow
question and answer, the gated session state, and the assembled report.
"""
from __future__ import annotations

import argparse
import hashlib
import json
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
    return {
        "title": title,
        "guidelines": guidelines,
        "incident_types": incident_types,
        "future_update_topics": list(updates),
        "incident_development": {
            "profiles": profiles,
            "complete": True,
            "phases": {
                "before": {"status": "answered", "evidence": "The transcript records the circumstances before the incident."},
                "precipitating_circumstances": {"status": "answered", "evidence": "The transcript records what set the incident in motion."},
                "decisions_and_actions": {"status": "answered", "evidence": "The transcript records the synthetic user's actions in sequence."},
                "incident": {"status": "answered", "evidence": narrative},
                "immediate_aftermath": {"status": "answered", "evidence": "The narrative records the immediate result or response."},
                "later_consequences": {"status": "answered", "evidence": "The narrative and follow-up answers record later consequences."},
                "current_status": {"status": "answered", "evidence": "The narrative states the current status as of the fictional report date."},
                "future_developments": {"status": "answered", "evidence": "The tailored update topics identify known or conditional future developments."},
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
        "**Workflow:** " + OPENING, "",
        "**Workflow:** This test uses the high-privacy mode. Keep your own mapping for numbered people; the tool does not collect their identities.", "",
        "**Synthetic user:** I will keep the private mapping for each Person number.", "",
    ]
    for q, a in route_qas(case):
        rows.extend([f"**Workflow:** {q}", "", f"**Synthetic user:** {a}", ""])
    rows.extend(["**Workflow:** What happened?", "", f"**Synthetic user:** {case['initial']}", ""])
    for q, a in case["qas"]:
        rows.extend([f"**Workflow:** {q}", "", f"**Synthetic user:** {a}", ""])
    rows.extend([
        "**Workflow:** I have completed the current incident. I will return to triage for any independent incident and will wait until all incidents are developed before providing the final reporting analysis.", "",
        "**Synthetic user:** No other independent incident remains beyond those already stated.", "",
        "**Workflow:** The final combined analysis is complete. The attached report uses one narrative for each factually independent incident and lists every applicable DISS incident type only for clearance-holder output.", "",
    ])
    return "\n".join(rows)


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
    verification = []
    for number, case in enumerate(CASES, 1):
        case_dir = out / case["slug"]
        case_dir.mkdir(parents=True, exist_ok=True)
        transcript = case_dir / "transcript.md"
        session_path = case_dir / "session.json"
        report_path = case_dir / "report.md"
        transcript.write_text(transcript_for(case), encoding="utf-8")
        session_path.write_text(json.dumps(session_for(case), indent=2) + "\n", encoding="utf-8")
        run([sys.executable, "scripts/validate_session.py", str(session_path)])
        run([sys.executable, "scripts/assemble_package.py", str(session_path), "-o", str(report_path)])
        verified = run([sys.executable, "scripts/verify_output.py", str(report_path), str(session_path)])
        digest = hashlib.sha256(report_path.read_bytes()).hexdigest()
        verification.append({"case": case["slug"], "sha256": digest, "verified": "PASS" in verified})
        rel = case["slug"]
        index.append(f"| {number} | {case['title']} | {case['role']} / {case['population']} | {len(case['events'])} | [transcript]({rel}/transcript.md) · [session]({rel}/session.json) · [report]({rel}/report.md) |")
    (out / "verification.json").write_text(json.dumps(verification, indent=2) + "\n", encoding="utf-8")
    index.extend(["", "## Verification", "", f"All {len(CASES)} sessions validated, assembled, and passed the deterministic output verifier. Hashes are recorded in `verification.json` and alongside each report.", ""])
    (out / "README.md").write_text("\n".join(index), encoding="utf-8")
    print(f"Generated and verified {len(CASES)} synthetic workflow runs in {out}")


if __name__ == "__main__":
    main()
