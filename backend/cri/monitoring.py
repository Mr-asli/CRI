"""Low-dependency host and dependency health snapshots plus Prometheus metrics."""
from __future__ import annotations
import os, shutil, time
from collections import defaultdict
from threading import Lock

class Metrics:
    def __init__(self): self.lock=Lock(); self.requests=defaultdict(int); self.latency=defaultdict(float); self.queue_depth=0
    def observe(self, method, path, status, elapsed):
        key=(method,path,status)
        with self.lock: self.requests[key]+=1; self.latency[key]+=elapsed
    def render(self):
        lines=['# TYPE cri_http_requests_total counter','# TYPE cri_http_request_duration_seconds_sum counter','# TYPE cri_queue_depth gauge']
        with self.lock:
            for (method,path,status),count in sorted(self.requests.items()):
                labels=f'method="{method}",path="{path}",status="{status}"'
                lines += [f'cri_http_requests_total{{{labels}}} {count}', f'cri_http_request_duration_seconds_sum{{{labels}}} {self.latency[(method,path,status)]:.6f}']
            lines.append(f'cri_queue_depth {self.queue_depth}')
        return '\n'.join(lines)+'\n'

def _mem_percent():
    try:
        values={line.split(':',1)[0]:int(line.split()[1]) for line in open('/proc/meminfo') if ':' in line}
        return round(100*(1-values['MemAvailable']/values['MemTotal']),2)
    except (OSError,KeyError,ValueError,IndexError): return None

_cpu_previous = None
def _cpu_percent():
    global _cpu_previous
    try:
        fields=open('/proc/stat', encoding='ascii').readline().split()[1:]
        values=[int(item) for item in fields]
        idle=values[3]+(values[4] if len(values)>4 else 0); total=sum(values)
        previous=_cpu_previous; _cpu_previous=(total,idle)
        if previous is None: return None
        total_delta=total-previous[0]; idle_delta=idle-previous[1]
        return round(100*(total_delta-idle_delta)/total_delta,2) if total_delta>0 else 0.0
    except (OSError,ValueError,IndexError): return None

def host_metrics():
    usage=shutil.disk_usage('/')
    cpu=_cpu_percent()
    return {'cpu_percent':cpu,'memory_percent':_mem_percent(),'disk_percent':round(100*usage.used/usage.total,2)}
