"""Deterministic query preparation and job matching; no network or model needed."""
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import re
import json
import unicodedata
from pathlib import Path

TAXONOMY=json.loads(Path(__file__).with_name('taxonomy.json').read_text(encoding='utf-8'))
TERM_GROUPS=TAXONOMY['concepts']
CITIES=TAXONOMY['cities']

DIGITS = str.maketrans('۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩', '01234567890123456789')
ALIASES = {term:[variant for variant in group if variant!=term] for group in TERM_GROUPS for term in group}
STOP = {'find', 'me', 'a', 'the', 'jobs', 'job', 'roles', 'role', 'in', 'for', 'posted', 'last', 'days', 'day', 'week', 'weeks', 'recent', 'open', 'and', 'or', 'فرصت', 'شغلی', 'استخدام', 'در', 'برای', 'روز', 'هفته', 'اخیر', 'پیدا', 'کن', 'بر', 'با', 'من', 'را', 'های', 'هایش', 'مناسب', 'اساس', 'رزومه', 'فرصتهای', 'به', 'از', 'یک', 'این', 'که', 'است', 'ها', 'پیدا', 'کنید', 'موقعیت', 'های', 'شغل', 'شغلی', 'کار', 'می', 'خوام', 'دنبال', 'هستم', 'please', 'my', 'with', 'based', 'resume', 'cv', 'looking', 'want'}
STOP |= {'مهارت','مهارتهای','مسلط','تسلط','آشنا','بلدم','هایی','هایشان','ترین','تر','راهنمایی','خواهش','میخوام','میشه','لطفا','لطفاً','دنبال','بگرد','بگردید','پیشنهاد','بدید','بده','کنم','میخوام','موقعیتهای','فرصتهای','منم','شما','حوزه','زمینه','تجربه','سابقه','دارم','هست','هستم','است','هستند','هایی','های','ای','آگهی','آگهیها','job','jobs','looking','find','show','please','i','am','have','experience','skills','skill','years','year','search','want','position','positions'}
# Hazm's MIT-licensed Persian stopword data; preserve domain terms that are
# meaningful in job titles despite their frequency in general Persian text.
_hazm_words = (Path(__file__).with_name('persian_stopwords.txt')).read_text(encoding='utf-8').splitlines()
_protected_terms = {'داده','رشد','تغییر','اجرا','برنامه','فروش','کارشناس','مدیر','محصول','بازار','مالی','پشتیبانی','حسابداری','طراحی','توسعه','تحلیل','هوش','مصنوعی','سازمان','عملیات','منابع','انسانی'}
STOP |= {re.sub(r'\s+', ' ', unicodedata.normalize('NFKC', word).replace('\u200c',' ')).strip().lower() for word in _hazm_words} - _protected_terms

def normalize(value):
    text = unicodedata.normalize('NFKC', value or '').translate(DIGITS).replace('ي','ی').replace('ك','ک').replace('\u200c',' ').replace('ـ','')
    return re.sub(r'\s+', ' ', re.sub(r'[\u064b-\u065f\u0670]', '', text)).strip().lower()

def needs_interpretation(query, resume=''):
    """Conservative routing: short straightforward searches use no model."""
    if resume.strip():
        return True
    text = normalize(query)
    ambiguity = ('نمی دانم چه', 'نمیدانم چه', 'چه شغلی', 'چه موقعیتی', 'چه نقشی',
                 'نمی دونم چه', 'نمیدونم چه', 'what role', 'which role',
                 'what job', 'which job', 'not sure what', 'don\'t know what')
    interpretive_markers = ('تجربه دارم', 'سابقه دارم', 'تجربه کار', 'به جز', 'ولی نه', 'نه برنامه', 'بدون برنامه', 'متناسب با', 'توصیه', 'experience in', 'i have', 'but not', 'except for', 'career change', 'change career')
    return any(marker in text for marker in interpretive_markers) or len(text) >= 140 or len(text.split()) >= 20 or any(marker in text for marker in ambiguity)

# Correct only unambiguous, one-edit English job vocabulary; leave names,
# unknown skills and short tokens untouched rather than guessing their meaning.
TYPO_VOCAB = {'manager','management','marketing','product','engineer','engineering','developer','development','director','designer','design','specialist','analyst','analysis','accounting','finance','financial','support','customer','sales','transformation','operations','software','python','javascript','typescript','machine','learning','artificial','intelligence'}

