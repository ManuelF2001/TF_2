# What the software does – every program and script of Lab 2

This document explains the code: what each program does, message by
message, and which lines implement which design decision. For *why* the
designs behave as they do, see `theory.md` and the part documents.

Contents:

1. The runtime in five lines (Maelstrom + `ms.py`)
2. The skeleton shared by all programs
3. `q1.py` – Part 1, values only
4. `q2.py` / `q2local.py` – Part 2, versions
5. `q3.py` – Part 3, tie-breaking (+ the `SLOW_PUT` test hook)
6. `q4a.py` – Part 4, cas without lock
7. `q4b.py` – Part 4, cas and write under a quorum lock
8. `qx.py` – Going further, read with write-back
9. Message types and costs, all programs side by side
10. Scripts and kit tools (`scenarios.sh`, `run_all.sh`, `cite_runs.sh`, `run.sh`, `summary.py`, `timeline.py`)
11. Analysis tools (`tools/anomaly.py`, `clockcheck.py`, `after.py`, `table.py`)

## 1. The runtime in five lines

Maelstrom (a Jepsen-based workbench, see Lab 1 `docs/explained/02-maelstrom.md`)
starts N copies of our program as processes `n0 … n(N-1)`, connects them
through a simulated network (latency, partitions), and runs 2·N clients
(`c…`) that send random `read`/`write`/`cas` requests on a few integer keys,
each client always to the same server. Messages are JSON lines on
stdin/stdout. At the end, Maelstrom (Knossos) checks whether the history of
client operations is **linearizable**, per key.

`ms.py` (course kit, unmodified copy in `code/`; explained line by line in
Lab 1 `docs/explained/03-ms-py.md`) gives us:

| helper | what it does |
|---|---|
| `run(handle)` | main loop: `handle(msg)` for every incoming message, **on one thread** |
| `reply(msg, **body)` | answer a request (`in_reply_to` = its `msg_id`) |
| `send(src, dest, **body)` | fire-and-forget message |
| `rpc(src, dest, callback, **body)` | send a request; `callback(reply)` runs when the reply arrives |
| `set_timeout(s, fn, *args)` | run `fn` later, on the same thread; returns a cancellable timer |
| `trace(event, **fields)` | structured event in the node log; `timeline.py` merges them |
| `MS_CRASH="n1@5"` | crash injection: n1 stops receiving, sending and executing 5 s after start |

The single thread is the most important fact: **a handler must never wait**
for a reply. Every quorum operation is therefore written as a chain of
callbacks: send to all, count answers in a callback, continue when the
Q-th answer arrives.

## 2. The skeleton shared by all programs

Every program has the same four pieces.

**Configuration** from the environment, so that one file covers every
configuration (`QR=1 QW=3 ./run.sh lin-kv q.py`):

```python
QR = int(environ.get('QR', 2))
QW = int(environ.get('QW', 2))
```

**`handle(msg)`** dispatches on `msg.body.type`. A server plays two roles:

- **coordinator** for client requests (`read`, `write`, `cas`): it runs the
  quorum protocol and replies to the client;
- **replica** for requests from coordinators (`get`, `put`, and in q4b
  `lock`/`unlock`): it reads or updates its own copy and replies.

**`serve(request, src)`** is the replica side: what a server does when a
coordinator asks it something. It returns the reply body. The coordinator
also calls it directly for **its own copy**: this is how "send to all
servers, *itself included*" is implemented without sending a message to
itself. Consequence: the coordinator's own answer is always the **first**
answer (it is computed synchronously, while remote answers can only be
processed after the handler returns).

**`quorum(q, on_quorum, **request)`** is the heart of every program:

```python
def quorum(q, on_quorum, **request):
    answers = []

    def collect(node, answer):
        answers.append((node, answer))
        if len(answers) == q:          # exactly once: the q-th answer
            on_quorum(answers)

    for dest in node_ids:
        if dest != node_id:
            rpc(node_id, dest, lambda r: collect(r.src, r.body), **request)
    collect(node_id, serve(sn(**request), node_id))
```

1. It sends the request to **all** other servers with `rpc`, registering
   `collect` as the callback.
2. It serves the request locally and collects that answer first.
3. Each answer is appended; when the **q-th** arrives, `on_quorum(answers)`
   runs, with the list in arrival order. Answers after the q-th are
   appended but ignored (`len == q` is true only once).
4. If fewer than q servers ever answer (crash, partition), `on_quorum`
   never runs and the client is **never answered**: Maelstrom times the
   client out after 1 s. (Design choice: no timeouts or retries in Parts
   1–3, `decisions.md` D3.)

