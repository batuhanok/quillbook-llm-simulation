"""Local run console. Uses the same CLI runners and saved files as the terminal."""
import argparse
import hashlib
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import secrets
import subprocess
import sys
import threading
import time
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent
JOBS = {}
LOCK = threading.RLock()
TOKEN = secrets.token_urlsafe(32)
CACHE = {}


def read_json(path, fallback=None):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return fallback


def rows(path):
    result = []
    try:
        with path.open() as handle:
            for line in handle:
                try:
                    result.append(json.loads(line))
                except ValueError:
                    pass  # A writer may not have finished the last line yet.
    except OSError:
        pass
    return result


def plan_signature(decisions, selectors=None):
    return hashlib.sha256(json.dumps({'decisions': decisions, 'selectors': selectors or {}},
                                     sort_keys=True).encode()).hexdigest()


def weekly_outcomes(manifest, weekly):
    """Display observed weekly outcomes without borrowing a future final metric."""
    profiles = {p['id']: p for p in manifest['profiles']}
    business_total = sum(p.get('represented_businesses', 0) for p in profiles.values())
    batches = {}
    for row in weekly:
        if row.get('persona') in profiles:
            batches.setdefault(row['week'], {})[row['persona']] = row
    complete = {week: batch for week, batch in batches.items() if len(batch) == len(profiles)}
    departed = {0: 0.0}
    for week, batch in complete.items():
        departed[week] = sum(profiles[pid].get('represented_businesses', 0) *
            sum(c['fraction'] for c in row.get('cohort_choices', []) if c['status'] == 'moved to a rival')
            for pid, row in batch.items())
    result = []
    for week, batch in sorted(complete.items()):
        due = renewed = 0
        known = True
        for pid, row in batch.items():
            p = profiles[pid]
            count = p.get('renewal_counts', {}).get(str(week), 0) if p.get('represented_businesses', 0) else 0
            due += count
            if count:
                fraction = row.get('renewal_fraction')
                if fraction is None:
                    known = False
                else:
                    renewed += count * fraction
        opening = business_total - departed.get(week - 4, 0)
        churn = (100 * (departed[week] - departed[week - 4]) / opening
                 if week >= 4 and week - 4 in departed and opening > 0 else None)
        result.append({'week': week, 'renewal_due': due,
                       'renewal_pct': 100 * renewed / due if due and known else None,
                       'churn_4week_pct': churn})
    return result


def safe_path(value, base=None):
    path = (ROOT / value).resolve()
    if not path.is_relative_to((base or ROOT).resolve()):
        raise ValueError('Path must stay inside the selected project directory.')
    return path


def run_path(value):
    path = safe_path(value, ROOT / 'output')
    if not (path / 'manifest.json').is_file():
        raise ValueError('Choose an existing runner output.')
    return path


def relative(path):
    return str(path.relative_to(ROOT))


def job_summary(job):
    code = job['process'].poll()
    return {k: v for k, v in job.items() if k not in ('process', 'handle')} | {
        'state': 'running' if code is None else ('complete' if code == 0 else 'stopped' if code < 0 else 'failed'),
        'exit_code': code,
    }


def summarize(folder):
    watched = ['manifest.json', 'weekly.jsonl', 'calls.jsonl', 'completion.json', 'metrics.json', 'failures.json', 'REJECTED.md']
    signature = tuple((name, (folder / name).stat().st_mtime_ns, (folder / name).stat().st_size)
                      for name in watched if (folder / name).exists())
    key = str(folder)
    if key in CACHE and CACHE[key][0] == signature:
        return CACHE[key][1].copy()
    m = read_json(folder / 'manifest.json', {})
    if not m.get('profiles') or 'end_week' not in m:
        return None
    weekly = rows(folder / 'weekly.jsonl')
    counts = {}
    for row in weekly:
        counts[row['week']] = counts.get(row['week'], 0) + 1
    n = len(m['profiles'])
    week = max((w for w, count in counts.items() if count == n), default=0)
    completion = read_json(folder / 'completion.json', {})
    calls = 0
    try:
        with (folder / 'calls.jsonl').open() as handle:
            calls = sum(1 for line in handle if line.strip())
    except OSError:
        pass
    modified = max((folder / name).stat().st_mtime for name in watched if (folder / name).exists())
    result = {'path': relative(folder), 'seed': m.get('seed'), 'kind': m.get('type'),
              'version': m['profiles'][0].get('profile_version', 'v1'), 'profiles': n,
              'model_version': m.get('model_version', 'earlier model'),
              'weeks': m['end_week'], 'week': week, 'weekly_rows': len(weekly), 'calls': calls,
              'complete': bool(completion.get('complete')), 'development': m.get('development', True),
              'rejected': (folder / 'REJECTED.md').exists(), 'event_count': len(m.get('events', [])),
              'decisions': len(m.get('decisions', [])), 'modified': modified,
              'plan_signature': plan_signature(m.get('decisions', []), m.get('selectors')),
              'metrics': read_json(folder / 'metrics.json', {}),
              'has_failure_record': (folder / 'failures.json').exists() and not completion.get('complete')}
    CACHE[key] = (signature, result)
    return result.copy()