def _one_edit(a,b):
    if abs(len(a)-len(b))>1: return False
    if len(a)==len(b):
        differences=[i for i,(x,y) in enumerate(zip(a,b)) if x!=y]
        return len(differences)==1 or (len(differences)==2 and differences[1]==differences[0]+1 and a[differences[0]]==b[differences[1]] and a[differences[1]]==b[differences[0]])
    shorter,longer=(a,b) if len(a)<len(b) else (b,a)
    return any(longer[:i]+longer[i+1:]==shorter for i in range(len(longer)))

def correct_query_spelling(text):
    corrections=[]
    def correct(match):
        word=match.group(0)
        if len(word)<5 or word in TYPO_VOCAB or word in {'manage', 'managed', 'manages', 'managing'}: return word
        candidates=[candidate for candidate in TYPO_VOCAB if _one_edit(word,candidate)]
        if len(candidates)==1:
            corrections.append({'original':word,'corrected':candidates[0]})
            return candidates[0]
        return word
    return re.sub(r'(?<![\w+#.])[a-z]+(?![\w+#.])',correct,text),corrections

def parse_query(query):
    text, corrections = correct_query_spelling(normalize(query))
    excluded_terms=[]
    negative = re.search(r'(?:ولی نه|نه|بدون|but not|excluding)\s+([^،,.!?]+)', text)
    if negative:
        phrase=negative.group(1).strip()
        excluded_terms=[phrase]
        if any(term in phrase for term in ('برنامه نویس','برنامه نویسی','developer','programming')):
            excluded_terms=['برنامه نویس','برنامه نویسی','developer','software engineer','programmer']
        text=text[:negative.start()].strip()

    match = re.search(r'(?:last|past|اخیر|گذشته)?\s*(\d+)\s*(days?|روز|weeks?|هفته)', text)
    days = min(365, int(match.group(1)) * (7 if match.group(2) in ('week','weeks','هفته') else 1)) if match else (7 if re.search(r'\b(?:last|past) week\b|هفته گذشته|هفته اخیر', text) else None)
    tokens = [t for t in re.findall(r'[\w+#.]+', text) if len(t) > 1 and t not in STOP and not t.isdigit()]
    requested_location=next((key for key,names in CITIES.items() if any(re.search(r'(?<!\w)'+re.escape(name)+r'(?!\w)',text) for name in names)), None)
    city_words={word for names in CITIES.values() for name in names for word in name.split()}
    tokens = [t for t in tokens if t not in city_words]
    terms = list(dict.fromkeys(tokens))
    for name, synonyms in ALIASES.items():
        if re.search(r'(?<!\w)' + re.escape(name) + r'(?!\w)', text):
            terms.extend(x for x in synonyms if x not in terms)
    if 'هوش مصنوعی' in text:
        terms = [term for term in terms if term not in ('هوش','مصنوعی')]
        terms.insert(0,'هوش مصنوعی')
    # Treat recognized multi-word concepts as one unit, and group translations.
    concepts=[]; remaining=list(dict.fromkeys(tokens))
    groups=TERM_GROUPS
    for group in groups:
        matched = next((phrase for phrase in group if re.search(r'(?<!\w)' + re.escape(phrase) + r'(?!\w)', text)), None)
        if matched:
            concepts.append(group)
            remaining=[token for token in remaining if token not in set(' '.join(group).split())]
    concepts.extend([[token] for token in remaining if token not in GENERIC_QUALIFIERS])
    # Preserve the role phrase for retrieval instead of issuing unrelated one-word searches.
    source_tokens=[token for token in tokens if token not in GENERIC_QUALIFIERS or token in TAXONOMY['leadership']]
    skill_words={word for group in concepts if any(term in TAXONOMY['skills'] for term in group) for variant in group for word in variant.split()}
    industry_words={word for group in concepts if any(term in TAXONOMY['industries'] for term in group) for variant in group for word in variant.split()}
    body_evidence_words=skill_words|industry_words
    if any(token not in body_evidence_words and token not in GENERIC_QUALIFIERS for token in source_tokens):
        source_tokens=[token for token in source_tokens if token not in body_evidence_words]
    source_phrase=' '.join(source_tokens[:6])
    search_terms=[source_phrase] if source_phrase else ([' '.join(tokens[:4])] if tokens else [])
    retrieval_concepts=[group for group in concepts if any(word in source_tokens for variant in group for word in variant.split())]
    if len(retrieval_concepts)==1:
        search_terms.extend(x for x in retrieval_concepts[0] if x != source_phrase)
    elif 1 < len(retrieval_concepts) <= 3 and any(len(group)>1 for group in retrieval_concepts):
        # Translate the complete set of concepts together; do not fan out into
        # broad searches for individual words like "AI" or "manager".
        search_terms.append(' '.join(group[1] if len(group)>1 else group[0] for group in retrieval_concepts))
    meaningful=[token for token in source_tokens if token not in GENERIC_QUALIFIERS]
    skill_query=bool(concepts) and all(any(term in TAXONOMY['skills'] for term in group) for group in concepts)
    if skill_query:
        search_terms=[group[0] for group in concepts]
    industry_query=bool(concepts) and all(any(term in TAXONOMY['industries'] for term in group) for group in concepts)
    role_kind=next((kind for kind,variants in TAXONOMY['role_kinds'].items() if any(re.search(r'(?<!\w)'+re.escape(term)+r'(?!\w)',text) for term in variants)),None)
    unsupported = []
    if re.search(r'(?<!\w)(?:remote only|only remote|fully remote|فقط دورکاری|فقط دورکار)(?!\w)', text):
        unsupported.append('remote_only')
    if re.search(r'(?<!\w)(?:not in tehran|except tehran|exclude tehran|به جز تهران|بجز تهران|غیر تهران)(?!\w)', text):
        unsupported.append('exclude_tehran')
    return {'query': query, 'corrections':corrections, 'terms': terms[:20], 'search_terms':list(dict.fromkeys(search_terms))[:4], 'concepts':concepts, 'skill_query':skill_query, 'industry_query':industry_query, 'role_kind':role_kind, 'strict_concepts':not needs_interpretation(query) and len(concepts)<=3, 'days': days, 'location': requested_location if 'exclude_tehran' not in unsupported else None, 'leadership': any(re.search(r'(?<!\w)'+re.escape(term)+r'(?!\w)',text) for term in TAXONOMY['leadership']), 'unsupported_constraints': unsupported, 'excluded_terms':excluded_terms, 'seniority': ('senior' if re.search(r'(?<!\w)(?:senior|ارشد)(?!\w)', text) else 'junior' if re.search(r'(?<!\w)(?:junior|intern|کارآموز|جونیور)(?!\w)', text) else None)}