Note that a quorum operation always sends **N − 1 messages and receives up
to N − 1 replies**, whatever q is: q only decides when we stop waiting.

## 3. `q1.py` – Part 1, values only

State: `store = {key: value}`.

**write(k, v)** at coordinator C:
`quorum(QW, done, type='put', key=k, value=v)`. Every replica that receives
`put` overwrites its copy (`store[k] = v`) and answers `put_ok`. After QW
acknowledgements (C's own included), C replies `write_ok`.

**read(k)**: `quorum(QR, done, type='get', key=k)`; replicas answer
`get_ok` with `value = store.get(k)` (`null` if missing). Our rule for
disagreeing answers (Part 1 question 1, `decisions.md` D2):

```python
values = [a.value for _, a in answers if a.value is not None]
reply(... value=values[0])          # first non-missing answer
```

i.e. a value beats "missing" (keys are never deleted), then the first
answer received, which is the coordinator's own copy when it has the key.
If all answers say missing: error 20.

**cas**: error 10.

Traces: `put` (at each replica, with the coordinator), `write` and
`write_done` (with the acknowledging servers), `read` (all answers and the
value returned).

What can go wrong, in code terms: `store[k] = v` in `serve` overwrites
**unconditionally**, so two concurrent puts can be applied in opposite
orders at two servers, which then keep different values forever; and
`values[0]` may be a stale own copy while another answer is newer.

## 4. `q2.py` / `q2local.py` – Part 2, versions

State: `store = {key: [version, value]}`, missing key = version 0.

**Replica `put`** now stores only if newer:

```python
stored = request.version > version
if stored:
    store[request.key] = [request.version, request.value]
```

and always answers `put_ok` (an old put is acknowledged: it was "applied"
in the sense that the replica has something at least as new). The trace
records `had` (what the replica had) and `stored` (true/false).

**Replica `get`** returns `version` and `value`.

**write (q2.py), two phases**:

1. `quorum(QR, versions_known, type='get')`: learn the highest version
   among QR servers;
2. `version = newest(answers).version + 1` (traced as `version`, with every
   version seen), then `quorum(QW, written, type='put', version=…)`, then
   `write_ok`.

**write (q2local.py)**, the alternative: no phase 1;
`version = own version + 1`, straight to the put phase.

**read**: `newest(answers)` = highest version; `max()` keeps the first of
equal versions, i.e. the earliest answer. Error 20 if its value is `null`.

The hole left on purpose: two concurrent writes can both compute the same
version v + 1 (both phase-1 quorums saw v). Replicas keep whichever arrives
first (`>` is strict), so different replicas keep different values for
the same version.

## 5. `q3.py` – Part 3, tie-breaking

The version becomes a **tag** `[number, writer]`, writer = client id of the
write (`msg.src`, e.g. `"c6"`); missing key = `[0, '']`. One function
decides everything:

```python
def newer(tag, other):
    return tuple(tag) > tuple(other)     # number first, then writer id
```

Replicas store a put iff `newer(put.tag, stored.tag)`; readers return the
answer with the `newer` tag; writers create `[highest number + 1, client]`.
Since all of them apply the same total order, all replicas converge on the
same value for a key once they have received the same puts, regardless of
arrival order. No extra message is needed.

(JSON has no tuples: tags travel as lists and are converted to tuples to be
compared. String comparison of client ids is arbitrary, `"c10" < "c9"`,
but it is the same everywhere, and that is all that matters.)

**Test hook `SLOW_PUT`**, not part of the protocol: with
`SLOW_PUT="n0=0.5"`, every `put` that n0 sends to another server is
scheduled with `set_timeout(0.5, send, dest)` instead of being sent now,
and traced as `slow_put`. n0's own copy is updated at once. This simulates
a slow link from n0 and reproduces the "write that has reached only the
server that received it" of Part 3, question 4 (the kit's
`inversion-run.tar.bz2` was not available to us at first, `decisions.md`
D8; once it was, it confirmed that the teachers' `p3_slow.py` holds n0's
puts in the same way, `03-concurrent-writers.md` §5.1).

## 6. `q4a.py` – Part 4, cas without lock

q3.py without the hook, plus `cas(k, from, to)`:

1. `quorum(QR, read_done, type='get')`; take the newest answer (traced as
   `cas_read`, with all answers, `expected` and `to`);
2. missing → error 20; value ≠ `from` → error 22 (with what was found);
3. otherwise `put_phase(…, tag=[number + 1, client], value=to, 'cas_ok')`,
   the same second phase as a write (`write` now also uses `put_phase`).

`getattr(msg.body, 'from')` because `from` is a Python keyword.

Nothing prevents two cas from executing steps 1–3 interleaved: both read
`from`, both write, both answer `cas_ok`.

