/* EGX Research — Arabic interface.

   Why company names stay in English
   ---------------------------------
   No free source publishes Arabic names for the 269 companies here. Writing
   them from memory would mean inventing the identity of real companies, which
   is the one thing this platform never does — a wrong Arabic name is worse
   than an English one, because a reader cannot tell it is wrong. Tickers are
   Latin on the exchange itself, so they need no translation.

   So: the interface, the labels and the explanations are Arabic. Company
   names, and the ticker beside them, stay as the exchange publishes them. The
   language switch says so rather than leaving the reader to wonder.

   Why Western digits
   ------------------
   Egypt uses both ٠١٢٣ and 0123, but the exchange, the brokers and every
   Egyptian financial app use Western digits. A price is something people
   compare against their broker screen, so it is formatted the same way there.

   Coverage
   --------
   The chrome, navigation, headings, table columns and the explanatory notes a
   reader meets first are translated. Some of the longer analytical prose is
   still English, and is marked in the interface rather than silently mixed.
*/

const I18N = {
  ar: {
    // ---- chrome ----
    "site.name": "‏EGX‏ للأبحاث",
    "site.tagline": "ابحث. افهم. قرّر.",
    "search.placeholder": "ابحث عن أي شركة مصرية — جرّب CIB أو فوري",
    "nav.home": "الرئيسية",
    "nav.today": "اليوم",
    "nav.markets": "الشركات",
    "nav.funds": "الصناديق",
    "nav.screener": "الفلترة",
    "nav.compare": "مقارنة",
    "nav.scenario": "ماذا لو استثمرت؟",
    "nav.backtest": "اختبار تاريخي",
    "nav.forecast": "سيناريوهات مستقبلية",
    "nav.plan": "توقّع محفظة",
    "nav.portfolio": "تحليل محفظة",
    "nav.weekly": "هذا الأسبوع",
    "nav.contact": "اتصل بنا وتصحيح الأخطاء",
    "contact.title": "اتصل بنا وتصحيح الأخطاء",
    "contact.lede": "يقوم شخص واحد ببناء هذا الموقع وتشغيله. لا توجد شركة خلفه ولا فريق دعم — أي أن كل رسالة تُقرأ، وأن الرد قد يستغرق بضعة أيام.",
    "contact.found.title": "وجدت رقماً يبدو خاطئاً؟",
    "contact.how": "كيف تتواصل معي",
    "contact.cannot": "ما لا أستطيع تقديمه",
    "nav.paper": "محفظة تجريبية",
    "weekly.title": "هذا الأسبوع في البورصة المصرية",
    "weekly.rose": "ارتفعت",
    "weekly.fell": "انخفضت",
    "weekly.median": "متوسط الحركة",
    "weekly.gainers": "أكبر الارتفاعات",
    "weekly.losers": "أكبر الانخفاضات",
    "weekly.sectors": "القطاعات",
    "weekly.dividends": "توزيعات قادمة",
    "nav.learn": "تعلّم الاستثمار",
    "paper.title": "محافظ تجريبية",
    "paper.lede": "سجّل ما كنت ستشتريه، ودع السوق يحكم عليه. لا أموال حقيقية ولا توصيات — إنه دفتر يقوم بالحساب، وسيخبرك بصراحة إن كنت قد تفوّقت على البورصة أم أن ارتفاع السوق هو الذي حملك.",
    "paper.storage.title": "محفوظة في متصفحك فقط.",
    "paper.storage.body": "لا يوجد حساب ولا خادم هنا، فلا شيء يُرفع ولا يُشارك. مسح بيانات المتصفح يحذفها، ولن تنتقل معك إلى جهاز آخر.",
    "paper.new": "سجّل محفظة",
    "paper.name": "سمّها",
    "paper.date": "تاريخ الشراء",
    "paper.shares": "عدد الأسهم",
    "paper.buyprice": "سعر الشراء",
    "paper.save": "احفظ المحفظة",
    "paper.holding": "سهم واحد",
    "paper.holdings": "أسهم",
    "paper.bench.note": "«السوق» هنا هو مؤشرنا المركّب متساوي الأوزان، وليس مؤشر EGX30 — إذ لا يتيح أي مصدر مجاني تاريخ المؤشر الرسمي. وهو يضم الشركات المقيدة اليوم فقط، لذا فهو متحيّز إيجابياً لغياب الشركات التي أخفقت وخرجت، مما يجعله معياراً أصعب في التفوّق عليه مما كان عليه السوق فعلياً.",
    "paper.bench.link": "كيف بُني",
    "paper.market": "السوق حقق",
    "paper.real": "بعد التضخم",

    "level.beginner": "مبتدئ",
    "level.normal": "عادي",
    "level.advanced": "تفصيلي",
    "lang.switch": "العربية",
    "lang.english": "English",

    // ---- the honest note about names ----
    "lang.names_note":
      "الواجهة بالعربية، أما أسماء الشركات فتظهر بالإنجليزية كما تنشرها البورصة. " +
      "لا يوجد مصدر مجاني ينشر الأسماء العربية لكل الشركات، وكتابتها من الذاكرة " +
      "قد يعطي اسمًا خاطئًا لشركة حقيقية — وهو أسوأ من تركه بالإنجليزية.",

    // ---- home ----
    "home.hero": "افهم البورصة المصرية قبل أن تستثمر فيها",
    "home.lede":
      "أبحاث وتقييم وتحليل تاريخي مجاني يغطي البورصة المصرية بالكامل. كل رقم " +
      "محسوب من أسعار السوق الحقيقية ومن القوائم المالية للشركات — لا تقديرات " +
      "ولا أرقام مُختلقة.",
    "home.philosophy.title": "ابحث. افهم. قرّر.",
    "home.philosophy.body":
      "هذا الموقع يعطيك المعلومات والأدوات. وهو لا يخبرك عمدًا بما تشتري أو " +
      "تبيع أو كيف تقسّم أموالك — تلك قرارات تعتمد على ظروفك أنت، وهي ملكك وحدك.",
    "home.glance": "البورصة في لمحة",

    "tile.research": "ابحث عن شركة",
    "tile.research.d": "الأسعار والأرباح والنسب والقوائم المالية لكل شركة مصرية مقيدة.",
    "tile.whatif": "ماذا لو استثمرت؟",
    "tile.whatif.d": "شاهد ما كان سيحدث فعلًا لاستثمار حقيقي — بالتوزيعات وبعد التضخم.",
    "tile.value": "القيمة العادلة",
    "tile.value.d": "تقديرات نموذجية لما قد تساويه الشركة، مع عرض كل الافتراضات.",
    "tile.screener": "الفلترة",
    "tile.screener.d": "افلتر البورصة كلها حسب القيمة والجودة والنمو والمخاطر.",
    "tile.compare": "قارن الشركات",
    "tile.compare.d": "ضع عدة شركات جنبًا إلى جنب على نفس المقاييس.",
    "tile.backtest": "اختبر محفظة",
    "tile.backtest.d": "اختبر أداء مزيج من الأسهم تاريخيًا، بإعادة التوازن والتكاليف.",
    "tile.forecast": "سيناريوهات مستقبلية",
    "tile.forecast.d": "توقعات ومحاكاة مونت كارلو — نطاقات، لا تنبؤات.",
    "tile.plan": "توقّع محفظة",
    "tile.plan.d": "كوّن محفظة اليوم واعرف كيف قد تتصرف في السنوات القادمة.",
    "tile.learn": "تعلّم الاستثمار",
    "tile.learn.d": "شرح بلغة بسيطة لكل مصطلح مستخدم في هذا الموقع.",

    // ---- shared labels ----
    "label.price": "السعر",
    "label.company": "الشركة",
    "label.ticker": "الرمز",
    "label.sector": "القطاع",
    "label.day": "اليوم",
    "label.year1": "سنة",
    "label.marketvalue": "القيمة السوقية",
    "label.data": "البيانات",
    "label.real": "حقيقي",
    "label.loading": "جارٍ التحميل…",
    "label.nodata": "لا توجد بيانات",
    "label.notavailable": "غير متاح",
    "label.source": "المصدر",
    "label.download": "تحميل CSV",
    "label.range": "النطاق",
    "label.today": "اليوم",
    "label.confidence": "درجة الثقة",

    // ---- company page ----
    "co.performance": "الأداء",
    "co.performance.sub": "العائد الكلي شاملًا التوزيعات.",
    "co.keynumbers": "الأرقام الأساسية",
    "co.valuation": "كم قد تساوي؟",
    "co.valuation.sub": "تقدير نموذجي من افتراضات معلنة — وليس سعرًا مستهدفًا.",
    "co.statements": "التاريخ المالي",
    "co.dividends": "التوزيعات",
    "co.liquidity": "سهولة التداول",
    "co.stress": "خلال تخفيضات قيمة الجنيه",
    "co.stress.sub": "مقاسة من أسعار حقيقية — وليست صدمة نموذجية.",
    "co.currentprice": "السعر الحالي",
    "co.modelestimate": "تقدير النموذج",
    "co.difference": "الفرق",
    "co.asof": "حتى تاريخ",

    "co.peers": "كيف تقارن بنظيراتها",
    "co.peers.sub": "مرتّبة مقابل الشركات التي تفصح عن نفس المقياس.",
    "co.nearest": "أقرب الشركات إليها في الحجم",
    "co.nearest.sub": "نفس القطاع، والأقرب في القيمة السوقية — الشركة الأكبر بعشرين ضعفًا تواجه تكاليف ورقابة مختلفة.",
    "co.band.return1y": "عائد سنة",
    "co.band.estimate": "تقدير النموذج",
    "co.band.liquidity": "سهولة التداول",
    "co.band.yield": "عائد التوزيعات",
    "co.band.data": "البيانات المتاحة",

    // ---- explanatory ----
    "note.notadvice":
      "هذه المنصة تقدّم معلومات وأبحاثًا ومحتوى تعليميًا وتحليلًا تاريخيًا " +
      "وأدوات تحليلية. وهي لا تقدّم نصائح استثمارية شخصية ولا إدارة محافظ ولا " +
      "ضمانات لأي عائد. الأداء التاريخي والسيناريوهات النموذجية لا تضمن نتائج " +
      "مستقبلية. وأنت مسؤول عن قراراتك الاستثمارية.",
    "note.realreturn":
      "«حقيقي» تعني بعد التضخم المصري — أي ما يمكن لأموالك أن تشتريه فعلًا. " +
      "خلال خمس سنوات تضاعفت الأسعار نحو مرتين ونصف، فقد يكون المكسب الاسمي " +
      "الكبير مكسبًا حقيقيًا متواضعًا، وقد يكون المكسب الصغير خسارة حقيقية.",
    "note.dash":
      "الشرطة تعني أن الشركة لا تُفصح عن هذا البند — لا أن قيمته صفر.",

    // ---- footer ----
    "foot.what": "ما هذا الموقع",
    "foot.whatnot": "ما ليس هو",
    "foot.methodology": "كيف تُحسب الأرقام",
    "foot.terms": "الشروط وإخلاء المسؤولية",
    "foot.quality": "ما الخطأ في بياناتنا",
    "foot.learn": "تعلّم الاستثمار",
  },
};

