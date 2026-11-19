import os,redis
from fastapi import HTTPException
from sqlalchemy import select
from .models import Intake,Triage,Matter
from .common import get,reject,finish,editable
from .intake_service import authorized
from .algorithm import statement_digest
queue=redis.Redis.from_url(os.getenv('REDIS_URL','redis://redis:6379/0'),decode_responses=True)
ACTIVE=('pending','confirmed')
def current_matters(db,intake_id):
    case=get(db,Intake,intake_id)
    rows=list(db.scalars(select(Matter).where(Matter.intake_id==intake_id,Matter.status.in_(ACTIVE),Matter.last_version==case.facts_version).order_by(Matter.id)))
    return case,rows
def confirmed_topics(db,intake_id):
    _,rows=current_matters(db,intake_id)
    return {m.approved for m in rows if m.status=='confirmed' and m.approved}
def enqueue(db,data,user):
    case=editable(db,data.intake_id);reject(not authorized(db,case.id),'未取得授权，不能提交行政分流')
    reject(db.scalar(select(Triage).where(Triage.intake_id==case.id,Triage.facts_version==case.facts_version,Triage.status.in_(['queued','running']))) is not None,'当前版本仍在分流')
    row=Triage(intake_id=case.id,facts_version=case.facts_version);db.add(row);db.flush();result=finish(db,user,'提交主题分流',row)
    try:queue.rpush('aid:triage',row.id)
    except redis.RedisError:
        row.status='failed';row.error='任务队列暂不可用，恢复后可重新提交';db.commit()
        raise HTTPException(503,row.error)
    return result
def reconcile(db,case,run,items):
    # 按归一化原话对账：未变且仍独立的事项保留确认；新增挂出待核；被拆并的标记失效；同批原话去重
    active=list(db.scalars(select(Matter).where(Matter.intake_id==case.id,Matter.status.in_(ACTIVE))))
    by_digest={m.digest:m for m in active};seen=set()
    for statement,label,confidence in items:
        digest=statement_digest(statement)
        if digest in seen:continue
        seen.add(digest);row=by_digest.get(digest)
        if row:
            row.statement=statement;row.predicted=label;row.confidence=confidence;row.manual_required=confidence<.68
            row.last_version=case.facts_version;row.triage_id=run.id
        else:
            db.add(Matter(intake_id=case.id,triage_id=run.id,statement=statement,digest=digest,predicted=label,confidence=confidence,manual_required=confidence<.68,status='pending',first_version=case.facts_version,last_version=case.facts_version))
    for row in active:
        if row.digest not in seen:row.status='stale'
def apply(db,run_id,items,metrics):
    # 卷宗锁内复核事实版本：迟到的旧版本结果整批丢弃，不带回已拆并的事项
    run=get(db,Triage,run_id,True);case=get(db,Intake,run.intake_id,True)
    if case.facts_version!=run.facts_version:
        run.status='failed';run.error='事实已更正，迟到结果已丢弃，未改动事项';db.commit();return False
    reconcile(db,case,run,items);run.metrics=metrics;run.status='done';db.commit();return True
def review(db,id,data,user):
    initial=get(db,Matter,id);case=get(db,Intake,initial.intake_id,True);row=get(db,Matter,id,True)
    reject(case.status=='closed','卷宗已销案，不能修改')
    reject(row.status=='stale','事项已被拆分或合并，请按最新分流结果复核')
    reject(row.last_version!=case.facts_version,'事实已更正，请重新分流后再复核')
    reject(not authorized(db,case.id),'来访授权已撤回')
    row.approved=data.topic;row.review_note=data.note;row.status='confirmed';return finish(db,user,'事项人工复核',row)