def relative_date(value, now=None):
    text = normalize(value)
    now = (now or datetime.now(timezone.utc)).astimezone(ZoneInfo('Asia/Tehran'))
    if 'امروز' in text or 'today' in text:
        return now.date().isoformat()
    if 'دیروز' in text or 'yesterday' in text:
        return (now - timedelta(days=1)).date().isoformat()
    m = re.search(r'(\d+)\s*(روز|ساعت|day|days|hour|hours)', text)
    if not m:
        return None
    amount = int(m.group(1))
    delta = timedelta(hours=amount) if m.group(2) in ('ساعت','hour','hours') else timedelta(days=amount)
    return (now - delta).date().isoformat()

# Bounded, explainable skills/role vocabulary for fallback when no model is available.
RESUME_TERMS = [
    'ai transformation', 'هوش مصنوعی', 'artificial intelligence', 'ai', 'تحول دیجیتال',
    'product manager', 'مدیر محصول', 'product management', 'marketing manager', 'مدیر مارکتینگ',
    'digital marketing', 'دیجیتال مارکتینگ', 'marketing', 'بازاریابی', 'human resources',
    'منابع انسانی', 'software engineer', 'software developer', 'python', 'javascript',
    'typescript', 'data science', 'data analyst', 'تحلیل داده', 'machine learning',
    'یادگیری ماشین', 'devops', 'sales manager', 'مدیر فروش', 'accounting', 'حسابداری',
    'seo', 'ui ux', 'مدیریت پروژه', 'project manager', 'automation', 'اتوماسیون',
]

def contains_term(text, term):
    # Word boundaries prevent "ai" matching "training" and "بر" inside Persian words.
    return bool(re.search(r'(?<!\w)' + re.escape(normalize(term)) + r'(?!\w)', normalize(text)))

def extract_resume_terms(resume):
    text = normalize(resume)
    return [term for term in RESUME_TERMS if contains_term(text, term)][:12]

# Only apply a role gate when the resume contains exactly one identifiable
# family. Skills on their own must not turn a product manager into a developer.
RESUME_ROLES = (
    ('product manager','product management','مدیر محصول','مدیریت محصول'),
    ('marketing manager','مدیر مارکتینگ','مدیر بازاریابی'),
    ('sales manager','مدیر فروش'),
    ('project manager','مدیر پروژه','مدیریت پروژه'),
    ('software engineer','software developer','مهندس نرم افزار','توسعه دهنده نرم افزار'),
    ('data analyst','تحلیلگر داده','تحلیل گر داده'),
)

