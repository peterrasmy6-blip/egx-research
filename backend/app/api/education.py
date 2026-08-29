"""
Educational content: glossary, lessons, and a risk-awareness questionnaire.

The questionnaire is deliberately NOT a robo-adviser. It describes how someone
tends to react to risk and explains what that tends to mean, then stops. It
does not output an allocation, name securities, or tell anyone what to do with
their money -- that would be personalised advice, which this platform does not
give and is not licensed to give.
"""
from __future__ import annotations

GLOSSARY = [
    {"term": "Share (stock)", "short": "A small piece of ownership in a company.",
     "long": "If a company has issued a million shares and you own one, you own "
             "one millionth of it. You share in its profits, and in its losses.",
     "category": "Basics"},
    {"term": "EGX", "short": "The Egyptian Exchange, where Egyptian shares are traded.",
     "long": "The Egyptian Exchange is Egypt's stock market. Companies list "
             "there to raise money, and investors buy and sell shares through "
             "licensed brokers. Prices move throughout the trading day.",
     "category": "Basics"},
    {"term": "Market capitalisation", "short": "What the whole company is worth at today's price.",
     "long": "Share price multiplied by the number of shares. A company at "
             "EGP 100 a share with 3 billion shares has a market value of "
             "EGP 300 billion. It tells you the company's size, not whether it "
             "is cheap or expensive.",
     "category": "Basics"},
    {"term": "P/E (price to earnings)", "short": "How many years of current profit you are paying for.",
     "long": "Price divided by profit per share. A P/E of 8 means you pay EGP 8 "
             "for every EGP 1 of annual profit. Lower can mean cheaper - or it "
             "can mean investors expect profits to fall. It is a question, not "
             "an answer.",
     "category": "Valuation"},
    {"term": "P/B (price to book)", "short": "Price compared with the company's accounting value.",
     "long": "Book value is roughly what would be left for shareholders if the "
             "company sold its assets and paid its debts. P/B below 1 means the "
             "market values the company at less than that figure. This measure "
             "matters most for banks, where the balance sheet is the business.",
     "category": "Valuation"},
    {"term": "EPS (earnings per share)", "short": "Profit divided by the number of shares.",
     "long": "If a company earns EGP 3 billion and has 1 billion shares, EPS is "
             "EGP 3. It is the slice of profit attached to each share.",
     "category": "Valuation"},
    {"term": "ROE (return on equity)", "short": "How much profit the company makes on shareholders' money.",
     "long": "Profit divided by shareholders' equity. An ROE of 25% means the "
             "company earns 25 piastres a year for every pound shareholders "
             "have in it. Consistently high ROE usually signals a strong "
             "business - but check how much debt is behind it.",
     "category": "Quality"},
    {"term": "EBITDA", "short": "Profit before interest, tax, and accounting write-downs.",
     "long": "A rough measure of what the core operations earn, before "
             "financing and accounting choices. Useful for comparing companies "
             "with different debt levels. It is not cash, and it is not profit.",
     "category": "Quality"},
    {"term": "Free cash flow", "short": "Cash left over after running and maintaining the business.",
     "long": "Cash from operations minus what is spent on equipment and "
             "property. This is the money that can genuinely pay dividends, "
             "repay debt, or fund growth. Profit is an opinion; cash is a fact.",
     "category": "Quality"},
    {"term": "Dividend", "short": "Cash the company pays out to shareholders.",
     "long": "Some companies distribute part of their profit as cash. Dividend "
             "yield is that cash divided by the share price. A very high yield "
             "sometimes means the share price has fallen because trouble is "
             "expected.",
     "category": "Income"},
    {"term": "Intrinsic value", "short": "What a business is worth based on what it earns.",
     "long": "An estimate of value built from the company's own cash flows and "
             "assets, rather than from what the share price happens to be. Every "
             "estimate depends on assumptions, so it is a range, never a "
             "precise figure.",
     "category": "Valuation"},
    {"term": "DCF (discounted cash flow)", "short": "Valuing a company by the future cash it will produce.",
     "long": "Project the cash a business will generate, then reduce those "
             "future amounts to today's terms - because money later is worth "
             "less than money now. Small changes in the assumptions produce "
             "large changes in the answer.",
     "category": "Valuation"},
    {"term": "Volatility", "short": "How much the price swings around.",
     "long": "A measure of how far prices move up and down. Higher volatility "
             "means a bumpier ride. It is not the same as risk of permanent "
             "loss - a stable company can still be a bad investment at a high "
             "enough price.",
     "category": "Risk"},
    {"term": "Drawdown", "short": "The biggest fall from a peak.",
     "long": "If an investment went from EGP 100 to EGP 60 before recovering, "
             "the drawdown was 40%. It answers a practical question: how much "
             "would you have watched disappear along the way?",
     "category": "Risk"},
    {"term": "Diversification", "short": "Not putting everything in one place.",
     "long": "Spreading money across different companies and industries so that "
             "one bad outcome does not sink everything. It reduces the damage "
             "from being wrong about any single company.",
     "category": "Risk"},
    {"term": "Inflation", "short": "Prices rising, so money buys less over time.",
     "long": "This matters enormously in Egypt. If your investment grows 20% in "
             "a year but prices rise 25%, you have more pounds but can buy less "
             "than before. Growing your money is not the same as growing your "
             "purchasing power.",
     "category": "Economy"},
    {"term": "Compounding", "short": "Growth earning its own growth.",
     "long": "Returns earned on returns already earned. EGP 100,000 growing 15% "
             "a year becomes about EGP 405,000 after ten years, not EGP 250,000 "
             "- because each year's gain joins the base for the next.",
     "category": "Basics"},
    {"term": "Mutual fund", "short": "A pool of money invested on behalf of many people.",
     "long": "Many investors put money into one pot, which a manager invests "
             "across many securities. It gives instant diversification, in "
             "exchange for a management fee.",
     "category": "Products"},
    {"term": "ETF", "short": "A fund that trades on the exchange like a share.",
     "long": "An exchange-traded fund holds a basket of securities, often "
             "tracking an index, and is bought and sold like an ordinary share. "
             "Fees are usually lower than actively managed funds.",
     "category": "Products"},
    {"term": "Fixed income", "short": "Lending money in return for interest.",
     "long": "Bonds, treasury bills and deposits pay a stated rate of interest. "
             "Less dramatic than shares, and in Egypt often paying high nominal "
             "rates - but still exposed to inflation eroding the real value.",
     "category": "Products"},
    {"term": "Bear market", "short": "A prolonged fall in prices.",
     "long": "Commonly defined as a fall of 20% or more from the peak. Bear "
             "markets are a normal part of investing, not an aberration.",
     "category": "Markets"},
    {"term": "Bull market", "short": "A prolonged rise in prices.",
     "long": "A sustained period of rising prices and general optimism. Rising "
             "markets can make risky decisions look clever for a while.",
     "category": "Markets"},
    {"term": "Margin of safety", "short": "Buying well below your estimate of value.",
     "long": "The gap between what you think something is worth and what you "
             "pay. Because every valuation can be wrong, the gap is what "
             "protects you when it is.",
     "category": "Valuation"},
    {"term": "Liquidity", "short": "How easily you can sell without moving the price.",
     "long": "A heavily traded share can be sold quickly near the quoted price. "
             "A thinly traded one may take time, or force you to accept less. "
             "Many smaller EGX companies trade very thinly.",
     "category": "Risk"},
]

