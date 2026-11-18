"""Declarative source registry. Platform parsers live independently of employers."""
JOBVISION={'id':'jobvision','name':'Jobvision','label':'جاب‌ویژن','site_url':'https://jobvision.ir'}
# Career URLs are explicit source configuration, never invented results.
CAREERS=[
 {'id':'snapp','name':'Snapp','label':'اسنپ','site_url':'https://snapp.ir','url':'https://career.snapp.ir/jobs','kind':'html','title_selector':'h6','card_fields':{'category':'p'},'verification':'current-official-careers-2026-11-17'},
 {'id':'divar','name':'Divar','label':'دیوار','site_url':'https://divar.ir','url':'https://careers.divar.ir/positions','kind':'html','verification':'browser-confirmed-2026-11-17','location_before_separator':True,'exclude_paths':['talent-pool']},
 {'id':'digikala','name':'Digikala','label':'دیجی‌کالا','site_url':'https://digikala.com','url':'https://career.hrcando.ir/co/Digikala','kind':'hrcando','verification':'official-careers-api-redirect-2026-11-17'},
 {'id':'tapsi','name':'Tapsi','label':'تپسی','site_url':'https://tapsi.ir','url':'https://careers.tapsi.ir/jobs','kind':'hrcando'},
 {'id':'snappfood','name':'Snappfood','label':'اسنپ‌فود','site_url':'https://snappfood.ir','url':'https://careers.snappfood.ir/','kind':'hrcando','job_path':'/job-details/','filters':True,'strip_opening_count':True},
 {'id':'azki','name':'Azki','label':'ازکی','site_url':'https://azki.com','url':'https://jobs.azki.com/','kind':'html'},
 {'id':'yektanet','name':'Yektanet','label':'یکتانت','site_url':'https://www.yektanet.ir','url':'https://www.yektanet.ir/careers/','kind':'jobvision_company','company_id':1236,'provider':'jobvision','verification':'official-company-careers-link-2026-11-17'},
 {'id':'jabama','name':'Jabama','label':'جاباما','site_url':'https://jabama.com','url':'https://careers.jabama.com/','kind':'html'},
 {'id':'alibaba','name':'Alibaba Travels','label':'علی‌بابا','site_url':'https://alibaba.ir','url':'https://jobs.alibaba.ir/','kind':'html'},
 {'id':'sabaidea','name':'Sabaidea','label':'صباایده','site_url':'https://sabaidea.com','url':'https://www.sabaidea.com/job','kind':'html','unavailable_marker':'بدلیل آپدیت موقعیت‌های شغلی فعلا قابل دسترس نیستند'},
 {'id':'torob','name':'Torob','label':'ترب','site_url':'https://torob.com','url':'https://jobs.torob.com/','kind':'html','verification':'official-homepage-link-2026-11-17','card_fields':{'company':'.product-tag','description':'.job-card-lead','category':'.job-facts > span:nth-child(1)','location':'.job-facts > span:nth-child(2)','contract':'.job-facts > span:nth-child(3)','experience':'.job-facts > span:nth-child(4)'}},
 {'id':'cafebazaar','name':'Cafe Bazaar','label':'کافه‌بازار','site_url':'https://cafebazaar.ir','url':'https://careers.cafebazaar.ir/','kind':'recrupen','api_url':'https://recrupen.cafebazaar.ir/job/','company_id':4},
 {'id':'nobitex','name':'Nobitex','label':'نوبیتکس','site_url':'https://nobitex.ir','url':'https://nobitex.ir/jobs/','kind':'html'},
 {'id':'doctoreto','name':'Doctoreto','label':'دکترتو','site_url':'https://doctoreto.com','url':'https://careers.doctoreto.com/','kind':'html'},
 {'id':'digiexpress','name':'Digiexpress','label':'دیجی‌اکسپرس','site_url':'https://digiexpress.ir','url':'https://careers.digiexpress.ir/opportunities','kind':'html','title_selector':'div.flex-col > span','card_fields':{'location':'span:has(svg.lucide-map-pin)','contract':'span:has(svg.lucide-clock)','category':'span:has(svg.lucide-users)'}},
 {'id':'mrbilit','name':'Mrbilit','label':'مستربلیط','site_url':'https://mrbilit.com','url':'https://career.hrcando.ir/co/MrBilit-1-1','kind':'hrcando','verification':'employer-published-ats-link'},
 {'id':'karnameh','name':'Karnameh','label':'کارنامه','site_url':'https://karnameh.com','url':'https://careers.karnameh.com/','kind':'html'},
 {'id':'blubank','name':'Blubank','label':'بلوبانک','site_url':'https://blubank.com','url':'https://careers.blubank.ir/','kind':'html'},
 {'id':'shab','name':'Shab','label':'شب','site_url':'https://shab.ir','url':'https://www.shab.ir/careers','kind':'html'},
 {'id':'arvancloud','name':'Arvancloud','label':'آروان‌کلاد','site_url':'https://arvancloud.ir','url':'https://www.arvancloud.ir/fa/jobs','kind':'html','access_challenge_marker':'__arcsjsc'},
]


def configured():
    return [JOBVISION, *CAREERS]

# Native province values inspected on Jobinja's public search form.
JOBINJA_PROVINCES={'tehran':'تهران','karaj':'البرز','isfahan':'اصفهان','shiraz':'فارس','mashhad':'خراسان رضوی','tabriz':'آذربایجان شرقی','ahvaz':'خوزستان','asaluyeh':'بوشهر','mahshahr':'خوزستان','bushehr':'بوشهر','rasht':'گیلان','yazd':'یزد','kerman':'کرمان','qom':'قم','qazvin':'قزوین','arak':'مرکزی'}
