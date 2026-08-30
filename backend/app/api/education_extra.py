"""
Additional glossary terms and lessons.

Kept in a second file so the original set stays readable and the two can be
reviewed independently. Merged into GLOSSARY and LESSONS by `education.py`.

Two rules for everything here.

Every explanation uses an Egyptian example where an example helps. "A P/E of 30
means the market expects fast growth" is abstract; "Egyptian banks trade near 5
times earnings while Edita has traded above 25" is something a reader can hold
on to and go and check.

Nothing recommends anything. These explain what a measure means and where it
misleads. Where a lesson touches on what people actually do with the idea, it
describes the trade-off and stops.
"""
from __future__ import annotations

EXTRA_GLOSSARY = [
    # ---- Basics -----------------------------------------------------------
    {"term": "Broker", "short": "The licensed firm that places your order on the exchange.",
     "long": "You cannot buy shares directly from the Egyptian Exchange. A "
             "broker holds your account, places the order, and charges a "
             "commission. In Egypt they are licensed by the Financial "
             "Regulatory Authority, and you can check that a firm is licensed "
             "before giving it money.",
     "category": "Basics"},
    {"term": "Order book", "short": "The queue of buy and sell offers waiting to be matched.",
     "long": "At any moment some people are offering to buy at a price and "
             "others to sell. A trade happens when the two meet. In a thinly "
             "traded Egyptian share that queue can be nearly empty, which is "
             "why your order can move the price on its own.",
     "category": "Basics"},
    {"term": "Bid and ask", "short": "The best price someone will buy at, and the best someone will sell at.",
     "long": "The gap between them is the spread, and it is a real cost: you "
             "buy at the ask and sell at the bid. On a heavily traded share the "
             "spread is a fraction of a percent. On a barely traded one it can "
             "be several percent, which you lose the moment you buy.",
     "category": "Basics"},
    {"term": "Free float", "short": "The portion of a company's shares that actually trade.",
     "long": "Many Egyptian companies are majority-owned by a family, a "
             "holding group or the state. Those shares never come to market, "
             "so the real supply is far smaller than the total share count — "
             "which makes the price easier to move in both directions.",
     "category": "Basics"},
    {"term": "Daily price limit", "short": "The most a share is allowed to move in one session.",
     "long": "The Egyptian Exchange caps how far a share can move in a day, "
             "usually 10% and 20% for some. It stops a panic running away in a "
             "single session, but it does not stop the fall — it spreads it "
             "over several days, and you may not be able to sell during them.",
     "category": "Markets"},
    {"term": "Ex-dividend date", "short": "The day a share starts trading without its next dividend.",
     "long": "Buy before it and you receive the dividend; buy on or after it "
             "and you do not. The price normally drops by roughly the dividend "
             "on that morning, which is why a sudden fall on an ex-dividend "
             "date is not a fall at all.",
     "category": "Income"},

    # ---- Valuation --------------------------------------------------------
    {"term": "P/S (price to sales)", "short": "Price compared with revenue rather than profit.",
     "long": "Useful when a company barely makes a profit, or when profit is "
             "distorted by a one-off. It says nothing about whether the sales "
             "are profitable, so a low P/S on a business that never makes money "
             "is not a bargain.",
     "category": "Valuation"},
    {"term": "EV/EBITDA", "short": "The whole business, including its debt, against its operating profit.",
     "long": "Market value plus debt, minus cash, divided by profit before "
             "interest, tax and depreciation. It lets you compare two companies "
             "with very different borrowing. It is meaningless for banks, where "
             "debt is the raw material of the business rather than a way to "
             "finance it.",
     "category": "Valuation"},
    {"term": "Terminal value", "short": "What a valuation model assumes a business is worth at the end of its forecast.",
     "long": "Most of a discounted cash-flow answer usually comes from this "
             "single assumption, which is why such models are so fragile. At "
             "Egyptian interest rates a small change in it moves the answer by "
             "a factor of two, and that is a property of the arithmetic rather "
             "than a fact about the company.",
     "category": "Valuation"},
    {"term": "Discount rate", "short": "The return an investor demands before parting with money.",
     "long": "Future money is worth less than money now, and the discount rate "
             "says by how much. In Egypt it is high because government paper "
             "alone has paid around 20%, so a business has to clear a very tall "
             "bar before it adds anything. Change this one number and every "
             "valuation on any site moves.",
     "category": "Valuation"},
    {"term": "Payout ratio", "short": "The share of profit paid out as dividends.",
     "long": "A company paying out 30% keeps the other 70% to grow. A payout "
             "above 100% means it is paying more than it earns, which it can do "
             "for a while and not forever. It is the first thing to check when a "
             "dividend yield looks unusually generous.",
     "category": "Income"},
    {"term": "Sustainable growth", "short": "How fast a company can grow from its own profits.",
     "long": "Return on equity multiplied by the share of profit it keeps. A "
             "company earning 20% on equity and keeping half of it can fund "
             "about 10% growth a year without borrowing or issuing shares. "
             "Growth promised well above this figure has to be paid for "
             "somehow.",
     "category": "Quality"},

    # ---- Quality ----------------------------------------------------------
    {"term": "ROIC (return on invested capital)", "short": "The return a business earns on all the money in it.",
     "long": "Unlike return on equity it counts borrowed money too, so a "
             "company cannot flatter it simply by taking on debt. A business "
             "earning consistently above its cost of capital is creating value; "
             "one earning below it is destroying value while still reporting a "
             "profit.",
     "category": "Quality"},
    {"term": "Working capital", "short": "The money tied up in running the business day to day.",
     "long": "Stock on the shelves and invoices customers have not yet paid, "
             "less what the company itself owes suppliers. A business whose "
             "working capital grows faster than its sales is consuming cash to "
             "stand still, which a profit figure alone will not show you.",
     "category": "Quality"},
    {"term": "Operating margin", "short": "Profit from the core business, before interest and tax.",
     "long": "It shows whether the actual operation makes money, separately "
             "from how it is financed. Two companies with identical operating "
             "margins can report very different net margins purely because one "
             "borrowed more.",
     "category": "Quality"},
    {"term": "Net debt", "short": "What a company owes, less the cash it holds.",
     "long": "A company with EGP 5bn of loans and EGP 4bn in the bank owes 1bn "
             "on a net basis. It matters because interest has to be paid in "
             "every kind of year, and a heavily indebted company has far less "
             "room when trading turns down.",
     "category": "Quality"},
    {"term": "Earnings quality", "short": "Whether reported profit turns into actual cash.",
     "long": "Profit is an opinion formed under accounting rules; cash is a "
             "fact. A company that reports rising profits while its operating "
             "cash flow stagnates is worth a much closer look — that gap is one "
             "of the most reliable early warnings there is.",
     "category": "Quality"},

    # ---- Risk -------------------------------------------------------------
    {"term": "Correlation", "short": "How much two investments move together.",
     "long": "Five Egyptian banks are not a diversified portfolio: they rise "
             "and fall together, because the same interest rates and the same "
             "economy drive all of them. Correlation also has a habit of rising "
             "in a crash, exactly when you were relying on it being low.",
     "category": "Risk"},
    {"term": "Concentration risk", "short": "Having too much riding on one outcome.",
     "long": "Half your money in one company means one management team, one "
             "industry and one accident decide how you do. It is the most "
             "common way private investors lose a large amount at once, and it "
             "is entirely avoidable.",
     "category": "Risk"},
    {"term": "Currency risk", "short": "The chance that the pound itself loses value.",
     "long": "Egypt has devalued sharply several times in a decade. If you "
             "hold Egyptian shares and think in dollars, a devaluation can wipe "
             "out a good year in the market. Companies that export or earn in "
             "foreign currency behave very differently from purely domestic "
             "ones when it happens.",
     "category": "Risk"},
    {"term": "Real return", "short": "What is left of a return after inflation.",
     "long": "The only number that answers whether you can buy more than you "
             "could before. A 15% return in a year when prices rose 20% is a "
             "loss of about 4% in what your money will actually buy, however "
             "good the percentage looked.",
     "category": "Risk"},
    {"term": "Survivorship bias", "short": "Judging by the ones that are still here.",
     "long": "Look at today's listed companies and you are looking at the "
             "survivors — the failures were delisted and left the list. It "
             "makes almost every long-run market statistic flattering, "
             "including some on this site, which is why we say where it "
             "applies.",
     "category": "Risk"},
    {"term": "Liquidity risk", "short": "The risk of not being able to sell.",
     "long": "A price is only real if someone will trade at it. A share that "
             "turns over EGP 40,000 a day cannot absorb an ordinary order "
             "without moving, and in a falling market may not absorb one at "
             "all. On the EGX this is the risk that catches private investors "
             "most often.",
     "category": "Risk"},

    # ---- Markets ----------------------------------------------------------
    {"term": "Index", "short": "A single number summarising a group of shares.",
     "long": "The EGX30 tracks thirty large Egyptian companies weighted by "
             "size. An index answers 'how did the market do', which is the "
             "question you need before you can ask whether your own choices "
             "did any better.",
     "category": "Markets"},
    {"term": "Benchmark", "short": "The standard you measure your own results against.",
     "long": "Making 20% sounds good until the market made 35%. Without a "
             "benchmark you cannot tell skill from a rising tide, and most "
             "investors who never compare turn out to have been carried by the "
             "market rather than beating it.",
     "category": "Markets"},
    {"term": "Rebalancing", "short": "Returning a portfolio to its intended proportions.",
     "long": "If shares rise sharply they become a larger share of your money "
             "than you chose, and your risk rises with them. Rebalancing sells "
             "some of what has done well and buys what has not — which is "
             "psychologically hard and is the point.",
     "category": "Markets"},
    {"term": "Corporate action", "short": "A company event that changes the shares themselves.",
     "long": "A split turns one share into several, a consolidation does the "
             "reverse, a rights issue offers existing holders new shares. None "
             "of them makes you richer or poorer by itself, but data that fails "
             "to adjust for one produces spectacular fictional returns.",
     "category": "Markets"},
    {"term": "Rights issue", "short": "An offer to existing shareholders to buy new shares.",
     "long": "Usually priced below the market to make it attractive. If you "
             "take it up your stake stays the same size; if you do not, it "
             "shrinks. The right itself trades separately for a short period "
             "and is not the company's shares.",
     "category": "Markets"},

    # ---- Products ---------------------------------------------------------
    {"term": "Money market fund", "short": "A fund holding short-term deposits and government bills.",
     "long": "The lowest-risk fund type available in Egypt and the usual "
             "alternative to leaving money in a current account. It is not "
             "risk-free in the way that matters: if it returns less than "
             "inflation, its holders steadily lose purchasing power.",
     "category": "Products"},
    {"term": "Treasury bill", "short": "Short-term government borrowing.",
     "long": "The government borrows for three months to a year and pays a "
             "fixed return. Egyptian bills have paid around 20% or more in "
             "recent years, which is why shares have to clear such a high bar — "
             "but a fixed 20% in 25% inflation still loses ground.",
     "category": "Products"},
    {"term": "Expense ratio", "short": "The annual cost of holding a fund.",
     "long": "Charged as a percentage of your money every year, whether the "
             "fund gains or loses. It compounds against you in exactly the way "
             "returns compound for you, and over a decade a difference of one "
             "percentage point is a large sum.",
     "category": "Products"},

    # ---- Economy ----------------------------------------------------------
    {"term": "Interest rate", "short": "The price of money, set largely by the central bank.",
     "long": "When the Central Bank of Egypt raises rates, safe deposits pay "
             "more, borrowing costs more, and shares have to compete harder for "
             "money. Rates are the single strongest influence on what any "
             "investment is worth.",
     "category": "Economy"},
    {"term": "Devaluation", "short": "A sharp fall in the value of the currency.",
     "long": "Egypt has been through several. Import costs jump, inflation "
             "follows, and companies that earn in foreign currency suddenly "
             "look very different from those that do not. Any long-run "
             "Egyptian return needs to be read with these dates in mind.",
     "category": "Economy"},
    {"term": "Volume", "short": "How many shares changed hands.",
     "long": "On its own it is hard to compare across companies: a million "
             "shares at EGP 0.40 and a thousand at EGP 400 are the same trade. "
             "Value traded, meaning volume multiplied by price, is the figure "
             "worth looking at, and it is what this site reports.",
     "category": "Markets"},
    {"term": "Book value per share", "short": "The company's own money, divided by the shares.",
     "long": "What would notionally be left for each share if the company sold "
             "everything and paid what it owes. It is an accounting figure, not "
             "a sale price: assets carried at historic cost can be worth far "
             "more or far less today.",
     "category": "Valuation"},
    {"term": "Residual income", "short": "Profit above what shareholders required.",
     "long": "A company earning 10% on shareholders' money, in a country where "
             "government paper pays 20%, is destroying value even while "
             "reporting a profit. Residual income measures the excess over that "
             "hurdle, which is why it suits banks, where book equity is the "
             "working asset.",
     "category": "Valuation"},
    {"term": "Bonus issue", "short": "Free extra shares given to existing holders.",
     "long": "You end up with more shares each worth proportionally less, and "
             "the same stake in the same company. Nothing has been created. It "
             "matters only because price history that fails to adjust for one "
             "shows an enormous fictional fall.",
     "category": "Markets"},
    {"term": "Stop loss", "short": "An instruction to sell if the price falls to a set level.",
     "long": "It caps a loss in an orderly market. In a thinly traded Egyptian "
             "share it can fail in the way that matters most: if there is no "
             "buyer at your level the order does not fill, or fills far below "
             "it. Daily price limits can also leave the share untradeable on "
             "the very day you needed to sell.",
     "category": "Risk"},
    {"term": "Purchasing power", "short": "What your money can actually buy.",
     "long": "The only measure of wealth that means anything over time. "
             "Egyptian prices have roughly two-and-a-half-folded in five years, "
             "so money that merely doubled bought less at the end than at the "
             "start.",
     "category": "Economy"},
]