LESSONS = [
    {
        "id": "what-you-are-buying",
        "title": "What are you actually buying?",
        "minutes": 4,
        "body": [
            "A share is not a lottery ticket with a company logo on it. It is a "
            "claim on a real business - its factories, its customers, its "
            "profits and its debts.",
            "That is why the price alone tells you almost nothing. A share at "
            "EGP 5 is not 'cheaper' than one at EGP 500. What matters is what "
            "you get for your money: how much profit, how much equity, how much "
            "cash, per pound invested.",
            "Before buying anything, you should be able to answer three "
            "questions in plain language: What does this company do? How does it "
            "make money? What would have to go wrong for me to lose?",
            "If you cannot answer those, no chart or ratio will save you.",
        ],
    },
    {
        "id": "inflation-in-egypt",
        "title": "Why inflation changes everything in Egypt",
        "minutes": 5,
        "body": [
            "In a country with low inflation, a 10% return is a good year. In "
            "Egypt, where inflation has often run far higher, a 10% return can "
            "leave you poorer than when you started.",
            "Here is a real example from this platform's own data. EGP 100,000 "
            "invested in CIB five years ago grew to roughly EGP 437,000 - a gain "
            "of about 337%. That sounds spectacular.",
            "But prices rose too. Measured in what that money can actually buy, "
            "the same investment was worth around EGP 147,000 in original terms "
            "- a real gain closer to 47%.",
            "Both numbers are true. The first tells you how many pounds you "
            "have. The second tells you whether you got richer. Whenever this "
            "site shows a return, it shows both.",
            "The practical lesson: when comparing an investment against a bank "
            "deposit paying 20%, the question is not 'did it go up?' but 'did it "
            "beat inflation, after the risk I took?'",
        ],
    },
    {
        "id": "risk-is-not-volatility",
        "title": "Risk is not the same as a bumpy chart",
        "minutes": 4,
        "body": [
            "Volatility measures how much a price jumps around. Risk is the "
            "chance of permanently losing money. They are related, but they are "
            "not the same thing.",
            "A solid company whose share price swings 30% a year may be far "
            "safer than a struggling one whose price barely moves because almost "
            "nobody trades it.",
            "Three risks matter more than volatility for most people: paying too "
            "much for a good business, owning a business that is quietly "
            "deteriorating, and needing your money at the exact moment the "
            "market is down.",
            "The third is the one that ruins people. Money you might need within "
            "two or three years does not belong in shares, however good the "
            "company.",
        ],
    },
    {
        "id": "reading-a-company",
        "title": "How to read a company in ten minutes",
        "minutes": 6,
        "body": [
            "Start with revenue over five years. Is it growing, flat, or "
            "shrinking? Growth that has stalled is the single most common early "
            "warning sign.",
            "Next look at net margin - profit as a percentage of revenue. Is it "
            "steady, improving, or slipping? A falling margin on rising revenue "
            "means the company is buying growth rather than earning it.",
            "Then return on equity. This tells you how hard shareholders' money "
            "is working. Consistently above 15-20% suggests a genuinely good "
            "business; but check debt, because borrowing can inflate ROE while "
            "adding fragility.",
            "Then debt against equity. High debt is not automatically bad, but "
            "it removes the company's margin for error.",
            "Finally free cash flow. Profit is an accounting figure and can be "
            "shaped by choices. Cash is harder to argue with. A company that "
            "reports profits but never generates cash deserves questions.",
            "Every company page on this site shows these five things side by "
            "side, with the years across the top.",
        ],
    },
    {
        "id": "valuation-is-a-range",
        "title": "Why fair value is a range, not a number",
        "minutes": 5,
        "body": [
            "Any valuation model is a machine for turning assumptions into a "
            "number. Change the assumptions slightly and the number moves a lot.",
            "A discounted cash flow model, for example, needs a growth rate and "
            "a discount rate. In Egypt the discount rate is heavily influenced "
            "by government bond yields, which have been above 20%. Using a "
            "European discount rate of 8% would roughly double every valuation "
            "on this site - and every one of them would be wrong.",
            "That is why this platform never shows a single fair value. It shows "
            "a bear, base and bull case, tells you which methods were used, and "
            "shows the assumptions behind them.",
            "It also reports how much the different methods disagree with each "
            "other. Wide disagreement is not a flaw to be hidden - it is the "
            "honest signal that the answer is genuinely uncertain.",
            "Treat a fair-value estimate as one input into your thinking, never "
            "as a verdict.",
        ],
    },
    {
        "id": "how-people-lose-money",
        "title": "The common ways people lose money",
        "minutes": 5,
        "body": [
            "Buying because the price has been rising. A rising price is "
            "evidence about the past, not the future. Most people who buy after "
            "a large run-up are buying from someone who understood the business "
            "earlier.",
            "Concentrating everything in one company or one sector. If most of "
            "your money is in banks, you do not own a portfolio - you own a bet "
            "on Egyptian banking.",
            "Selling in a panic. Falls of 20-40% are normal and recur. The "
            "investor who sells at the bottom converts a temporary decline into "
            "a permanent loss.",
            "Investing money that is already committed. School fees, rent and "
            "emergencies do not wait for the market to recover.",
            "Confusing a story with an analysis. 'This sector is the future' is "
            "not a reason to pay any price.",
            "None of these are avoided by finding a better tip. They are avoided "
            "by understanding what you own and why.",
        ],
    },
]

