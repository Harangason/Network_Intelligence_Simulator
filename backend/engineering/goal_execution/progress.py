"""Transient progress; durable evidence is the execution journal after commit."""
from contextvars import ContextVar

sink = ContextVar('engineering_goal_progress', default=None)

def publish(goal):
    callback = sink.get()
    if callback is None or (goal.get('authorization') or {}).get('authorized_by') == 'technical-preview': return
    steps = goal['plan']['steps']
    current = next((i for i, step in enumerate(steps) if step['status'] == 'RUNNING'), len(steps) - 1)
    callback({'type': 'PROGRESS', 'status': 'RUNNING', 'text': steps[current]['action'],
        'workload': {'workload_id': goal['workload_id'], 'goal': goal['goal'], 'status': 'RUNNING',
            'completed': sum(s['status'] == 'SUCCEEDED' for s in steps), 'total': len(steps)},
        'progress': [{'label': s['action'], 'status': 'done' if s['status'] == 'SUCCEEDED' else 'active' if s['status'] == 'RUNNING' else 'pending'}
            for s in steps[max(0, current - 2):current + 4]], 'metadata': {'transient': True, 'canonical_batch': 'uncommitted'}})
