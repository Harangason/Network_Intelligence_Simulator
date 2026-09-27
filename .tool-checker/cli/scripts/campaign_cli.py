"""Commands integrated into tool_check.py."""
from campaign_state import Campaign
def add_parser(sub):
    p=sub.add_parser("campaign")
    p.add_argument("action", choices=["start","run","close-run","block","repair","repair-exec",
                                     "delivery-run","repair-plan","repair-record","repair-complete","status","report","stopp"])
    p.add_argument("--id",required=True)
    p.add_argument("--repair-id")
    p.add_argument("--build")
    p.add_argument("--test")
    p.add_argument("--reason")
    p.add_argument("--evidence")
    p.add_argument("--file")
    p.add_argument("--post-run3",action="store_true")
def dispatch(tc,a):
    c=Campaign(tc,a.id)
    if a.action=="start":
        if not a.task: raise ValueError("--task required for campaign start")
        return c.create(a.task)
    if a.action=="run": return c.run(a.build)
    if a.action=="close-run": return c.close_run()
    if a.action=="block": return c.block(a.test,a.reason,a.evidence)
    if a.action=="repair": return c.repair(a.post_run3)
    if a.action=="repair-exec": return c.execute_repair(a.file)
    if a.action=="repair-plan": return c.plan_repair(a.file)
    if a.action=="delivery-run": return c.deliver_repair(a.repair_id)
    if a.action=="repair-record": return c.record_repair(a.file)
    if a.action=="repair-complete": return c.complete_repair()
    if a.action=="stopp": return c.stop()
    return c.report()