# --------------------------------------------------------------------------
# Risk-awareness questionnaire (educational)
# --------------------------------------------------------------------------
QUESTIONNAIRE = [
    {"id": "q1", "dimension": "tolerance",
     "question": "You invest EGP 500,000. Six months later the market has "
                 "fallen and it is worth EGP 375,000. What would you most "
                 "likely do?",
     "options": [
         {"value": 1, "text": "Sell everything to stop further losses"},
         {"value": 2, "text": "Sell some of it and wait"},
         {"value": 3, "text": "Do nothing and wait for recovery"},
         {"value": 4, "text": "Invest more while prices are lower"}]},
    {"id": "q2", "dimension": "tolerance",
     "question": "Which of these outcomes over one year would you rather have?",
     "options": [
         {"value": 1, "text": "A certain 18%, no ups or downs"},
         {"value": 2, "text": "Likely 20%, possibly as low as 10%"},
         {"value": 3, "text": "Likely 28%, possibly a small loss"},
         {"value": 4, "text": "Possibly 45%, possibly a 25% loss"}]},
    {"id": "q3", "dimension": "tolerance",
     "question": "A company you own falls 30% after a disappointing quarter, "
                 "but the business itself has not changed. How do you feel?",
     "options": [
         {"value": 1, "text": "Very anxious - I would struggle to sleep"},
         {"value": 2, "text": "Uncomfortable, and tempted to sell"},
         {"value": 3, "text": "Concerned, but I would re-check the facts first"},
         {"value": 4, "text": "Calm - falls like this are normal"}]},
    {"id": "q4", "dimension": "capacity",
     "question": "If your investments lost 30% and stayed down for two years, "
                 "how would that affect your day-to-day life?",
     "options": [
         {"value": 1, "text": "Severely - I would need that money"},
         {"value": 2, "text": "Noticeably - some plans would change"},
         {"value": 3, "text": "Slightly - it would be uncomfortable but manageable"},
         {"value": 4, "text": "Not at all - it is money I do not need soon"}]},
    {"id": "q5", "dimension": "capacity",
     "question": "How many months of expenses could you cover from savings "
                 "without touching investments?",
     "options": [
         {"value": 1, "text": "Less than one month"},
         {"value": 2, "text": "One to three months"},
         {"value": 3, "text": "Three to six months"},
         {"value": 4, "text": "More than six months"}]},
    {"id": "q6", "dimension": "capacity",
     "question": "How stable is your income?",
     "options": [
         {"value": 1, "text": "Unpredictable or currently no income"},
         {"value": 2, "text": "It varies a lot month to month"},
         {"value": 3, "text": "Mostly steady with some variation"},
         {"value": 4, "text": "Very steady and secure"}]},
    {"id": "q7", "dimension": "horizon",
     "question": "When do you expect to need most of this money?",
     "options": [
         {"value": 1, "text": "Within 2 years"},
         {"value": 2, "text": "In 2 to 5 years"},
         {"value": 3, "text": "In 5 to 10 years"},
         {"value": 4, "text": "In more than 10 years"}]},
    {"id": "q8", "dimension": "horizon",
     "question": "Do you expect any large expense in the next three years "
                 "(property, education, wedding, medical)?",
     "options": [
         {"value": 1, "text": "Yes, and I would need this money for it"},
         {"value": 2, "text": "Possibly, and I might need part of it"},
         {"value": 3, "text": "Possibly, but I could cover it elsewhere"},
         {"value": 4, "text": "No large expense expected"}]},
    {"id": "q9", "dimension": "knowledge",
     "question": "How would you describe your investing experience?",
     "options": [
         {"value": 1, "text": "None - I have never invested"},
         {"value": 2, "text": "A little - deposits, or a small amount in shares"},
         {"value": 3, "text": "Moderate - I have invested through a market fall"},
         {"value": 4, "text": "Extensive - I read financial statements regularly"}]},
    {"id": "q10", "dimension": "knowledge",
     "question": "A share trades at a P/E of 6 while similar companies trade at "
                 "12. What is your first thought?",
     "options": [
         {"value": 1, "text": "I am not sure what that means"},
         {"value": 2, "text": "It is cheap, so it is probably a good buy"},
         {"value": 3, "text": "It might be cheap - I would check why"},
         {"value": 4, "text": "The market may expect profits to fall; I would "
                              "examine the accounts and the sector"}]},
]