## 7. `q4b.py` – Part 4, cas and write under a quorum lock

New replica state: `locks = {key: owner}`. Owners are unique strings
`"<coordinator>:<attempt number>"`, a new one for each attempt.

**Replica side** (`serve`):

| request | effect | answer |
|---|---|---|
| `lock{key, owner}` | if the key is free or already held by `owner`: `locks[key] = owner` (trace `lock`) | `lock_ok` |
| | else (held by someone else) (trace `lock_busy`) | `lock_busy{holder}` |
| `unlock{key, owner}` | if held by `owner`: delete (trace `unlock`); otherwise nothing | none (fire and forget, `send`) |

**Coordinator side**: `write` and `cas` are wrapped in
`with_lock(msg, action)`; `read` is not.

```
attempt():
    owner = "<me>:<n>", phase = 'locking'
    timer = set_timeout(LOCK_RETRY = 0.25 s, give_up, 'timeout')
    send lock{key, owner} to all (own answer first)
    on each answer:
        phase 'done'    and lock_ok  -> unlock that server at once (late grant)
        phase 'locked'               -> ignore (released at the end anyway)
        lock_ok  -> granted += node;  if len(granted) == QL: phase = 'locked',
                                         cancel timer, action(msg, release)
        lock_busy -> refused += node; if len(refused) > N - QL: give_up('busy')
give_up(reason):          (if still 'locking')
    release()  = phase 'done', unlock{key, owner} to ALL servers
    wait random(0, 0.25 s) and attempt() again,
    unless that would pass LOCK_GIVE_UP = 0.8 s since the request: error 11
```

- `QL` defaults to `N // 2 + 1` (majority), overridable with `QL=…`.
- `len(refused) > N − QL` means "even if every remaining server grants,
  we cannot reach QL": fail fast instead of waiting for the timer.
- The **random backoff** makes it unlikely that two coordinators that
  split the quorum collide again on the retry (livelock).
- **Error 11** is correct here: when we give up, nothing has been written
  (the action starts only after the lock is held), so the operation
  "surely did not happen".
- **0.8 s** is chosen below the client timeout (1 s), so that the client
  gets the definite error 11 rather than a timeout.
- `release()` sends `unlock` to **all** servers, not only those that
  granted: a grant may still be on its way; unlocking where we are not the
  owner is a no-op. If a grant arrives after release (phase `done`), the
  coordinator unlocks that server again: this covers an `unlock` that
  overtook its `lock` in the network.

**The actions** run while the lock is held and call `release()` when they
end: `write` = phase 1 (tags) + `put_phase` → release → `write_ok`; `cas`
= read → compare → (release + error 20/22) or (`put_phase` → release →
`cas_ok`).

What is *not* there (on purpose): if the coordinator crashes, or the
network drops its `unlock` messages, or its put phase never gets QW
acknowledgements, the lock is **never released**: the key is blocked for
all writes and cas until the end of the run (`04-compare-and-set.md`).

## 8. `qx.py` – Going further, read with write-back

q3.py (cas still error 10) with a new read:

1. phase 1 as before: `best = newest(QR answers)`;
2. `have` = servers among the answers that already have `best.tag`;
   if `len(have) >= QW` (or the key is missing), answer at once: the value
   is already at a write quorum;
3. otherwise **write-back**: `quorum(QW, …, type='put', tag=best.tag,
   value=best.value)`, i.e. a normal put of the value read, with its
   original tag; answer the client only after QW acknowledgements
   (trace `write_back_done`).

The `read` trace has `write_back=true/false`. The replica side is
unchanged: a put with a tag that the replica already has or exceeds is
acknowledged and ignored.

## 9. Message types and costs, side by side

| program | write | read | cas |
|---|---|---|---|
| q1 | put (1 round) | get (1 round) | error 10 |
| q2, q3 | get + put (2 rounds) | get (1) | error 10 |
| q2local | put (1 round) | get (1) | error 10 |
| q4a | get + put (2) | get (1) | get + put (2) |
| q4b | lock + get + put + unlock (3 rounds + 1 one-way) | get (1) | lock + get (+ put) + unlock |
| qx | get + put (2) | get (+ put if needed) (1–2) | error 10 |

Every round sends N − 1 messages and gets up to N − 1 replies, so a round
costs ≈ 2(N − 1) messages between servers. With N = 3: read ≈ 4,
two-phase write ≈ 8. `summary.py`'s `msgs/op` divides by **all** operations,
including cas answered with error 10 without any message, so it is lower
than these numbers.

## 10. Scripts and kit tools

