#!/usr/bin/env python3
"""
Create sample legal data for ingestion.
"""
import asyncio
import json
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.config import settings


async def create_sample_acts():
    """Create sample Indian Acts with sections."""
    print("📝 Creating sample Acts...")
    
    acts = [
        {
            "act_name": "Central Goods and Services Tax Act, 2017",
            "short_name": "CGST Act",
            "year": 2017,
            "sections": [
                {
                    "number": "2",
                    "subsection": "",
                    "chapter": "Chapter I: Preliminary",
                    "marginal_note": "Definitions",
                    "text": "In this Act, unless the context otherwise requires,—\n(1) \"actionable claim\" shall have the same meaning as assigned to it in the Transfer of Property Act, 1882;\n(2) \"address of delivery\" means the address of the recipient of goods or services or both indicated on the tax invoice issued by a registered person for delivery of such goods or services or both;\n(3) \"adjudicating authority\" means any authority, appointed or authorised to pass any order or decision under this Act, but does not include the Board, the First Appellate Authority and the Appellate Tribunal;"
                },
                {
                    "number": "7",
                    "subsection": "",
                    "chapter": "Chapter II: Levy and Collection of Tax",
                    "marginal_note": "Scope of supply",
                    "text": "(1) For the purposes of this Act, the expression \"supply\" includes—\n(a) all forms of supply of goods or services or both such as sale, transfer, barter, exchange, licence, rental, lease or disposal made or agreed to be made for a consideration by a person in the course or furtherance of business;\n(b) import of services for a consideration whether or not in the course or furtherance of business;\n(c) the activities specified in Schedule I, made or agreed to be made without a consideration;\n(d) the activities to be treated as supply of goods or supply of services as referred to in Schedule II."
                },
                {
                    "number": "9",
                    "subsection": "",
                    "chapter": "Chapter II: Levy and Collection of Tax",
                    "marginal_note": "Levy and collection",
                    "text": "(1) Subject to the provisions of sub-section (2), there shall be levied a tax called the central goods and services tax on all intra-State supplies of goods or services or both, except on the supply of alcoholic liquor for human consumption, on the value determined under section 15 and at such rates, not exceeding twenty per cent., as may be notified by the Government on the recommendations of the Council and collected in such manner as may be prescribed and shall be paid by the taxable person."
                },
                {
                    "number": "16",
                    "subsection": "",
                    "chapter": "Chapter V: Input Tax Credit",
                    "marginal_note": "Eligibility and conditions for taking input tax credit",
                    "text": "(1) Every registered person shall, subject to such conditions and restrictions as may be prescribed and in the manner specified in section 49, be entitled to take credit of input tax charged on any supply of goods or services or both to him which are used or intended to be used in the course or furtherance of his business and the said amount shall be credited to the electronic credit ledger of such person."
                },
                {
                    "number": "17",
                    "subsection": "(5)",
                    "chapter": "Chapter V: Input Tax Credit",
                    "marginal_note": "Apportionment of credit and blocked credits",
                    "text": "Notwithstanding anything contained in sub-section (1) of section 16 and sub-section (1) of section 18, input tax credit shall not be available in respect of the following, namely:—\n(a) motor vehicles and other conveyances, except when they are used—\n(i) for making the following taxable supplies, namely:—\n(A) further supply of such motor vehicles or conveyances; or\n(B) transportation of passengers; or\n(C) imparting training on driving, flying, navigating such motor vehicles or conveyances;\n(ii) for transportation of goods;\n(b) goods lost, stolen, destroyed, written off or disposed of by way of gift or free samples."
                }
            ]
        },
        {
            "act_name": "Income Tax Act, 1961",
            "short_name": "IT Act",
            "year": 1961,
            "sections": [
                {
                    "number": "44AD",
                    "subsection": "",
                    "chapter": "Chapter IV: Computation of Business Income",
                    "marginal_note": "Special provision for computing profits and gains of business on presumptive basis",
                    "text": "(1) Notwithstanding anything to the contrary contained in sections 28 to 43C, in the case of an eligible assessee engaged in an eligible business, a sum equal to eight per cent of the total turnover or gross receipts of the assessee in the previous year on account of such business or, if the assessee so opts, a sum equal to such higher percentage as he may declare in the return of income, shall be deemed to be the profits and gains of such business chargeable to tax under the head \"Profits and gains of business or profession\"."
                },
                {
                    "number": "44AD",
                    "subsection": "(1)",
                    "chapter": "Chapter IV: Computation of Business Income",
                    "marginal_note": "Presumptive taxation for eligible assessees",
                    "text": "Where an eligible assessee engaged in an eligible business declares income at a rate lower than eight per cent of the total turnover or gross receipts, the provisions of section 44AD shall not apply and the assessee shall be required to maintain books of account and get them audited under section 44AB."
                }
            ]
        }
    ]
    
    # Save to file
    os.makedirs("data/sample", exist_ok=True)
    with open("data/sample/acts.json", "w", encoding="utf-8") as f:
        json.dump(acts, f, indent=2, ensure_ascii=False)
    
    print(f"✅ Created sample acts: {len(acts)} acts")
    for act in acts:
        print(f"   - {act['act_name']} ({len(act['sections'])} sections)")
    
    return acts


async def main():
    print("Creating sample legal data...")
    await create_sample_acts()
    
    # Create sample cases
    cases = [
        {
            "citation": "2023 SCC 5 123",
            "title": "ABC Pvt Ltd vs Union of India",
            "court": "Supreme Court of India",
            "year": 2023,
            "act_referenced": "Central Goods and Services Tax Act, 2017",
            "section_referenced": "Section 17(5)",
            "holding": "Input tax credit cannot be claimed on motor vehicles used for personal purposes, even if occasionally used for business.",
            "ratio": "Section 17(5)(a) blocks ITC on motor vehicles for passenger transport unless exclusively used for specified taxable supplies."
        },
        {
            "citation": "2022 SCC 8 456",
            "title": "XYZ Traders vs State of Maharashtra",
            "court": "Bombay High Court",
            "year": 2022,
            "act_referenced": "Income Tax Act, 1961",
            "section_referenced": "Section 44AD",
            "holding": "Presumptive taxation under Section 44AD applies to eligible assessees even if actual profits are higher, provided conditions are met.",
            "ratio": "Section 44AD provides optional presumptive taxation; assessee cannot be compelled to maintain books if opting for presumptive scheme."
        }
    ]
    
    os.makedirs("data/sample", exist_ok=True)
    with open("data/sample/cases.json", "w", encoding="utf-8") as f:
        json.dump(cases, f, indent=2, ensure_ascii=False)
    
    print(f"✅ Created sample cases: {len(cases)} cases")
    
    # Create sample notifications
    notifications = [
        {
            "notification_number": "GST/2023/01",
            "date": "2023-01-15",
            "title": "Extension of due date for GSTR-9",
            "content": "The due date for furnishing annual return in Form GSTR-9 for FY 2021-22 is extended to 31st December 2023."
        },
        {
            "notification_number": "CBDT/2023/05",
            "date": "2023-03-31",
            "title": "New TDS rates for FY 2023-24",
            "content": "Revised TDS rates under various sections effective from 1st April 2023."
        }
    ]
    
    with open("data/sample/notifications.json", "w", encoding="utf-8") as f:
        json.dump(notifications, f, indent=2, ensure_ascii=False)
    
    print(f"✅ Created sample notifications: {len(notifications)}")
    
    print("\n✅ All sample data created in data/sample/")
    return True


if __name__ == "__main__":
    import json
    import os
    import asyncio
    asyncio.run(main())