PROFILES = {
    "Conservative": {
        "range": "You lean strongly towards protecting what you have.",
        "means": [
            "Sharp falls are likely to trouble you more than missed gains.",
            "Historically, portfolios weighted towards deposits and fixed "
            "income have shown smaller swings than share-heavy ones - though in "
            "Egypt they carry real exposure to inflation eating purchasing power.",
            "The main risk for a conservative investor is not a market crash. It "
            "is holding money in something that grows slower than prices rise.",
        ],
    },
    "Moderate": {
        "range": "You are willing to accept some ups and downs for better long-run growth.",
        "means": [
            "You are likely to tolerate ordinary market falls without acting, "
            "but a very sharp decline could still be uncomfortable.",
            "Mixed portfolios have historically sat between deposits and pure "
            "equity in both return and volatility.",
            "The practical question for you is how much of a fall you could "
            "watch without selling - because selling during a fall is what turns "
            "it into a permanent loss.",
        ],
    },
    "Growth-oriented": {
        "range": "You accept meaningful volatility in exchange for long-term growth.",
        "means": [
            "Falls of 20-30% are a realistic feature of share investing, and "
            "your answers suggest you could sit through one.",
            "Long horizons have historically been the main thing that made "
            "equity volatility survivable - time allows recovery.",
            "The risk to watch is overconfidence: a tolerance for volatility is "
            "not the same as an ability to pick companies well.",
        ],
    },
    "Aggressive": {
        "range": "You are comfortable with large swings and focused on maximum growth.",
        "means": [
            "Your answers suggest large falls would not push you into selling.",
            "Concentrated, high-volatility positions can produce both the best "
            "and the worst outcomes; the range of results widens in both "
            "directions.",
            "The most common mistake at this end is confusing a high risk "
            "tolerance with a high risk capacity - being willing to lose money "
            "is not the same as being able to afford to.",
        ],
    },
}


