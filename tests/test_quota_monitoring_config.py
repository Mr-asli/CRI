from datetime import date
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from cri.db.models import Base, PlanRecord, UserAccountRecord, FeatureFlagRecord
from cri.quota import QuotaService
from cri.config import validate_environment
from cri.monitoring import Metrics, host_metrics

class AuditSink:
    def __init__(self): self.events=[]
    def add(self, event, actor, details): self.events.append((event,actor,details))

@pytest.fixture
def quota_db():
    engine=create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    sessions=sessionmaker(bind=engine, expire_on_commit=False)
    with sessions() as db:
        db.add(PlanRecord(id='limited',name='Limited',quotas={'task_create':1}))
        db.add(UserAccountRecord(id='ordinary',plan_id='limited'))
        db.add(FeatureFlagRecord(name='task_create',enabled=True))
        db.commit()
    yield sessions
    engine.dispose()

def test_owner_bypasses_quota_and_is_audited(quota_db):
    audit=AuditSink(); service=QuotaService(quota_db,audit,True,True)
    decision=service.check('ordinary','task_create',is_owner=True)
    assert decision.allowed and decision.reason=='owner_bypass'
    assert audit.events[-1][0]=='quota.decision'

def test_ordinary_user_is_denied_at_limit(quota_db):
    audit=AuditSink(); service=QuotaService(quota_db,audit,True,False)
    service.record('ordinary','task_create')
    decision=service.check('ordinary','task_create')
    assert not decision.allowed and decision.reason=='quota_exceeded'
    assert decision.used==1 and decision.limit==1

def test_disabled_quota_allows_every_user(quota_db):
    service=QuotaService(quota_db,AuditSink(),False,False)
    assert service.check('nonexistent','task_create').allowed

def test_null_quota_is_unlimited(quota_db):
    with quota_db() as db:
        plan=db.get(PlanRecord,'limited'); plan.quotas={'task_create':None}; db.commit()
    assert QuotaService(quota_db,AuditSink(),True,False).check('ordinary','task_create').allowed

def test_config_fails_closed_for_missing_secrets():
    with pytest.raises(RuntimeError): validate_environment({})

def test_config_rejects_invalid_boolean_and_threshold():
    base={'CRI_ADMIN_TOKEN':'a'*32,'CRI_APPROVAL_SECRET':'b'*32,'QUOTA_ENABLED':'sometimes'}
    with pytest.raises(RuntimeError): validate_environment(base)
    base['QUOTA_ENABLED']='true'; base['ALERT_CPU_PERCENT']='101'
    with pytest.raises(RuntimeError): validate_environment(base)

def test_config_accepts_valid_required_secrets():
    assert validate_environment({'CRI_ADMIN_TOKEN':'a'*32,'CRI_APPROVAL_SECRET':'b'*32})

def test_metrics_exposes_request_and_queue_series():
    metrics=Metrics(); metrics.observe('GET','/api/status',200,.025)
    output=metrics.render()
    assert 'cri_http_requests_total' in output and 'cri_queue_depth 0' in output
    assert 'path="/api/status"' in output

def test_host_metrics_has_cpu_memory_and_disk_fields():
    result=host_metrics()
    assert {'cpu_percent','memory_percent','disk_percent'} <= result.keys()
    assert result['disk_percent'] is None or 0 <= result['disk_percent'] <= 100

def test_plan_assignment_changes_effective_quota(quota_db):
    with quota_db() as db:
        db.add(PlanRecord(id='unlimited', name='Unlimited', quotas={'task_create': None}))
        user=db.get(UserAccountRecord,'ordinary'); user.plan_id='unlimited'; db.commit()
    assert QuotaService(quota_db,AuditSink(),True,False).check('ordinary','task_create').allowed

def test_disabled_feature_flag_denies_consumption(quota_db):
    with quota_db() as db:
        db.get(FeatureFlagRecord,'task_create').enabled=False; db.commit()
    decision=QuotaService(quota_db,AuditSink(),True,False).check('ordinary','task_create')
    assert not decision.allowed and decision.reason=='feature_disabled'

def test_alerting_without_configured_channel_is_safe(monkeypatch):
    for name in ('TELEGRAM_BOT_TOKEN','TELEGRAM_CHAT_ID','SMTP_HOST','ALERT_EMAIL_TO','ALERT_EMAIL_FROM'):
        monkeypatch.delenv(name,raising=False)
    from cri.alerts import notify
    result=notify('test-no-channel','test')
    assert result['sent'] is False and result['channels']==[]
