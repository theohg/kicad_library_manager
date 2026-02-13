set pagination off
set breakpoint pending on
set print thread-events off
set debuginfod enabled off

set confirm off

set logging file /tmp/kicad_library_manager_timer.log
set logging overwrite on
set logging on

handle SIGSEGV stop print nopass

delete breakpoints

python
import glob
import gdb

def _try_source(patterns):
    for pat in patterns:
        paths = glob.glob(pat, recursive=True)
        if not paths:
            continue
        # Prefer the non-debug "python3.X-gdb.py" if present.
        paths = sorted(paths)
        try:
            gdb.execute("source " + paths[0])
            gdb.write(f"[gdb] sourced: {paths[0]}\n")
            return True
        except gdb.error as e:
            gdb.write(f"[gdb] failed to source {paths[0]}: {e}\n")
    return False

_try_source([
    "/usr/share/gdb/auto-load/usr/bin/python3.*-gdb.py",
    "/usr/share/gdb/auto-load/usr/bin/python3.*dbg-gdb.py",
    "/usr/share/gdb/auto-load/usr/lib/**/libpython3.*-gdb.py",
])
end

break sipwxTimer::sipwxTimer(wxEvtHandler*, int)
break sipwxTimer::Start
break sipwxTimer::Notify
break wxTimerImpl::SendEvent

commands 1
silent
printf "\n=== sipwxTimer ctor(owner,id) ===\n"
printf "timer=%p owner=%p id=%ld\n", $rdi, $rsi, $rdx
python
import gdb
try:
    gdb.execute("py-bt")
except gdb.error as e:
    gdb.write(f"[gdb] py-bt unavailable: {e}\n")
end
bt 15
continue
end

commands 2
silent
printf "\n=== sipwxTimer::Start ===\n"
printf "timer=%p interval_ms=%ld oneShot=%ld\n", $rdi, $rsi, $rdx
python
import gdb
try:
    gdb.execute("py-bt")
except gdb.error as e:
    gdb.write(f"[gdb] py-bt unavailable: {e}\n")
end
bt 15
continue
end

commands 3
silent
printf "\n=== sipwxTimer::Notify ===\n"
printf "timer=%p\n", $rdi
python
import gdb
try:
    gdb.execute("py-bt")
except gdb.error as e:
    gdb.write(f"[gdb] py-bt unavailable: {e}\n")
end
bt 20
continue
end

commands 4
silent
printf "\n=== wxTimerImpl::SendEvent ===\n"
printf "impl=%p\n", $rdi
bt 20
continue
end

continue

