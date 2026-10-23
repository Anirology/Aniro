import json
import unittest
from datetime import date, datetime, timezone
from unittest.mock import patch
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session

from db import Base
from models import LifeArea, Goal, Task, CalendarBlock, BudgetMonth, ExpenseCategory, Expense, GoogleIntegration
from plan_api import current_user, edit_block, BlockIn
from stage4_api import (CalendarChoice, CalendarEventIn, CoachIn, Confirm, RemoteError, ask, calendars, choose_calendar,
                        coach_context, create_calendar_event, update_calendar_event, delete_calendar_event,
                        access_token, disconnect, events, google_callback, google_start, protect,
                        remove_synced_block, status, sync_block, unprotect)

WEEK = "2026-10-12"

class Stage4Tests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        @event.listens_for(self.engine, "connect")
        def foreign_keys(connection, _): connection.execute("PRAGMA foreign_keys=ON")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.user = current_user(self.db)
        self.area = LifeArea(user_id=self.user.id, name="Relationships", color_key="relationships")
        self.db.add(self.area)
        self.db.flush()
        self.goal = Goal(user_id=self.user.id, life_area_id=self.area.id, horizon="week", title="Call Riya", target_date=WEEK)
        self.db.add(self.goal)
        self.db.flush()
        self.task = Task(user_id=self.user.id, goal_id=self.goal.id, week_start=WEEK, title="Call Riya")
        self.db.add(self.task)
        self.db.flush()
        self.block = CalendarBlock(task_id=self.task.id, start_at=datetime(2026,10,13,9), end_at=datetime(2026,10,13,10))
        self.db.add(self.block)
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def test_token_encryption_round_trip_and_tamper_rejection(self):
        cipher = protect({"refresh_token": "private"})
        self.assertNotIn("private", cipher)
        self.assertEqual(unprotect(cipher)["refresh_token"], "private")
        with self.assertRaises(Exception): unprotect(cipher[:-3] + "ABC")

    def test_refresh_network_failure_keeps_valid_connection(self):
        from fastapi import HTTPException
        record = GoogleIntegration(user_id=self.user.id, encrypted_token=protect({"access_token":"old", "refresh_token":"refresh", "created_at":0, "expires_in":3600}))
        self.db.add(record)
        self.db.commit()
        with patch("stage4_api.http_json", side_effect=RemoteError(503, "Provider is unreachable")):
            with self.assertRaises(HTTPException) as failed:
                access_token(self.db, record)
        self.assertEqual(failed.exception.status_code, 503)
        self.assertEqual(record.last_error, "Provider is unreachable")
        self.assertTrue(status(self.db)["connected"])
        self.assertEqual(unprotect(record.encrypted_token)["refresh_token"], "refresh")
        with patch("stage4_api.http_json", return_value={"access_token":"fresh", "expires_in":3600}):
            self.assertEqual(access_token(self.db, record), "fresh")
        self.assertIsNone(record.last_error)

    def test_refresh_invalid_grant_requires_reconnection(self):
        from fastapi import HTTPException
        record = GoogleIntegration(user_id=self.user.id, encrypted_token=protect({"access_token":"old", "refresh_token":"refresh", "created_at":0, "expires_in":3600}))
        self.db.add(record)
        self.db.commit()
        with patch("stage4_api.http_json", side_effect=RemoteError(400, "Provider returned HTTP 400", "invalid_grant")):
            with self.assertRaises(HTTPException) as failed:
                access_token(self.db, record)
        self.assertEqual(failed.exception.status_code, 409)
        self.assertIn("reconnection", record.last_error)

    def test_direct_calendar_event_create_edit_delete_and_linked_block_guard(self):
        record = GoogleIntegration(user_id=self.user.id, selected_calendar_id="aniruththens@gmail.com", encrypted_token="mock")
        self.db.add(record)
        self.db.commit()
        data = CalendarEventIn(title="Study", start=datetime(2026,10,13,9,tzinfo=timezone.utc),
                               end=datetime(2026,10,13,10,tzinfo=timezone.utc), request_id="a"*32)
        calls = []
        def fake_google_call(db, method, path, body=None, params=None):
            calls.append((method,path,body))
            return {"id":"aniroevent"+"a"*32}
        with patch("stage4_api.google_call", side_effect=fake_google_call):
            created = create_calendar_event(data,self.db)
            self.assertEqual(created["id"],"aniroevent"+"a"*32)
            self.assertEqual(calls[-1][2]["summary"],"Study")
            self.assertEqual(calls[-1][2]["start"]["dateTime"],"2026-10-13T09:00:00+00:00")
            all_day = CalendarEventIn(title="Leave", all_day=True, start_date=date(2026,10,14),
                                      end_date=date(2026,10,16), request_id="b"*32)
            create_calendar_event(all_day,self.db)
            self.assertEqual(calls[-1][2]["start"],{"date":"2026-10-14"})
            self.assertEqual(calls[-1][2]["end"],{"date":"2026-10-16"})
            update_calendar_event(created["id"],data,self.db)
            self.assertEqual(calls[-1][0],"PATCH")
            delete_calendar_event(created["id"],True,self.db)
            self.assertEqual(calls[-1][0],"DELETE")
            self.block.google_event_id=created["id"]
            self.db.commit()
            from fastapi import HTTPException
            with self.assertRaises(HTTPException) as blocked:
                update_calendar_event(created["id"],data,self.db)
            self.assertEqual(blocked.exception.status_code,409)

    def test_imported_google_block_never_writes_or_deletes_original(self):
        from fastapi import HTTPException
        self.db.add(GoogleIntegration(user_id=self.user.id, selected_calendar_id="owned@example.com", encrypted_token="mock"))
        self.block.google_event_id = "existing-event"
        self.block.sync_state = "imported"
        self.db.commit()
        with patch("stage4_api.google_call") as remote:
            with self.assertRaises(HTTPException):
                sync_block(self.block.id, Confirm(confirm=True), self.db)
            with self.assertRaises(HTTPException):
                edit_block(self.block.id, BlockIn(task_id=self.task.id,
                    start_at=datetime(2026,10,13,10,tzinfo=timezone.utc),
                    end_at=datetime(2026,10,13,11,tzinfo=timezone.utc)), self.db)
            removed = remove_synced_block(self.block.id, Confirm(confirm=True), self.db)
            self.assertFalse(removed["google_deleted"])
            remote.assert_not_called()

    def test_oauth_calendar_read_write_retry_edit_delete_disconnect(self):
        calls = []
        def fake_setting(name):
            return {"ANIRO_GOOGLE_CLIENT_ID":"client", "ANIRO_GOOGLE_CLIENT_SECRET":"secret", "ANIRO_GOOGLE_ALLOWED_EMAIL":"aniruththens@gmail.com"}.get(name, "")
        def fake_http(method,url,*,data=None,form=False,token=None,key=None):
            calls.append((method,url,data))
            if url.endswith("/token"): return {"access_token":"access", "refresh_token":"refresh", "expires_in":3600}
            if url.endswith("/userinfo"): return {"email":"aniruththens@gmail.com", "email_verified":True}
            if "/calendarList" in url: return {"items":[{"id":"aniruththens@gmail.com","summary":"Primary","primary":True}]}
            if method == "GET" and "/events?" in url: return {"items":[{"id":"external","summary":"Dentist","start":{"dateTime":"2026-10-13T08:00:00+05:30"},"end":{"dateTime":"2026-10-13T09:00:00+05:30"}}]}
            if method == "POST" and "/events" in url: return {"id":data["id"]}
            if method == "PUT" and "/events/" in url: return {"id":url.rsplit("/",1)[-1]}
            return {}
        with patch("stage4_api.setting", side_effect=fake_setting), patch("stage4_api.http_json", side_effect=fake_http):
            redirect = google_start(self.db)
            self.assertIn("code_challenge", redirect.headers["location"])
            self.assertIn("calendar.events.owned", redirect.headers["location"])
            state = self.db.get(GoogleIntegration, self.user.id).oauth_state
            response = google_callback(state=state,code="code",db=self.db)
            self.assertIn("connected", response.headers["location"])
            self.assertEqual(status(self.db)["account_email"], "aniruththens@gmail.com")
            self.assertEqual(len(calendars(self.db)["calendars"]), 1)
            choose_calendar(CalendarChoice(calendar_id="aniruththens@gmail.com"), self.db)
            self.assertEqual(events(WEEK,self.db)["events"][0]["title"],"Dentist")
            first = sync_block(self.block.id,Confirm(confirm=True),self.db)
            self.assertEqual(first["block"]["sync_state"], "synced")
            google_start(self.db)
            reconnect_state = self.db.get(GoogleIntegration, self.user.id).oauth_state
            google_callback(state=reconnect_state,code="new-code",db=self.db)
            self.assertEqual(status(self.db)["selected_calendar_id"], "aniruththens@gmail.com")
            edit_block(self.block.id,BlockIn(task_id=self.task.id,start_at=datetime(2026,10,13,10,tzinfo=timezone.utc),end_at=datetime(2026,10,13,11,tzinfo=timezone.utc)),self.db)
            self.assertEqual(self.block.sync_state, "pending_update")
            sync_block(self.block.id,Confirm(confirm=True),self.db)
            self.assertEqual(len([c for c in calls if c[0]=="POST" and "/events" in c[1]]), 1)
            self.assertEqual(len([c for c in calls if c[0]=="PUT" and "/events/" in c[1]]), 1)
            removed = remove_synced_block(self.block.id,Confirm(confirm=True),self.db)
            self.assertTrue(removed["google_deleted"])
            self.assertIsNotNone(self.block.archived_at)
            self.assertTrue(any(c[0]=="DELETE" and "/events/" in c[1] for c in calls))
            self.assertFalse(disconnect(Confirm(confirm=True),self.db)["connected"])
            self.assertIsNotNone(self.db.get(Task,self.task.id))

    def test_coach_privacy_opt_in_and_fallback(self):
        category = ExpenseCategory(user_id=self.user.id,name="Food")
        budget = BudgetMonth(user_id=self.user.id,year=2026,month=10,limit_minor=500000)
        self.db.add_all([category,budget]); self.db.flush()
        self.db.add(Expense(budget_month_id=budget.id,category_id=category.id,amount_minor=120000,spent_on="2026-10-13",description="Private purchase"))
        self.db.commit()
        minimal = coach_context(self.db,WEEK,"plan",False)
        self.assertNotIn("Riya",json.dumps(minimal))
        self.assertNotIn("Private purchase",json.dumps(minimal))
        self.assertNotIn("finance_lkr",minimal)
        approved = coach_context(self.db,WEEK,"money",True,True)
        self.assertEqual(approved["finance_lkr"]["remaining"],3800)
        self.assertIn("Call Riya",approved["selected_task_titles"])
        with patch("stage4_api.setting",return_value=""):
            answer = ask(CoachIn(question="How am I doing?",week=WEEK,use_gemini=True),self.db)
        self.assertEqual(answer["source"],"local")
        self.assertNotIn("Riya",answer["answer"])
        with patch("stage4_api.setting",side_effect=lambda name:"key" if name=="ANIRO_GEMINI_API_KEY" else ""), patch("stage4_api.http_json",side_effect=RemoteError(429,"quota")):
            answer = ask(CoachIn(question="How am I doing?",week=WEEK,use_gemini=True),self.db)
        self.assertEqual(answer["source"],"local")
        with patch("stage4_api.setting",side_effect=lambda name:"key" if name=="ANIRO_GEMINI_API_KEY" else ""), patch("stage4_api.http_json",side_effect=RemoteError(503,"offline")):
            self.assertEqual(ask(CoachIn(question="Help me plan",week=WEEK,use_gemini=True),self.db)["source"],"local")
        captured = {}
        def fake_gemini(method,url,*,data=None,form=False,token=None,key=None):
            captured["payload"] = data
            return {"candidates":[{"content":{"parts":[{"text":"Focus on **one realistic task** this week. Give it a short time block."}]}}],"usageMetadata":{"candidatesTokenCount":9}}
        with patch("stage4_api.setting",side_effect=lambda name:"key" if name=="ANIRO_GEMINI_API_KEY" else ""), patch("stage4_api.http_json",side_effect=fake_gemini):
            answer = ask(CoachIn(question="Help me plan",week=WEEK,use_gemini=True,
                                 history=[{"role":"user","text":"I have a study goal."},
                                          {"role":"assistant","text":"Start with one session."}]),self.db)
        self.assertEqual(answer["source"],"gemini")
        self.assertNotIn("**",answer["answer"])
        self.assertIn("\n\n",answer["answer"])
        self.assertIn("You are Aniru",captured["payload"]["systemInstruction"]["parts"][0]["text"])
        self.assertEqual([turn["role"] for turn in captured["payload"]["contents"]],["user","model","user"])
        self.assertEqual(captured["payload"]["generationConfig"]["maxOutputTokens"],1024)
        self.assertEqual(captured["payload"]["generationConfig"]["thinkingConfig"]["thinkingLevel"],"low")
        self.assertNotIn("Riya",json.dumps(captured["payload"]))
        self.assertNotIn("Private purchase",json.dumps(captured["payload"]))
        self.assertEqual(self.db.scalar(select(Expense).where(Expense.budget_month_id==budget.id)).description,"Private purchase")

if __name__ == "__main__": unittest.main()