def score_questionnaire(answers: dict) -> dict:
    """
    Turn answers into a descriptive risk profile.

    Deliberately returns education, not an allocation. Where the two dimensions
    conflict - a high appetite for risk alongside a low ability to absorb loss -
    that tension is surfaced explicitly, because it is the single most useful
    thing the exercise can reveal.
    """
    dims = {"tolerance": [], "capacity": [], "horizon": [], "knowledge": []}
    answered = 0
    for q in QUESTIONNAIRE:
        v = answers.get(q["id"])
        if v is None:
            continue
        try:
            v = int(v)
        except (TypeError, ValueError):
            continue
        if 1 <= v <= 4:
            dims[q["dimension"]].append(v)
            answered += 1

    if answered < len(QUESTIONNAIRE) * 0.6:
        return {"complete": False,
                "reason": "Please answer more of the questions - at least %d of "
                          "%d - before we describe a profile."
                          % (int(len(QUESTIONNAIRE) * 0.6), len(QUESTIONNAIRE))}

    def pct(vals):
        if not vals:
            return None
        return round((sum(vals) / len(vals) - 1) / 3 * 100)

    tolerance = pct(dims["tolerance"])
    capacity = pct(dims["capacity"])
    horizon = pct(dims["horizon"])
    knowledge = pct(dims["knowledge"])

    # Capacity and horizon constrain what tolerance can safely mean.
    parts = [x for x in (tolerance, capacity, horizon) if x is not None]
    overall = round(sum(parts) / len(parts)) if parts else 0
    if capacity is not None and horizon is not None:
        ceiling = min(capacity, horizon) + 20
        overall = min(overall, ceiling)

    if overall < 30:
        name = "Conservative"
    elif overall < 55:
        name = "Moderate"
    elif overall < 78:
        name = "Growth-oriented"
    else:
        name = "Aggressive"

    tensions = []
    if tolerance is not None and capacity is not None and tolerance - capacity >= 30:
        tensions.append(
            "Your appetite for risk is considerably higher than your current "
            "ability to absorb a loss. Being willing to take a risk and being "
            "able to afford it are different things, and the second is the one "
            "that determines what a bad year does to your life.")
    if horizon is not None and horizon < 35 and tolerance is not None and tolerance > 60:
        tensions.append(
            "You are comfortable with volatility, but you may need this money "
            "within a few years. Time is what allows a market fall to recover; "
            "without it, a fall and a loss become the same thing.")
    if capacity is not None and capacity < 30:
        tensions.append(
            "Your answers suggest limited savings to fall back on. Historically, "
            "an emergency reserve is what stops people from having to sell "
            "investments at the worst possible moment.")
    if knowledge is not None and knowledge < 35:
        tensions.append(
            "You described limited investing experience. That is not a problem "
            "in itself - but it is a strong argument for understanding what you "
            "own before committing money to it.")

    return {
        "complete": True,
        "profile": name,
        "summary": PROFILES[name]["range"],
        "what_this_means": PROFILES[name]["means"],
        "scores": {
            "risk_tolerance": tolerance,
            "risk_capacity": capacity,
            "time_horizon": horizon,
            "knowledge": knowledge,
            "overall": overall,
        },
        "score_meaning": {
            "risk_tolerance": "How comfortable you feel about losses and swings.",
            "risk_capacity": "How much loss your finances could actually absorb.",
            "time_horizon": "How long before you are likely to need the money.",
            "knowledge": "How familiar you are with investing concepts.",
        },
        "tensions": tensions,
        "next_steps": [
            "Read the education section to understand the measures used on this site.",
            "Use the historical scenario tool to see how real EGX investments "
            "behaved, including their worst falls.",
            "Use the Monte Carlo tool to see a range of possible outcomes rather "
            "than a single expected number.",
        ],
        "disclaimer": (
            "This is an educational exercise, not advice. It does not know your "
            "full circumstances, and it deliberately does not suggest what to "
            "buy, sell, or how to split your money. Those decisions are yours, "
            "and a licensed adviser can help with them."),
    }