EXTRA_LESSONS = [
    {"id": "before-you-buy-anything", "title": "Before you buy anything",
     "minutes": 5,
     "body": [
         "Three things are worth settling before you look at a single share, "
         "because none of them is about the market.",
         "First: money you might need soon does not belong in shares. Prices "
         "can fall for years, and being forced to sell during one of those "
         "years is how a temporary fall becomes a permanent loss. Rent, school "
         "fees and emergencies need to sit somewhere boring.",
         "Second: know what you are being charged. A broker takes a commission "
         "on each trade, the exchange takes its fees, and the gap between the "
         "buying and selling price is a cost too. Someone trading frequently "
         "in a thinly traded share can lose several percent a year to costs "
         "alone, before the company has done anything.",
         "Third: decide what would make you sell. Writing it down beforehand is "
         "the only reliable defence against deciding in a panic, and the "
         "moments when it matters are precisely the moments when clear "
         "thinking is hardest.",
         "None of this requires knowing anything about any company. It is the "
         "part most people skip, and the part that decides most outcomes.",
     ]},
    {"id": "liquidity-egypt", "title": "The risk nobody mentions: getting out",
     "minutes": 5,
     "body": [
         "Every ratio on this site tells you something about a business. None "
         "of them tells you whether you could sell it.",
         "A large share of Egyptian listed companies trade a few tens of "
         "thousands of pounds on an average day. At that level an ordinary "
         "private order is a significant part of the day's volume, which means "
         "your own buying pushes the price up as you buy and your own selling "
         "pushes it down as you sell.",
         "The number that matters is the average daily value traded, and this "
         "site shows it on every company page along with how many of the last "
         "ninety sessions the share traded at all. A company that traded on "
         "seven of them is not an investment you can change your mind about.",
         "The trap is that thin companies often look attractive on paper. They "
         "are frequently cheap on earnings, because the people who would bid "
         "the price up cannot buy them in size either. A screen for cheapness "
         "with no liquidity filter is a machine for finding exactly this.",
         "This is not an argument against small companies. It is an argument "
         "for sizing a position so that you could leave without needing anyone "
         "else's permission.",
     ]},
    {"id": "dividends-in-egypt", "title": "What a dividend really tells you",
     "minutes": 5,
     "body": [
         "A dividend is cash the company hands to its owners instead of "
         "keeping it. Nothing about it is free: money paid out is money not "
         "invested in the business.",
         "The yield — the dividend as a percentage of the price — is the number "
         "people look at, and it misleads in a specific way. A yield rises when "
         "the price falls. A company yielding 15% is often not generous but "
         "troubled, with the market pricing in a cut that has not been "
         "announced yet.",
         "The check that matters is the payout ratio: what share of profit the "
         "dividend represents. Below about half is comfortable. Above 100% the "
         "company is paying out more than it earns, which is possible for a "
         "year or two and not indefinitely.",
         "In Egypt there is a further test. A 12% dividend yield in a year when "
         "prices rose 20% is not income at all — it is a slower way of losing "
         "purchasing power. Compare the yield against inflation, not against "
         "zero.",
         "And treat the record as evidence. A company that has paid and raised "
         "its dividend through a devaluation has told you something about its "
         "business that no ratio can.",
     ]},
    {"id": "reading-cash-flow", "title": "Why cash matters more than profit",
     "minutes": 6,
     "body": [
         "Profit is an opinion formed under accounting rules. Cash is a fact. "
         "When the two disagree, the cash is usually telling the truth first.",
         "A company records a sale when it delivers, not when it is paid. So a "
         "business can report a fine profit while its customers owe it more and "
         "more money and nothing actually arrives. The profit line looks "
         "healthy; the bank balance does not.",
         "The comparison to make is simple: is operating cash flow keeping pace "
         "with reported profit, year after year? They will never match exactly, "
         "and they should move together. A widening gap over several years is "
         "one of the most reliable early warnings available to an ordinary "
         "investor, and it needs no special skill to spot.",
         "Free cash flow goes one step further and subtracts what the company "
         "must spend to keep its assets working. That is the money genuinely "
         "available to pay dividends, repay debt or reinvest. A company paying "
         "dividends it is not generating in free cash flow is funding them from "
         "somewhere else — usually borrowing.",
         "On this site, a company's cash flow sits in the statement table on "
         "its own page, next to profit, for exactly this comparison.",
     ]},
    {"id": "banks-are-different", "title": "Why banks break the usual rules",
     "minutes": 5,
     "body": [
         "Egyptian banks are among the largest and most heavily traded "
         "companies on the exchange, and almost every standard measure means "
         "something different for them.",
         "For an ordinary company, debt is how it finances itself. For a bank, "
         "borrowing is the raw material: it takes deposits and lends them out, "
         "and the difference is the business. So a debt-to-equity ratio that "
         "would be alarming anywhere else is simply what a bank looks like.",
         "'Free cash flow' has no comparable meaning either, which is why a "
         "cash-flow valuation model should never be pointed at a bank. This "
         "site uses book value and the returns earned on it instead — and says "
         "so on every bank's page.",
         "The two measures that do work are return on equity, which says how "
         "much profit the bank makes on shareholders' money, and price to book, "
         "which says what you pay for each pound of that money. A bank earning "
         "35% on equity and trading at twice its book value is being priced for "
         "that performance to continue.",
         "The risk that does not show up in either is credit: loans that stop "
         "being repaid. It arrives suddenly and usually when the economy is "
         "already weak.",
     ]},
    {"id": "when-cheap-is-a-trap", "title": "When cheap is a trap",
     "minutes": 5,
     "body": [
         "A low price-to-earnings ratio means the market expects something. "
         "The question is always what.",
         "Sometimes the expectation is wrong and the share is genuinely "
         "underpriced. Far more often the market has noticed something real: "
         "profits that are about to fall, a customer about to leave, a debt "
         "about to be refinanced at a much higher rate, or an owner who treats "
         "minority shareholders as an afterthought.",
         "The specific trap is a cyclical business at the top of its cycle. "
         "Earnings are at a peak, so the ratio looks low, and then earnings "
         "halve and the same share is suddenly expensive at a lower price. "
         "Cement, steel and property all behave this way.",
         "A useful habit: before deciding a company is cheap, write down what "
         "the market must be worrying about. If you cannot name anything, you "
         "probably have not looked hard enough rather than found something "
         "everyone else missed.",
         "And check the company against its own history rather than against "
         "other companies. This site shows what the market has paid for each "
         "company over the years we hold, which is often more informative than "
         "any comparison with its peers.",
     ]},
    {"id": "diversification-really", "title": "What diversification actually requires",
     "minutes": 4,
     "body": [
         "Owning ten shares is not diversification if they are ten Egyptian "
         "banks. They rise and fall together, because the same interest rates, "
         "the same economy and the same currency drive all of them.",
         "What reduces risk is owning things that do not move together. On a "
         "single exchange in a single country that is genuinely hard: almost "
         "everything is affected by the same devaluation and the same rate "
         "decision. This site measures the real correlations between your "
         "holdings and shows how much diversification you are actually "
         "getting, which is often less than the number of names suggests.",
         "There is also a limit. Beyond roughly fifteen genuinely different "
         "companies, adding more does little except make the portfolio harder "
         "to follow. The first few make an enormous difference; the twentieth "
         "makes almost none.",
         "And diversification protects against the risk of being wrong about "
         "one company. It does not protect against the market falling, or the "
         "currency devaluing. Those require a different answer entirely: not "
         "putting in money you will need soon.",
     ]},
    {"id": "what-a-forecast-is", "title": "What a forecast can and cannot tell you",
     "minutes": 5,
     "body": [
         "Every forward-looking number on this site — every projection, every "
         "probability — is arithmetic on stated assumptions. It is a way of "
         "asking 'if these things were true, what would follow?'. It is not a "
         "prediction, and nobody has one.",
         "That does not make it useless. A model is a disciplined way to find "
         "out which assumptions actually matter. Change the expected return by "
         "two percentage points and watch the ten-year figure move by a third: "
         "now you know how much weight that assumption is carrying.",
         "Treat the range as the answer, never the middle. A projection saying "
         "'somewhere between EGP 85,000 and EGP 900,000' is being honest about "
         "genuine uncertainty. The midpoint of that range is the least "
         "informative number in it.",
         "Be especially wary of a low stated chance of loss. Models of this "
         "kind understate extreme events, because the future contains shocks "
         "the past did not. This site resamples real Egyptian market history "
         "rather than drawing from a smooth curve, precisely so that runs of "
         "bad months and currency breaks survive into the simulation — but "
         "even that only contains the shocks that have already happened.",
         "The most useful question a forecast answers is not 'what will I "
         "have?'. It is 'could I live with the bad end of this?'",
     ]},
    {"id": "reading-the-market", "title": "How to tell if you did well",
     "minutes": 4,
     "body": [
         "Making 25% in a year feels good. Whether it was good depends "
         "entirely on two things you have to look up.",
         "The first is inflation. If Egyptian prices rose 20% while your money "
         "grew 25%, you gained about 4% in what you can actually buy. That is "
         "positive and it is not 25%.",
         "The second is the market. If the exchange as a whole rose 40% and you "
         "made 25%, your selection cost you money relative to simply owning the "
         "market. Making less than the market is not a failure in itself, but "
         "not knowing is.",
         "Both comparisons are unflattering more often than not, which is "
         "exactly why they are worth making. An investor who checks them "
         "regularly learns something; one who only notes the raw percentage "
         "learns nothing and usually assumes they are doing better than they "
         "are.",
     ]},
    {"id": "when-data-is-wrong", "title": "Why the numbers here might be wrong",
     "minutes": 4,
     "body": [
         "This site is built from free public data, and free public data "
         "contains errors. Being specific about them is more useful than "
         "promising accuracy.",
         "Some are mechanical. When a company splits its shares, every earlier "
         "price should be restated to match; our source sometimes does not, "
         "which once produced a company that appeared to have returned 805% in "
         "a year. We detect those breaks and withhold the affected returns "
         "rather than publish fiction.",
         "Some are stranger. A source occasionally prints a price that leaps "
         "and returns within days — a company sitting near 31 printing 18.89 "
         "for a single day. That is not a day's trading, and those bars are "
         "excluded from every calculation.",
         "Some are structural. Financial statements exist for only about a "
         "third of the companies listed here, prices reach back about ten "
         "years, and no free source publishes a history of Egyptian fund "
         "values at all.",
         "All of it is listed, with counts, on the data-quality page. If a "
         "figure here disagrees with your broker, check the dates first — ours "
         "is the previous close, not a live price.",
     ]},
    {"id": "how-a-share-price-moves", "title": "Why the price moves at all",
     "minutes": 4,
     "body": [
         "A share price is not a measurement of a company. It is whatever the "
         "last buyer and the last seller agreed on, which is a different thing.",
         "Over a day it moves on almost nothing: someone needed cash, someone "
         "read a headline, a large order arrived in a thin market. Over years "
         "it tracks what the business actually earns, because eventually "
         "nothing else can sustain it.",
         "This is why a falling price is not information on its own. It might "
         "mean the business has deteriorated, or that a large holder needed to "
         "sell, or that interest rates rose and every share became worth less "
         "at once. Those call for completely different responses.",
         "The practical habit is to separate two questions. Has anything "
         "changed about what this business earns? And separately, has the price "
         "changed? Most poor decisions come from assuming the second answers "
         "the first.",
     ]},
    {"id": "reading-a-balance-sheet", "title": "A balance sheet in five minutes",
     "minutes": 5,
     "body": [
         "A balance sheet is a photograph taken on one day: what the company "
         "owns, what it owes, and what is left over for shareholders.",
         "Start at the bottom. Total equity is that leftover, the company's own "
         "money. Compare it with the market value of the shares and you have "
         "price to book, which says what you are paying for each pound of it.",
         "Then look at debt against equity. A company owing far more than it "
         "owns has less room when trading turns down, because interest falls "
         "due in every kind of year. What counts as too much varies by "
         "industry: a property developer and a software company are not "
         "comparable, and a bank is a different case again.",
         "Then look at cash. A company holding substantial cash has options: it "
         "can survive a bad year, buy something, or keep paying a dividend. Net "
         "debt, which is borrowing less cash, is usually the more honest "
         "figure.",
         "That is most of the value in five minutes. The detail matters, but "
         "these three comparisons catch the problems that actually sink "
         "companies.",
     ]},
    {"id": "costs-and-taxes-egypt", "title": "What investing in Egypt actually costs",
     "minutes": 4,
     "body": [
         "Every cost is certain. Every return is not. That asymmetry makes "
         "costs worth more attention than they usually get.",
         "Buying and selling shares in Egypt carries a broker commission on "
         "each side, plus exchange and regulatory fees. Each is small on its "
         "own and each applies to every trade, so someone trading monthly pays "
         "them twelve times a year.",
         "Then there is the spread, the gap between the price you can buy at "
         "and the price you can sell at. It is invisible because it never "
         "appears on a statement, and on a thinly traded share it can exceed "
         "every explicit fee combined.",
         "Taxes change, so check the current position rather than trusting a "
         "figure written down here or anywhere else. Egypt has treated capital "
         "gains and dividends differently at different times, and the rules "
         "have moved more than once.",
         "The general shape holds regardless: costs scale with how often you "
         "trade, and they compound against you exactly as returns compound for "
         "you.",
     ]},
    {"id": "funds-or-shares", "title": "Funds or individual shares?",
     "minutes": 5,
     "body": [
         "A fund pools many investors' money across many holdings, run by "
         "someone paid to do it. Buying shares directly means choosing "
         "yourself.",
         "The honest case for a fund is that diversification is difficult with "
         "a small amount of money and limited time. Twenty companies bought "
         "individually means twenty sets of dealing costs and twenty companies "
         "to follow. A fund gives the spread in one transaction.",
         "The honest case against is cost and opacity. A fund charges every "
         "year whether it does well or badly, and you do not choose what it "
         "holds. In Egypt there is a further problem this site cannot solve: no "
         "free source publishes a history of daily fund values, so a fund "
         "cannot be examined the way a share can. We show what is published and "
         "say plainly what is missing.",
         "The money-market question is separate and simpler. Those funds are "
         "the usual alternative to a bank deposit, and the only test that "
         "matters is whether the return beats inflation. Often it has not.",
         "There is no general answer here, and anyone offering one is not "
         "answering it for you.",
     ]},
]