def state():
    runs = []
    for manifest in (ROOT / 'output').glob('**/manifest.json'):
        if 'archive' in manifest.parts or 'engine_cache' in manifest.parts:
            continue
        result = summarize(manifest.parent)
        if result:
            runs.append(result)
    runs.sort(key=lambda r: r['modified'], reverse=True)
    events = read_json(ROOT / 'data/official_events.json', {})
    locked = read_json(ROOT / 'decisions/locked_plan.json', {})
    plans = [relative(p) for p in sorted((ROOT / 'decisions').glob('*.json'))]
    if (ROOT / 'data/candidate_plan.json').exists():
        plans.append('data/candidate_plan.json')
    with LOCK:
        jobs = [job_summary(j) for j in JOBS.values()]
    return {'runs': runs, 'jobs': jobs, 'personas': rows(ROOT / 'data/personas.jsonl'),
            'events': events.get('events', []) if isinstance(events, dict) else events,
            'locked_plan_signature': plan_signature(locked.get('run_decisions', []), locked.get('selectors')),
            'plans': plans, 'token': TOKEN, 'now': time.time()}


def integer(value, low, high):
    value = int(value)
    if not low <= value <= high:
        raise ValueError(f'Value must be between {low} and {high}.')
    return value


def command_for(body):
    action = body.get('action', 'run')
    if action == 'audit':
        folder = run_path(body['run'])
        if not read_json(folder / 'completion.json', {}).get('complete'):
            raise ValueError('Audit needs a completed run.')
        return [sys.executable, str(ROOT / 'audit_engine.py'), '--run', relative(folder)], relative(folder)
    if action == 'resume':
        folder = run_path(body['run'])
        if read_json(folder / 'completion.json', {}).get('complete'):
            raise ValueError('This run is already complete.')
        # CLI checks exact manifest equality; never reinterpret an old run with new inputs.
        m = read_json(folder / 'manifest.json')
        from engine import load_inputs
        profiles, links, events, _, _ = load_inputs(ROOT / 'data/official_events.json')
        import hashlib
        if (profiles != m['profiles'] or links != m['links'] or events != m['events']
                or any(hashlib.sha256((ROOT / f).read_bytes()).hexdigest() != h for f, h in m['sources'].items())):
            raise ValueError('Inputs/code changed since this run. Start a fresh output instead.')
        if time.time() - max((p.stat().st_mtime for p in folder.iterdir() if p.is_file()), default=0) < 90:
            raise ValueError('Recent writes: this may still be running in a terminal. Wait or use its terminal session.')
        if not m.get('development', True):
            raise ValueError('Resume official suites through the original terminal suite command.')
        saved = folder / 'dashboard_resume_plan.json'
        saved.write_text(json.dumps({'run_decisions': m['decisions'], 'selectors': m['selectors']}))
        cmd = [sys.executable, str(ROOT / 'engine.py'), 'run', '--plan', relative(saved), '--output', relative(folder),
               '--events', 'data/official_events.json', '--weeks', str(m['end_week']), '--seed', str(m['seed']),
               '--model', m['model'], '--concurrency', str(integer(body.get('concurrency', 24), 1, 24))]
        # Retain all custom assumptions and interaction settings from the saved run.
        assumptions = folder / 'dashboard_resume_assumptions.json'
        assumptions.write_text(json.dumps(m['assumptions']))
        cmd += ['--assumptions', relative(assumptions)]
        if m.get('probes'):
            cmd.append('--probes')
        if m.get('interactions_off'):
            cmd.append('--interactions-off')
        if m.get('conversation_version') in ('reasoned-messages-v1', 'reasoned-calendar-v2'):
            cmd.append('--reasoned-messages')
        elif m.get('conversation_version') == 'calendar-only-v2':
            cmd.append('--no-reasoned-messages')
        return cmd, relative(folder)
    if action not in ('run', 'suite'):
        raise ValueError('Unknown action.')
    stamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S') + '_' + secrets.token_hex(3)
    output = 'output/ui_runs/' + stamp
    cmd = [sys.executable, str(ROOT / 'engine.py'), action, '--output', output,
           '--events', 'data/official_events.json', '--concurrency', str(integer(body.get('concurrency', 24), 1, 24))]
    plan = body.get('plan', '')
    if plan:
        if plan not in state()['plans']:
            raise ValueError('Choose a listed plan file.')
        if action == 'suite' and not plan.startswith('decisions/'):
            raise ValueError('Select the actual downloaded dashboard plan in decisions/.')
        cmd += ['--locked-plan' if action == 'suite' else '--plan', plan]
    elif action == 'suite':
        raise ValueError('Final suite requires the actual locked dashboard plan.')
    if action == 'suite':
        from engine import load_inputs
        from actions import validate_plan
        profiles, _, _, decisions, selectors = load_inputs(ROOT / 'data/official_events.json', ROOT / plan)
        validate_plan(decisions, profiles, selectors, require_two=True)
        cmd += ['--parallel-runs', str(integer(body.get('parallel_runs', 3), 1, 5))]
    else:
        cmd += ['--weeks', str(integer(body.get('weeks', 10), 1, 10)), '--seed', str(integer(body.get('seed', 42), 0, 2147483647))]
        if body.get('probes', True):
            cmd.append('--probes')
    return cmd, output