def fallback_resume_role(resume):
    roles=[role for role in RESUME_ROLES if any(contains_term(resume,variant) for variant in role)]
    return list(roles[0]) if len(roles)==1 else []

GENERIC_QUALIFIERS = {'manager','lead','head','director','senior','junior','engineer','developer','specialist','مدیر','رهبر','سرپرست','ارشد','کارشناس','مهندس','توسعه دهنده','تهران','tehran'}

def rank_and_filter(jobs, profile, today=None):
    today = today or datetime.now(ZoneInfo('Asia/Tehran')).date()
    terms = list(dict.fromkeys(normalize(t) for t in profile['terms'] if len(t) > 1 and normalize(t) not in STOP))
    out = []
    for original in jobs:
        job = dict(original)
        if job.get('status') == 'closed':
            continue
        if profile.get('location') and not any(contains_term(job.get('location') or '', place) for place in CITIES.get(profile['location'],[profile['location']])):
            continue
        title = job.get('title') or ''
        primary_title=title.split('|',1)[0]
        requested_families={name for name,variants in TAXONOMY.get('role_families',{}).items() if any(contains_term(profile.get('query') or '',term) for term in variants)}
        job_families={name for name,variants in TAXONOMY.get('role_families',{}).items() if any(contains_term(primary_title,term) for term in variants)}
        if requested_families and job_families and requested_families.isdisjoint(job_families):
            continue
        if any(contains_term(title, term) for term in profile.get('excluded_terms', [])):
            continue
        description = job.get('description') or ''
        if profile.get('industry_query') or any(any(term in TAXONOMY['industries'] for term in group) for group in profile.get('concepts',[])):
            description += ' ' + (job.get('company') or '')
        role_kind=profile.get('role_kind')
        if role_kind and not any(contains_term(title, term) for term in TAXONOMY['role_kinds'][role_kind]):
            continue
        if profile.get('leadership') and not any(contains_term(title, term) for term in TAXONOMY['leadership']):
            continue
        seniority = profile.get('seniority')
        levels = {'senior': ('senior', 'lead', 'head', 'director', 'ارشد', 'سرپرست'), 'junior': ('junior', 'intern', 'جونیور', 'کارآموز', 'مبتدی')}
        if seniority and not any(contains_term(title, level) for level in levels[seniority]):
            continue
        role=profile.get('fallback_resume_role') or []
        if role and not any(contains_term(title,variant) for variant in role):
            continue
        title_hits = [t for t in terms if contains_term(title, t)]
        body_hits = [t for t in terms if contains_term(description, t) and t not in title_hits]
        discriminative = [term for term in terms if term not in GENERIC_QUALIFIERS]
        content_hits = title_hits + body_hits
        if terms and (not content_hits or (discriminative and not any(term in discriminative for term in content_hits))):
            continue
        concepts=profile.get('concepts', [])
        if profile.get('strict_concepts') and concepts:
            if not all(any(contains_term(title+' '+description, variant) for variant in concept) for concept in concepts):
                continue
            # Generic "specialist" alone cannot make a finance title match a
            # support mention in its description. Technical roles can still
            # match an explicitly requested skill that appears in the body.
            technical_titles={'developer','engineer','مهندس','توسعه دهنده'}
            if not (profile.get('skill_query') or profile.get('industry_query')) and not any(hit not in GENERIC_QUALIFIERS for hit in title_hits) and not any(hit in technical_titles for hit in title_hits):
                continue
        if profile.get('days') is not None:
            if not job.get('posted_date'):
                continue
            try:
                age = (today - datetime.fromisoformat(job['posted_date']).date()).days
                if age < 0 or age > profile['days']:
                    continue
            except ValueError:
                continue
        job['match_terms'] = [hit for hit in content_hits if hit not in GENERIC_QUALIFIERS and hit not in STOP][:5]
        job['score'] = 5 * len(title_hits) + 2 * len(body_hits)
        out.append(job)
    # Relevance first, then more recent dated postings; unknown dates sort last on ties.
    return sorted(out, key=lambda x: (-x['score'], -(date_ordinal(x.get('posted_date'))), x.get('title','')))

def date_ordinal(value):
    try:
        return datetime.fromisoformat(value).date().toordinal() if value else 0
    except (ValueError, TypeError):
        return 0