/* ---------------- state ---------------- */
function currentLang() {
  // An explicit choice wins. Failing that, the page was served as one language
  // or the other -- an Arabic landing page arrives with lang="ar" already on
  // the root, and flipping it back to English the moment JavaScript boots
  // would undo the whole point of serving it.
  try {
    const stored = localStorage.getItem("egx-lang");
    if (stored === "ar" || stored === "en") return stored;
  } catch (e) { /* private mode: fall through to what was served */ }
  return document.documentElement.lang === "ar" ? "ar" : "en";
}

function setLang(lang) {
  try { localStorage.setItem("egx-lang", lang); } catch (e) {}
  applyLang();
  if (typeof render === "function") render();
}

/** Translate a key. Falls back to the English default handed in. */
function t(key, fallback) {
  const lang = currentLang();
  if (lang === "en") return fallback !== undefined ? fallback : key;
  const table = I18N[lang] || {};
  return table[key] !== undefined ? table[key]
    : (fallback !== undefined ? fallback : key);
}

const isRTL = () => currentLang() === "ar";

function applyLang() {
  const lang = currentLang();
  const html = document.documentElement;
  html.lang = lang === "ar" ? "ar" : "en";
  // dir on the root element flips the whole layout, including scrollbars and
  // the direction text wraps in.
  html.dir = lang === "ar" ? "rtl" : "ltr";
  document.body.dataset.lang = lang;

  document.querySelectorAll("[data-set-lang]").forEach(b =>
    b.classList.toggle("on", b.dataset.setLang === lang));

  // Chrome that lives in index.html rather than in a view.
  document.querySelectorAll("[data-i18n]").forEach(el => {
    const key = el.dataset.i18n;
    if (!el.dataset.i18nDefault) el.dataset.i18nDefault = el.textContent.trim();
    el.textContent = t(key, el.dataset.i18nDefault);
  });
  document.querySelectorAll("[data-i18n-placeholder]").forEach(el => {
    const key = el.dataset.i18nPlaceholder;
    if (!el.dataset.i18nDefault) el.dataset.i18nDefault = el.placeholder || "";
    el.placeholder = t(key, el.dataset.i18nDefault);
  });
}