def launch(body):
    with LOCK:
        if sum(j['process'].poll() is None for j in JOBS.values()) >= 3:
            raise ValueError('Three dashboard jobs are already active. Monitor them before launching more.')
        cmd, output = command_for(body)
        if any(j['output'] == output and j['process'].poll() is None for j in JOBS.values()):
            raise ValueError('This output already has an active dashboard job.')
        job_id = secrets.token_hex(6)
        folder = ROOT / 'output/dashboard_jobs'
        folder.mkdir(parents=True, exist_ok=True)
        log = folder / (job_id + '.log')
        handle = log.open('w')
        try:
            proc = subprocess.Popen(cmd, cwd=ROOT, stdout=handle, stderr=subprocess.STDOUT, start_new_session=True)
        except Exception:
            handle.close()
            raise
        job = {'id': job_id, 'output': output, 'command': cmd, 'started': time.time(),
               'log': relative(log), 'process': proc, 'handle': handle}
        JOBS[job_id] = job
        meta = job_summary(job)
        (folder / (job_id + '.json')).write_text(json.dumps(meta, indent=2))
        return meta


class Handler(BaseHTTPRequestHandler):
    def send(self, value, status=200):
        data = json.dumps(value, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def valid_host(self):
        return self.headers.get('Host') in (f'127.0.0.1:{self.server.server_port}', f'localhost:{self.server.server_port}')

    def do_GET(self):
        if not self.valid_host():
            return self.send({'error': 'Local requests only.'}, 403)
        url = urlparse(self.path)
        args = parse_qs(url.query)
        try:
            if url.path == '/':
                page = (ROOT / 'dashboard.html').read_bytes()
                self.send_response(200)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self.send_header('Content-Length', str(len(page)))
                self.end_headers()
                return self.wfile.write(page)
            if url.path == '/api/state':
                return self.send(state())
            if url.path == '/api/run':
                folder = run_path(args['path'][0])
                manifest = read_json(folder / 'manifest.json')
                weekly = rows(folder / 'weekly.jsonl')
                return self.send({'manifest': manifest, 'weekly': weekly,
                                  'weekly_metrics': weekly_outcomes(manifest, weekly),
                                  'audit': read_json(folder / 'audit.json'), 'metrics': read_json(folder / 'metrics.json')})
            if url.path == '/api/call':
                folder = run_path(args['path'][0])
                with (folder / 'calls.jsonl').open() as handle:
                    for line in handle:
                        try:
                            row = json.loads(line)
                        except ValueError:
                            continue
                        if row.get('id') == args['id'][0]:
                            return self.send(row)
                raise ValueError('Call not found.')
            if url.path == '/api/log':
                with LOCK:
                    job = JOBS.get(args['id'][0])
                if not job:
                    raise ValueError('Unknown dashboard job.')
                with (ROOT / job['log']).open('rb') as handle:
                    handle.seek(max(0, (ROOT / job['log']).stat().st_size - 16000))
                    return self.send({'text': handle.read().decode(errors='replace')})
            self.send({'error': 'Not found.'}, 404)
        except (ValueError, KeyError, OSError) as error:
            self.send({'error': str(error)}, 400)

    def do_POST(self):
        origin = self.headers.get('Origin')
        if (not self.valid_host() or self.headers.get('X-Console-Token') != TOKEN
                or origin not in (None, f'http://{self.headers.get("Host")}')):
            return self.send({'error': 'Local console session required.'}, 403)
        try:
            size = int(self.headers.get('Content-Length', '0'))
            if not 0 < size <= 16000:
                raise ValueError('Invalid request size.')
            body = json.loads(self.rfile.read(size))
            if self.path == '/api/start':
                return self.send(launch(body))
            if self.path == '/api/stop':
                with LOCK:
                    job = JOBS.get(body.get('id'))
                    if not job or job['process'].poll() is not None:
                        raise ValueError('Only an active dashboard-owned job can be stopped.')
                    import os, signal
                    os.killpg(job['process'].pid, signal.SIGTERM)
                return self.send({'stopped': True, 'note': 'Saved calls are retained for resume.'})
            self.send({'error': 'Not found.'}, 404)
        except (ValueError, KeyError, OSError) as error:
            self.send({'error': str(error)}, 400)

    def log_message(self, *_):
        pass


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8765)
    args = parser.parse_args()
    server = ThreadingHTTPServer(('127.0.0.1', args.port), Handler)
    print(f'Quillbook console: http://127.0.0.1:{server.server_port}', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('Console stopped. Simulation jobs retain their own processes and output files.')
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
