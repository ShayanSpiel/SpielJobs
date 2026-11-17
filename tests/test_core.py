import sys
import unittest
from datetime import datetime, timezone, date
sys.path.insert(0,'backend')
from spieljobs.core import normalize,parse_query,relative_date,rank_and_filter
class CoreTests(unittest.TestCase):
    def test_persian_normalization(self):
        self.assertEqual(normalize('يک ۱۲'), 'یک 12')
    def test_dates(self):
        now=datetime(2026,11,16,tzinfo=timezone.utc)
        self.assertEqual(relative_date('۳ روز پیش',now),'2026-11-13')
        self.assertIsNone(relative_date('unknown',now))
    def test_query(self):
        self.assertEqual(parse_query('AI jobs last 7 days')['days'],7)
        self.assertIsNone(parse_query('AI')['days'])
    def test_unknown_dates_excluded(self):
        jobs=[{'title':'AI engineer','posted_date':None}]
        self.assertEqual(rank_and_filter(jobs,{'terms':['ai'],'days':7},date(2026,11,16)),[])
if __name__=='__main__': unittest.main()

class RankingTests(unittest.TestCase):
    def test_persian_stop_words_do_not_become_skills(self):
        terms=parse_query('فرصت‌های مناسب بر اساس رزومه من')['terms']
        self.assertNotIn('بر',terms)
    def test_ai_does_not_match_inside_training(self):
        jobs=[{'title':'Training coordinator'},{'title':'AI engineer'}]
        results=rank_and_filter(jobs,{'terms':['ai'],'days':None})
        self.assertEqual([x['title'] for x in results],['AI engineer'])
    def test_title_match_outranks_description(self):
        jobs=[{'title':'Sales','description':'AI'},{'title':'AI engineer','description':''}]
        results=rank_and_filter(jobs,{'terms':['ai'],'days':None})
        self.assertEqual(results[0]['title'],'AI engineer')
    def test_cv_extracts_known_skills(self):
        from spieljobs.core import extract_resume_terms
        self.assertIn('python',extract_resume_terms('Experienced Python engineer and data analyst'))
        self.assertNotIn('ai',extract_resume_terms('training management'))

class LocationTests(unittest.TestCase):
    def test_tehran_filters_known_other_cities(self):
        profile=parse_query('Python developer in Tehran')
        jobs=[{'title':'Python Developer','location':'تهران، تهران'}, {'title':'Python Developer','location':'اصفهان'}]
        self.assertEqual([x['location'] for x in rank_and_filter(jobs,profile)],['تهران، تهران'])

class ResumeRoleTests(unittest.TestCase):
    def test_product_manager_skills_do_not_promote_developer_roles(self):
        from spieljobs.core import fallback_resume_role
        role=fallback_resume_role('Senior product manager Python SQL 5 years')
        profile={'terms':['product manager','python'],'days':None,'fallback_resume_role':role}
        jobs=[{'title':'Python Developer'}, {'title':'Senior Product Manager'}, {'title':'مدیر محصول'}]
        self.assertEqual([job['title'] for job in rank_and_filter(jobs,profile)],['Senior Product Manager'])
    def test_multiple_identified_roles_remain_ambiguous(self):
        from spieljobs.core import fallback_resume_role
        self.assertEqual(fallback_resume_role('product manager and project manager'),[])