**`../env.sh`** puts Java 17 and gnuplot (user-space installs from Lab 1)
on the PATH and sets `MAELSTROM` to `../maelstrom/maelstrom` (a symlink to
Lab 1's Maelstrom 0.2.4).

**`../kit/run.sh <workload> <program> [options]`** (course kit, unmodified):
`maelstrom test -w lin-kv --bin <program> --node-count 3 --time-limit 20
--rate 10 --concurrency 2n [options]`; later options override the defaults.
Environment variables (QR, QW, MS_CRASH, SLOW_PUT) are inherited by the
node processes.

**`scenarios.sh <program> <QR> <QW> <scenario> [repeats] [N]`** (ours):
maps a scenario name to options (table in its header), runs it `repeats`
times with `QR`, `QW`, `MS_CRASH`, `SLOW_PUT` set, and appends one line per
run to `results/results.tsv`:

```
program  N=3  QR=2  QW=2  scenario  lin=yes ok=… fail=… info=… msgs/op=… cas_ok=… bad_keys=…  store/lin-kv/<run>
```

(the middle part is `summary.py`'s output). The full output of the last
run is kept in `results/last-output.txt`.

**`run_all.sh [part1|part2|part3|part4|further]`** (ours): every run cited
in the documents, part by part.

**`../kit/summary.py [runs…]`** (course kit): reads `results.edn` and prints
`lin=` (the `:workload :valid?` verdict: linearizability only, ignoring
the "cas never succeeded" failure that makes Maelstrom print *Analysis
invalid!* in Parts 1–3), the ok/fail/info counts, `msgs/op` (server-to-
server messages per client operation), `cas_ok`, and the keys found
non-linearizable.

**`../kit/timeline.py [run] [--history] [--key k] [--node n] [--event e]
[--process p]`** (course kit): merges the `trace()` events of all nodes in
time order; `--history` adds the client operations (`p<process>`, with the
node they were sent to) and the nemesis events. We use it in every
explanation, e.g. `../kit/timeline.py runs/p1-majority-latency --history --key 0`.

**`cite_runs.sh`** (ours): copies the runs named in its list from
`store/lin-kv/<id>` to `runs/<name>` and writes `runs/INDEX.md` (name,
store id, program, configuration, summary; and which runs the record
cites, i.e. what to submit).

## 11. Analysis tools (`tools/`, ours)

All take a run directory (`store/lin-kv/<id>`, `store/latest` or
`runs/<name>`), read only files Maelstrom wrote, and never modify them.

**`tools/anomaly.py <run> [--key K] [--before s] [--after s] [--hide-cas]`**
answers "where did the checker find this run non-linearizable?":

1. From `results.edn`, for each key whose `:linearizable :valid?` is
   false: `:previous-ok` (the last operation the checker could place) and
   every operation in `:final-paths` whose model is `Inconsistent` (the
   ones it could not), with the checker's message (e.g. *can't read 0
   from register 3*).
2. It finds *when* those operations happened by their `:index` in the
   history: the i-th operation line of `jepsen.log` is history entry i,
   and `jepsen.log` uses the same clock as the node traces. (The
   `:time` field of the history is a monotonic clock that drifted from
   the wall clock by up to 0.5 s here, so it is not used.)
3. It prints `../kit/timeline.py <run> --history --key K` restricted to
   `[t − before, t + after]` around the failing operation, and warns if
   the wall clock jumped back inside that window.

**`tools/clockcheck.py <run>…`** reports wall-clock jumps: each node
writes its log in execution order, so a trace whose time is lower than
the previous one of the same node reveals a backward step of the clock
(the WSL virtual machine is resynchronised with Windows from time to
time). Around a jump, merged timelines can be in the wrong order.

**`tools/sccheck.py <run> [--key K] [--merge A,B]`** answers "is the
history of key K sequentially consistent?", which Knossos does not check.
It takes the `:ok` reads and writes of `history.edn` per process, in
history order, and searches depth-first for one total order that keeps
every process's order and register semantics (a read can be placed only
if it returns the current value). States (operations placed per process,
current value) are memoised. `--merge A,B` treats B's operations as A's,
to answer "what if the same client had done both?". Exponential in the
worst case: 4 s on the kit's `inversion-run` (rate 10), did not finish
in 15 min on our rate-50 runs.

**`tools/after.py <run> [seconds]`** counts client results (ok / fail /
info) per server and per operation type, before and after a given time
(default 5 s, the `MS_CRASH` time), from `timeline.py --history`. It is
how the availability tables were made.

**`tools/table.py [program…]`** turns `results/results.tsv` into the
markdown tables of the documents: one row per (program, N, QR, QW,
scenario), with the verdicts, counts per run, mean msgs/op and run ids.
