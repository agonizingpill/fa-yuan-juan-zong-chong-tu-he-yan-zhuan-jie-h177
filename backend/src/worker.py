import logging,time,json
from pathlib import Path
from .database import Session
from .models import Triage,Intake
from .triage_service import queue,apply
from .algorithm import classify_statements
logging.basicConfig(level=logging.INFO)
while True:
    Path('/tmp/worker-heartbeat').touch()
    try:
        item=queue.blpop('aid:triage',timeout=2)
        if not item:continue
        with Session() as db:
            run=db.get(Triage,int(item[1]))
            if not run or run.status!='queued':continue
            run.status='running';db.commit()
            try:
                case=db.get(Intake,run.intake_id)
                items,metrics=classify_statements(case.facts)
            except Exception as e:run.status='failed';run.error=str(e)[:200];db.commit();continue
            if apply(db,run.id,items,metrics):
                Path('/artifacts').mkdir(exist_ok=True);Path(f'/artifacts/triage-{run.id}.json').write_text(json.dumps(metrics,ensure_ascii=False))
    except Exception:logging.exception('triage loop');time.sleep(1)
