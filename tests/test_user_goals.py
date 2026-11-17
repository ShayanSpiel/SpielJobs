"""User-intent acceptance scenarios. Fixtures do not establish live market recall."""
import unittest
from unittest.mock import AsyncMock, patch
import httpx
from spieljobs.server import app

# Distinct professions and locations, including deliberate lexical traps.
VACANCIES=[
 {'title':'کارشناس حسابداری','description':'Excel و ثبت اسناد مالی','location':'تهران','company':'Example Accounting','url':'https://example.org/accountant','source':'fixture'},
 {'title':'کارشناس پشتیبانی مشتریان','description':'ارتباط با تیم حسابداری','location':'تهران','company':'Example Support','url':'https://example.org/support','source':'fixture'},
 {'title':'Sales Supervisor','description':'Lead the sales team','location':'شیراز','company':'Example Sales','url':'https://example.org/sales-supervisor','source':'fixture'},
 {'title':'Junior Sales Representative','location':'شیراز','company':'Example Sales','url':'https://example.org/junior-sales','source':'fixture'},
 {'title':'Operations Manager','location':'Tehran','company':'Example Operations','url':'https://example.org/operations','source':'fixture'},
 {'title':'Process Engineer','description':'مهندسی فرایند در صنعت پتروشیمی','location':'عسلویه','company':'Example Petrochemical','url':'https://example.org/process','source':'fixture'},
 {'title':'Process Analyst','description':'تحلیل فرایند کسب و کار','location':'عسلویه','company':'Example Consulting','url':'https://example.org/analyst','source':'fixture'},
 {'title':'کارشناس تولید','description':'کار در صنعت پتروشیمی','location':'ماهشهر','company':'Example Petrochemical','url':'https://example.org/production','source':'fixture'},
 {'title':'Data Analyst','description':'SQL queries and dashboards','location':'اصفهان','company':'Example Data','url':'https://example.org/sql','source':'fixture'},
]

class UserGoalTests(unittest.IsolatedAsyncioTestCase):
    async def search(self, query):
        data=([dict(job) for job in VACANCIES],[{'id':'fixture','name':'Fixture','state':'partial'}])
        with patch('spieljobs.agent.collect',AsyncMock(return_value=data)),patch('spieljobs.agent.extract_profile',AsyncMock(return_value=([],None))):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as client:
                response=await client.post('/search',json={'query':query})
        self.assertEqual(response.status_code,200)
        return [job['url'] for job in response.json()['jobs']]

    async def test_accountant_finds_accounting_not_support_department_mentions(self):
        self.assertEqual(await self.search('حسابدار در تهران'),['https://example.org/accountant'])

    async def test_accountant_skill_is_read_from_description(self):
        self.assertEqual(await self.search('حسابداری با مهارت Excel در تهران'),['https://example.org/accountant'])

    async def test_support_specialist_is_not_sent_accounting_jobs(self):
        self.assertEqual(await self.search('کارشناس پشتیبانی در تهران'),['https://example.org/support'])

    async def test_sales_supervisor_does_not_receive_junior_sales(self):
        self.assertEqual(await self.search('سرپرست فروش در شیراز'),['https://example.org/sales-supervisor'])

    async def test_operations_manager_matches_bilingual_title(self):
        self.assertEqual(await self.search('مدیر عملیات تهران'),['https://example.org/operations'])

    async def test_industry_worker_can_search_by_sector_and_city(self):
        self.assertEqual(await self.search('پتروشیمی ماهشهر'),['https://example.org/production'])

    async def test_process_engineer_is_not_a_business_process_analyst(self):
        self.assertEqual(await self.search('مهندس فرایند در عسلویه'),['https://example.org/process'])

    async def test_skill_only_query_can_match_description_and_location(self):
        self.assertEqual(await self.search('SQL در اصفهان'),['https://example.org/sql'])

    async def test_no_city_match_is_empty_not_a_different_city(self):
        self.assertEqual(await self.search('حسابدار در کرج'),[])
